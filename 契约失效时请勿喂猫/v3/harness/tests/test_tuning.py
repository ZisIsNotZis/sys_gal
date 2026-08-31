"""Regression tests for the wall-time tuning knobs (harness/tuning.py)."""

import os
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.kernel import ActorState, Intention, LocationState, World
from harness.agent_state import PrivateState
from harness.runner import Runner
from harness.seed import load_story_pack
from harness.system import Ledger
from harness.trace import Trace
from harness.tuning import apply_idle_wait, effective_clock_stop, idle_wait_seconds


class TuningTests(unittest.TestCase):
    def _restore_env(self, saved: dict[str, str | None]) -> None:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_idle_wait_env_knob_and_apply(self):
        saved = {key: os.environ.get(key) for key in ("V3_IDLE_WAIT_SECONDS",)}
        try:
            os.environ.pop("V3_IDLE_WAIT_SECONDS", None)
            self.assertEqual(idle_wait_seconds(), 3600)
            os.environ["V3_IDLE_WAIT_SECONDS"] = "21600"
            self.assertEqual(idle_wait_seconds(), 21600)
            world = load_story_pack().build_world()
            apply_idle_wait(world)
            self.assertEqual(world.longest_wait_seconds, 21600)
            with self.assertRaises(ValueError):
                os.environ["V3_IDLE_WAIT_SECONDS"] = "nope"
                idle_wait_seconds()
        finally:
            self._restore_env(saved)

    def test_clock_stop_override_inserts_world_stops_marker(self):
        saved = {key: os.environ.get(key) for key in ("V3_CLOCK_STOP",)}
        try:
            pack = load_story_pack()
            os.environ.pop("V3_CLOCK_STOP", None)
            world = pack.build_world()
            stop = effective_clock_stop(world, str(pack.manifest["clock"]["stop"]))
            self.assertEqual(stop.isoformat(), pack.manifest["clock"]["stop"])
            os.environ["V3_CLOCK_STOP"] = "2026-03-21T12:00:00+08:00"
            world2 = pack.build_world()
            stop2 = effective_clock_stop(world2, str(pack.manifest["clock"]["stop"]))
            self.assertEqual(stop2.isoformat(), "2026-03-21T12:00:00+08:00")
            world2.advance(until=stop2)
            self.assertTrue(any(e.kind == "world_event"
                                and e.payload.get("event") == "world_stops"
                                for e in world2.event_log))
        finally:
            self._restore_env(saved)

    def test_longest_wait_affordance_is_configurable(self):
        world = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                      actors=[ActorState("a", "room")],
                      locations=[LocationState("room")],
                      longest_wait_seconds=21600)
        waits = [option["duration_seconds"] for option in world.affordances("a")
                 if option["kind"] == "wait"]
        self.assertIn(900, waits)
        self.assertIn(21600, waits)

    def test_short_arc_deterministic_run_reaches_shortened_endpoint(self):
        saved = {key: os.environ.get(key) for key in ("V3_CLOCK_STOP", "V3_IDLE_WAIT_SECONDS")}
        try:
            os.environ["V3_CLOCK_STOP"] = "2026-03-21T12:00:00+08:00"
            os.environ["V3_IDLE_WAIT_SECONDS"] = "21600"
            pack = load_story_pack()
            world = pack.build_world()
            apply_idle_wait(world)
            endpoint = effective_clock_stop(world, str(pack.manifest["clock"]["stop"]))
            states = {actor: PrivateState(actor) for actor in world.actors}

            def longest_wait(state, perception, affordances):
                offered = {str(option.get("kind")) for option in affordances}
                if state.actor_id == "chen-mo" and "system_accept" in offered:
                    return Intention(state.actor_id, "system_accept",
                                     {"case": "ambiguous-obligations"},
                                     perception["world_version"])
                waits = [option["duration_seconds"] for option in affordances
                         if option.get("kind") == "wait"]
                return Intention(state.actor_id, "wait",
                                 {"duration_seconds": max(waits)},
                                 perception["world_version"])

            ledger = Ledger(pack.system.get("facts", {}), pack.system)
            trace = Trace("v3-test", "short-arc-tuned")
            reason = Runner(world, {actor: longest_wait for actor in world.actors},
                            states, trace, ledger).run(stop_at=endpoint, max_turns=100_000)
            self.assertEqual(reason, "stop_at_reached")
            trace.verify_complete(world, endpoint=endpoint.isoformat(), stop_event="world_stops")
            self.assertEqual(world.now.isoformat(), "2026-03-21T12:00:00+08:00")
            # Shortened arc + 6h idle must still fire the key climax events.
            self.assertTrue(any(e.kind == "world_event"
                                and e.payload.get("event") == "storm_records_available"
                                for e in world.event_log))
        finally:
            self._restore_env(saved)


if __name__ == "__main__":
    unittest.main()
