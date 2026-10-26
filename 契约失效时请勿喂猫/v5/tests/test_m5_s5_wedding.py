"""M5 的第二世界：《婚礼》四条路、一整天、记忆互污、无名指称、记录权威。

最要紧的四条：**四条路各自走到不同结局，而结局是从世界事实拼出来的**；
**一局从 09:00 签到走到 22:00 散场，跨过中午，日期不翻页**；
**同一件事在不同人的记忆里留下了不同版本**；
**不认识的人靠衣着被叫住，名字和 id 都叫不动他**。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

import library  # noqa: F401
from engine.core import ATOM_OPS
from engine.events import EventLog, replay
from engine.resolve import resolve
from engine.rules import submit
from engine.seed import load
from engine.surface import clock_label
from library import EFFECTS
from library.concepts import resolve_looks
from stories.s5_wedding import scenario
from stories.s5_wedding.scenario import (DEFAULT_SEED, EXTRA_NAME, SIGNIN_ID,
                                         STRANGER_ID, play, summary)
from stories.s5_wedding.transcript import transcript

VARIANTS = ("a", "b", "c", "d")
START, NOON, CLOSE = 540, 720, 1320


def _mem(world, who: str) -> str:
    return " ".join(text for _at, text in world.memory.get(who, []))


class EndingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {v: play(v) for v in VARIANTS}
        cls.sums = {v: summary(run) for v, run in cls.runs.items()}

    def test_each_path_has_a_readable_ending(self):
        expected = {"a": "查出了是谁", "b": "没有人再查",
                    "c": "记录被改", "d": "大家装作没看见"}
        for variant, token in expected.items():
            self.assertIn(token, self.sums[variant]["结局"], self.sums[variant]["结局"])
            self.assertGreater(len(transcript(self.runs[variant])), 500, variant)

    def test_four_paths_reach_four_endings(self):
        endings = {v: s["结局"] for v, s in self.sums.items()}
        self.assertEqual(len(set(endings.values())), 4, endings)

    def test_endings_are_computed_from_world_facts_not_from_the_path_name(self):
        """反证：把 `d` 的脚本换成 `a` 的，`d` 就必须按 `a` 的方式结束。"""
        original = scenario.SCRIPTS["d"]
        scenario.SCRIPTS["d"] = scenario.SCRIPTS["a"]
        try:
            aliased = summary(play("d"))
        finally:
            scenario.SCRIPTS["d"] = original
        self.assertEqual(aliased["结局"], summary(play("a"))["结局"],
                         "同一条脚本在两条路上结束得不一样：结局不是从世界算出来的")

    def test_the_extra_name_is_in_the_book_until_someone_erases_it(self):
        self.assertEqual({v: s["签到本上多出来的名字"] for v, s in self.sums.items()},
                         {"a": EXTRA_NAME, "b": EXTRA_NAME, "c": "已经被抹掉", "d": EXTRA_NAME})
        self.assertEqual({v: s["本子改过"] for v, s in self.sums.items()},
                         {"a": False, "b": False, "c": True, "d": False})


class OneDayTests(unittest.TestCase):
    def test_the_day_runs_from_nine_to_ten_same_date(self):
        run = play("b")
        world = run.world
        self.assertEqual(world.date, "2026-05-20")
        self.assertEqual(load(DEFAULT_SEED).clock, START)
        self.assertEqual(world.clock, CLOSE)
        self.assertEqual(clock_label(world.clock, world.date), "2026-05-20 22:00")

        # 中午过了一道：12:00 的张贴事件真的落进了账本
        world_events = [(e.at, e.what) for e in run.log if e.kind == "world"]
        self.assertIn((NOON, "post"), world_events)
        self.assertIn((CLOSE, "close"), world_events)
        # 日期不翻页：所有时钟读数都还是同一天
        stamps = {clock_label(e.at, world.date) for e in run.log}
        self.assertTrue(all(s.startswith("2026-05-20 ") for s in stamps), stamps)
        self.assertTrue(any(s.endswith("12:00") for s in stamps), stamps)

    def test_the_signed_row_survives_the_whole_day(self):
        run = play("b")
        self.assertEqual(run.world.container(SIGNIN_ID), "checkin")
        rows = run.world.get(SIGNIN_ID, "marks")
        self.assertTrue(any(EXTRA_NAME in r["text"] for r in rows))
        self.assertIn("09:0", rows[-1]["text"])

    def test_the_venue_has_four_places_and_a_crowd(self):
        seed = yaml.safe_load(DEFAULT_SEED.read_text(encoding="utf-8"))
        places = {row["id"]: row for row in seed["places"]}
        for eid in ("hall", "checkin", "corridor", "parking"):
            self.assertIn(eid, places)
        people = seed["people"]
        self.assertGreaterEqual(len(people), 10, len(people))
        world = load(DEFAULT_SEED)
        in_venue = [p for p in world.entities
                    if world.kind_of(p) == "person"
                    and world.place_of(p) in ("venue", "hall", "checkin",
                                              "corridor", "parking")]
        self.assertGreaterEqual(len(in_venue), 10, in_venue)


class MemoryContaminationTests(unittest.TestCase):
    """一时之间，同一件事在几张嘴里长成了不同的样子。"""

    @classmethod
    def setUpClass(cls):
        cls.played = play("d")
        cls.world = cls.played.world

    def test_who_heard_what(self):
        # 记账的人读过本子：他知道那个名字
        self.assertIn(EXTRA_NAME, _mem(self.world, "bookkeeper"))
        # 新娘的母亲也读过本子
        self.assertIn(EXTRA_NAME, _mem(self.world, "bride_mother"))
        # 经理只在私下被告知，没读过本子
        self.assertNotIn("你读着签到本", _mem(self.world, "manager"))
        # 厅里的宾客只听见了转述后的版本
        self.assertIn(EXTRA_NAME, _mem(self.world, "groom"))

    def test_one_memory_gains_a_detail_the_others_lose(self):
        manager = _mem(self.world, "manager")
        groom = _mem(self.world, "groom")
        # 经理听过完整一句（是穿灰夹克的男人写的）
        self.assertIn("是穿灰夹克的男人写的", manager)
        # 转述到厅里时，那一截已经掉了
        self.assertIn(EXTRA_NAME, groom)
        self.assertNotIn("穿灰夹克", groom)

    def test_the_private_aside_is_not_heard_by_the_room(self):
        mother = _mem(self.world, "bride_mother")
        self.assertIn("低声说话", mother)
        self.assertNotIn("是穿灰夹克的男人写的", mother)

    def test_at_least_two_versions_of_the_same_matter_coexist(self):
        versions = set()
        for person in self.world.entities:
            if self.world.kind_of(person) != "person":
                continue
            for _at, text in self.world.memory.get(person, []):
                if EXTRA_NAME in text and "签到本" in text:
                    versions.add(text)
        self.assertGreaterEqual(len(versions), 2, versions)


class AnonymousReferenceTests(unittest.TestCase):
    def test_an_unknown_person_is_named_by_clothes_not_by_id(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        # 名字与 id 都叫不出一个你根本不认识的人
        self.assertFalse(resolve(world, "bride", "陌生人").ok)
        self.assertFalse(resolve(world, "bride", "stranger").ok)
        by_id = submit(world, log, "bride", "hail", {"who": "stranger", "text": "喂"})
        self.assertFalse(by_id.ok)
        # 衣着叫得动
        by_looks = submit(world, log, "bride", "hail",
                          {"who": "穿灰夹克的男人", "text": "你就是陈明？"})
        self.assertTrue(by_looks.ok, by_looks.reason)
        self.assertEqual(resolve_looks(world, "bride", "穿灰夹克的男人"), STRANGER_ID)
        self.assertIsNone(resolve_looks(world, "bride", "stranger"))

    def test_recognizing_him_does_not_tell_the_rest_of_the_room(self):
        world = play("a").world
        self.assertIn(STRANGER_ID, world.knowledge["bride"])
        for other in ("groom", "best_man", "maid", "manager"):
            self.assertNotIn(STRANGER_ID, world.knowledge[other], other)


class RecordAuthorityTests(unittest.TestCase):
    def test_only_what_is_written_into_the_book_counts(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        before = len(world.get(SIGNIN_ID, "marks"))
        oral = submit(world, log, "groom", "speak", {"text": "我签过了，就写我的名字。"})
        self.assertTrue(oral.ok)
        self.assertEqual(len(world.get(SIGNIN_ID, "marks")), before,
                         "嘴上说的进了签到本")
        submit(world, log, "bookkeeper", "take", {"target": "铅笔"})
        written = submit(world, log, "bookkeeper", "sign",
                         {"target": "签到本", "text": "记账人代签"})
        self.assertTrue(written.ok, written.reason)
        rows = world.get(SIGNIN_ID, "marks")
        self.assertEqual(len(rows), before + 1)
        self.assertIn("记账人代签", rows[-1]["text"])

    def test_a_signature_requires_a_register(self):
        world = load(DEFAULT_SEED)
        submit(world, EventLog(), "bookkeeper", "take", {"target": "铅笔"})
        receipt = submit(world, EventLog(), "bookkeeper", "sign",
                         {"target": "名单", "text": "我也签个"})
        self.assertFalse(receipt.ok)
        self.assertIn("登记", receipt.reason)

    def test_the_erased_row_leaves_a_physical_trace(self):
        run = play("c")
        self.assertTrue(run.world.get(SIGNIN_ID, "smudge"))
        self.assertFalse(any(EXTRA_NAME in r["text"]
                             for r in run.world.get(SIGNIN_ID, "marks")))


class CrowdFanoutTests(unittest.TestCase):
    def test_an_announcement_reaches_the_room_and_stops_at_its_door(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        submit(world, log, "groom", "announce", {"text": "开席了。"})
        for hearer in ("bride", "best_man", "stranger"):
            self.assertIn("开席了", _mem(world, hearer), hearer)
        # 签到台与停车场的人不在这一处，听不见
        for far in ("bookkeeper", "manager"):
            self.assertNotIn("开席了", _mem(world, far), far)

    def test_a_rumor_cannot_be_retold_by_someone_who_never_heard_it(self):
        world = load(DEFAULT_SEED)
        receipt = submit(world, EventLog(), "groom", "retell",
                         {"about": "陈明", "text": "签到本上多了个名字，叫陈明。"})
        self.assertFalse(receipt.ok)
        self.assertIn("没听人说起", receipt.reason)


class NoScheduledActorTests(unittest.TestCase):
    def test_world_events_are_physics_or_institution_only(self):
        for variant in VARIANTS:
            run = play(variant)
            for event in run.log:
                if event.kind != "world":
                    continue
                self.assertIsNone(event.actor)
                self.assertIn(event.what, EFFECTS)
                effect = event.note["effect"]
                self.assertEqual({"actor", "say", "do"} & set(effect), set(), effect)
                for atom in event.atoms:
                    self.assertIn(atom["op"], ATOM_OPS)

    def test_the_seed_schedules_only_institutions_without_a_decider(self):
        seed = yaml.safe_load(DEFAULT_SEED.read_text(encoding="utf-8"))
        self.assertTrue(seed["schedule"])
        allowed = {"kind", "place", "item", "who", "station"}
        for item in seed["schedule"]:
            effect = item["effect"]
            self.assertIn(effect["kind"], EFFECTS, effect)
            self.assertFalse(set(effect) - allowed, effect)


class ReplayTests(unittest.TestCase):
    def test_all_four_paths_replay_identically(self):
        for variant in VARIANTS:
            run = play(variant)
            self.assertEqual(replay(lambda: load(DEFAULT_SEED), run.log).digest(),
                             run.world.digest(), variant)


if __name__ == "__main__":
    unittest.main()
