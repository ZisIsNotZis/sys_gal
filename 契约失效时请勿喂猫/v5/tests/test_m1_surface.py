"""M1 的智能体表面：一眼、最近、知道的事、检索、回想。

这一层的职责只有一个：回答"他此刻知道什么"，而且只包含他自己感知过或相信过的东西。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401
from engine.events import EventLog
from engine.rules import submit
from engine.seed import load
from engine.surface import beliefs, block, flashback, glance, recall, recent, render_block
from stories.s1_last_bus.scenario import DEFAULT_SEED, play


class GlanceTests(unittest.TestCase):
    def setUp(self):
        self.world = load(DEFAULT_SEED)

    def test_glance_says_when_where_who_and_what_is_in_hand(self):
        g = glance(self.world, "yi")
        self.assertEqual(g["time"], "2026-03-15 22:30")   # 一个人知道自己站在哪一天
        self.assertEqual(g["place"], "车厢")
        self.assertEqual(g["hands"], ["包"])
        self.assertTrue(any("那个人" in item for item in g["here"]))

    def test_glance_does_not_reveal_a_name_you_do_not_know(self):
        text = render_block(block(self.world, "jia"))
        self.assertNotIn("乙", text)
        self.assertIn("那个人", text)

    def test_glance_sees_that_there_is_writing_but_not_what_it_says(self):
        text = render_block(block(self.world, "jia"))
        self.assertIn("上面有字", text)
        self.assertNotIn("终点站后不再发车", text)

    def test_glance_carries_your_own_first_person_identity(self):
        g = glance(self.world, "yi")
        self.assertIn("守夜", g["self"])
        self.assertIn("守夜", render_block(block(self.world, "yi")))

    def test_glance_is_closed_door_honest(self):
        g = glance(self.world, "jia")
        self.assertTrue(any("门关着" in item for item in g["here"]))
        self.assertFalse(any("五十来岁" in item for item in g["here"]))   # 看不见司机


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.world = load(DEFAULT_SEED)
        self.log = EventLog()

    def test_recent_holds_only_what_this_person_perceived(self):
        submit(self.world, self.log, "yi", "open", {"target": "包"})
        submit(self.world, self.log, "yi", "read", {"target": "药盒"})
        jia_lines = recent(self.world, "jia")
        self.assertFalse(any("每日两次" in line for line in jia_lines), jia_lines)

    def test_recall_is_literal_and_honest_about_missing_things(self):
        submit(self.world, self.log, "jia", "read", {"target": "通知"})
        self.assertTrue(recall(self.world, "jia", "末班车"))
        self.assertEqual(recall(self.world, "jia", "药盒"), [])
        self.assertEqual(recall(self.world, "jia", ""), [])

    def test_flashback_yields_what_you_saw_not_what_you_did_not_read(self):
        submit(self.world, self.log, "yi", "open", {"target": "包"})
        submit(self.world, self.log, "yi", "read", {"target": "药盒"})
        # 甲看见"有人在看那个盒子"，但没读到内容
        seen = flashback(self.world, "jia", "药盒")
        self.assertTrue(any("在看药盒" in line for line in seen), seen)
        self.assertFalse(any("每日两次" in line for line in seen))
        # 乙自己读到过，所以他想得起来内容
        mine = flashback(self.world, "yi", "药盒")
        self.assertTrue(any("每日两次" in line for line in mine), mine)

    def test_flashback_can_be_limited_in_time(self):
        submit(self.world, self.log, "jia", "read", {"target": "通知"})
        later = self.world.clock
        submit(self.world, self.log, "jia", "touch", {"target": "包"})
        self.assertEqual(flashback(self.world, "jia", "通知", since=later), [])


class BeliefTests(unittest.TestCase):
    def test_beliefs_are_the_characters_own_and_may_be_wrong(self):
        world = load(DEFAULT_SEED)
        self.assertIn("司机姓刘", "；".join(beliefs(world, "jia")))
        self.assertEqual(beliefs(world, "yi"), ["药是按点吃的，不能断",
                                                "包里没有值钱的东西，丢了也不可惜"])
        # 乙相信包里没值钱的东西——世界并没有这样说他错，但也没有替他纠正
        self.assertEqual(set(world.state["bag"]), {"closed", "portable"})


class ContextRecordingTests(unittest.TestCase):
    def test_every_turn_records_the_context_it_was_given(self):
        run = play("a")
        turns = [item for item in run.items if item["kind"] == "turn"]
        self.assertEqual(len(turns), len(run.receipts))
        for item in turns:
            ctx = item["context"]
            self.assertEqual(set(ctx), {"glance", "recent", "beliefs"})
            self.assertTrue(ctx["glance"]["time"])

    def test_the_scripted_actor_honestly_did_not_read_it(self):
        run = play("a")
        self.assertTrue(all(item["context_used"] is False
                            for item in run.items if item["kind"] == "turn"))

    def test_context_never_contains_another_persons_private_memory(self):
        run = play("a")
        for item in run.items:
            if item["kind"] != "turn":
                continue
            text = render_block(item["context"])
            if item["actor"] == "jia":
                self.assertNotIn("每日两次", text)
                self.assertNotIn("司机熄了火", text)


if __name__ == "__main__":
    unittest.main()
