"""M5 的验收：《夜班》四条路 + 数量与盘点、锁与钥匙、交接、远程通道、承诺。

四条路各自走到 `V5-SCENES` 承认的四种结局（找到了·记错 / 真丢了 / 被人做了账 /
自己背），而结局是从世界事实拼出来的：抽屉里的数、记录上的数、钱最后在谁手里、
记录上多出来的是谁的字。最后一段是过夜：这一班从 22:00 走到次日 08:00，
轨迹上印着次日的日期；夜里取一次检查点再续跑，账本与不中断的那一本一字不差。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401
from engine import checkpoint
from engine.core import ATOM_OPS
from engine.events import EventLog, dump_log, replay
from engine.rules import advance_idle, drain, submit
from engine.resolve import in_sight, visible
from engine.seed import load
from library import EFFECTS
from stories.s4_night_shop import scenario
from stories.common import advance_next
from stories.s4_night_shop.scenario import DEFAULT_SEED, NEXT, NIGHT, SCRIPTS, play, summary
from stories.s4_night_shop.transcript import transcript

VARIANTS = ("a", "b", "c", "d")
SPARE, BOX, RECORD = "spare_cash", "box", "handover_record"
OFFICE, KEY = "office", "office_key"


def walk(world, log, steps):
    """按脚本走一段；世界事件先于动作，夜里那一段交给 `advance_idle`。"""
    for actor, verb, args in steps:
        drain(world, log, EFFECTS)
        if verb == NIGHT:
            advance_idle(world, log, EFFECTS)
            continue
        if verb == NEXT:
            advance_next(world, log, EFFECTS)
            continue
        submit(world, log, actor, verb, dict(args))
    return world, log


def event_ids(log):
    return [event.id for event in log]


class StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {v: play(v) for v in VARIANTS}
        cls.sums = {v: summary(run) for v, run in cls.runs.items()}

    def test_four_paths_reach_four_endings(self):
        endings = {v: s["结局"] for v, s in self.sums.items()}
        self.assertEqual(len(set(endings.values())), 4, endings)

    def test_each_path_reads_as_its_own_ending(self):
        phrases = {"a": "找到了（记错）", "b": "真丢了", "c": "被人做了账", "d": "自己背"}
        for variant, phrase in phrases.items():
            self.assertIn(phrase, self.sums[variant]["结局"], variant)

    def test_endings_come_from_world_facts_not_path_names(self):
        facts = {v: (s["收银抽屉里的数"], s["记录上的数"], s["店里现金总数"],
                     s["备用金最后在谁手里"], tuple(s["交班者添的行"]),
                     tuple(s["接班者添的行"]))
                 for v, s in self.sums.items()}
        endings = {v: s["结局"] for v, s in self.sums.items()}
        self.assertEqual(len(set(endings.values())), len(set(facts.values())), facts)
        # 反证：把 c 的脚本换成 a 的，c 就必须按 a 的方式结束。
        original = scenario.SCRIPTS["c"]
        scenario.SCRIPTS["c"] = scenario.SCRIPTS["a"]
        try:
            aliased = summary(play("c"))
        finally:
            scenario.SCRIPTS["c"] = original
        self.assertEqual(aliased["结局"], self.sums["a"]["结局"],
                         "同一条脚本在两条路上结束得不一样：结局不是从世界算出来的")

    def test_the_counts_are_real_numbers(self):
        self.assertEqual({v: s["收银抽屉里的数"] for v, s in self.sums.items()},
                         {"a": 1000, "b": 800, "c": 800, "d": 800})
        self.assertEqual({v: s["店里现金总数"] for v, s in self.sums.items()},
                         {"a": 1000, "b": 800, "c": 800, "d": 1000})
        # 少的 200 是备用金自己那一份，不是"短款"这种状态键。
        self.assertEqual({v: s["备用金最后在谁手里"] for v, s in self.sums.items()},
                         {"a": "收银抽屉", "b": "送货员拿着的纸箱",
                          "c": "送货员拿着的纸箱", "d": "后仓的纸箱里"})

    def test_every_turn_is_marked_as_scripted(self):
        for run in self.runs.values():
            turns = [i for i in run.items if i["kind"] == "turn"]
            self.assertTrue(turns)
            self.assertTrue(all(i["decided_by"] == "script" and not i["context_used"]
                                for i in turns))

    def test_no_action_was_refused_by_the_world(self):
        for variant, run in self.runs.items():
            self.assertEqual([r.reason for r in run.receipts if not r.ok], [], variant)


class MidnightTests(unittest.TestCase):
    def test_the_shift_runs_from_22_to_the_next_morning(self):
        run = play("a")
        self.assertGreaterEqual(run.world.clock, 1920)
        view = transcript(run)
        self.assertIn("2026-04-02 22:00", view)
        self.assertIn("2026-04-03 08:", view)
        self.assertNotIn("32:00", view)
        self.assertEqual(run.summary["交班时刻读法"][:10], "2026-04-03")

    def test_the_promise_enters_the_time_table_and_wakes_the_promiser(self):
        run = play("a")
        heard = " ".join(text for _at, text in run.world.memory.get("incoming", []))
        self.assertIn("明晚白班我替你顶", heard)
        reminders = [e for e in run.log if e.kind == "world" and e.what == "remind"]
        self.assertEqual([e.at for e in reminders], [1900])

    def test_the_night_has_no_silent_gap_longer_than_two_hours(self):
        """这一班从 22:00 到次日 08:00，相邻两条轨迹的时间戳间隔不得超过 120 分钟。

        观察自：本包合入后的人工通读（2026-10-23）——`runs/a.md` 从 22:45 一直空到 07:40，
        九个小时没有一条事件；判据只数世界与脚本动作，不数时钟 tick。
        """
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                run = play(variant)
                stamps = [item["at"] for item in run.items
                          if 1320 <= item["at"] <= 1920]
                self.assertGreater(len(stamps), 20, variant)
                gaps = [(b - a, a, b) for a, b in zip(stamps, stamps[1:])]
                longest = max(gaps)
                self.assertLessEqual(longest[0], 120,
                                     f"路 {variant} 的空档 {longest[0]} 分钟：{longest[1]} → {longest[2]}")
                self.assertIn(1320, stamps, variant)
                self.assertIn(1920, stamps, variant)

    def test_the_nights_institutions_reach_the_shop(self):
        """送货、巡夜签到、清晨补货与清扫真的落在账本里，而不是人物嘴上。"""
        run = play("a")
        world = [(event.at, event.what) for event in run.log if event.kind == "world"]
        self.assertEqual([at for at, what in world if what == "deliver"], [1425, 1770])
        self.assertEqual([at for at, what in world if what == "stamp"], [1530])
        self.assertEqual([at for at, what in world if what == "clean"], [1880])
        self.assertIn("夜间补货", " ".join(text for _at, text in run.world.memory["incoming"]))
        log_rows = [row["text"] for row in run.world.get("patrol_log", "marks")]
        self.assertTrue(any("巡夜签到" in text for text in log_rows), log_rows)

    def test_closing_hands_the_key_back(self):
        run = play("a")
        self.assertEqual(run.world.container(KEY), "outgoing")
        self.assertEqual(run.world.get(RECORD, "marks")[-1]["style"], "in_hand")


class RemoteChannelTests(unittest.TestCase):
    def test_the_manager_hears_but_never_sees(self):
        world = play("a").world
        heard = " ".join(text for _at, text in world.memory.get("manager", []))
        self.assertIn("抽屉里数出八百", heard)          # 听到了
        self.assertNotIn("你数了收银抽屉", heard)        # 没看见数钱
        self.assertFalse(in_sight(world, "manager", "drawer"))
        self.assertEqual(visible(world, "manager"), [])

    def test_the_shop_side_hears_the_voice_back(self):
        world = play("a").world
        heard = " ".join(text for _at, text in world.memory.get("incoming", []))
        self.assertIn("钥匙在谁手里", heard)

    def test_outsiders_do_not_hear_the_call(self):
        world = play("a").world
        for outsider in ("customer", "driver"):
            heard = " ".join(text for _at, text in world.memory.get(outsider, []))
            self.assertNotIn("钥匙在谁手里", heard, outsider)


class ConceptTests(unittest.TestCase):
    """库新增概念各一条：数量、锁/钥匙、交接记录、远程通道（外加承诺）。"""

    def test_count_sees_only_what_is_not_sealed(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        self.assertTrue(submit(world, log, "incoming", "move", {"target": "后仓"}).ok)
        sealed = submit(world, log, "incoming", "count", {"target": BOX})
        self.assertTrue(sealed.ok, sealed.reason)
        self.assertIn("没有可数的份数", sealed.texts[0])
        self.assertTrue(submit(world, log, "incoming", "open", {"target": BOX}).ok)
        rows = submit(world, log, "incoming", "count", {"target": BOX})
        self.assertTrue(rows.ok, rows.reason)
        self.assertIn("200", rows.texts[0])

    def test_a_key_and_a_lock_are_containment_and_physics(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        locked_out = submit(world, log, "incoming", "unlock", {"target": OFFICE})
        self.assertFalse(locked_out.ok)
        self.assertIn("钥匙", locked_out.reason)
        self.assertTrue(submit(world, log, "outgoing", "unlock", {"target": OFFICE}).ok)
        self.assertTrue(submit(world, log, "outgoing", "open", {"target": OFFICE}).ok)
        self.assertTrue(submit(world, log, "outgoing", "lock", {"target": OFFICE}).ok)
        self.assertTrue(world.get(OFFICE, "locked"))
        self.assertEqual(world.get(OFFICE, "door"), "closed")

    def test_handover_writes_one_row_and_moves_the_key(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        before = len(world.get(RECORD, "marks"))
        receipt = submit(world, log, "outgoing", "shift",
                         {"target": "交接记录", "to": "接班者", "key": "办公室钥匙"})
        self.assertTrue(receipt.ok, receipt.reason)
        self.assertEqual(len(world.get(RECORD, "marks")), before + 1)
        self.assertIn("交班", world.get(RECORD, "marks")[-1]["text"])
        self.assertEqual(world.container(KEY), "incoming")


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
        import yaml
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


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_dir = Path(tempfile.mkdtemp(prefix="v5-night-shop-"))
        cls.steps = SCRIPTS["a"]
        cls.night_at = cls.steps.index(("", NIGHT, {}))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.run_dir, ignore_errors=True)

    def test_a_checkpoint_taken_during_the_shift_resumes_into_the_same_ledger(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        walk(world, log, self.steps[:self.night_at])
        self.assertLess(world.clock, 1920)
        path = checkpoint.save_new(self.run_dir, world, log, label="night", run_id="night")
        payload = checkpoint.load(path)

        resumed_world, resumed_log = checkpoint.restore(payload)
        self.assertIsNot(resumed_world, world)
        self.assertEqual(resumed_world.digest(), world.digest())

        walk(resumed_world, resumed_log, self.steps[self.night_at:])

        straight_world = load(DEFAULT_SEED)
        straight_log = EventLog()
        walk(straight_world, straight_log, self.steps)

        kept = payload["event_count"]
        self.assertEqual([e.to_json() for e in resumed_log.events[:kept]],
                         [e.to_json() for e in log.events])
        self.assertEqual(event_ids(resumed_log), list(range(1, len(resumed_log) + 1)))
        self.assertEqual(dump_log(resumed_log), dump_log(straight_log))
        self.assertEqual(dump_log(resumed_log), dump_log(play("a").log))

        replayed = replay(lambda: load(DEFAULT_SEED), resumed_log)
        self.assertEqual(replayed.digest(), resumed_world.digest())
        self.assertEqual(replayed.digest(), straight_world.digest())
        self.assertGreaterEqual(resumed_world.clock, 1920)
        self.assertEqual(resumed_world.container(KEY), "outgoing")


if __name__ == "__main__":
    unittest.main()
