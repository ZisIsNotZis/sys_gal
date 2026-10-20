"""M2 的验收：《借条》四条路 + 书写/擦除/复写/认字/开锁/说话。

最要紧的一条：**认字只能是知识，不能是魔法**——纸只给墨色与字形，谁的字要靠人自己认。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401
from engine.events import EventLog, ReplayMismatch, replay
from engine.rules import submit
from engine.seed import build, load
from stories.s2_borrow_note.scenario import DEFAULT_SEED, play, summary


def _world():
    return load(DEFAULT_SEED)


def _hand_of(world, mark):
    return mark["style"]


class StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {v: play(v) for v in ("a", "b", "c", "d")}

    def test_four_paths_reach_four_findings(self):
        ends = {v: summary(run) for v, run in self.runs.items()}
        self.assertEqual(len({e["结局"] for e in ends.values()}), 4)
        self.assertEqual(ends["a"]["借条上有几笔字"], 2)
        self.assertEqual(ends["a"]["纸面上有擦痕"], False)
        self.assertEqual(ends["b"]["纸面上有擦痕"], True)
        self.assertIn("三千", ends["b"]["读出来的全文"])
        self.assertEqual(ends["c"]["借条上有几笔字"], 3)
        self.assertTrue(ends["c"]["丙认出是乙的字"])
        self.assertEqual(ends["c"]["有人当场说话"], 0)
        self.assertEqual(ends["d"]["有人当场说话"], 2)
        self.assertTrue(ends["d"]["甲说不出是谁写的"])

    def test_the_victim_reads_a_number_he_does_not_believe(self):
        run = self.runs["b"]
        read = [i for i in run.items if i["kind"] == "turn" and i["verb"] == "read"][0]
        self.assertIn("三千", read["texts"][0])
        self.assertIn("一千", " ".join(
            says for _about, says in run.world.beliefs["jia"]))

    def test_every_run_is_marked_as_scripted(self):
        for run in self.runs.values():
            turns = [i for i in run.items if i["kind"] == "turn"]
            self.assertTrue(all(i["decided_by"] == "script" and not i["context_used"]
                                for i in turns))

    def test_no_script_ever_narrates_an_unperceived_world_event(self):
        for run in self.runs.values():
            for item in run.items:
                if item["kind"] == "world":
                    self.assertTrue(item["perceived"])


class WritingTests(unittest.TestCase):
    def test_writing_appends_a_mark_in_the_writers_own_hand(self):
        world = _world()
        log = EventLog()
        submit(world, log, "jia", "unlock", {"target": "抽屉"})
        submit(world, log, "jia", "open", {"target": "抽屉"})
        submit(world, log, "jia", "take", {"target": "借条"})
        submit(world, log, "jia", "place", {"target": "借条", "to": "出租屋"})
        submit(world, log, "jia", "take", {"target": "钢笔"})
        submit(world, log, "jia", "write", {"target": "借条", "text": "补：无息。", "with": "钢笔"})
        marks = world.get("iou", "marks")
        self.assertEqual(len(marks), 3)
        self.assertEqual(marks[-1]["text"], "补：无息。")
        self.assertEqual(marks[-1]["ink"], "ink")
        self.assertEqual(_hand_of(world, marks[-1]), "jia_hand")

    def test_writing_needs_an_implement(self):
        world = _world()
        log = EventLog()
        submit(world, log, "jia", "unlock", {"target": "抽屉"})
        submit(world, log, "jia", "open", {"target": "抽屉"})
        submit(world, log, "jia", "take", {"target": "借条"})
        submit(world, log, "jia", "place", {"target": "借条", "to": "出租屋"})
        receipt = submit(world, log, "jia", "write", {"target": "借条", "text": "补。"})
        self.assertFalse(receipt.ok)
        self.assertTrue(any("能写" in hint for hint in receipt.hints), receipt.hints)


class EraseTests(unittest.TestCase):
    def test_erase_needs_pencil_marks_and_an_eraser(self):
        world = _world()
        log = EventLog()
        submit(world, log, "jia", "unlock", {"target": "抽屉"})
        submit(world, log, "jia", "open", {"target": "抽屉"})
        submit(world, log, "jia", "take", {"target": "借条"})
        submit(world, log, "jia", "place", {"target": "借条", "to": "出租屋"})
        receipt = submit(world, log, "jia", "erase", {"target": "借条"})
        self.assertFalse(receipt.ok)
        self.assertIn("橡皮", receipt.reason)

    def test_erasing_leaves_a_smudge_and_takes_only_the_pencil_mark(self):
        world = _world()
        log = EventLog()
        for verb, args in (("unlock", {"target": "抽屉"}), ("open", {"target": "抽屉"}),
                           ("take", {"target": "借条"}), ("place", {"target": "借条", "to": "出租屋"}),
                           ("take", {"target": "橡皮"})):
            submit(world, log, "jia", verb, args)
        self.assertTrue(submit(world, log, "jia", "erase", {"target": "借条"}).ok)
        marks = world.get("iou", "marks")
        self.assertEqual([m["ink"] for m in marks], ["ink"])   # 只剩钢笔签的那一笔
        self.assertTrue(world.get("iou", "smudge"))
        again = submit(world, log, "jia", "erase", {"target": "借条"})
        self.assertFalse(again.ok)


class CopyTests(unittest.TestCase):
    def test_a_copy_carries_the_same_text_and_a_physical_trace(self):
        run = play("a")
        world = run.world
        copy = next(e for e in world.entities if world.entities[e].name == "抄件1")
        self.assertEqual([m["text"] for m in world.get(copy, "marks")],
                         [m["text"] for m in world.get("iou", "marks")])
        self.assertTrue(world.get(copy, "imprint"))
        self.assertNotIn("blank", world.entities)      # 空白纸被用掉了
        self.assertEqual(world.container(copy), "jia")

    def test_copy_needs_carbon_paper(self):
        world = _world()
        log = EventLog()
        submit(world, log, "jia", "unlock", {"target": "抽屉"})
        submit(world, log, "jia", "open", {"target": "抽屉"})
        submit(world, log, "jia", "take", {"target": "借条"})
        submit(world, log, "jia", "place", {"target": "借条", "to": "出租屋"})
        submit(world, log, "jia", "take", {"target": "空白纸"})
        world.parent["carbon"] = "drawer"      # 复写纸藏起来
        world.state["drawer"]["closed"] = True
        receipt = submit(world, log, "jia", "copy", {"target": "借条"})
        self.assertFalse(receipt.ok)
        self.assertIn("复写纸", receipt.reason)


class RecognitionTests(unittest.TestCase):
    def _ready(self):
        world = _world()
        log = EventLog()
        for verb, args in (("unlock", {"target": "抽屉"}), ("open", {"target": "抽屉"}),
                           ("take", {"target": "借条"}), ("place", {"target": "借条", "to": "出租屋"})):
            submit(world, log, "jia", verb, args)
        return world, log

    def test_only_someone_who_knows_the_hand_can_name_it(self):
        world, log = self._ready()
        bing = submit(world, log, "bing", "recognize", {"target": "借条"})
        jia = submit(world, log, "jia", "recognize", {"target": "借条"})
        self.assertIn("像是甲的字", bing.texts[0])
        self.assertIn("是你自己的字", jia.texts[0])
        self.assertNotIn("像是乙的字", jia.texts[0])

    def test_recognition_is_knowledge_not_magic(self):
        world, log = self._ready()
        world.hand_readers["bing"] = {}         # 丙不认识任何人的字
        receipt = submit(world, log, "bing", "recognize", {"target": "借条"})
        self.assertIn("说不出是谁写的", receipt.texts[0])
        self.assertNotIn("像是", receipt.texts[0])

    def test_reading_gives_the_words_and_never_the_hand(self):
        world, log = self._ready()
        receipt = submit(world, log, "jia", "read", {"target": "借条"})
        text = receipt.texts[0]
        self.assertIn("今借到现金一千元", text)
        self.assertNotIn("字", text.replace("借条", ""))

    def test_a_paper_never_says_who_wrote_it(self):
        world = _world()
        for mark in world.get("iou", "marks"):
            self.assertEqual(set(mark), {"text", "ink", "style"})
        self.assertNotIn("author", world.state["iou"])


class ReferenceTests(unittest.TestCase):
    """人用描述性说法指东西：引擎要能听懂「手里的空白纸」「桌子底下那只铁皮抽屉」。"""

    def test_a_descriptive_phrase_resolves_to_the_thing(self):
        world = _world()
        log = EventLog()
        submit(world, log, "jia", "unlock", {"target": "桌子底下那只铁皮抽屉"})
        self.assertFalse(world.get("drawer", "locked"))
        submit(world, log, "jia", "open", {"target": "那个抽屉"})
        self.assertFalse(world.get("drawer", "closed"))

    def test_in_hand_phrasing_prefers_what_you_hold(self):
        world = _world()
        log = EventLog()
        submit(world, log, "jia", "unlock", {"target": "抽屉"})
        submit(world, log, "jia", "open", {"target": "抽屉"})
        submit(world, log, "jia", "take", {"target": "借条"})
        receipt = submit(world, log, "jia", "place",
                         {"target": "手里的借条", "to": "出租屋"})
        self.assertTrue(receipt.ok, receipt.reason)
        self.assertEqual(world.container("iou"), "room")


class SchemaTests(unittest.TestCase):
    def test_an_unknown_seed_field_fails_loudly(self):
        seed = {
            "start_clock": 0,
            "objects": [{"id": "x", "name": "某物", "handwritten": True}],
        }
        with self.assertRaises(ValueError) as ctx:
            build(seed)
        self.assertIn("handwritten", str(ctx.exception))


class ReplayTests(unittest.TestCase):
    def test_all_four_paths_replay_identically(self):
        for variant in ("a", "b", "c", "d"):
            run = play(variant)
            self.assertEqual(replay(lambda: load(DEFAULT_SEED), run.log).digest(),
                             run.world.digest(), variant)

    def test_tampering_with_a_mark_is_caught(self):
        import copy
        run = play("d")
        rows = copy.deepcopy(run.log.to_json())
        target = next(r for r in rows
                      if any(a.get("op") == "set" and a.get("k") == "marks" for a in r["atoms"]))
        for atom in target["atoms"]:
            if atom.get("op") == "set" and atom.get("k") == "marks":
                atom["v"] = atom["v"][:-1]
                break
        with self.assertRaises(ReplayMismatch):
            replay(lambda: load(DEFAULT_SEED), EventLog.from_json(rows))


class UnknownNameTests(unittest.TestCase):
    def test_a_name_that_does_not_exist_lists_what_is_here(self):
        world = _world()
        log = EventLog()
        receipt = submit(world, log, "jia", "take", {"target": "合同"})
        self.assertFalse(receipt.ok)
        self.assertIn("合同", receipt.reason)
        self.assertTrue(any("眼前能看见" in hint for hint in receipt.hints))


if __name__ == "__main__":
    unittest.main()
