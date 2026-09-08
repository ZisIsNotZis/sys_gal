"""V4-ENGINE.md invariants: freeze rule, wake-early waits, silent
abandonment, heartbeat liveness, deterministic endpoint flow."""

from __future__ import annotations

import threading
import time as wall_time
import unittest
from datetime import datetime, timedelta

from harness.agent_state import PrivateState
from harness.engine import AsyncEngine
from harness.kernel import TICK_SECONDS, ActorState, Intention, LocationState, World
from harness.trace import Trace

START = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def _world(scheduled=()):
    return World(start=START,
                 actors=[ActorState("a", "room"), ActorState("b", "room")],
                 locations=[LocationState("room"), LocationState("far")],
                 routes={("room", "far"): 120},
                 scheduled=list(scheduled))


def _iso(offset_seconds):
    return (START + timedelta(seconds=offset_seconds)).isoformat()


class Scripted:
    """Thread-safe scripted agent: pops intentions, optional blocking hook."""

    def __init__(self, script, gate=None):
        self.script = list(script)
        self.gate = gate
        self.calls = 0

    def __call__(self, state, perception, affordances):
        self.calls += 1
        if self.gate is not None:
            self.gate.wait(timeout=30)
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return None


class EngineTests(unittest.TestCase):
    def _engine(self, world, agents, **kw):
        states = {actor: PrivateState(actor) for actor in world.actors}
        return AsyncEngine(world, agents, states, Trace("v4-test", "engine-test"), **kw)

    def test_conversation_roundtrip_wakes_waiter_early(self):
        # b waits 600 s; a speaks at t=0 (speech lands t=60). The wake class
        # ends b's wait early, so b's reply exists far before the wait would
        # have ended (V4-ENGINE §3/§4: M exchanges = M ticks).
        world = _world()
        agents = {
            "a": Scripted([Intention("a", "speak", {"text": "你好"}, world.version)]),
            "b": Scripted([Intention("b", "wait", {"duration_seconds": 600}, world.version),
                           Intention("b", "speak", {"text": "你好呀"}, None)]),
        }
        engine = self._engine(world, agents)
        reason = engine.run(stop_at=START + timedelta(seconds=300), max_turns=50)
        self.assertEqual(reason, "stop_at_reached")
        speeches = [e for e in world.event_log if e.kind == "speech"]
        by_b = [e for e in speeches if e.actor == "b"]
        self.assertTrue(by_b, "b never replied")
        self.assertLess(by_b[0].time, START + timedelta(seconds=600),
                        "b stayed in its wait instead of waking early")

    def test_freeze_rule_bounds_world_drift_to_one_tick(self):
        # While a's decision is in flight, the world may process events up to
        # wake + 1 tick (the t+60 beat) but must freeze before the t+600 beat
        # (V4-ENGINE §2.3).
        gate = threading.Event()
        scheduled = [{"time": _iso(60), "kind": "world_event", "notice": "one tick later"},
                     {"time": _iso(600), "kind": "world_event", "notice": "far later"}]
        world = _world(scheduled=scheduled)
        agents = {"a": Scripted([Intention("a", "speak", {"text": "想好了"}, None)], gate=gate),
                  "b": Scripted([])}
        engine = self._engine(world, agents, decision_timeout=30)
        result = {}

        def run():
            result["reason"] = engine.run(stop_at=START + timedelta(seconds=1200), max_turns=50)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        deadline = wall_time.monotonic() + 10
        while wall_time.monotonic() < deadline and world.now <= START:
            wall_time.sleep(0.01)
        deadline = wall_time.monotonic() + 5
        while wall_time.monotonic() < deadline and world.now < START + timedelta(seconds=60):
            wall_time.sleep(0.01)
        self.assertEqual(world.now, START + timedelta(seconds=60),
                         "world did not drift exactly one tick")
        wall_time.sleep(0.5)
        self.assertEqual(world.now, START + timedelta(seconds=60),
                         "world drifted past the decision horizon while frozen")
        gate.set()
        thread.join(timeout=30)
        self.assertFalse(thread.is_alive())
        self.assertGreaterEqual(world.now, START + timedelta(seconds=600),
                                "world never resumed after the decision landed")

    def test_silent_abandonment_auto_continues_pending_action(self):
        # a starts a 120 s move; b's named speech suspends it; a's next
        # decision crashes; the abandonment resumes the pending move
        # (V4-ENGINE §3: silence = the actor keeps doing what it was doing).
        world = _world()
        agents = {
            "a": Scripted([Intention("a", "move", {"target": "far"}, world.version),
                           RuntimeError("provider exploded")]),
            "b": Scripted([Intention("b", "speak", {"text": "哎，等一下"},
                                     world.version, interrupt=("a",))]),
        }
        engine = self._engine(world, agents, decision_timeout=5)
        engine.run(stop_at=START + timedelta(seconds=300), max_turns=50)
        self.assertEqual(world.actors["a"].location, "far",
                         "pending move was not auto-continued")
        self.assertTrue(any(e.kind == "action_resumed" for e in world.event_log))
        self.assertTrue(any(e.kind == "action_interrupted" for e in world.event_log))

    def test_heartbeat_gives_idle_mc_turns_without_churn(self):
        # An MC that never decides must still get periodic turns via the idle
        # heartbeat, spaced by mc_idle_heartbeat — not one turn per tick.
        world = _world()
        agents = {"a": Scripted([]), "b": Scripted([])}
        engine = self._engine(world, agents, mc_idle_heartbeat=60)
        engine.run(stop_at=START + timedelta(seconds=200), max_turns=200)
        for actor in ("a", "b"):
            turns = [t for t in engine.trace.agent_turns if t["actor"] == actor]
            self.assertGreaterEqual(len(turns), 2, f"{actor} never got heartbeat turns")
        self.assertGreaterEqual(world.now, START + timedelta(seconds=120))

    def test_rejection_costs_one_tick_before_feedback(self):
        # A wrong call still costs one tick; the corrective feedback arrives
        # on the next turn (V4-ENGINE §2.1 economics).
        world = _world()
        agents = {
            "a": Scripted([Intention("a", "move", {"target": "nowhere"}, world.version),
                           Intention("a", "speak", {"text": "那走不过去"}, None)]),
            "b": Scripted([]),
        }
        engine = self._engine(world, agents)
        engine.run(stop_at=START + timedelta(seconds=300), max_turns=50)
        feedback = [fact for facts in engine._operational_facts.values()
                    for fact in facts if fact["type"] == "rejected_action"]
        self.assertTrue(feedback, "rejection never recorded")
        speeches = [e for e in world.event_log if e.kind == "speech" and e.actor == "a"]
        self.assertTrue(speeches, "agent never got to retry after the rejection")
        self.assertGreaterEqual(speeches[0].time, START + timedelta(seconds=TICK_SECONDS),
                                "retry happened before the rejection tick elapsed")


if __name__ == "__main__":
    unittest.main()
