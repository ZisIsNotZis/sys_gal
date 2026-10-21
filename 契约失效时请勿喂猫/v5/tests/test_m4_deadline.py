"""M4 半日 + S3《夜市》：期限与“动作的中途打断”。

这个文件的夹具就是一个脚本演员的《夜市》切片：摊子在收摊时限前把箱子封上，
而摊主正隔着一张复写纸抄押金条——动作在飞，时限到了，前提被抽走。

它同时钉住三件事：
1. 到点的世界效果落在动作**区间里**时，动作不是“没成”，而是做不完：一样都不留
   （P2：一次意愿要么全成要么全不成），落成一条 `interrupted` 事件；
2. 世界停在时限那一刻，不是停在这个动作本来该做完的那一刻；
3. 本人与在场的人看见的不是同一件事（本人知道没做完，旁人只看见动作停在半路）。

夹具里的 `seal` 是本文件里的**测试替身**：现实里“到点封箱”属于
`library/institutions.py` 的制度表。引擎这一层只认 `effects` 这张表本身。
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401  登记渲染与规则
from engine.core import World
from engine.events import EventLog, replay
from engine.render import pairing_report
from engine.rules import advance_idle, drain, submit
from engine.seed import build, state_keys
from library import EFFECTS


# ---------- 制度替身：到点把某个地方或容器封上

def seal(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    """到点封上一样东西（收摊、打烊、截件）。只改物性，不替任何人做决定。"""
    eid = effect["place"]
    name = world.entities[eid].name
    here = world.place_of(eid)
    atoms = [{"op": "set", "e": eid, "k": "closed", "v": True}]
    atoms += [{"op": "remember", "e": p, "at": world.clock,
               "v": f"有人过来把{name}封上了。"}
              for p in world.entities
              if world.kind_of(p) == "person" and world.place_of(p) == here]
    return atoms


FIXTURE_EFFECTS = {**EFFECTS, "seal": seal}


# ---------- 《夜市》切片：一个摊子，一条押金条，一个收摊时限

def market_seed(deadline: int = 1439) -> dict[str, Any]:
    """收摊时限默认 23:59：抄一份押金条要三分钟，从 23:57 抄，时限正好落在中间。"""
    return {
        "story": "s3_night_market slice",
        "date": "2026-06-01",
        "start_clock": 1436,
        "places": [
            {"id": "street", "name": "街",
             "prose": "夜市散了一半的地面，纸屑和竹签"},
            {"id": "stall", "parent": "street", "name": "摊位",
             "prose": "一盏电瓶灯，塑料布上还压着没收完的货"},
        ],
        "people": [
            {"id": "vendor", "parent": "stall", "name": "摊主",
             "prose": "袖口卷着，手里攥着一张纸",
             "identity": "你在这个夜市摆了六年。押金条是你要回来的东西，摊子说收就收，账不能糊涂。",
             "knows": ["stall", "street", "slip", "chest", "blank"]},
            {"id": "buyer", "parent": "stall", "name": "买主",
             "prose": "挑着东西，眼睛一直在秤上",
             "identity": "你只关心秤准不准。",
             "knows": ["vendor", "stall", "slip"]},
            {"id": "warden", "parent": "street", "name": "管理员",
             "prose": "手里一把钥匙，一条锁链搭在肩上",
             "identity": "收摊是你的活。",
             "knows": ["stall", "street", "vendor"]},
        ],
        "objects": [
            {"id": "slip", "parent": "vendor", "name": "押金条",
             "prose": "边角被手汗泡软的小票",
             "state": {"marks": [{"text": "押金 三十 收摊退", "ink": "printed",
                                  "style": "printed"}],
                       "portable": True}},
            {"id": "blank", "parent": "vendor", "name": "空白纸",
             "prose": "从本子上撕下来的一页",
             "state": {"accepts": ["ink"], "portable": True}},
            {"id": "chest", "parent": "stall", "name": "木箱",
             "prose": "铁皮包角的木箱，盖子虚掩着",
             "state": {"closed": False}},
            {"id": "carbon", "parent": "chest", "name": "复写纸",
             "prose": "一张用旧了的蓝复写纸",
             "state": {"copies": True}},
        ],
        "schedule": [
            {"at": deadline, "effect": {"kind": "seal", "place": "chest"}},
        ],
    }


#: 脚本演员：一条物理上可行的路径，动作与时限在时间上真的撞上了。
SCRIPT: list[tuple[str, str, dict[str, Any]]] = [
    ("vendor", "examine", {}),           # 23:36 → 23:37
    ("vendor", "copy", {"target": "押金条"}),   # 23:37 起，本来 23:40 完
    ("vendor", "copy", {"target": "押金条"}),   # 时限已经过去：这一次连开始都开始不了
]


def play(deadline: int = 1439, *, submit_effects: dict | None = None) -> dict[str, Any]:
    """跑一遍切片。`submit_effects` 决定动作在飞的时候世界能不能插进来。"""
    world = build(market_seed(deadline))
    log = EventLog()
    receipts = []
    for actor, verb, args in SCRIPT:
        drain(world, log, FIXTURE_EFFECTS)
        receipts.append(submit(world, log, actor, verb, dict(args),
                               effects=submit_effects))
    advance_idle(world, log, FIXTURE_EFFECTS)
    return {"world": world, "log": log, "receipts": receipts,
            "events": [e for e in log]}


def copies(world: World) -> list[str]:
    return sorted(e for e in world.entities if e.startswith("copy_"))


class DeadlineTests(unittest.TestCase):
    def setUp(self):
        self.run = play(submit_effects=FIXTURE_EFFECTS)
        self.world = self.run["world"]
        self.log = self.run["log"]
        self.look, self.inflight, self.after = self.run["receipts"]

    def test_action_in_flight_is_cut_by_the_clock_deadline(self):
        """正例：抄到一半，箱子被封上——回执说被打断，账本里有一条 interrupted。"""
        self.assertTrue(self.inflight.interrupted, self.inflight.reason)
        self.assertFalse(self.inflight.ok)
        self.assertIn("复写纸", self.inflight.reason)     # 规则第二次问出来的拒绝
        kinds = [e.kind for e in self.log]
        self.assertIn("interrupted", kinds)

    def test_the_world_stops_at_the_deadline_not_at_the_finish(self):
        self.assertEqual(self.world.clock, 1439)       # 时限那一刻，不是 1440
        cut = [e for e in self.log if e.kind == "interrupted"][0]
        self.assertEqual(cut.at, 1439)
        self.assertEqual(cut.note["started_at"], 1437)
        self.assertEqual(cut.note["would_finish_at"], 1440)

    def test_an_interrupted_intent_leaves_nothing_behind(self):
        """P2：一次意愿要么全成要么全不成。所以没有半个抄件，也没有被吃掉的空白纸。"""
        self.assertEqual(copies(self.world), [])
        self.assertEqual(self.world.container("blank"), "vendor")
        self.assertNotIn("copy_seq", self.world.flags)
        cut = [e for e in self.log if e.kind == "interrupted"][0]
        self.assertEqual({a["op"] for a in cut.atoms}, {"remember"})

    def test_the_cut_is_what_the_actor_and_the_onlookers_perceive_differently(self):
        mine = [text for _at, text in self.world.memory["vendor"]]
        nearby = [text for _at, text in self.world.memory["buyer"]]
        across = [text for _at, text in self.world.memory["warden"]]
        self.assertTrue(any("你的动作停在半路" in t for t in mine), mine)
        self.assertFalse(any("你的动作停在半路" in t for t in nearby))
        self.assertTrue(any("摊主的动作停在半路" in t for t in nearby), nearby)
        self.assertTrue(any("摊主的动作停在半路" in t for t in across), across)
        # 制度本身也是被看见的：封箱发生在截断之前
        self.assertTrue(any("把木箱封上了" in t for t in mine), mine)
        self.assertTrue(any("把木箱封上了" in t for t in nearby))

    def test_the_cut_is_replayable(self):
        """截断同样只是事件里的原子效果：重放逐事件对得上摘要。"""
        again = replay(lambda: build(market_seed(1439)), self.log)
        self.assertEqual(again.digest(), self.world.digest())

    def test_a_refusal_after_the_deadline_is_not_an_interrupt(self):
        """时限过去之后，同一个动作连开始都开始不了：这是没成，不是被打断。"""
        self.assertFalse(self.after.ok)
        self.assertFalse(self.after.interrupted)
        self.assertIn("复写纸", self.after.reason)

    def test_the_action_before_the_deadline_runs_its_full_cost(self):
        """区间之外的动作不受影响：细看一秒不多一秒不少地走完。"""
        self.assertTrue(self.look.ok)
        self.assertFalse(self.look.interrupted)
        self.assertEqual(self.look.event.at, 1436)


class NoInterruptWithoutHandlersTests(unittest.TestCase):
    """对照：只改一件事——动作在飞的时候，世界有没有机会插进来。"""

    def test_without_effect_handlers_the_action_completes(self):
        run = play(submit_effects=None)
        world, log, receipts = run["world"], run["log"], run["receipts"]
        self.assertEqual(copies(world), ["copy_1"])
        self.assertNotIn("interrupted", [e.kind for e in log])
        self.assertTrue(receipts[1].ok)
        # 老行为：时限滑到了动作之后——箱子是在抄完之后才被封上的
        sealed = [e for e in log if e.what == "seal"][0]
        self.assertGreaterEqual(sealed.at, 1440)


class BoundaryTests(unittest.TestCase):
    def test_a_deadline_at_the_finish_minute_does_not_cut(self):
        """边界：到期点正好等于完成时刻，那一刻你已经做完了。"""
        run = play(1440, submit_effects=FIXTURE_EFFECTS)
        self.assertTrue(run["receipts"][1].ok)
        self.assertNotIn("interrupted", [e.kind for e in run["log"]])

    def test_a_deadline_already_passed_fires_before_the_action_starts(self):
        """到期的先发生（不在飞行区间里）：封箱先落，然后那个动作连开始都开始不了。"""
        run = play(1435, submit_effects=FIXTURE_EFFECTS)
        self.assertTrue(run["receipts"][0].ok)
        self.assertNotIn("interrupted", [e.kind for e in run["log"]])
        sealed = [e for e in run["log"] if e.what == "seal"][0]
        self.assertEqual(sealed.at, 1436)

    def test_a_short_action_never_has_a_window(self):
        """耗时 1 的动作与整数时钟之间没有区间：时限不可能落在它中间。"""
        world = build(market_seed(1437))
        log = EventLog()
        receipt = submit(world, log, "vendor", "examine", {}, effects=FIXTURE_EFFECTS)
        self.assertTrue(receipt.ok)
        self.assertFalse(receipt.interrupted)
        self.assertEqual(world.clock, 1437)


class InstitutionDoubleTests(unittest.TestCase):
    def test_the_deadline_effect_is_physics_only(self):
        """替身只许动物性：改状态、让在场的人看见，不替任何人做决定。"""
        world = build(market_seed(1439))
        atoms = seal(world, {"kind": "seal", "place": "chest"})
        self.assertEqual({a["op"] for a in atoms}, {"set", "remember"})
        # 这一条现实里属于 library/institutions.py 的制度表（EFFECTS）；
        # 本包按分工不碰 library/，所以只在夹具里落成替身，需求写在报告里。

    def test_the_fixture_seed_states_all_have_renderers(self):
        self.assertEqual(pairing_report(state_keys(market_seed())), [])


if __name__ == "__main__":
    unittest.main()
