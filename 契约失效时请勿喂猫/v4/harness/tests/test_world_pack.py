import unittest
from copy import deepcopy
from pathlib import Path
from collections.abc import Mapping
from tempfile import TemporaryDirectory

from datetime import datetime
from harness.kernel import (ActionRejected, ActorState, Intention, LocationState,
                            World, apply_world_effects)
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
        self.assertIn("分钟", text)
        self.assertIn("whisper", text)
        self.assertIn("speak", text)

    def test_readiness_rejects_orphan_markdown(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "characters").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "locations" / "unlisted.md").write_text("orphan", encoding="utf-8")
            (root / "characters" / "aa.md").write_text("A", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock: {start: '2026-01-01T00:00:00+00:00', stop: '2026-01-01T01:00:00+00:00'}\n"
                "locations: [{id: room}]\nactors: [{id: aa, location: room}]\nitems: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\nkb:\n  aa:\n    - {keys: [aa], desc: '我，aa。'}\n", encoding="utf-8")
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
            (root / "characters" / "aa.md").write_text("A", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock: {start: '2026-01-01T00:00:00+00:00', stop: '2026-01-01T01:00:00+00:00'}\n"
                "locations: [{id: room}]\nactors: [{id: aa, location: room}]\nitems: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\nkb:\n  aa:\n    - {keys: [aa], desc: '我，aa。'}\n", encoding="utf-8")
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
        self.assertEqual(pack.manifest["clock"]["stop"], "2026-03-27T21:30:00+08:00")
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
                "locations:\n  - id: room\nactors:\n  - id: aa\n    location: room\n"
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
                "locations: [{id: room}]\nactors: [{id: aa, location: room}]\n"
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
                "locations: [{id: room}]\nactors: [{id: aa, location: room}]\n"
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
                "locations: [{id: room}]\nactors: [{id: aa, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\n"
                "scheduled: [{event: x, time: '2026-01-01T02:00:00+00:00'}]\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                load_world_pack(root)

    def test_loader_rejects_unknown_scheduled_effect_reference(self):
        from tempfile import TemporaryDirectory
        base = (
            "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
            "locations: [{id: room}]\nactors: [{id: aa, location: room}]\n"
            "items: []\ndocuments: []\nroutes: []\nbarriers: []\n"
            "kb:\n  aa:\n    - {keys: [aa], desc: '我，aa。'}\n"
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
                "locations: [{id: room}]\nactors: [{id: aa, location: room}]\n"
                "items: [{id: coin, location: room}]\ndocuments: []\nroutes: []\n"
                "barriers: []\nscheduled: []\nkb:\n  aa:\n    - {keys: [aa], desc: '我，aa。'}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "items missing"):
                load_world_pack(root)

    def test_loaded_pack_has_descriptions_for_every_static_entity(self):
        pack = load_world_pack(ROOT / "world")
        for category, rows in (("locations", pack.locations), ("items", pack.items),
                               ("documents", pack.documents)):
            self.assertEqual({str(row["id"]) for row in rows}, set(pack.descriptions[category]))

    def test_contacts_are_actor_scoped_with_private_nicknames(self):
        # T3: 联系人行是角色作用域的，昵称只属于持有人。
        pack = load_world_pack(ROOT / "world")
        chen = [row for row in pack.kb["陈默"] if "!contact" in row["keys"]]
        formal = {next(k for k in row["keys"] if k != "!contact") for row in chen}
        # The institutional figures (宿管阿姨/辅导员) are known in advance too:
        # every cast member who plausibly knows them holds a contact row.
        self.assertEqual(formal,
                         {"林瑶", "唐小岚", "陈默妈", "班长", "宿管阿姨", "辅导员"})
        mom = next(row for row in chen if "陈默妈" in row["keys"])
        self.assertIn("妈妈", mom["keys"], "陈默's private nickname for his mother")
        self.assertIn("陈默妈", mom["keys"], "the formal name is the row's anchor")
        # 昵称是私有的：妈妈这个称呼不属于唐小岚的联系人行。
        xiaolan = [row for row in pack.kb["唐小岚"] if "!contact" in row["keys"]]
        self.assertFalse(any("妈妈" in row["keys"] for row in xiaolan))


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

    def test_leave_note_is_a_read_once_room_message(self):
        """Ruling 2026-09-22: 字条 is a room message, not an item —
        co-located actors read it immediately and the note burns."""
        world = self.world()
        world.submit(Intention("a", "leave_note", {"text": "去后街找我"},
                               world.version))
        world.advance()
        # no 字条- item is created; the room held the message and it burned
        self.assertFalse(any(i.startswith("字条-") for i in world.item_locations))
        self.assertEqual(world.locations["room"].notes, [])
        packet = world.poll("b")
        reads = [e for e in packet["events"] if e["kind"] == "note_read"]
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0]["payload"]["text"], "去后街找我")
        self.assertEqual(reads[0]["payload"]["readers"], ["b"])
        # empty text rejected
        with self.assertRaises(ActionRejected):
            world.submit(Intention("a", "leave_note", {"text": "  "}, world.version))

    def test_note_is_delivered_privately_to_next_enterer(self):
        """Ruling 2026-09-22: the next enterer reads the note as a private
        line and the note is removed from the room (阅后即焚)."""
        world = World(
            start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            actors=[ActorState("a", "room"), ActorState("b", "far")],
            locations=[LocationState("room"), LocationState("far")],
            routes={("room", "far"): 60, ("far", "room"): 60})
        world.submit(Intention("a", "leave_note", {"text": "灯坏了"}, world.version))
        world.advance()
        # nobody else present: the note waits on the room
        self.assertEqual(len(world.locations["room"].notes), 1)
        world.submit(Intention("b", "move", {"target": "room"}, world.version))
        world.advance()
        self.assertEqual(world.locations["room"].notes, [])
        packet = world.poll("b")
        reads = [e for e in packet["events"] if e["kind"] == "note_read"]
        self.assertEqual(len(reads), 1)
        # the content is private: the leaver never receives it
        self.assertNotIn(reads[0]["id"],
                         [e["id"] for e in world.poll("a")["events"]])

    def test_notes_survive_checkpoint_and_replay(self):
        world = World(
            start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            actors=[ActorState("a", "room")],
            locations=[LocationState("room")])
        pristin = deepcopy(world)  # pre-run state for the replay baseline
        world.submit(Intention("a", "leave_note", {"text": "1"}, world.version))
        world.advance()
        restored = World.from_checkpoint(world, world.checkpoint_state())
        self.assertEqual([n["text"] for n in restored.locations["room"].notes], ["1"])
        from harness.replay import replay_world
        replayed = replay_world(pristin, world.replayable_log())
        self.assertEqual([n["text"] for n in replayed.locations["room"].notes], ["1"])

    def test_item_appearing_without_description_fails_loud(self):
        """Ruling 2026-09-22: an undescribed item appearing is an error."""
        world = self.world()
        world.actors["a"].inventory.add("mystery")
        world.entity_descriptions.pop("mystery", None)
        world.submit(Intention("a", "place", {"item": "mystery"}, world.version))
        with self.assertRaises(ValueError):
            world.advance()  # completion fires the fail-loud check
        with self.assertRaises(ValueError):
            apply_world_effects(world, {"effects": [
                {"op": "add_item", "id": "mystery", "location": "room"}]})

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
    """V4-AGENT-INTERFACE §6: KB rows are seeded in the manifest as key sets
    and validated at load time; identity is derived from the actor's own name."""

    def test_kb_section_exists_and_covers_every_actor(self):
        pack = load_world_pack(ROOT / "world")
        self.assertEqual(set(pack.kb), {row["id"] for row in pack.actors})
        for actor_id, rows in pack.kb.items():
            self.assertTrue(rows, f"{actor_id} has no kb rows")

    def test_every_actor_has_an_identity_row_keyed_by_its_own_name(self):
        pack = load_world_pack(ROOT / "world")
        for actor_id, rows in pack.kb.items():
            identity = [row for row in rows if actor_id in row["keys"]]
            self.assertEqual(len(identity), 1, f"{actor_id} identity row")
            self.assertTrue(identity[0]["desc"].startswith("我，"),
                            f"{actor_id} identity desc must be first-person")

    def test_key_sets_are_unique_per_actor(self):
        pack = load_world_pack(ROOT / "world")
        for actor_id, rows in pack.kb.items():
            sets = [frozenset(row["keys"]) for row in rows]
            self.assertEqual(len(sets), len(set(sets)), f"{actor_id} duplicate key sets")

    def test_key_shapes_are_valid(self):
        from harness.kb import ALWAYS_KEY, CONTACT_KEY, _AT_PREFIX
        pack = load_world_pack(ROOT / "world")
        for actor_id, rows in pack.kb.items():
            for row in rows:
                self.assertTrue(row["keys"], f"{actor_id} row without keys")
                for key in row["keys"]:
                    if key.startswith("!"):
                        self.assertTrue(key == ALWAYS_KEY or key == CONTACT_KEY
                                        or key.startswith(_AT_PREFIX),
                                        f"{actor_id} unknown directive {key!r}")
                    else:
                        self.assertGreaterEqual(len(key), 2,
                                                f"{actor_id} short key {key!r}")

    def test_mc_seeds_carry_always_and_scheduled_rows(self):
        pack = load_world_pack(ROOT / "world")
        for actor_id in ("陈默", "林瑶", "唐小岚"):
            rows = pack.kb[actor_id]
            self.assertTrue(any("!always" in row["keys"] for row in rows),
                            f"{actor_id} needs at least one !always row")
            scheduled = [row for row in rows
                         if any(k.startswith("!at=") for k in row["keys"])]
            self.assertEqual(len(scheduled), 1, f"{actor_id} needs exactly one !at row")

    def test_scheduled_keys_are_strictly_parseable(self):
        from harness.world_loader import _reminder_time_ok
        pack = load_world_pack(ROOT / "world")
        for actor_id, rows in pack.kb.items():
            for row in rows:
                for key in row["keys"]:
                    if not key.startswith("!at="):
                        continue
                    value = key[len("!at="):]
                    self.assertTrue(_reminder_time_ok(value),
                                    f"{actor_id} scheduled key {value!r} unparseable")
                    self.assertRegex(
                        value, r"^\d{1,2}/\d{1,2}\(周[一二三四五六日]\) \d{1,2}:\d{2}$")

    def test_loader_rejects_actor_without_identity_row(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: aa, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\n"
                "kb:\n  aa:\n    - {keys: [别处], desc: 没有自己的身份行}\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identity"):
                load_world_pack(root)

    def test_loader_rejects_missing_kb_section(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: aa, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing the kb: section"):
                load_world_pack(root)

    def test_loader_rejects_unparseable_scheduled_key(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locations").mkdir()
            (root / "locations" / "room.md").write_text("room", encoding="utf-8")
            (root / "manifest.yml").write_text(
                "schema_version: 1\nclock:\n  start: '2026-01-01T00:00:00+00:00'\n  stop: '2026-01-01T01:00:00+00:00'\n"
                "locations: [{id: room}]\nactors: [{id: aa, location: room}]\n"
                "items: []\ndocuments: []\nroutes: []\nbarriers: []\nscheduled: []\n"
                "kb:\n  aa:\n    - {keys: [aa], desc: '我，aa。'}\n"
                "    - {keys: ['!at=下周二早上'], desc: 不合法时间}\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unparseable scheduled"):
                load_world_pack(root)

    def test_known_to_gates_personal_entity_rows(self):
        # docs §6: 个人关联的物品按 known_to 展开——陈默的哨子只有他有行，
        # 唐小岚的马克杯只有她有行，无关角色（林瑶）没有哨子行。
        pack = load_world_pack(ROOT / "world")

        def has(actor: str, key: str) -> bool:
            return any(key in row["keys"] for row in pack.kb[actor])

        self.assertTrue(has("陈默", "红色哨子"), "陈默 must have the 红色哨子 row")
        self.assertTrue(has("唐小岚", "裂纹马克杯"), "唐小岚 must have the 裂纹马克杯 row")
        self.assertFalse(has("林瑶", "红色哨子"), "林瑶 must NOT have the 红色哨子 row")

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


class ConceptRegistryTests(unittest.TestCase):
    """concepts: is the registry every named non-entity thing must live in
    (V4-AGENT-INTERFACE §6.1). The seed name lint is the inverse gate."""

    def _write_pack(self, root: Path, concepts_yaml: str) -> Path:
        (root / "locations").mkdir()
        (root / "locations" / "room.md").write_text("room", encoding="utf-8")
        (root / "characters").mkdir()
        (root / "items").mkdir()
        (root / "documents").mkdir()
        (root / "characters" / "aa.md").write_text("A", encoding="utf-8")
        (root / "manifest.yml").write_text(
            "schema_version: 1\nclock: {start: '2026-01-01T00:00:00+00:00', stop: '2026-01-01T01:00:00+00:00'}\n"
            "locations: [{id: room}]\nactors: [{id: aa, location: room}]\nitems: []\ndocuments: []\n"
            "routes: []\nbarriers: []\nscheduled: []\n"
            "kb:\n  aa:\n    - {keys: [aa], desc: '我，aa。'}\n"
            + concepts_yaml, encoding="utf-8")
        return root

    def test_concepts_expand_into_one_merged_row(self):
        with TemporaryDirectory() as directory:
            root = self._write_pack(
                Path(directory),
                "concepts:\n"
                "- {id: old-place, name: 老地方, aliases: [旧地方], kind: place,\n"
                "   desc: 一个旧地方。,\n"
                "   known_to: [aa], memory: {aa: 我在那儿长大。}}\n")
            pack = load_world_pack(root)
            rows = [row for row in pack.kb["aa"] if "老地方" in row["keys"]]
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0]["keys"]), {"老地方", "旧地方"})
            self.assertIn("一个旧地方", rows[0]["desc"])
            self.assertIn("我在那儿长大", rows[0]["desc"])
            self.assertEqual(pack.lexicon["老地方"], ("旧地方",))

    def test_concept_named_after_an_entity_merges_memory_into_its_row(self):
        with TemporaryDirectory() as directory:
            root = self._write_pack(
                Path(directory),
                "concepts:\n"
                "- {id: room-memory, name: room, kind: place, known_to: [aa],\n"
                "   memory: {aa: 我在这个房间长大。}}\n")
            pack = load_world_pack(root)
            room_rows = [row for row in pack.kb["aa"] if row["keys"] == ["room"]]
            self.assertEqual(len(room_rows), 1)
            self.assertIn("我在这个房间长大", room_rows[0]["desc"])

    def test_concept_aliases_enrich_the_entity_row_instead_of_duplicating(self):
        """A concept named after a location must not render twice: its aliases
        join the auto row's keys and its memory is appended there."""
        with TemporaryDirectory() as directory:
            root = self._write_pack(
                Path(directory),
                "concepts:\n"
                "- {id: room-aliases, name: room, aliases: [那个房间], kind: place,\n"
                "   known_to: [aa], memory: {aa: 我在这里长大。}}\n")
            pack = load_world_pack(root)
            rows = [row for row in pack.kb["aa"] if "room" in row["keys"]]
            self.assertEqual(len(rows), 1, "老家属院-style duplicate row")
            self.assertEqual(set(rows[0]["keys"]), {"room", "那个房间"})
            self.assertIn("我在这里长大", rows[0]["desc"])

    def test_memory_alone_creates_a_row(self):
        with TemporaryDirectory() as directory:
            root = self._write_pack(
                Path(directory),
                "concepts:\n"
                "- {id: x, name: 某处, kind: place, desc: 某处。, memory: {aa: 我记得。}}\n")
            pack = load_world_pack(root)
            self.assertTrue(any(row["keys"] == ["某处"] for row in pack.kb["aa"]))

    def test_unknown_kind_and_duplicate_name_rejected(self):
        for yaml_text, message in (
                ("concepts:\n- {id: x, name: 某处, kind: wormhole, desc: 某处。}\n",
                 "unknown kind"),
                ("concepts:\n"
                 "- {id: x, name: 某处, kind: place, desc: 某处。}\n"
                 "- {id: y, name: 某处, kind: place, desc: 某处2。}\n",
                 "duplicate concept name")):
            with TemporaryDirectory() as directory:
                root = self._write_pack(Path(directory), yaml_text)
                with self.assertRaisesRegex(ValueError, message):
                    load_world_pack(root)

    def test_reference_markers_never_reach_the_model(self):
        """[[name]] is linter-only syntax: stripping must happen at every
        authored-string entry point (T5 裁决)."""
        pack = load_world_pack(ROOT / "world")
        for concept in pack.concepts:
            self.assertNotIn("[[", concept["desc"])
            for memory in concept["memory"].values():
                self.assertNotIn("[[", memory)
        for rows in pack.kb.values():
            for row in rows:
                self.assertNotIn("[[", row["desc"])
        for kind in ("items", "documents"):
            for row in getattr(pack, kind):
                self.assertNotIn("[[", pack.descriptions[kind][str(row["id"])])
        from harness.character_loader import load_story_characters
        for seed in load_story_characters(ROOT / "world").values():
            for text in (seed.identity, seed.private_seed, seed.goals,
                         seed.director_notes):
                self.assertNotIn("[[", text)
        for row in pack.manifest.get("scheduled", ()):
            self.assertNotIn("[[", str(row.get("notice", "")))
        # The WorldPack.scheduled and the built world's events are what the
        # model actually sees — the live run proved pack.manifest alone is not
        # enough (ticket-20 leak: build_world schedule rows kept raw markers).
        for row in pack.scheduled:
            if isinstance(row, dict):
                self.assertNotIn("[[", str(row.get("notice", "")))
            else:
                self.assertNotIn("[[", str(row))
        world = pack.build_world()
        for job in world._queue:
            notice = str(job.payload.get("notice", ""))
            self.assertNotIn("[[", notice)

    def test_seed_names_all_resolve(self):
        """The name registry gate: every name-like token in authored prose
        resolves to a registered entity or concept (scripts/seed_lint.py)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "seed_lint", ROOT / "scripts" / "seed_lint.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.lint(ROOT / "world"), [])
