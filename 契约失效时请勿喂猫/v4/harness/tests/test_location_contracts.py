"""Ticket 58 — a location's public brief vs its interior detail.

A location's identity (what it is called, where it is, roughly what it is for)
is public and belongs in every aware actor's KB and in the world primer. Its
interior detail (how the shelves are arranged, which page is creased) is not
common knowledge: it reaches an actor only through a real source — the ticket-49
arrival description, a note, or a read.

The regression, from the d1-am artifact (real-20261001T065553): 宿管阿姨
(turn 292, 11:25) reasoned "档案室2013年台风台账那页折痕翻得厉害" without ever
leaving the 女生宿舍 值班台, and 食堂大妈 (turn 388, 12:44) told 陈默 "铁皮柜
按年份码着呢" without ever entering the archive. Root cause: `_expand_entity_rows`
auto-expanded every location's full body into each actor's KB, and `world_primer`
used the body's first line.
"""

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from harness.world_loader import load_world_pack, world_primer


ROOT = Path(__file__).parents[2]
# Present ONLY in world/locations/校史档案室.md, so it isolates the location
# leak from the separate (unfixed) unmarked-document leak that also names 铁皮柜.
ARCHIVE_INTERIOR = "扫描仪的待机灯常绿"
ARCHIVE_BRIEF = "老楼一层的档案库，白天开放，学生值班，查阅要登记。"
NEVER_VISITED = ("宿管阿姨", "食堂大妈")


def _lint_module():
    spec = importlib.util.spec_from_file_location(
        "seed_lint_location58", ROOT / "scripts" / "seed_lint.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocationBriefVsInteriorTests(unittest.TestCase):
    def test_unvisited_actors_are_not_told_the_archive_interior(self):
        # Ticket 58 (a): an actor who never visited the archive must not carry
        # its interior detail — in their KB or in the world primer.
        pack = load_world_pack(ROOT / "world")
        self.assertNotIn(ARCHIVE_INTERIOR, world_primer(pack))
        for actor in NEVER_VISITED:
            delivered = "\n".join(str(row["desc"]) for row in pack.kb[actor])
            self.assertNotIn(ARCHIVE_INTERIOR, delivered,
                             f"{actor} never visited the archive")
            # The public identity is still delivered.
            self.assertIn(ARCHIVE_BRIEF, delivered)

    def test_location_identity_is_available_to_every_actor(self):
        # Ticket 58 (c): the brief (name/purpose) stays public.
        pack = load_world_pack(ROOT / "world")
        self.assertIn("校史档案室：", world_primer(pack))
        remote = {str(row["id"]) for row in pack.actors if row.get("remote")}
        for actor, rows in pack.kb.items():
            if actor in remote:
                continue
            self.assertTrue(any("校史档案室" in row["keys"] for row in rows),
                            f"{actor} must still know the archive exists")

    def test_arriving_at_the_archive_delivers_its_interior(self):
        # Ticket 58 (b): the interior arrives with the ticket-49 arrival
        # description and is written into `observed` — a real source.
        pack = load_world_pack(ROOT / "world")
        world = pack.build_world()
        actor = world.actors["宿管阿姨"]
        before = world.poll("宿管阿姨")
        self.assertNotIn(ARCHIVE_INTERIOR, str(before.get("descriptions", {})))
        actor.location = "校史档案室"
        after = world.poll("宿管阿姨")
        self.assertIn(ARCHIVE_INTERIOR, after["descriptions"]["校史档案室"])
        self.assertIn(ARCHIVE_INTERIOR, actor.observed["校史档案室"]["objective"])

    def test_brief_is_only_the_first_paragraph_of_a_location_body(self):
        from harness.world_loader import _location_brief
        markdown = "# 某地\n\n这是可公开的身份。\n\n这是只有到过才知道的内部细节。\n"
        self.assertEqual(_location_brief(markdown), "这是可公开的身份。")

    def test_expanded_location_rows_carry_the_brief_not_the_interior(self):
        pack = load_world_pack(ROOT / "world")
        rows = [row for row in pack.kb["宿管阿姨"]
                if "校史档案室" in row["keys"]]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["desc"], ARCHIVE_BRIEF)


class LocationBriefLintTests(unittest.TestCase):
    def _write_world(self, root, location_body):
        root = Path(root)
        (root / "locations").mkdir(parents=True)
        (root / "items").mkdir()
        (root / "documents").mkdir()
        (root / "locations" / "room.md").write_text(
            f"# room\n\n{location_body}", encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "clock": {"start": "2026-03-16T07:00:00+08:00",
                      "stop": "2026-03-16T08:00:00+08:00"},
            "locations": [{"id": "room"}],
            "actors": [{"id": "aa", "location": "room"}],
            "items": [], "documents": [], "routes": [], "barriers": [],
            "scheduled": [],
            "kb": {"aa": [{"keys": ["aa"], "desc": "我，aa。"}]},
        }
        (root / "manifest.yml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
        return root

    def test_one_paragraph_location_fails_seed_lint_and_splitting_turns_green(self):
        # Ticket 58 lint: a body that mixes identity and interior in a single
        # paragraph must go red with remediation text; splitting turns it green.
        module = _lint_module()
        with TemporaryDirectory() as directory:
            mixed = self._write_world(Path(directory) / "mixed",
                                      "一间屋子，柜子按年份码着。\n")
            findings = module.lint(mixed)
            self.assertTrue(any("locations/room.md" in f for f in findings), findings)
            self.assertTrue(any("内部细节" in f for f in findings), findings)
            split = self._write_world(Path(directory) / "split",
                                      "一间屋子。\n\n柜子按年份码着。\n")
            self.assertEqual(module.lint(split), [])


if __name__ == "__main__":
    unittest.main()
