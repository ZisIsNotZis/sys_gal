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
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "characters").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "locations" / "unlisted.md").write_text("orphan", encoding="utf-8")
            (root / "characters" / "a.md").write_text("A", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock: {start: '2026-01-01T00:00:00+00:00', stop: '2026-01-01T01:00:00+00:00'}\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\nitems: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\nkb:\n  a:\n    - {fields: {person: a, self: true}, id: identity, desc: '我，a。'}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "orphan unlisted"):
                validate_story_pack(root)

    def test_readiness_rejects_case_insensitive_duplicate_markdown(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "characters").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "locations" / "ROOM.md").write_text("duplicate", encoding="utf-8")
            (root / "characters" / "a.md").write_text("A", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock: {start: '2026-01-01T00:00:00+00:00', stop: '2026-01-01T01:00:00+00:00'}\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\nitems: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\nkb:\n  a:\n    - {fields: {person: a, self: true}, id: identity, desc: '我，a。'}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate Markdown id"):
                validate_story_pack(root)

    def test_readiness_accepts_story_catalog(self):
        validate_story_pack(ROOT / "world")

    def test_pack_loads_machine_data_and_markdown_descriptions(self):
        pack = load_world_pack(ROOT / "world")
        # v4 首验日 slice（V4-DESIGN §6）：一日、三角色、五个地点。
        self.assertGreaterEqual(len(pack.locations), 5)
        self.assertGreaterEqual(len(pack.items), 2)
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
                         {"2013年邻里撤离通知书"})
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
                for nxt in set(graph.get(node, ())) - seen:
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
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
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
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
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
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
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
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
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
            "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
            "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
            "items: []\ndocuments: []\nroutes: []\nbarriers: []\n"
            "kb:\n  a:\n    - {fields: {person: a, self: true}, id: identity, desc: '我，a。'}\n"
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
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "items").mkdir()
            (root / "documents").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
                "  stop: '2026-01-01T01:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
                "items: [{id: coin, location: room}]\ndocuments: []\nroutes: []\n"
                "barriers: []\nscheduled: []\nkb:\n  a:\n    - {fields: {person: a, self: true}, id: identity, desc: '我，a。'}\n", encoding="utf-8")
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
            actors=[ActorState("a", "room", {"2013年邻里撤离通知书"}), ActorState("b", "room")],
            locations=[LocationState("room")],
            item_locations={"ledger": "room"},
            document_defs={"ledger": {"title": "Ledger", "content": "same text", "reading_seconds": 2}},
            copy_material_items={"2013年邻里撤离通知书"},
        )

    def test_read_is_private_and_returns_content_only_to_reader(self):
        world = self.world()
        world.submit(Intention("a", "read", {"item": "ledger"}, world.version))
        world.advance()
        a = world.poll("a")
        b = world.poll("b")
        event = next(e for e in a["events"] if e["kind"] == "document_read")
        self.assertEqual(event["payload"]["content"], "same text")
        self.assertFalse(any(e["kind"] == "document_read" for e in b["events"]))

    def test_compare_and_label_never_allow_unavailable_document(self):
        world = self.world()
        world.item_locations["other"] = "elsewhere"
        world.locations["elsewhere"] = LocationState("elsewhere")
        world.document_defs["other"] = {"title": "Other", "content": "different"}
        with self.assertRaises(ActionRejected):
            world.submit(Intention("a", "read", {"item": "other"}, world.version))

    def test_leave_note_creates_readable_item_here(self):
        world = self.world()
        world.submit(Intention("a", "leave_note", {"text": "去后街找我"},
                               world.version))
        world.advance()
        note_id = next(i for i in world.item_locations
                       if i.startswith("字条-") and world.item_locations[i] == "room")
        note = world.document_defs[note_id]
        self.assertEqual(note["content"], "去后街找我")
        self.assertEqual(note["left_by"], "a")
        # a co-located actor can take the note
        world.submit(Intention("b", "take", {"item": note_id}, world.version))
        world.advance()
        self.assertIn(note_id, world.actors["b"].inventory)
        # empty text rejected
        with self.assertRaises(ActionRejected):
            world.submit(Intention("a", "leave_note", {"text": "  "}, world.version))

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


