"""M1 的三条反向门（用失败才能通过的检查）。

1. 摸与读都不留痕；
2. 渲染里没有来源元数据（作者、时间、读者）；
3. 指称不到时给可行动的清单。
外加第四条：轨迹不许叙述没人感知到的事。
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401
from engine.events import EventLog
from engine.resolve import resolve
from engine.rules import submit
from engine.seed import load
from stories.s1_last_bus.scenario import DEFAULT_SEED, play
from stories.s1_last_bus.transcript import transcript

PROVENANCE_WORDS = ("作者", "写于", "打印于", "谁写的", "读者", "签名是", "author", "written by")


class Gate1NoTrace(unittest.TestCase):
    def test_read_leaves_the_paper_untouched(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        before = copy.deepcopy(world.state["notice"])
        receipt = submit(world, log, "jia", "read", {"target": "通知"})
        self.assertTrue(receipt.ok, receipt.reason)
        self.assertEqual(world.state["notice"], before)
        self.assertFalse([a for a in receipt.event.atoms
                          if a["op"] in {"set", "unset", "move", "create", "destroy"}])

    def test_touch_leaves_the_thing_untouched(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        before = copy.deepcopy(world.state)
        before_parent = copy.deepcopy(world.parent)
        receipt = submit(world, log, "jia", "touch", {"target": "包"})
        self.assertTrue(receipt.ok, receipt.reason)
        self.assertEqual(world.state, before)
        self.assertEqual(world.parent, before_parent)

    def test_reading_does_not_tell_anyone_else_what_was_read(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        before = {p: list(m) for p, m in world.memory.items()}
        submit(world, log, "jia", "read", {"target": "通知"})
        notice_text = world.get("notice", "inscription")
        self.assertIn(notice_text, world.memory["jia"][-1][1])
        for person, rows in world.memory.items():
            if person == "jia":
                continue
            for _at, text in rows[len(before[person]):]:
                self.assertNotIn(notice_text, text, "读的内容不许被别人凭空知道")


class Gate2NoProvenance(unittest.TestCase):
    def test_no_memory_text_mentions_an_author_or_a_reader(self):
        texts: list[str] = []
        for variant in ("a", "b", "c"):
            run = play(variant)
            for rows in run.world.memory.values():
                texts += [text for _at, text in rows]
        self.assertTrue(texts)
        for text in texts:
            for word in PROVENANCE_WORDS:
                self.assertNotIn(word, text, f"渲染里出现了来源元数据：{text}")

    def test_a_paper_carries_only_what_is_written_on_it(self):
        world = load(DEFAULT_SEED)
        self.assertEqual(set(world.state["notice"]), {"inscription"})

    def test_reading_returns_only_the_inscription(self):
        run = play("a")
        first = [item for item in run.items if item["kind"] == "turn" and item["verb"] == "read"][0]
        self.assertEqual(first["texts"], ["你读着通知：「本车为末班车，终点站后不再发车。」"])

    def test_transcript_never_explains_who_wrote_anything(self):
        text = transcript(play("a"))
        for word in PROVENANCE_WORDS:
            self.assertNotIn(word, text)


class Gate3ActionableRefusals(unittest.TestCase):
    def test_unknown_place_lists_where_you_can_go(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        receipt = submit(world, log, "jia", "move", {"target": "宿舍"})
        self.assertFalse(receipt.ok)
        self.assertIn("宿舍", receipt.reason)
        self.assertTrue(receipt.hints)
        self.assertTrue(any("眼前能看见" in h for h in receipt.hints), receipt.hints)
        self.assertEqual(len(log), 1)
        self.assertEqual(log.events[0].kind, "refused")

    def test_reading_something_without_writing_says_what_is_readable(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        receipt = submit(world, log, "jia", "read", {"target": "包"})
        self.assertFalse(receipt.ok)
        self.assertTrue(any("能读" in h for h in receipt.hints), receipt.hints)

    def test_refusal_does_not_change_the_world(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        before = world.digest()
        submit(world, log, "jia", "read", {"target": "包"})
        self.assertEqual(world.digest(), before)


class Gate4PerceptionOnly(unittest.TestCase):
    def test_world_events_are_shown_through_who_perceived_them(self):
        run = play("a")
        world_items = [i for i in run.items if i["kind"] == "world"]
        self.assertTrue(world_items)
        for item in world_items:
            self.assertTrue(item["perceived"], f"{item['at']} 的世界事件没有任何人感知到")

    def test_a_passenger_who_left_does_not_hear_the_later_stops(self):
        run = play("a")
        later = [i for i in run.items if i["kind"] == "world" and i["what"] == "arrive"]
        self.assertTrue(later)
        last = later[-1]
        perceivers = {who for who, _ in last["perceived"]}
        self.assertNotIn("jia", perceivers)
        self.assertIn("driver", perceivers)


if __name__ == "__main__":
    unittest.main()
