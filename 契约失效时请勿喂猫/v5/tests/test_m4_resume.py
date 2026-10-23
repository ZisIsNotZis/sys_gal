"""M4 的续跑门：半天检查点写下来，从它还原，继续走，账本仍是一本。

三件事必须同时成立，少一件就不算"因果连续"：
1. 检查点里的世界与账本前缀，读回后逐字一致（世界快照结构相等 + digest 相等）；
2. 续跑后的账本与未中断的那本逐字节相同，id 从 1 连续到结尾；
3. 整本账从种子重放出来的世界，与续跑结束时的世界是同一个世界（digest 相等）。

第 3 条是因果的判据：账本没有缺口，续跑没有凭记忆补状态。
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
from stories.s1_last_bus.scenario import DEFAULT_SEED, SCRIPTS, play


def run_steps(world, log, steps):
    """按脚本走 `steps` 步；世界事件先于动作发生，和 scenario.play 同一顺序。"""
    for actor, verb, args in steps:
        drain(world, log, EFFECTS)
        submit(world, log, actor, verb, dict(args))
    return world, log


def mid_run_clock() -> int:
    """这一局的中途断点：脚本跨度的中点。

    名字里没有"半天"二字，因为它不是半天：这一局世界时间只有二十几分钟。
    真的半夜边界（18:30 收摊 → 次日 08:00 开门）在 `tests/test_m5_cross_night.py`
    里检验，那一处才是"半日一局"里"半日"两个字的证据。
    """
    start = load(DEFAULT_SEED).clock
    end = play("a").world.clock
    return start + (end - start) // 2


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_dir = Path(tempfile.mkdtemp(prefix="v5-checkpoint-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.run_dir, ignore_errors=True)

    # ---- 1. 写下来、读回来，世界逐字一致
    def test_a_checkpoint_round_trips_the_world_exactly(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        world, log = run_steps(world, log, SCRIPTS["a"][:4])

        path = checkpoint.save_new(self.run_dir, world, log, label="round-trip",
                                   run_id="round-trip")
        payload = checkpoint.load(path)
        restored, restored_log = checkpoint.restore(payload)

        self.assertEqual(payload["format"], checkpoint.FORMAT)
        self.assertEqual(payload["event_count"], len(log))
        self.assertEqual(checkpoint.snapshot_world(restored), payload["world"])
        self.assertEqual(restored.digest(), world.digest())
        # digest 看不见排程序号与时钟序号，单独比一次
        self.assertEqual(restored.seq, world.seq)
        self.assertEqual(dump_log(restored_log), dump_log(log))

    # ---- 2. 唯一命名：同一 run_id 的第二个检查点不覆盖第一个
    def test_a_second_checkpoint_never_overwrites_the_first(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        world, log = run_steps(world, log, SCRIPTS["a"][:2])
        first = checkpoint.save_new(self.run_dir, world, log, label="unique", run_id="unique")
        before = first.read_bytes()

        world, log = run_steps(world, log, SCRIPTS["a"][2:4])
        second = checkpoint.save_new(self.run_dir, world, log, label="unique", run_id="unique")

        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), before)          # 旧工件一个字节都没动
        self.assertEqual(checkpoint.last_event_id(checkpoint.load(first)), 2)
        self.assertGreater(checkpoint.last_event_id(checkpoint.load(second)), 2)
        with self.assertRaises(FileExistsError):
            checkpoint.save(first, checkpoint.load(second))

    # ---- 3. 检查点坏了必须被拒绝，而不是还原出半个世界
    def test_a_tampered_checkpoint_is_refused(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        world, log = run_steps(world, log, SCRIPTS["a"][:3])
        payload = checkpoint.snapshot(world, log, label="tamper")
        world.memory["jia"].append([world.clock, "检查点之后才发生的事"])
        stale = dict(payload, digest=world.digest())
        with self.assertRaises(checkpoint.CheckpointError):
            checkpoint.restore(stale)
        with self.assertRaises(checkpoint.CheckpointError):
            checkpoint.restore(dict(payload, event_count=payload["event_count"] + 1))
        with self.assertRaises(checkpoint.CheckpointError):
            checkpoint.restore(dict(payload, format="v4-checkpoint-2"))

    # ---- 4. 中途断点 → 检查点 → 续跑 → 账本连续、重放相等
    def test_resume_from_a_mid_run_checkpoint_is_causally_continuous(self):
        boundary = mid_run_clock()
        steps = SCRIPTS["a"]

        # (a) 走到中途断点，写检查点
        world = load(DEFAULT_SEED)
        log = EventLog()
        cut = 0
        for index, step in enumerate(steps, start=1):
            drain(world, log, EFFECTS)
            submit(world, log, step[0], step[1], dict(step[2]))
            cut = index
            if world.clock >= boundary:
                break
        self.assertGreaterEqual(world.clock, boundary, "没走到中途断点")
        path = checkpoint.save_new(self.run_dir, world, log, label="mid-run", run_id="mid-run")
        payload = checkpoint.load(path)

        # (b) 从检查点造一个全新的世界与账本；不许借原来的对象
        resumed_world, resumed_log = checkpoint.restore(payload)
        self.assertIsNot(resumed_world, world)
        self.assertEqual(resumed_world.digest(), world.digest())

        # (c) 接着往下走，直到世界自己停
        run_steps(resumed_world, resumed_log, steps[cut:])
        advance_idle(resumed_world, resumed_log, EFFECTS)

        # (c') 作为对照：同一份脚本不中断地走一遍
        straight_world = load(DEFAULT_SEED)
        straight_log = EventLog()
        run_steps(straight_world, straight_log, steps)
        advance_idle(straight_world, straight_log, EFFECTS)

        # (d) 续跑没有重写历史：前缀逐字节相同，id 从 1 连续到结尾
        kept = payload["event_count"]
        self.assertEqual([e.to_json() for e in resumed_log.events[:kept]],
                         [e.to_json() for e in log.events])
        self.assertEqual([e.id for e in resumed_log.events],
                         list(range(1, len(resumed_log) + 1)))
        self.assertGreater(len(resumed_log), kept)
        self.assertEqual(dump_log(resumed_log), dump_log(straight_log))

        # (e) 因果：整本账从种子重放 = 续跑出来的世界
        replayed = replay(lambda: load(DEFAULT_SEED), resumed_log)
        self.assertEqual(replayed.digest(), resumed_world.digest())
        self.assertEqual(replayed.digest(), straight_world.digest())
        self.assertTrue(resumed_world.flags.get("stopped"))


if __name__ == "__main__":
    unittest.main()