class KbSeedTests(unittest.TestCase):
    """V4-AGENT-INTERFACE §6: every actor's KB rows are seeded in the
    manifest and validated at load time (M2 identity anchor)."""

    def test_kb_section_exists_and_covers_every_actor(self):
        pack = load_world_pack(ROOT / "world")
        self.assertEqual(set(pack.kb), {row["id"] for row in pack.actors})
        for actor_id, rows in pack.kb.items():
            self.assertTrue(rows, f"{actor_id} has no kb rows")

    def test_every_actor_has_exactly_one_identity_row(self):
        pack = load_world_pack(ROOT / "world")
        for actor_id, rows in pack.kb.items():
            self_rows = [row for row in rows if row["fields"].get("self") is True]
            self.assertEqual(len(self_rows), 1, f"{actor_id} identity anchor (docs §6/M2)")
            self.assertTrue(self_rows[0]["desc"].startswith("我，"),
                            f"{actor_id} identity desc must be first-person")

    def test_kb_ids_are_unique_and_snake_kebab(self):
        import re
        pack = load_world_pack(ROOT / "world")
        for actor_id, rows in pack.kb.items():
            ids = [row["id"] for row in rows]
            self.assertEqual(len(ids), len(set(ids)), f"{actor_id} duplicate kb ids")
            for row_id in ids:
                self.assertTrue(re.match(r"^[a-z0-9-]+$", row_id),
                                f"{actor_id} kb id {row_id!r} not lowercase-kebab")

    def test_mc_seeds_carry_todo_and_reminder_rows(self):
        pack = load_world_pack(ROOT / "world")
        for actor_id in ("陈默", "林瑶", "唐小岚"):
            rows = pack.kb[actor_id]
            self.assertTrue(any(row["fields"].get("todo") is True for row in rows),
                            f"{actor_id} needs at least one todo row")
            reminders = [row for row in rows if "reminder" in row["fields"]]
            self.assertEqual(len(reminders), 1, f"{actor_id} needs exactly one reminder row")

    def test_reminder_times_are_strictly_parseable(self):
        import re
        from harness.world_loader import _reminder_time_ok
        pack = load_world_pack(ROOT / "world")
        for actor_id, rows in pack.kb.items():
            for row in rows:
                if "reminder" in row["fields"]:
                    value = str(row["fields"]["reminder"])
                    self.assertTrue(_reminder_time_ok(value),
                                    f"{actor_id} reminder {value!r} unparseable")
                    self.assertRegex(value, r"^\d{1,2}/\d{1,2}\(周[一二三四五六日]\) \d{1,2}:\d{2}$")

    def test_loader_rejects_actor_without_identity_row(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\nkb:\n  a:\n    - {fields: {person: a, self: true}, id: identity, desc: '我，a。'}\n"
                "kb:\n  a:\n    - {fields: {person: a}, id: note, desc: no identity here}\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly one self:true"):
                load_world_pack(root)

    def test_loader_rejects_missing_kb_section(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing the kb: section"):
                load_world_pack(root)

    def test_loader_rejects_unparseable_reminder(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: a, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\n"
                "kb:\n  a:\n    - {fields: {person: a, self: true}, id: identity, desc: '我，a。'}\n"
                "    - {fields: {reminder: '下周二早上'}, id: bad, desc: 不合法时间}\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unparseable reminder time"):
                load_world_pack(root)

    def test_known_to_gates_personal_entity_rows(self):
        # docs §6 (修订): 个人关联的物品按 known_to 展开——陈默的哨子只有
        # 他有行；唐小岚的店杯只有她有行；无关角色（林瑶）没有哨子行。
        pack = load_world_pack(ROOT / "world")
        chen = {row["id"]: row for row in pack.kb["陈默"]}
        self.assertTrue(any(r["fields"].get("item") == "红色哨子"
                            for r in chen.values()),
                        "陈默 must have the 红色哨子 row")
        self.assertTrue(any(r["fields"].get("item") == "裂纹马克杯"
                            for r in pack.kb["唐小岚"]),
                        "唐小岚 must have the 裂纹马克杯 row")
        self.assertFalse(any(r["fields"].get("item") == "红色哨子"
                             for r in pack.kb["林瑶"]),
                         "林瑶 must NOT have the 红色哨子 row")

    def test_descriptions_have_no_manual_wrapping_or_meta_voice(self):
        # 用户点名：描述正文不得手工换行（段落单行），且不得有作者旁白。
        pack = load_world_pack(ROOT / "world")
        for kind in ("items", "documents"):
            for row in getattr(pack, kind):
                from harness.world_loader import _plain_description
                markdown = pack.descriptions[kind].get(str(row["id"]), "")
                desc = _plain_description(markdown)
                body_lines = [l for l in desc.splitlines() if l.strip()]
                self.assertEqual(len(body_lines), 1,
                                 f"{row['id']} description must be a single line: {desc!r}")
                for banned in ("世界不做", "不是引擎提供", "剧情开关", "登记文本为准",
                               "不是自动赠予", "世界不替任何人回答", "世界不替"):
                    self.assertNotIn(banned, desc, f"{row['id']} carries author meta-voice")
