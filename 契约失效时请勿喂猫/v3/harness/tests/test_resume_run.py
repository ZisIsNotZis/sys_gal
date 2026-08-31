"""Guard the resume-from-checkpoint workflow (fix code -> resume)."""

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.agent_state import PrivateState
from harness.checkpoint import save_checkpoint
from harness.character_loader import load_story_characters
from harness.kernel import Intention
from harness.natural_agent import make_persistent_agent
from harness.runner import Runner
from harness.seed import load_story_pack
from harness.system import Ledger
from harness.trace import Trace, verify_event_log


class ResumeRunTests(unittest.TestCase):
    def _mock_call(self, messages):
        # Deterministic model: acknowledge history then wait.
        return '{"kind":"wait","args":{"duration_seconds":60}}'

    def test_resume_preserves_sessions_and_continues_causally(self):
        from harness.resume_run import resume
        from harness.kernel import World
        pack = load_story_pack()
        seeds = load_story_characters(Path("world"))
        ledger = Ledger(pack.system.get("facts", {}), pack.system)

        # 1) Run the original a little, then checkpoint.
        world = pack.build_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        agents = {actor: make_persistent_agent(seeds[actor], self._mock_call)
                  for actor in world.actors}
        trace = Trace("v3", "resume-original")
        runner = Runner(world, agents, states, trace, ledger, max_workers=8)
        runner.run(stop_at=datetime.fromisoformat("2026-03-16T07:10:00+08:00"), max_turns=50)
        original_turns = len(trace.agent_turns)
        checkpoint = trace.checkpoint_snapshot(world, runner)

        with TemporaryDirectory() as directory:
            cp_path = Path(directory) / "checkpoint.json"
            save_checkpoint(cp_path, checkpoint)
            out_path = Path(directory) / "resumed.json"
            resumed = resume(cp_path, out=out_path,
                             endpoint="2026-03-16T07:20:00+08:00", call=self._mock_call)
            import json
            data = json.loads(out_path.read_text(encoding="utf-8"))

        # The resumed artifact keeps the whole history, contiguous.
        self.assertGreater(len(data["agent_turns"]), original_turns)
        verify_event_log(data["world_events"])
        self.assertTrue(data["replay"]["contiguous"])
        self.assertTrue(data["replay"]["world_versions_contiguous"])
        # Session transcripts survived the restart (conversation preserved).
        for row in pack.actors:
            session = data["sessions"][row["id"]]
            self.assertGreaterEqual(len(session["messages"]), 2)  # system + init at least
            self.assertEqual(session["actor"], row["id"])
        # The resumed run reached the (shortened) endpoint cleanly.
        self.assertEqual(data["outcome"]["time"], "2026-03-16T07:20:00+08:00")

    def test_trace_restore_carries_prior_history(self):
        from harness.trace import Trace
        world = load_story_pack().build_world()
        trace = Trace("v3", "history")
        trace.record_agent(state=PrivateState("a"), perception={}, affordances=[],
                           intention=Intention("a", "wait", {"duration_seconds": 60}, 1),
                           result="submitted", version_before=1, version_after=2, event_ids=[1])
        trace.sessions["a"] = {"messages": [{"role": "system", "content": "keep me"}]}
        fresh = Trace("v3", "resumed")
        fresh.restore_from_snapshot(trace.snapshot(world))
        self.assertEqual(len(fresh.agent_turns), 1)
        self.assertEqual(fresh.sessions["a"]["messages"][0]["content"], "keep me")


if __name__ == "__main__":
    unittest.main()
