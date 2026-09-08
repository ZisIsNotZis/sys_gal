import unittest
from pathlib import Path
from collections.abc import Mapping

from datetime import datetime
from harness.kernel import ActionRejected, ActorState, Intention, LocationState, World
from harness.world_loader import load_world_pack
from harness.seed import create_world
from harness.readiness import validate_story_pack


ROOT = Path(__file__).parents[2]


class WorldPackTests(unittest.TestCase):
    def test_world_primer_describes_places_routes_and_time_rules(self):
        from harness.world_loader import world_primer
        pack = load_world_pack(ROOT / "world")
        text = world_primer(pack)
        self.assertIn("宿舍", text)
        self.assertIn("半坡咖啡馆", text)
        self.assertIn("步行约", text)
        self.assertIn("5 分钟", text)
        self.assertIn("whisper", text)
        self.assertIn("observe", text)

    def test_readiness_rejects_orphan_markdown(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "characters").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "locations" / "unlisted.md").write_text("orphan", encoding="utf-8")
            (root / "characters" / "a.md").write_text("A", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock: {start: '2026-01-01T00:00:00+00:00', stop: '2026-01-01T01:00:00+00:00'}\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\nitems: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "orphan unlisted"):
                validate_story_pack(root)

    def test_readiness_rejects_case_insensitive_duplicate_markdown(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "characters").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "locations" / "ROOM.md").write_text("duplicate", encoding="utf-8")
            (root / "characters" / "a.md").write_text("A", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock: {start: '2026-01-01T00:00:00+00:00', stop: '2026-01-01T01:00:00+00:00'}\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\nitems: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate Markdown id"):
                validate_story_pack(root)

    def test_readiness_accepts_story_catalog(self):
        validate_story_pack(ROOT / "world")

    def test_pack_loads_machine_data_and_markdown_descriptions(self):
        pack = load_world_pack(ROOT / "world")
        # v4 首验日 slice（V4-DESIGN §6）：一日、三角色、五个地点。
        self.assertGreaterEqual(len(pack.locations), 5)
        self.assertGreaterEqual(len(pack.items), 3)
        self.assertGreaterEqual(len(pack.documents), 5)
        self.assertIn("2013年台风台账", pack.descriptions["documents"])
        self.assertIsInstance(pack.descriptions["documents"], Mapping)

    def test_pack_references_are_valid_and_build_world_without_hardcoded_seed(self):
        pack = load_world_pack(ROOT / "world")
        world = pack.build_world()
        self.assertEqual(world.now.isoformat(), "2026-03-16T07:00:00+08:00")
        self.assertIn("2013年台风台账", world.document_defs)
        self.assertEqual(world.document_defs["2013年台风台账"]["title"], "2013年台风台账")
        self.assertEqual(world.actors["陈默"].inventory,
                         {"2013年邻居许可证", "空白纸"})
        self.assertEqual(pack.manifest["clock"]["stop"], "2026-03-16T22:00:00+08:00")
        # 内容层全中文，协议层 id 保持 ASCII（V4-DESIGN §0）。
        self.assertTrue(any("\u4e2d" in text or text for text in
                            [world.document_defs["2013年台风台账"]["content"]]))

    def test_seeded_schedule_effects_produce_reachable_causal_exits(self):
        from datetime import datetime
        pack = load_world_pack(ROOT / "world")
        world = pack.build_world()
        # 首验日的 seeded 事件在当日必须可达（食堂早高峰）。
        events = world.advance(until=datetime.fromisoformat("2026-03-16T08:00:00+08:00"))
        self.assertTrue(any(e.kind == "world_event" and
                            e.payload.get("event") == "breakfast_rush" for e in events))

    def test_direct_meeting_routes_make_colocation_reachable(self):
        pack = load_world_pack(ROOT / "world")
        world = pack.build_world()
        # ticket 10 新路网：三个 MC 的起点都必须能走到半坡咖啡馆（会面点）。
        mc_starts = {a.location for a in world.actors.values() if a.role == "mc"}
        graph: dict[str, set] = {loc: set() for loc in world.locations}
        for (src, dst) in world.routes:
            graph.setdefault(src, set()).add(dst)
            graph.setdefault(dst, set()).add(src)
        for start in mc_starts:
            seen, stack = {start}, [start]
            while stack:
                node = stack.pop()
                for nxt in graph.get(node, ()) - seen:
                    seen.add(nxt)
                    stack.append(nxt)
            self.assertIn("半坡咖啡馆", seen,
                          f"{start} 必须能走到会面点半坡咖啡馆")

    def test_world_pack_does_not_allow_accidental_shared_location_locking(self):
        pack = load_world_pack(ROOT / "world")
        world = pack.build_world()
        for location in world.locations.values():
            self.assertFalse(location.controllable)
        self.assertNotIn({"kind": "close"}, world.affordances("陈默"))

    def test_default_seed_is_the_loaded_pack(self):
        world = create_world()
        self.assertIn("2013年台风台账", world.document_defs)
        self.assertEqual(set(world.actors),
                         {"陈默", "林瑶", "唐小岚", "宿管阿姨", "食堂大妈",
                          "辅导员", "班长", "陈默妈", "林瑶室友", "下棋大爷"})
        # V4-CAST §1: exactly the three protagonists drive the clock.
        self.assertEqual({a for a, x in world.actors.items() if x.role == "mc"},
                         {"陈默", "林瑶", "唐小岚"})

    def test_world_pack_contains_character_seeds_for_every_actor(self):
        from harness.character_loader import load_story_characters
        pack = load_world_pack(ROOT / "world")
        characters = load_story_characters(ROOT / "world")
        self.assertEqual(set(characters), {row["id"] for row in pack.actors})

    def test_loader_rejects_unknown_route_endpoint(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n"
                "locations:\n  - id: room\nactors:\n  - id: a\n    location: room\n"
                "routes:\n  - from: room\n    to: nowhere\n    duration_seconds: 1\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                load_world_pack(root)

    def test_loader_rejects_schedule_before_clock_start(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\n"
                "scheduled: [{event: too_early, time: '2025-12-31T23:59:00+00:00'}]\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                load_world_pack(root)

    def test_loader_rejects_unknown_schedule_target_and_invalid_stop(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n"
                "  stop: '2025-01-01T00:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\n"
                "scheduled: [{event: x, target: nobody, time: '2026-01-01T00:00:00+00:00'}]\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                load_world_pack(root)

    def test_loader_rejects_schedule_after_clock_stop(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n"
                "  stop: '2026-01-01T01:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\n"
                "scheduled: [{event: x, time: '2026-01-01T02:00:00+00:00'}]\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                load_world_pack(root)

    def test_loader_rejects_unknown_scheduled_effect_reference(self):
        from tempfile import TemporaryDirectory
        base = (
            "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n"
            "  stop: '2026-01-01T01:00:00+00:00'\n"
            "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
            "items: []\ndocuments: []\nroutes: []\nbarriers: []\n"
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.yml").write_text(
                base + "scheduled: [{event: x, time: '2026-01-01T00:01:00+00:00', "
                        "effects: [{op: open_location, id: nowhere}]}]\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "open_location"):
                load_world_pack(root)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.yml").write_text(
                base + "scheduled: [{event: x, time: '2026-01-01T00:01:00+00:00', "
                        "effects: [{op: add_item, id: ghost, location: room}]}]\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "add_item"):
                load_world_pack(root)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.yml").write_text(
                base + "scheduled: [{event: x, time: '2026-01-01T00:01:00+00:00', "
                        "effects: [{op: explode}]}]\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "explode"):
                load_world_pack(root)

    def test_loader_rejects_missing_description_for_manifest_entity(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "items").mkdir()
            (root / "documents").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n"
                "  stop: '2026-01-01T01:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
                "items: [{id: coin, location: room}]\ndocuments: []\nroutes: []\n"
                "barriers: []\nscheduled: []\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "items missing"):
                load_world_pack(root)

    def test_loaded_pack_has_descriptions_for_every_static_entity(self):
        pack = load_world_pack(ROOT / "world")
        for category, rows in (("locations", pack.locations), ("items", pack.items),
                               ("documents", pack.documents)):
            self.assertEqual({str(row["id"]) for row in rows}, set(pack.descriptions[category]))

    def test_loaded_pack_known_contacts_are_actor_scoped(self):
        pack = load_world_pack(ROOT / "world")
        chen = next(row for row in pack.actors if row["id"] == "陈默")
        # v4 slice: 陈默的熟人圈是角色作用域的（V4-DESIGN §4）。
        self.assertEqual(set(chen["known_contacts"]),
                         {"林瑶", "唐小岚", "陈默妈", "班长"})


class DocumentInteractionTests(unittest.TestCase):
    def world(self):
        return World(
            start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            actors=[ActorState("a", "room", {"空白纸"}), ActorState("b", "room")],
            locations=[LocationState("room")],
            item_locations={"ledger": "room"},
            document_defs={"ledger": {"title": "Ledger", "content": "same text", "reading_seconds": 2}},
            copy_material_items={"空白纸"},
        )

    def test_read_is_private_and_returns_content_only_to_reader(self):
        world = self.world()
        world.submit(Intention("a", "read", {"document": "ledger"}, world.version))
        world.advance()
        a = world.poll("a")
        b = world.poll("b")
        event = next(e for e in a["events"] if e["kind"] == "document_read")
        self.assertEqual(event["payload"]["content"], "same text")
        self.assertFalse(any(e["kind"] == "document_read" for e in b["events"]))

    def test_copy_creates_a_provenance_link_and_consumes_material(self):
        world = self.world()
        world.submit(Intention("a", "copy", {"document": "ledger"}, world.version))
        world.advance()
        copied = next(e for e in world.poll("a")["events"] if e["kind"] == "document_copied")
        new_id = copied["payload"]["copy"]
        self.assertNotIn("空白纸", world.actors["a"].inventory)
        self.assertEqual(world.document_defs[new_id]["copied_from"], "ledger")
        self.assertEqual(world.item_locations[new_id], "room")
        copied_event = next(e for e in world.event_log if e.kind == "document_copied")
        self.assertEqual(copied_event.payload["copy"], new_id)

    def test_copy_replay_reconstructs_inventory_and_provenance(self):
        from harness.replay import replay_world
        initial = self.world()
        world = self.world()
        world.submit(Intention("a", "copy", {"document": "ledger"}, world.version))
        world.advance()
        replayed = replay_world(initial, world.replayable_log())
        self.assertEqual(replayed.actors["a"].inventory, world.actors["a"].inventory)
        copied = next(e for e in world.event_log if e.kind == "document_copied")
        copy_id = copied.payload["copy"]
        self.assertEqual(replayed.document_defs[copy_id]["copied_from"], "ledger")

    def test_compare_and_label_never_allow_unavailable_document(self):
        world = self.world()
        world.item_locations["other"] = "elsewhere"
        world.locations["elsewhere"] = LocationState("elsewhere")
        world.document_defs["other"] = {"title": "Other", "content": "different"}
        with self.assertRaises(ActionRejected):
            world.submit(Intention("a", "compare", {"first": "ledger", "second": "other"}, world.version))
        with self.assertRaises(ActionRejected):
            world.submit(Intention("a", "label", {"document": "other", "label": "fake"}, world.version))
        with self.assertRaises(ActionRejected):
            world.submit(Intention("a", "annotate", {"document": "other", "text": "x"}, world.version))

    def test_annotate_is_objective_and_visible_to_other_readers(self):
        world = self.world()
        world.submit(Intention("a", "annotate", {"document": "ledger", "text": "timestamp conflicts with export"},
                               world.version))
        world.advance()
        # The annotation lands on the record itself (objective state).
        self.assertEqual(world.document_defs["ledger"]["annotations"][0]["text"],
                         "timestamp conflicts with export")
        self.assertEqual(world.document_defs["ledger"]["annotations"][0]["by"], "a")
        # v4: the annotation is ON the physical record - co-located actors
        # perceive the fact (V4-DESIGN §3); the reader still needs to read
        # to see the text.
        a = world.poll("a")
        b = world.poll("b")
        self.assertTrue(any(e["kind"] == "document_annotated" for e in a["events"]))
        self.assertTrue(any(e["kind"] == "document_annotated" for e in b["events"]))
        # A different reader sees the annotation on the record.
        world.submit(Intention("b", "read", {"document": "ledger"}, world.version))
        world.advance()
        read = next(e for e in world.poll("b")["events"] if e["kind"] == "document_read")
        self.assertEqual(read["payload"]["annotations"][0]["text"], "timestamp conflicts with export")

    def test_annotate_replay_reconstructs_annotation(self):
        from harness.replay import replay_world
        initial = self.world()
        world = self.world()
        world.submit(Intention("a", "annotate", {"document": "ledger", "text": "noted"}, world.version))
        world.advance()
        replayed = replay_world(initial, world.replayable_log())
        self.assertEqual(replayed.document_defs["ledger"]["annotations"][0]["text"], "noted")
        self.assertEqual(replayed.document_defs["ledger"]["annotations"][0]["by"], "a")

    def test_annotate_rejects_empty_text(self):
        world = self.world()
        with self.assertRaises(ActionRejected):
            world.submit(Intention("a", "annotate", {"document": "ledger", "text": "  "},
                                   world.version))
        with self.assertRaises(ActionRejected):
            world.submit(Intention("a", "annotate", {"document": "ledger", "text": "x"},
                                   world.version + 1))

    def test_hidden_description_is_not_resolvable_until_actor_can_physically_access_entity(self):
        world = self.world()
        world.entity_descriptions["secret"] = "a hidden description"
        world.entity_access["secret"] = {"b"}
        self.assertIsNone(world.resolve_entity("a", "secret"))
        self.assertEqual(world.resolve_entity("b", "secret"), "a hidden description")

    def test_poll_injects_only_actor_visible_descriptions(self):
        world = self.world()
        world.entity_descriptions.update({"ledger": "readable", "secret": "hidden"})
        world.entity_access["secret"] = {"b"}
        packet = world.poll("a")
        self.assertEqual(packet["descriptions"], {"ledger": "readable"})


if __name__ == "__main__":
    unittest.main()
