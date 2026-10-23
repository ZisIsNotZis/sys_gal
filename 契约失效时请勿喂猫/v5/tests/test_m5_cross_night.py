"""M5 的入口条件：S3 真的跨过 18:30→次日 08:00 的边界，并从那里续跑。

M4 的 claim 3 只证明了机制：唯一的断点是 S1 的 23 分钟中点，没有任何测试跨过一夜。
这一份测的就是那一天：夜里关掉的排程、次日的开门，以及"在夜里存一份检查点，
从它续跑到第二天早上"是同一个世界、同一本账。

三条判据，少一条就不算过夜：
1. 这一局真的跨过边界：`close` 在 1110 发生、`open` 在 1920 发生，结局落在收摊之后；
2. 夜里存、次日续跑：前缀逐字节相同、id 从 1 连续、续跑账本与不中断的那本一字不差、
   整本账从种子重放 = 续跑出来的世界；
3. 负向对照：把次日开门那条排程从检查点里拿掉，甲第二天就开不了门、条子留在管理处——
   跨夜这一刀真的做了事，不是一条永远通过的断言。
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
from engine.events import EventLog, dump_log, replay
from engine.rules import advance_idle, drain, submit
from engine.seed import load
from library import EFFECTS
from stories.s3_night_market.scenario import DEFAULT_SEED, NIGHT, NOTE_ID, SCRIPTS, play

STEPS = SCRIPTS["e"]
NIGHT_AT = STEPS.index(("", NIGHT, {}))
CLOSE_AT, OPEN_AT = 1110, 1920


def walk(world, log, steps):
    """按脚本走一段；世界事件先于动作，夜里那一段交给 `advance_idle`。"""
    for actor, verb, args in steps:
        drain(world, log, EFFECTS)
        if verb == NIGHT:
            advance_idle(world, log, EFFECTS)
            continue
        submit(world, log, actor, verb, dict(args))
    return world, log


def world_events(log):
    return [(event.at, event.what) for event in log if event.kind == "world"]


class NightBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_dir = Path(tempfile.mkdtemp(prefix="v5-night-"))
        cls.night = play("e")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.run_dir, ignore_errors=True)

    # ---- 1. 这一局真的过夜 ----------------------------------------------
    def test_the_run_crosses_the_night_boundary(self):
        fired = world_events(self.night.log)
        self.assertIn((CLOSE_AT, "close"), fired)
        self.assertIn((OPEN_AT, "open"), fired)
        self.assertLess(fired.index((CLOSE_AT, "close")), fired.index((OPEN_AT, "open")))
        self.assertGreaterEqual(self.night.world.clock, OPEN_AT)
        # 门先关后开，条子隔了一夜回到甲手里，结局落在收摊之后
        self.assertEqual(self.night.world.get("office", "door"), "open")
        self.assertEqual(self.night.world.container(NOTE_ID), "a")
        self.assertFalse(self.night.summary["结局落在收摊之前"])

    # ---- 2. 夜里存、次日续跑 --------------------------------------------
    def test_resume_from_a_checkpoint_taken_at_night_is_causally_continuous(self):
        # (a) 走到收摊前，条子已经在管理处，人走开了 —— 这是夜里的断点
        world = load(DEFAULT_SEED)
        log = EventLog()
        walk(world, log, STEPS[:NIGHT_AT])
        self.assertLess(world.clock, OPEN_AT)
        path = checkpoint.save_new(self.run_dir, world, log, label="night", run_id="night")
        payload = checkpoint.load(path)

        # (b) 从检查点造一个全新的世界与账本，不许借原来的对象
        resumed_world, resumed_log = checkpoint.restore(payload)
        self.assertIsNot(resumed_world, world)
        self.assertEqual(resumed_world.digest(), world.digest())

        # (c) 续跑：世界自己过夜，第二天甲开门领条子
        walk(resumed_world, resumed_log, STEPS[NIGHT_AT:])

        # (c') 对照：同一份脚本不中断地走一遍
        straight_world = load(DEFAULT_SEED)
        straight_log = EventLog()
        walk(straight_world, straight_log, STEPS)

        # (d) 续跑没有重写历史
        kept = payload["event_count"]
        self.assertEqual([event.to_json() for event in resumed_log.events[:kept]],
                         [event.to_json() for event in log.events])
        self.assertEqual([event.id for event in resumed_log.events],
                         list(range(1, len(resumed_log) + 1)))
        self.assertEqual(dump_log(resumed_log), dump_log(straight_log))
        self.assertEqual(dump_log(resumed_log), dump_log(self.night.log))

        # (e) 因果：整本账从种子重放 = 续跑出来的世界，且它确实过了夜
        replayed = replay(lambda: load(DEFAULT_SEED), resumed_log)
        self.assertEqual(replayed.digest(), resumed_world.digest())
        self.assertEqual(replayed.digest(), straight_world.digest())
        self.assertGreaterEqual(resumed_world.clock, OPEN_AT)
        self.assertEqual(resumed_world.get("office", "door"), "open")
        self.assertEqual(resumed_world.container(NOTE_ID), "a")

    # ---- 3. 负向对照：拿掉次日开门，跨夜就白跨 --------------------------
    def test_without_the_next_morning_open_the_note_stays_in_the_office(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        walk(world, log, STEPS[:NIGHT_AT])
        payload = checkpoint.snapshot(world, log, label="night-no-open")

        resumed_world, resumed_log = checkpoint.restore(payload)
        # 只动一处：从还原后的世界里摘掉次日开门。
        # （改检查点本身会被 digest 自校验拒掉——那是另一条属性，这里要的是
        #  同一个夜里少掉次日开门，看这一刀到底做不做事。）
        before = list(resumed_world.schedule)
        resumed_world.schedule = [row for row in before if row[2].get("kind") != "open"]
        self.assertEqual(len(resumed_world.schedule), len(before) - 1)

        walk(resumed_world, resumed_log, STEPS[NIGHT_AT:])

        self.assertEqual(resumed_world.get("office", "door"), "closed")
        self.assertEqual(resumed_world.container(NOTE_ID), "office")
        # 对照：同一个动作在跨了夜的世界里撞到的是“门开着了”，不是“门锁着”。
        doors = [item for item in self.night.items
                 if item["kind"] == "turn" and item["verb"] == "open"]
        self.assertTrue(doors, "路 e 里得有一次去开门")
        self.assertIn("本来就开着", doors[-1]["reason"])
        self.assertNotEqual(resumed_world.digest(), load(DEFAULT_SEED).digest())


if __name__ == "__main__":
    unittest.main()
