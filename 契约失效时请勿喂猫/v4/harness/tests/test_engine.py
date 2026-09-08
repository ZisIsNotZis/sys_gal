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


class MultiHopMoveTests(unittest.TestCase):
    """V4 multi-hop move: engine pathfinding + discrete leave/enter events
    with per-location visibility (user verdict 2026-09-08)."""

    def _world(self):
        from harness.replay import replay_world
        world = World(start=START,
                      actors=[ActorState("a", "A"), ActorState("b", "B"), ActorState("c", "C")],
                      locations=[LocationState("A"), LocationState("B"), LocationState("C")],
                      routes={("A", "B"): 60, ("B", "A"): 60, ("B", "C"): 120, ("C", "B"): 120})
        return world, replay_world

    def test_multihop_event_sequence_and_visibility(self):
        world, replay_world = self._world()
        world.submit(Intention("a", "move", {"target": "C"}, world.version))
        world.advance()
        kinds = [(e.kind, e.actor, e.payload.get("location")) for e in world.event_log]
        self.assertEqual(kinds, [
            ("action_started", "a", None),
            ("leave", "a", "A"),        # t=0, origin sees departure
            ("enter", "a", "B"),        # t=60, B sees arrival
            ("leave", "a", "B"),        # t=60, leaves again immediately
            ("enter", "a", "C"),        # t=180, C sees arrival
            ("action_completed", "a", None),
        ])
        times = [e.time for e in world.event_log]
        self.assertEqual(times[1], START)
        self.assertEqual(times[2], START + timedelta(seconds=60))
        self.assertEqual(times[3], START + timedelta(seconds=60))
        self.assertEqual(times[4], START + timedelta(seconds=180))
        self.assertEqual(world.actors["a"].location, "C")
        # Per-location visibility: b (at B) sees exactly a's B-events; the
        # mover sees its whole route.
        b_seen = {(e.kind, e.payload.get("location")) for e in world.event_log if "b" in e.visible_to}
        self.assertEqual(b_seen, {("enter", "B"), ("leave", "B")})
        a_seen = {(e.kind, e.payload.get("location")) for e in world.event_log
                  if e.actor == "a" and e.kind in {"enter", "leave"}}
        self.assertEqual(a_seen, {("leave", "A"), ("enter", "B"), ("leave", "B"), ("enter", "C")})
        c_seen = [e for e in world.event_log if "c" in e.visible_to and e.kind == "enter"]
        self.assertEqual(len(c_seen), 1)
        # Replay reconstructs the same final location from the enter events.
        replayed = replay_world(self._world()[0], world.replayable_log())
        self.assertEqual(replayed.actors["a"].location, "C")

    def test_interrupt_midroute_resumes_from_last_entered_location(self):
        world, _ = self._world()
        world.submit(Intention("a", "move", {"target": "C"}, world.version))
        world.advance(until=START + timedelta(seconds=60))  # a enters B
        self.assertEqual(world.actors["a"].location, "B")
        world.submit(Intention("b", "speak", {"text": "站住"}, world.version,
                               interrupt=("a",)))
        self.assertIsNotNone(world.actors["a"].pending)
        self.assertEqual(world.actors["a"].pending["remaining_path"], ["B", "C"])
        world.submit(Intention("a", "continue_action", {}, world.version))
        world.advance()
        self.assertIsNone(world.actors["a"].pending)
        self.assertEqual(world.actors["a"].location, "C")
        enters = [e for e in world.event_log if e.kind == "enter" and e.payload.get("location") == "C"]
        self.assertEqual(len(enters), 1, "resumed walk must still enter C exactly once")

    def test_unreachable_move_is_rejected_with_guidance(self):
        world, _ = self._world()
        world.locations["D"] = LocationState("D")
        with self.assertRaises(Exception) as ctx:
            world.submit(Intention("a", "move", {"target": "D"}, world.version))
        self.assertIn("没有可用的路", str(ctx.exception))

    def test_engine_accepts_world_with_extras_but_requires_mc_agents(self):
        # Regression: resume from a checkpoint whose world contains spawned
        # extras — the engine must not demand agents/states for them
        # (胡大爷 KeyError, 2026-09-08).
        world, _ = self._world()
        from harness.agent_state import PrivateState as PS
        world.add_extra("路人甲", "B")
        states = {"a": PS("a"), "b": PS("b"), "c": PS("c")}
        agents = {"a": Scripted([]), "b": Scripted([]), "c": Scripted([])}
        engine = AsyncEngine(world, agents, states, Trace("v4-test", "extras-init"),
                             mc_idle_heartbeat=60)
        self.assertIn("路人甲", engine.world.actors)
        with self.assertRaises(ValueError):
            AsyncEngine(world, {"a": agents["a"], "b": agents["b"]}, states,
                        Trace("v4-test", "missing-mc"))
