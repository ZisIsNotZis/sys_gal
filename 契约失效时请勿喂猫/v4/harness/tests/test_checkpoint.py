import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.agent_state import PrivateState
from harness.character_loader import CharacterSeed
from harness.character_session import CharacterSession
from harness.checkpoint import load_checkpoint, save_checkpoint
from harness.kernel import ActorState, CheckpointError, Intention, LocationState, World
from harness.runner import Runner
from harness.trace import Trace


class CheckpointTests(unittest.TestCase):
    def world(self):
        return World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                     actors=[ActorState("a", "room"), ActorState("b", "room")],
                     locations=[LocationState("room")],
                     scheduled=[{"event": "alarm", "time": "2026-01-01T00:10:00+00:00"}])

    def test_world_checkpoint_restores_queue_mutable_state_and_cursors(self):
        world = self.world()
        world.submit(Intention("a", "wait", {"duration_seconds": 120}, world.version))
        world.poll("a")
        data = world.checkpoint_state()
        restored = World.from_checkpoint(self.world(), data)
        self.assertEqual(restored.checkpoint_state(), data)
        self.assertEqual(restored.next_event_time(), world.next_event_time())
        self.assertEqual(restored.advance(), world.advance())

    def test_runner_resume_matches_uninterrupted_run(self):
        def agent(state, perception, affordances):
            return Intention(state.actor_id, "wait", {"duration_seconds": 60},
                             perception["world_version"])

        def make():
            world = self.world()
            states = {actor: PrivateState(actor) for actor in world.actors}
            trace = Trace("test", "run")
            runner = Runner(world, {actor: agent for actor in world.actors}, states, trace,
                            max_workers=1)
            return world, states, trace, runner

        full = make()
        full[3].run(max_turns=6)
        interrupted = make()
        interrupted[3].run(max_turns=2)
        checkpoint = interrupted[2].checkpoint_snapshot(interrupted[0], interrupted[3])
        resumed = make()
        resumed[0].restore_checkpoint(checkpoint["world"])
        resumed[1].update({k: PrivateState.from_snapshot(v)
                           for k, v in checkpoint["states"].items()})
        resumed[3].restore_checkpoint(checkpoint["runner"])
        resumed[3].run(max_turns=4)
        self.assertEqual(resumed[0].replayable_log(), full[0].replayable_log())
        self.assertEqual(resumed[1]["a"].snapshot(), full[1]["a"].snapshot())

    def test_corrupt_checkpoint_fails_before_mutating_live_world(self):
        world = self.world()
        before = world.checkpoint_state()
        with self.assertRaises(CheckpointError):
            world.restore_checkpoint({"format": "v3-checkpoint-1", "world": {}})
        self.assertEqual(world.checkpoint_state(), before)

    def test_checkpoint_file_is_round_trippable_and_sessions_are_actor_local(self):
        seed_a = CharacterSeed("a", "A", "A secret")
        session = CharacterSession(seed_a, PrivateState("a"), lambda messages: "null")
        session.record_world_result("only a sees this")
        trace = Trace("test", "run")
        world = self.world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        runner = Runner(world, {actor: lambda *_: None for actor in world.actors}, states, trace)
        trace.record_session("a", session.snapshot())
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            save_checkpoint(path, trace.checkpoint_snapshot(world, runner))
            loaded = load_checkpoint(path)
        self.assertEqual(loaded["sessions"]["a"]["actor"], "a")
        self.assertNotIn("a", loaded["sessions"].get("b", {}))


if __name__ == "__main__":
    unittest.main()
