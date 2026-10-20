"""M1 原始项：实体、状态、包含、时间、渲染成对、命名解析。"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401  登记渲染与规则
from engine.core import World, apply_atom
from engine.render import STATE_RENDERERS, describe, pairing_report
from engine.resolve import in_sight, resolve
from engine.seed import build, entity_names, load, state_keys
from engine.rules import submit
from engine.events import EventLog
from stories.s1_last_bus.scenario import DEFAULT_SEED


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.world = load(DEFAULT_SEED)

    def test_containment_tree(self):
        w = self.world
        self.assertEqual(w.place_of("jia"), "car")
        self.assertEqual(w.place_of("driver"), "cab")
        self.assertEqual(w.place_of("bag"), "car")
        self.assertEqual(w.place_of("pillbox"), "car")       # 透过包看它的位置
        self.assertEqual(w.container("pillbox"), "bag")

    def test_clock_and_schedule_from_seed(self):
        self.assertEqual(self.world.clock, 1350)
        self.assertEqual(len(self.world.schedule), 4)

    def test_cycle_is_rejected(self):
        seed = {
            "start_clock": 0,
            "places": [
                {"id": "a", "name": "甲地", "parent": "b"},
                {"id": "b", "name": "乙地", "parent": "a"},
            ],
        }
        with self.assertRaises(ValueError):
            build(seed)

    def test_every_state_key_has_a_renderer(self):
        import yaml
        seed = yaml.safe_load(DEFAULT_SEED.read_text(encoding="utf-8"))
        problems = pairing_report(state_keys(seed))
        self.assertEqual(problems, [], problems)

    def test_renderers_are_registered_not_hardcoded(self):
        self.assertIn("inscription", STATE_RENDERERS)
        self.assertEqual(STATE_RENDERERS["portable"], (None, None))   # 物性，不可见


class PrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.world = load(DEFAULT_SEED)

    def test_closed_container_hides_its_contents(self):
        self.assertFalse(in_sight(self.world, "jia", "pillbox"))
        self.assertTrue(in_sight(self.world, "jia", "bag"))   # 包本身看得见，里面的看不见
        log = EventLog()
        submit(self.world, log, "yi", "open", {"target": "包"})
        self.assertTrue(in_sight(self.world, "jia", "pillbox"))

    def test_unknown_atom_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_atom(self.world, {"op": "teleport", "e": "jia"})

    def test_describe_is_physics_only(self):
        glimpse = describe(self.world, "notice")
        text = describe(self.world, "notice", detail=True)
        self.assertIn("上面有字", glimpse)
        self.assertNotIn("末班车", glimpse)
        self.assertIn("印上去的", text)
        self.assertNotIn("末班车", text)   # 内容只能由"读"得到
        for word in ("作者", "写于", "谁写的", "读者"):
            self.assertNotIn(word, text)

    def test_engine_does_not_know_story_names(self):
        """引擎不许认识故事名词。单字中文名（甲、乙、包）会与常用字撞车，只查两字以上与 id。"""
        import re
        import yaml
        seed = yaml.safe_load(DEFAULT_SEED.read_text(encoding="utf-8"))
        names = {n for n in entity_names(seed) if len(n) >= 2}
        engine_dir = Path(__file__).resolve().parents[1] / "engine"
        for path in engine_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for name in sorted(names):
                if re.fullmatch(r"[a-z_]+", name):
                    hit = re.search(rf"\b{name}\b", source)
                else:
                    hit = name in source
                self.assertFalse(
                    hit,
                    f"引擎源码 {path.name} 出现了故事名词 {name}：引擎不该认识任何故事",
                )


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.world = load(DEFAULT_SEED)

    def test_unknown_name_lists_what_is_here(self):
        res = resolve(self.world, "jia", "宿舍")
        self.assertFalse(res)
        self.assertIn("宿舍", res.reason)
        self.assertTrue(any("眼前能看见" in h for h in res.hints), res.hints)

    def test_known_but_unseen_says_so(self):
        res = resolve(self.world, "jia", "司机")     # 驾驶室门关着
        self.assertFalse(res)
        self.assertIn("看不见", res.reason)
        self.assertTrue(any("不在眼前" in h for h in res.hints), res.hints)


class NoTraceTests(unittest.TestCase):
    """最基础的一条：读与碰都不改变被碰/被读的东西。"""

    def test_read_and_touch_change_nothing(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        before_state = copy.deepcopy(world.state)
        before_parent = copy.deepcopy(world.parent)
        submit(world, log, "jia", "read", {"target": "通知"})
        submit(world, log, "jia", "touch", {"target": "通知"})
        self.assertEqual(world.state, before_state)
        self.assertEqual(world.parent, before_parent)
        for event in log:
            for atom in event.atoms:
                self.assertNotIn(atom["op"], {"set", "unset", "move", "create", "destroy"})


if __name__ == "__main__":
    unittest.main()
