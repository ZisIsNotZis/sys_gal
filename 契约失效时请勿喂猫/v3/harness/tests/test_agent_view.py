"""Guard the per-agent trajectory view tool."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.agent_state import PrivateState
from harness.kernel import Intention
from harness.runner import Runner
from harness.seed import load_story_pack
from harness.system import Ledger
from harness.trace import Trace
from harness.agent_view import render_agent_view


class AgentViewTests(unittest.TestCase):
    def _small_trajectory(self):
        pack = load_story_pack()
        world = pack.build_world()
        states = {actor: PrivateState(actor) for actor in world.actors}

        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo" and not perception["inbox"]:
                return Intention("chen-mo", "send_message",
                                 {"target": "lin-yao", "text": "meet me at the archive"},
                                 perception["world_version"])
            return None

        ledger = Ledger(pack.system.get("facts", {}), pack.system)
        trace = Trace("v3-test", "agent-view-fixture")
        Runner(world, {actor: agent for actor in world.actors}, states, trace, ledger).run(
            max_turns=20)
        return trace.snapshot(world)

    def test_every_actor_renders_a_view_with_its_own_angle(self):
        trajectory = self._small_trajectory()
        for actor in trajectory["sessions"]:
            view = render_agent_view(trajectory, actor)
            self.assertIn(actor, view)
            self.assertIn("Decision log", view)
        # Lin's view must show the message delivered to her.
        lin_view = render_agent_view(trajectory, "lin-yao")
        self.assertIn("meet me at the archive", lin_view)

    def test_views_write_to_disk_per_actor(self):
        import json
        from harness.agent_view import main as view_main
        with TemporaryDirectory() as directory:
            trajectory_path = Path(directory) / "fixture.json"
            trajectory_path.write_text(
                json.dumps(self._small_trajectory(), ensure_ascii=False), encoding="utf-8")
            out_dir = Path(directory) / "views"
            view_main([str(trajectory_path), "--all", "--out", str(out_dir)])
            files = sorted(out_dir.glob("*.view.md"))
            self.assertEqual(len(files), 8)
            for file in files:
                self.assertGreater(file.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
