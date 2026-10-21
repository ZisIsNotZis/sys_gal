"""M4 的验收：《夜市》四条路 + 制度角色 + 公开/私下 + 期限。

最要紧的两条：**押金条的每种归属都物理可达**（条子只在包含关系里换手，
没有"谁的东西"这种状态键）；**当众与私下的差是真的**（带 `to` 的那句话只有
一个人听见，旁人只看见两人在低声说话）。最后一条：没有任何结局是排程替角色做的。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

import library  # noqa: F401
from engine.core import ATOM_OPS, apply_atom
from engine.events import EventLog, replay
from engine.rules import submit
from engine.seed import load
from library import EFFECTS
from library.institutions import close
from stories.s3_night_market import scenario
from stories.s3_night_market.scenario import DEFAULT_SEED, NOTE_ID, play, summary

VARIANTS = ("a", "b", "c", "d")
PRIVATE_PHRASE = "这摊是我的，货我认"
PUBLIC_PHRASE = "这摊今晚是乙替我看着的"


def _mem(world, who: str) -> str:
    return " ".join(text for _at, text in world.memory.get(who, []))


class StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {v: play(v) for v in VARIANTS}
        cls.sums = {v: summary(run) for v, run in cls.runs.items()}

    def test_each_path_names_who_holds_the_note_at_the_end(self):
        self.assertEqual({v: s["押金条最后在谁手里"] for v, s in self.sums.items()},
                         {"a": "摊主甲", "b": "摊主丙", "c": "管理处", "d": "摊主甲"})

    def test_every_ownership_of_the_note_is_physically_reachable(self):
        handled: set[str] = set()
        for s in self.sums.values():
            handled.update(s["押金条经过谁的手"])
        self.assertTrue({"摊主甲", "摊主乙", "摊主丙", "管理处"} <= handled, handled)

    def test_four_paths_reach_four_endings(self):
        endings = {v: s["结局"] for v, s in self.sums.items()}
        self.assertEqual(len(set(endings.values())), 4, endings)
        # 结局是四件事的拼法，不是按路径名查的表：两条路若在这四件事上一模一样，
        # 就必须算作同一个结局（否则“四种结局”只是把同一个结局换了个说法）。
        facts = {v: (s["押金条最后在谁手里"], tuple(s["押金条经过谁的手"]),
                     s["决定性那句话"], s["结局落在收摊之前"])
                 for v, s in self.sums.items()}
        self.assertEqual(len(set(endings.values())), len(set(facts.values())),
                         f"结局数（{endings}）与世界事实组合数（{facts}）不一致")

    def test_two_paths_that_end_the_same_way_count_as_one_ending(self):
        """反证：把 `d` 的脚本换成 `a` 的，`d` 就必须按 `a` 的方式结束。

        结局若还认得出路径名（即按变体手写的句子表），这条会红。
        """
        original = scenario.SCRIPTS["d"]
        scenario.SCRIPTS["d"] = scenario.SCRIPTS["a"]
        try:
            aliased = summary(play("d"))
        finally:
            scenario.SCRIPTS["d"] = original
        self.assertEqual(aliased["结局"], summary(play("a"))["结局"],
                         "同一条脚本在两条路上结束得不一样：结局不是从世界算出来的")
        self.assertEqual(aliased["决定性那句话"], "私下", aliased)

    def test_every_turn_is_marked_as_scripted(self):
        for run in self.runs.values():
            turns = [i for i in run.items if i["kind"] == "turn"]
            self.assertTrue(turns)
            self.assertTrue(all(i["decided_by"] == "script" and not i["context_used"]
                                for i in turns))

    def test_whoever_holds_it_is_containment_not_a_state_key(self):
        world = load(DEFAULT_SEED)
        self.assertEqual(world.container(NOTE_ID), "a")
        for key in ("holder", "owner", "belongs_to"):
            self.assertNotIn(key, world.state[NOTE_ID])


class PrivateSpeechTests(unittest.TestCase):
    def test_private_words_reach_exactly_one_listener(self):
        world = play("a").world
        heard = [p for p in world.memory if PRIVATE_PHRASE in _mem(world, p)]
        self.assertEqual(set(heard), {"a", "warden"})
        for outsider in ("b", "c", "neighbour"):
            self.assertNotIn(PRIVATE_PHRASE, _mem(world, outsider), outsider)
            self.assertIn("低声说话", _mem(world, outsider), outsider)

    def test_public_words_reach_everyone_in_sight(self):
        world = play("b").world
        for hearer in ("b", "c", "warden", "neighbour"):
            self.assertIn(PUBLIC_PHRASE, _mem(world, hearer), hearer)

    def test_the_summary_says_which_kind_the_decisive_sentence_was(self):
        self.assertEqual(summary(play("a"))["决定性那句话"], "私下")
        self.assertEqual(summary(play("b"))["决定性那句话"], "当众")


class DeadlineTests(unittest.TestCase):
    def test_the_late_path_hits_a_recorded_consequence(self):
        run = play("c")
        closed = [e for e in run.log if e.kind == "world" and e.what == "close"]
        self.assertEqual(len(closed), 1, "收摊这条制度效果没有落进事件账本")
        refusals = [r for r in run.receipts if not r.ok]
        self.assertTrue(refusals, "晚到的路径没有任何回执被拒")
        self.assertGreater(refusals[0].event.at, closed[0].at)
        self.assertIn("管理处", refusals[0].reason)
        self.assertTrue(any("锁着" in r.reason for r in refusals), [r.reason for r in refusals])

    def test_only_the_late_path_falls_after_closing(self):
        self.assertEqual({v: summary(play(v))["结局落在收摊之前"] for v in VARIANTS},
                         {"a": True, "b": True, "c": False, "d": True})

    def test_the_earlier_paths_close_nothing(self):
        for variant in ("a", "b", "d"):
            run = play(variant)
            self.assertEqual([e for e in run.log if e.what == "close"], [], variant)


class InstitutionTests(unittest.TestCase):
    def test_only_an_institution_role_can_impound(self):
        world = load(DEFAULT_SEED)
        receipt = submit(world, EventLog(), "a", "impound", {"target": "货"})
        self.assertFalse(receipt.ok)
        self.assertIn("身份", receipt.reason)

    def test_impound_moves_the_thing_and_leaves_exactly_one_row(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        before = len(world.get("register", "marks"))
        receipt = submit(world, log, "warden", "impound", {"target": "货"})
        self.assertTrue(receipt.ok, receipt.reason)
        rows = world.get("register", "marks")
        self.assertEqual(len(rows), before + 1)
        self.assertIn("货", rows[-1]["text"])
        self.assertIn("摊区", rows[-1]["text"])
        self.assertEqual(world.container("goods"), "warden")

    def test_impound_needs_a_register_and_a_pen(self):
        world = load(DEFAULT_SEED)
        world.parent["pen"] = "office"
        receipt = submit(world, EventLog(), "warden", "impound", {"target": "货"})
        self.assertFalse(receipt.ok)
        self.assertIn("笔", receipt.reason)

    def test_a_closed_institution_door_is_locked_against_reopening(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        submit(world, log, "a", "move", {"target": "夜市"})
        for atom in close(world, {"kind": "close", "place": "office"}):
            apply_atom(world, atom)
        receipt = submit(world, log, "a", "open", {"target": "管理处"})
        self.assertFalse(receipt.ok)
        self.assertIn("锁着", receipt.reason)


class NoScheduledActorTests(unittest.TestCase):
    """结局不许来自"排程替某个角色做了一个动作"。"""

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
