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
            if state.actor_id == "陈默" and not perception["inbox"]:
                return Intention("陈默", "send_message",
                                 {"target": "林瑶", "text": "meet me at the 校史档案室"},
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
        lin_view = render_agent_view(trajectory, "林瑶")
        self.assertIn("meet me at the 校史档案室", lin_view)

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
            # Each actor that actually took a turn gets exactly one view file
            # (V4-CAST §1: idle NPCs take no turns, so no view either).
            names = {f.name.split(".")[1] for f in files}
            self.assertEqual(names,
                             {t["actor"] for t in json.loads(
                                 trajectory_path.read_text(encoding="utf-8"))["agent_turns"]})
            for file in files:
                self.assertGreater(file.stat().st_size, 0)


    def test_chatml_view_is_a_flat_ordered_stream(self):
        from harness.agent_view import render_chatml_view
        trajectory = {"sessions": {"陈默": {"messages": [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "init"},
            {"role": "assistant", "content": "{\"kind\":\"wait\",\"args\":{\"seconds\":600}}"},
            {"role": "user", "name": "world", "content": "The world accepted your wait; it is in progress."},
            {"role": "assistant", "content": "X" * 5000},
        ]}}}
        view = render_chatml_view(trajectory, "陈默")
        tags = [line for line in view.splitlines() if line.startswith("[")]
        # One flat stream: system, user, assistant, world-as-user, assistant.
        self.assertEqual(tags, ["[system]", "[user]", "[assistant]", "[user]", "[assistant]"])
        # World feedback renders as a plain user message with full content.
        self.assertIn("[user]\nThe world accepted your wait", view)
        self.assertNotIn("[world]", view)
        # No analysis sections and no display truncation.
        self.assertNotIn("Decision log", view)
        self.assertNotIn("Private state", view)
        self.assertIn("X" * 5000, view)


    def test_history_view_reconstructs_every_turn_in_order(self):
        from harness.agent_view import render_history_view
        trajectory = self._small_trajectory()
        view = render_history_view(trajectory, "林瑶")
        # Every 林瑶 turn appears: one [assistant] block per turn.
        turns = [t for t in trajectory["agent_turns"] if t["actor"] == "林瑶"]
        self.assertEqual(view.count("\n[assistant]\n"), len(turns))
        # The rhythm: perception first, then the action; no accept receipt.
        self.assertIn("现在是", view)
        chen_view = render_history_view(trajectory, "陈默")
        self.assertIn('{"kind": "send_message"', chen_view)
        self.assertNotIn("The world accepted your", chen_view)
        # Chen's delivered message shows up in lin's perception stream.
        self.assertIn("meet me at the 校史档案室", view)
        # Rejections render as immediate corrective feedback with detail.
        rejects = [t for t in turns if t["result"] == "rejected"]
        if rejects:
            self.assertIn("The world rejects your action", view)


    def test_history_view_includes_system_and_compaction_boundary(self):
        from harness.agent_view import render_history_view
        trajectory = {
            "world_events": [{"id": 1, "kind": "action_completed", "actor": "陈默",
                              "payload": {"action": "wait"}}],
            "sessions": {"陈默": {"messages": [
                {"role": "system", "content": "PERSONA"},
                {"role": "user", "content": "init"},
                {"role": "assistant", "content": "{}"},
            ], "compacted_memories": [
                {"order": 0, "content": "MEMORY-ONE"},
                {"order": 1, "content": "MEMORY-TWO"},
            ]}},
            "agent_turns": [
                {"actor": "陈默",
                 "perception": {"time": "2026-03-16T07:00:00+08:00", "location": "宿舍",
                                "events": [], "inbox": []},
                 "affordances": [{"kind": "wait", "duration_seconds": 900}],
                 "intention": {"kind": "wait", "args": {"duration_seconds": 900}},
                 "result": "submitted", "error": None, "event_ids": [1]},
            ],
        }
        view = render_history_view(trajectory, "陈默")
        # The persona prompt the agent saw with every request.
        self.assertIn("[system]\nPERSONA", view)
        # No synthesized accept receipts: an accepted action is followed
        # directly by the next perception; outcomes live in event lines.
        self.assertNotIn("The world accepted your", view)
        # Bullet affordances.
        self.assertIn("  - ", view)
        # Compaction boundary and verbatim live context are still present.
        self.assertIn("MEMORY-ONE", view)
        self.assertIn("MEMORY-TWO", view)
        self.assertGreaterEqual(view.count("\n---\n"), 3)
        self.assertIn("当前活跃上下文", view)
        self.assertIn("[assistant]\n{}", view)

    def test_history_view_dedupes_constants_and_filters_other_waits(self):
        from harness.agent_view import render_history_view
        events = [{"id": 1, "time": "2026-03-16T07:00:00+08:00", "kind": "action_completed",
                   "actor": "陈默", "payload": {"action": "wait", "duration_seconds": 900}},
                  {"id": 2, "time": "2026-03-16T07:05:00+08:00", "kind": "action_completed",
                   "actor": "林瑶", "payload": {"action": "wait", "duration_seconds": 900}}]
        turn = {"actor": "陈默",
                "perception": {"time": "2026-03-16T07:05:00+08:00", "location": "宿舍",
                               "observer": "陈默", "events": events, "inbox": [],
                               "descriptions": {"宿舍": "A small 宿舍 room."},
                               "knowledge": {"old-basement": {"public": "Closed."}}},
                "affordances": [{"kind": "wait", "duration_seconds": 900}],
                "intention": {"kind": "wait", "args": {"duration_seconds": 900}},
                "result": "submitted", "error": None, "event_ids": [1, 2]}
        trajectory = {"world_events": events, "sessions": {"陈默": {"messages": []}},
                      "agent_turns": [dict(turn), dict(turn, perception=dict(
                          turn["perception"], events=[]))]}
        view = render_history_view(trajectory, "陈默")
        # Own wait completion is visible; another actor's wait is not an event.
        self.assertIn("[07:00:00] 等了15分钟", view)
        self.assertNotIn("林瑶", view.split("[assistant]")[0])
        # Constant description and knowledge appear exactly once across turns.
        self.assertEqual(view.count("A small 宿舍 room."), 1)
        self.assertEqual(view.count("old-basement——Closed."), 1)
        # No accept receipt between action and next perception.
        self.assertNotIn("The world accepted", view)


if __name__ == "__main__":
    unittest.main()
