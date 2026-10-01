"""Ticket 61 — a document/item description is not world-public by default.

Ticket 58 separated a location's public brief from its interior detail but
deliberately left one leak: a placed item/document with no ``known_to`` had its
FULL description auto-expanded into every actor's KB. The d1-am artifact
(real-20261001T065553) shows the consequence — 宿管阿姨 (turn 292, 11:25)
reasoned "档案室2013年台风台账那页折痕翻得厉害" without ever leaving the
女生宿舍 值班台, and the 折痕 clause came verbatim from
``world/documents/2013年台风台账.md``.

A document/item is now public only when the seed says so (``known_to``): an
unmarked placed object expands to nobody, and whoever needs it receives its
objective description through the ticket-49 arrival/`[所见]` path.
"""

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from harness.world_loader import load_world_pack


ROOT = Path(__file__).parents[2]
# Present ONLY in world/documents/2013年台风台账.md, the real 折痕 clause.
LEDGER_STATE = "2013 年那一页有反复翻动的折痕"
LEDGER = "2013年台风台账"
ARCHIVE = "校史档案室"
NEVER_VISITED = ("宿管阿姨", "食堂大妈", "辅导员", "班长")


def _lint_module():
    spec = importlib.util.spec_from_file_location(
        "seed_lint_document61", ROOT / "scripts" / "seed_lint.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DocumentDescriptionContractTests(unittest.TestCase):
    def test_unvisited_actors_are_not_told_the_ledgers_state(self):
        # Ticket 61 (a): an actor who never reached the archive and is not in
        # the ledger's known_to must not carry its description — in the KB or
        # in the world primer. Before the fix every actor's KB held this line.
        pack = load_world_pack(ROOT / "world")
        from harness.world_loader import world_primer
        self.assertNotIn(LEDGER_STATE, world_primer(pack))
        for actor in NEVER_VISITED:
            delivered = "\n".join(str(row["desc"]) for row in pack.kb[actor])
            self.assertNotIn(LEDGER_STATE, delivered,
                             f"{actor} never reached the archive")

    def test_arriving_at_the_archive_delivers_the_ledgers_state(self):
        # Ticket 61 (b): the description arrives through the ticket-49 arrival
        # description and is written into `observed` — a real source.
        pack = load_world_pack(ROOT / "world")
        world = pack.build_world()
        actor = world.actors["宿管阿姨"]
        before = world.poll("宿管阿姨")
        self.assertNotIn(LEDGER, before.get("descriptions", {}))
        actor.location = ARCHIVE
        after = world.poll("宿管阿姨")
        self.assertIn(LEDGER_STATE, after["descriptions"][LEDGER])
        self.assertIn(LEDGER_STATE, actor.observed[LEDGER]["objective"])

    def test_known_to_actors_still_receive_their_document_rows(self):
        # Ticket 61 (c): a document that DOES declare its readers keeps
        # expanding to them, and only them (移交存根: known_to [陈默, 林瑶]).
        pack = load_world_pack(ROOT / "world")
        keys = {actor: {key for row in rows for key in row["keys"]}
                for actor, rows in pack.kb.items()}
        self.assertIn("移交存根", keys["陈默"])
        self.assertIn("移交存根", keys["林瑶"])
        self.assertNotIn("移交存根", keys["宿管阿姨"])
        self.assertNotIn("移交存根", keys["食堂大妈"])

    def test_existing_item_known_to_behaviour_is_unchanged(self):
        # Ticket 61 (d): items already carry known_to, so their expansion is
        # untouched — the holder/reader gets the row, an unrelated actor does
        # not (红色哨子 [陈默], 裂纹马克杯 [唐小岚]).
        pack = load_world_pack(ROOT / "world")
        keys = {actor: {key for row in rows for key in row["keys"]}
                for actor, rows in pack.kb.items()}
        self.assertIn("红色哨子", keys["陈默"])
        self.assertNotIn("红色哨子", keys["林瑶"])
        self.assertIn("裂纹马克杯", keys["唐小岚"])
        self.assertNotIn("裂纹马克杯", keys["陈默"])

    def test_held_unmarked_document_reaches_its_holder_by_observation(self):
        # The plot need that drove the seed check: 陈默 holds the unmarked
        # 2013年邻里撤离通知书. He still gets its description — via the
        # ticket-49 observation of what he holds, never as a default row that
        # everyone else also receives.
        pack = load_world_pack(ROOT / "world")
        world = pack.build_world()
        notice = "2013年邻里撤离通知书"
        self.assertIn(notice, world.actors["陈默"].inventory)
        packet = world.poll("陈默")
        self.assertIn(notice, packet["descriptions"])
        self.assertIn(notice, world.actors["陈默"].observed)
        for actor in ("宿管阿姨", "食堂大妈"):
            rows = "\n".join(str(row["desc"]) for row in pack.kb[actor])
            self.assertNotIn("许可证表格", rows, f"{actor} never saw the notice")


class DocumentStateLintTests(unittest.TestCase):
    """Ticket 61 lint (non-blocking): flag a placed document that asserts a
    concrete physical state while naming no `known_to`, so a human confirms
    whether that state should really be common knowledge."""

    def _write_world(self, root, documents, body):
        root = Path(root)
        (root / "locations").mkdir(parents=True)
        (root / "items").mkdir()
        (root / "documents").mkdir()
        # Two paragraphs so the ticket-58 location lint stays green.
        (root / "locations" / "room.md").write_text(
            "# room\n\n一间屋子。\n\n柜子按年份码着。\n", encoding="utf-8")
        for document in documents:
            (root / "documents" / f"{document['id']}.md").write_text(
                f"# {document['id']}\n\n{body}\n", encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "clock": {"start": "2026-03-16T07:00:00+08:00",
                      "stop": "2026-03-16T08:00:00+08:00"},
            "locations": [{"id": "room"}],
            "actors": [{"id": "aa", "location": "room"}],
            "items": [], "documents": documents, "routes": [], "barriers": [],
            "scheduled": [],
            "kb": {"aa": [{"keys": ["aa"], "desc": "我，aa。"}]},
        }
        (root / "manifest.yml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
        return root

    def test_unmarked_placed_document_with_a_state_clause_warns(self):
        module = _lint_module()
        with TemporaryDirectory() as directory:
            root = self._write_world(
                Path(directory) / "unmarked",
                [{"id": "ledger", "title": "ledger", "location": "room"}],
                "一本台账，2013 年那一页有反复翻动的折痕。")
            warnings = module.document_state_warnings(root)
            self.assertTrue(any("ledger" in w and "折痕" in w for w in warnings),
                            warnings)
            # Non-blocking: the lint itself still passes.
            self.assertEqual(module.lint(root), [])

    def test_declared_known_to_silences_the_warning(self):
        module = _lint_module()
        with TemporaryDirectory() as directory:
            root = self._write_world(
                Path(directory) / "declared",
                [{"id": "ledger", "title": "ledger", "location": "room",
                  "known_to": ["aa"]}],
                "一本台账，2013 年那一页有反复翻动的折痕。")
            self.assertEqual(module.document_state_warnings(root), [])

    def test_unplaced_and_state_free_documents_do_not_warn(self):
        module = _lint_module()
        with TemporaryDirectory() as directory:
            # No location and not held: not yet in the world.
            unplaced = self._write_world(
                Path(directory) / "unplaced",
                [{"id": "ledger", "title": "ledger"}],
                "一本台账，2013 年那一页有反复翻动的折痕。")
            self.assertEqual(module.document_state_warnings(unplaced), [])
            clean = self._write_world(
                Path(directory) / "clean",
                [{"id": "ledger", "title": "ledger", "location": "room"}],
                "一本按年份登记的台账，页数是整的。")
            self.assertEqual(module.document_state_warnings(clean), [])


if __name__ == "__main__":
    unittest.main()
