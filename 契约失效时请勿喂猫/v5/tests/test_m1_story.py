"""M1 的故事验收：《末班车》三条路，三个不同结局，一份可通读的轨迹。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401
from stories.s1_last_bus.scenario import ending, play
from stories.s1_last_bus.transcript import transcript


class StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {v: play(v) for v in ("a", "b", "c")}

    def test_three_paths_reach_three_different_endings(self):
        ends = {v: ending(run)["结局"] for v, run in self.runs.items()}
        self.assertEqual(len(set(ends.values())), 3, ends)
        self.assertEqual(ending(self.runs["a"])["包在谁那里"], "司机")
        self.assertEqual(ending(self.runs["b"])["药盒在谁那里"], "甲")
        self.assertEqual(ending(self.runs["c"])["包在谁那里"], "车厢")

    def test_every_path_runs_to_the_end_of_the_world(self):
        for variant, run in self.runs.items():
            self.assertTrue(run.world.flags.get("stopped"), variant)
            self.assertGreaterEqual(len(run.receipts), 12, variant)

    def test_variant_a_takes_seventeen_actions(self):
        self.assertEqual(len(self.runs["a"].receipts), 17)

    def test_the_mid_story_refusal_is_natural_and_actionable(self):
        run = self.runs["a"]
        refused = [r for r in run.receipts if not r.ok]
        self.assertEqual(len(refused), 1)
        self.assertIn("看不见", refused[0].reason)
        self.assertTrue(refused[0].hints)

    def test_every_action_is_marked_with_who_decided_it(self):
        text = transcript(self.runs["a"])
        self.assertIn("`[世界]`", text)
        self.assertIn("`[脚本]`", text)
        self.assertIn("0 个为 `[角色]`", text)      # M1 没有任何动作是角色自己决定的
        turns = [i for i in self.runs["a"].items if i["kind"] == "turn"]
        self.assertTrue(all(i["decided_by"] == "script" for i in turns))
        self.assertTrue(all(i["context_used"] is False for i in turns))

    def test_the_driver_exists_before_he_is_named(self):
        """司机的存在必须是甲感知到的人影，而不是读者替他补的常识。"""
        first = [i for i in self.runs["a"].items if i["kind"] == "turn"][0]
        self.assertTrue(any("人影" in item for item in first["context"]["glance"]["here"]))

    def test_knocking_is_followed_by_waiting_not_by_instant_entry(self):
        verbs = [i["verb"] for i in self.runs["a"].items if i["kind"] == "turn"]
        self.assertIn("knock", verbs)
        self.assertEqual(verbs[verbs.index("knock") + 1], "wait")
        self.assertGreater(verbs.index("open", verbs.index("knock")), verbs.index("knock"))

    def test_transcript_reads_in_plain_language(self):
        text = transcript(self.runs["a"])
        self.assertIn("## 结局", text)
        self.assertIn("细看", text)
        self.assertNotIn("examine", text)
        self.assertNotIn("give", text)
        self.assertNotIn("None", text)

    def test_the_bag_ends_with_the_driver_only_in_variant_a(self):
        self.assertEqual(self.runs["a"].world.container("bag"), "driver")
        self.assertEqual(self.runs["b"].world.container("bag"), "car")
        self.assertEqual(self.runs["c"].world.container("bag"), "car")

    def test_nobody_is_omniscient(self):
        """每个人的记忆里只有自己经历的事：司机不知道包里有什么。"""
        driver_memory = " ".join(t for _at, t in self.runs["c"].world.memory["driver"])
        self.assertNotIn("药盒", driver_memory)
        self.assertNotIn("每日两次", driver_memory)


if __name__ == "__main__":
    unittest.main()
