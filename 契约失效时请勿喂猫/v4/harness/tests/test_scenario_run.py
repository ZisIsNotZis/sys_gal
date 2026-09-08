"""Guard the scenario-run tooling used for manual trajectory review."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.scenario_run import run_scenario


class ScenarioRunTests(unittest.TestCase):
    """v3-pack scenario anchors (permit_review 等) are not part of the v4
    one-day slice; the scenario tooling gets v4 anchors with ticket 05."""

    @unittest.skip("v4 slice: scenario anchors are v3-pack specific (ticket 05)")
    def test_scenario_starts_from_checkpoint_and_reacts_live(self):
        """A scenario resumed from a snapshot reaches its boundary, stays
        contiguous, fires the boundary exactly once, and lets an actor read
        the newly available document."""
        with TemporaryDirectory() as directory:
            summary = run_scenario(anchor="permit_review", hours=2, policy="active",
                                   prelude="lean", runs_dir=Path(directory))
            self.assertTrue(Path(summary["trajectory"]).is_file())
            self.assertTrue(Path(summary["checkpoint"]).is_file())
        self.assertEqual(summary["reason"], "stop_at_reached")
        self.assertTrue(summary["boundary_fired"])
        self.assertIn("permit-review-outcome", summary["documents_read_during_scenario"])
        self.assertGreater(summary["agent_turns"], 0)

    def test_scenario_snapshot_files_are_loadable(self):
        from harness.checkpoint import load_checkpoint
        import json
        with TemporaryDirectory() as directory:
            summary = run_scenario(anchor="bank_call", hours=1, policy="active",
                                   prelude="lean", runs_dir=Path(directory))
            checkpoint = load_checkpoint(summary["checkpoint"])
            self.assertEqual(checkpoint["format"], "v3-checkpoint-1")
            trajectory = json.loads(Path(summary["trajectory"]).read_text(encoding="utf-8"))
            self.assertEqual(trajectory["format"], "v3-trajectory-1")
            self.assertTrue(trajectory["replay"]["contiguous"])
            self.assertTrue(trajectory["replay"]["world_versions_contiguous"])


if __name__ == "__main__":
    unittest.main()
