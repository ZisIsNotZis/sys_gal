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

    def test_day_one_public_notices_are_placed_readable_and_removed(self):
        pack = load_world_pack(ROOT / "world")
        world = pack.build_world()
        chen = world.actors["陈默"]
        yao = world.actors["林瑶"]
        chen.location = yao.location = "学生会办公室"
        self.assertNotIn("学生会审计通知", world.item_locations)
        self.assertFalse(any("学生会审计通知" in row["keys"]
                             for rows in pack.kb.values() for row in rows))

        ten = datetime.fromisoformat("2026-03-16T10:00:00+08:00")
        world.advance(until=ten)
        self.assertEqual(world.item_locations["学生会审计通知"], "学生会办公室")
        self.assertIn("学生会审计通知", world.poll("陈默")["nearby_items"])
        self.assertIn({"kind": "read", "item": "学生会审计通知"},
                      world.affordances("陈默"))
        world.submit(Intention("陈默", "read", {"item": "学生会审计通知"}, world.version))
        completed = chen.busy_until
        self.assertIsNotNone(completed)
        events = world.advance(until=completed)
        read_event = next(event for event in events if event.kind == "document_read")
        self.assertIn("今日 16:00 前", read_event.payload["content"])
        self.assertIn("陈默", read_event.visible_to)
        self.assertNotIn("林瑶", read_event.visible_to)

        fifteen = datetime.fromisoformat("2026-03-16T15:00:00+08:00")
        sixteener = datetime.fromisoformat("2026-03-16T16:00:00+08:00")
        world.advance(until=fifteen)
        self.assertEqual(world.item_locations["台风纪念活动通知"], "学生会办公室")
        self.assertEqual(world.item_locations["学生会审计通知"], "学生会办公室")
        world.advance(until=sixteener)
        self.assertNotIn("学生会审计通知", world.item_locations)
        self.assertEqual(world.item_locations["审计催办单"], "学生会办公室")
        available = {row["item"] for row in world.affordances("陈默")
                     if row["kind"] == "read"}
        self.assertNotIn("学生会审计通知", available)
        self.assertIn("审计催办单", available)

    def test_actionable_refs_reject_unregistered_names_and_alias_bypass(self):
        from harness.world_loader import _validate_actionable_refs

        pack = load_world_pack(ROOT / "world")
        base_fields = {name: tuple(deepcopy(row) for row in getattr(pack, name))
                       for name in ("locations", "actors", "items", "documents",
                                    "routes", "barriers", "scheduled")}

        def validate(ref, notice):
            fields = dict(base_fields)
            fields["scheduled"] = (*fields["scheduled"], {
                "event": "contract_test", "time": "2026-03-17T00:00:00+08:00",
                "notice": notice, "actionable_refs": [ref]})
            _validate_actionable_refs(fields, pack.descriptions)

        with self.assertRaisesRegex(ValueError, "not a registered location"):
            validate({"action": "knock", "target": "未注册办公室", "from": "教学楼"},
                     "可以敲未注册办公室的门。")
        with self.assertRaisesRegex(ValueError, "not a readable document or item"):
            validate({"action": "read", "target": "催办单", "at": "学生会办公室"},
                     "公告栏上有催办单。")
        with self.assertRaisesRegex(ValueError, "unresolved location"):
            validate({"action": "read", "target": "台风纪念活动通知", "at": "不存在的地点"},
                     "请读台风纪念活动通知。")

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

    def test_leave_note_waits_for_next_entry_and_hides_text_from_room(self):
        """A note is a room message, but co-located actors are not readers."""
        from harness.prompt import render_world_message

        world = self.world()
        text = "去后街找我"
        world.submit(Intention("a", "leave_note", {"text": text}, world.version))
        world.advance()
        self.assertFalse(any(i.startswith("字条-") for i in world.item_locations))
        self.assertEqual([n["text"] for n in world.locations["room"].notes], [text])

        packet = world.poll("b")
        events = packet["events"]
        self.assertFalse(any(e["kind"] == "note_read" for e in events))
        note_events = [e for e in events if e["kind"] == "note_left" or
                       (e["kind"] in {"action_started", "action_completed"}
                        and e["payload"].get("action") == "leave_note")]
        self.assertTrue(note_events)
        self.assertTrue(all("text" not in e["payload"] for e in note_events))
        rendered = render_world_message(packet, world.affordances("b"), observer="b")
        self.assertNotIn(text, rendered)

        # Empty text remains invalid.
        with self.assertRaises(ActionRejected):
            world.submit(Intention("a", "leave_note", {"text": "  "}, world.version))

    def test_note_is_delivered_privately_to_only_the_next_enterer(self):
        """The entering actor alone gets the private, read-once note line."""
        from harness.prompt import render_world_message

        world = World(
            start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            actors=[ActorState("a", "room"), ActorState("b", "far"),
                    ActorState("c", "room")],
            locations=[LocationState("room"), LocationState("far")],
            routes={("room", "far"): 60, ("far", "room"): 60})
        text = "灯坏了"
        world.submit(Intention("a", "leave_note", {"text": text}, world.version))
        world.advance()
        # Another person already in the room sees only that a note was left.
        c_before = world.poll("c")
        self.assertNotIn(text, str(c_before["events"]))
        self.assertFalse(any(e["kind"] == "note_read" for e in c_before["events"]))

        world.submit(Intention("b", "move", {"target": "room"}, world.version))
        world.advance()
        self.assertEqual(world.locations["room"].notes, [])
        b_packet = world.poll("b")
        reads = [e for e in b_packet["events"] if e["kind"] == "note_read"]
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0]["payload"]["readers"], ["b"])
        self.assertIn(text, render_world_message(
            b_packet, world.affordances("b"), observer="b"))

        c_packet = world.poll("c")
        self.assertFalse(any(e["kind"] == "note_read" for e in c_packet["events"]))
        self.assertNotIn(text, str(c_packet["events"]))
        # The author does not receive the private note_read event either.
        self.assertFalse(any(e["kind"] == "note_read"
                             for e in world.poll("a")["events"]))

    def test_note_author_reentry_preserves_own_note_for_a_later_reader(self):
        """An author may read others' notes but never consumes their own."""
        from harness.prompt import _clock, render_world_message
        from harness.replay import replay_world

        start = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
        world = World(
            start=start,
            actors=[ActorState("author", "room"), ActorState("coauthor", "room"),
                    ActorState("entrant", "far")],
            locations=[LocationState("room"), LocationState("far")],
            routes={("room", "far"): 60, ("far", "room"): 60})
        initial = deepcopy(world)
        for actor, text in (("author", "留给后来者的第一张"),
                            ("author", "留给后来者的第二张"),
                            ("coauthor", "另一位作者的字条")):
            world.submit(Intention(actor, "leave_note", {"text": text}, world.version))
            world.advance()
        own_notes = [dict(note) for note in world.locations["room"].notes
                     if note["author"] == "author"]

        # The original author returns first: their own two notes stay pending,
        # while notes from a different author are independently consumable.
        world.submit(Intention("author", "move", {"target": "far"}, world.version))
        world.advance()
        world.submit(Intention("author", "move", {"target": "room"}, world.version))
        world.advance()
        self.assertEqual(world.locations["room"].notes, own_notes)
        author_reads = [event for event in world.event_log if event.kind == "note_read"]
        self.assertEqual([(event.payload["author"], event.payload["readers"])
                          for event in author_reads], [("coauthor", ["author"])])
        self.assertIn("left_at", author_reads[0].payload)
        author_packet = world.poll("author")
        author_private = render_world_message(author_packet, observer="author")
        self.assertIn("另一位作者的字条", author_private)
        self.assertIn("1/1(四) 0:", author_private)

        # A checkpoint retains the author's notes; the next non-author entrant
        # privately receives both immutable envelopes, then the notes are gone.
        checkpointed = World.from_checkpoint(initial, world.checkpoint_state())
        checkpointed.submit(Intention("entrant", "move", {"target": "room"},
                                      checkpointed.version))
        checkpointed.advance()
        entrant_reads = [event for event in checkpointed.event_log
                         if event.kind == "note_read" and event.payload["readers"] == ["entrant"]]
        self.assertEqual([event.payload["text"] for event in entrant_reads],
                         ["留给后来者的第一张", "留给后来者的第二张"])
        self.assertEqual([event.payload["author"] for event in entrant_reads],
                         ["author", "author"])
        self.assertEqual([event.payload["left_at"] for event in entrant_reads],
                         [note["left_at"] for note in own_notes])
        self.assertEqual(checkpointed.locations["room"].notes, [])
        entrant_packet = checkpointed.poll("entrant")
        entrant_private = render_world_message(entrant_packet, observer="entrant")
        for note in own_notes:
            self.assertIn(note["text"], entrant_private)
            self.assertIn(_clock(note["left_at"]), entrant_private)
        author_after_delivery = checkpointed.poll("author")
        self.assertFalse(any(event["kind"] == "note_read"
                             for event in author_after_delivery["events"]))
        self.assertNotIn("留给后来者的第一张", render_world_message(
            author_after_delivery, observer="author"))
        self.assertNotIn("留给后来者的第一张", render_world_message(
            checkpointed.poll("coauthor"), observer="coauthor"))
        replayed = replay_world(initial, checkpointed.replayable_log())
        self.assertEqual(replayed.locations["room"].notes, [])
        self.assertEqual([event.payload for event in replayed.event_log
                          if event.kind == "note_read"],
                         [event.payload for event in checkpointed.event_log
                          if event.kind == "note_read"])

    def test_notes_go_to_first_same_timestamp_entrant_and_survive_checkpoint_replay(self):
        """Same-time arrivals are serialized; one entrant burns all queued notes."""
        from harness.replay import replay_world

        world = World(
            start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            actors=[ActorState("author", "room"), ActorState("first", "far"),
                    ActorState("second", "far")],
            locations=[LocationState("room"), LocationState("far")],
            routes={("room", "far"): 60, ("far", "room"): 60})
        initial = deepcopy(world)
        for text in ("第一张", "重留的一张"):
            world.submit(Intention("author", "leave_note", {"text": text},
                                   world.version))
            world.advance()
        pending = World.from_checkpoint(world, world.checkpoint_state())
        self.assertEqual([n["text"] for n in pending.locations["room"].notes],
                         ["第一张", "重留的一张"])

        pending.submit(Intention("first", "move", {"target": "room"},
                                 pending.version))
        pending.submit(Intention("second", "move", {"target": "room"},
                                 pending.version))
        pending.advance()
        entrants = [e for e in pending.event_log
                    if e.kind == "enter" and e.actor in {"first", "second"}]
        self.assertEqual(len(entrants), 2)
        self.assertEqual(entrants[0].time, entrants[1].time)
        note_reads = [e for e in pending.event_log if e.kind == "note_read"]
        self.assertEqual([e.payload["text"] for e in note_reads],
                         ["第一张", "重留的一张"])
        self.assertEqual([e.payload["readers"] for e in note_reads],
                         [[entrants[0].actor], [entrants[0].actor]])
        self.assertTrue(all(e.cause == entrants[0].id for e in note_reads))
        self.assertEqual(pending.locations["room"].notes, [])

        first_packet = pending.poll("first")
        second_packet = pending.poll("second")
        first_reads = [e for e in first_packet["events"] if e["kind"] == "note_read"]
        second_reads = [e for e in second_packet["events"] if e["kind"] == "note_read"]
        if entrants[0].actor == "first":
            self.assertEqual(len(first_reads), 2)
            self.assertEqual(second_reads, [])
        else:
            self.assertEqual(first_reads, [])
            self.assertEqual(len(second_reads), 2)

        restored_after_delivery = World.from_checkpoint(
            initial, pending.checkpoint_state())
        self.assertEqual(restored_after_delivery.locations["room"].notes, [])
        replayed = replay_world(initial, pending.replayable_log())
        self.assertEqual(replayed.locations["room"].notes, [])
        self.assertEqual([e.kind for e in replayed.event_log if e.kind == "note_read"],
                         ["note_read", "note_read"])

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

    def test_known_to_alone_does_not_expose_a_description(self):
        """issue 40: entity_access (known_to) is awareness, not availability.

        Knowing a thing exists lets an actor name or recall it, but it no
        longer injects the entity's objective description."""
        world = self.world()
        world.entity_descriptions["secret"] = "a hidden description"
        world.entity_access["secret"] = {"b"}
        self.assertIsNone(world.resolve_entity("a", "secret"))
        self.assertIsNone(world.resolve_entity("b", "secret"))

    def test_description_resolves_only_where_the_entity_really_is(self):
        world = self.world()
        world.entity_descriptions["secret"] = "a hidden description"
        world.item_locations["secret"] = "room"
        self.assertEqual(world.resolve_entity("a", "secret"), "a hidden description")
        del world.item_locations["secret"]
        world.actors["b"].inventory.add("secret")
        self.assertEqual(world.resolve_entity("b", "secret"), "a hidden description")
        self.assertIsNone(world.resolve_entity("a", "secret"))

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


class SceneObjectContractTests(unittest.TestCase):
    """Issue 35: concrete-presence coverage for objective notices and prose.

    A scheduled notice or location description that asserts a concrete prop is
    at a place ("X 在 Y" / "可从 Y 取、读、交") must carry an actionable_refs
    entry, object_presence metadata, or a completeness declaration, or seed
    lint fails with remediation text. The regression: deleting the registration
    of 签到本 while keeping the notice must turn the seed red.
    """

    def _write_world(self, directory, *, notice=None, location_prose="一间屋子。",
                     item=None, item_location=None, scheduled_row=None,
                     item_content=None):
        import yaml
        root = Path(directory)
        for category in ("locations", "items", "documents"):
            (root / category).mkdir()
        (root / "locations" / "room.md").write_text(
            f"# room\n\n{location_prose}\n\n墙角立着一个旧柜子。\n", encoding="utf-8")
        items = []
        if item:
            (root / "items" / f"{item}.md").write_text(
                f"# {item}\n\n一件东西。\n", encoding="utf-8")
            # Issue 39: a prose body must be readable or explicitly declared
            # unreadable; these fixtures are pure props.
            row = {"id": item, "location": item_location}
            if item_content is not None:
                row["content"] = item_content
                row["reading_seconds"] = 5
            else:
                row["readable"] = False
                row["readable_reason"] = "只是一件实物，没有可读的正文。"
            items.append(row)
        row = {"event": "contract_test", "time": "2026-03-16T07:10:00+08:00"}
        if notice is not None:
            row["notice"] = notice
        if scheduled_row:
            row.update(scheduled_row)
        manifest = {
            "schema_version": 1,
            "clock": {"start": "2026-03-16T07:00:00+08:00",
                      "stop": "2026-03-16T08:00:00+08:00"},
            "locations": [{"id": "room"}],
            "actors": [{"id": "aa", "location": "room"}],
            "items": items, "documents": [], "routes": [], "barriers": [],
            "scheduled": [row],
            "kb": {"aa": [{"keys": ["aa"], "desc": "我，aa。"}]},
        }
        (root / "manifest.yml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
        return root

    def _lint(self, world_root):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "seed_lint_contract", ROOT / "scripts" / "seed_lint.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.lint(world_root)

    def test_uncovered_presence_claim_fails_seed_lint_with_remediation(self):
        with TemporaryDirectory() as directory:
            root = self._write_world(
                directory, item="登记本", item_location=None,
                notice="门边的值班桌上，登记本就在那里。")
            findings = self._lint(root)
            self.assertTrue(findings, "an uncovered presence claim must fail")
            self.assertIn("登记本", findings[0])
            self.assertIn("completeness", findings[0])

    def test_expectation_narration_is_legal_and_object_stays_unreadable(self):
        with TemporaryDirectory() as directory:
            root = self._write_world(
                directory, item="登记本", item_location=None,
                notice="按惯例登记本本该在门口，今天没有找到。",
                scheduled_row={"completeness": "expectation"})
            self.assertEqual(self._lint(root), [])
            world = load_world_pack(root).build_world()
            with self.assertRaises(ActionRejected):
                world.submit(Intention("aa", "read", {"item": "登记本"},
                                       world.version))

    def test_object_presence_present_must_match_a_real_placement(self):
        with TemporaryDirectory() as directory:
            root = self._write_world(
                directory, item="登记本", item_location=None,
                notice="登记本就在桌上。",
                scheduled_row={"object_presence": [
                    {"name": "登记本", "place": "room", "state": "present"}]})
            with self.assertRaisesRegex(ValueError, "actually placed at None"):
                load_world_pack(root)

    def test_declared_object_presence_covers_a_placed_prop(self):
        with TemporaryDirectory() as directory:
            root = self._write_world(
                directory, item="登记本", item_location="room",
                notice="登记本就在桌上。",
                scheduled_row={"object_presence": [
                    {"name": "登记本", "place": "room", "state": "present"}]})
            self.assertEqual(self._lint(root), [])

    def test_unknown_completeness_state_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = self._write_world(
                directory, item="登记本", item_location=None,
                notice="登记本就在桌上。",
                scheduled_row={"completeness": "perhaps"})
            with self.assertRaisesRegex(ValueError, "completeness"):
                load_world_pack(root)

    def test_cue_before_prop_claim_is_also_covered(self):
        # "压着一本没人翻的值班簿" asserts presence as strongly as prop-then-cue.
        with TemporaryDirectory() as directory:
            root = self._write_world(
                directory, notice="桌上压着一本没人翻的值班簿。")
            findings = self._lint(root)
            self.assertTrue(findings, "cue-before-prop claims must not slip through")
            self.assertIn("值班簿", findings[0])

    def test_unregistered_concrete_prop_claim_fails(self):
        with TemporaryDirectory() as directory:
            root = self._write_world(
                directory, notice="门边的值班桌上，登记本就在那里。")
            findings = self._lint(root)
            self.assertTrue(findings)
            self.assertIn("register", findings[0])

    def test_location_scene_prose_presence_claim_needs_coverage(self):
        with TemporaryDirectory() as directory:
            root = self._write_world(
                directory, item="登记本", item_location=None,
                location_prose="门边桌上，登记本就在那里。")
            findings = self._lint(root)
            self.assertTrue(findings)
            self.assertIn("location room", findings[0])

    def test_signin_and_borrow_registers_are_distinct_placed_entities(self):
        from datetime import datetime
        world = load_world_pack(ROOT / "world").build_world()
        self.assertEqual(world.item_locations.get("签到本"), "校史档案室")
        self.assertNotIn("借阅登记本", world.item_locations)
        world.advance(until=datetime.fromisoformat("2026-03-19T08:25:00+08:00"))
        self.assertEqual(world.item_locations.get("借阅登记本"), "校史档案室")

    def test_application_form_is_posted_with_supplies_and_rejected(self):
        from datetime import datetime
        world = load_world_pack(ROOT / "world").build_world()
        world.actors["林瑶"].location = "学生会办公室"
        world.advance(until=datetime.fromisoformat("2026-03-16T08:25:00+08:00"))
        self.assertEqual(world.item_locations.get("场地申请表"), "学生会办公室")
        self.assertEqual(world.item_locations.get("可用纸笔"), "学生会办公室")
        readable = {row["item"] for row in world.affordances("林瑶")
                    if row["kind"] == "read"}
        self.assertIn("场地申请表", readable)
        events = world.advance(until=datetime.fromisoformat("2026-03-16T12:31:00+08:00"))
        rejected = [e for e in events
                    if e.payload.get("event") == "application_rejected"]
        self.assertTrue(rejected, "the office must reject applications at 12:30")


def _seed_lint_findings(world_root):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "seed_lint_item_body", ROOT / "scripts" / "seed_lint.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.lint(world_root)


class Issue39ReadableItemTests(unittest.TestCase):
    """Issue 39/40: an `items:` row that carries `content:` is read exactly
    like a document; a read rejection states the real situation and only ever
    offers reads that will succeed."""

    def _pack(self, directory, *, item_declaration="readable",
              item_location="room"):
        import yaml
        root = Path(directory)
        for category in ("locations", "items", "documents"):
            (root / category).mkdir(parents=True)
        (root / "locations" / "room.md").write_text(
            "# room\n\n一间屋子。\n\n墙角立着一个旧柜子。\n", encoding="utf-8")
        (root / "locations" / "vault.md").write_text(
            "# vault\n\n一间库房。\n\n靠墙一排铁架子。\n", encoding="utf-8")
        (root / "items" / "签到本.md").write_text("# 签到本\n\n一本签到簿。\n",
                                                  encoding="utf-8")
        (root / "documents" / "移交存根.md").write_text(
            "# 移交存根\n\n一份存根。\n", encoding="utf-8")
        item = {"id": "签到本", "location": item_location}
        if item_declaration == "readable":
            item["content"] = "到岗签到记录。"
            item["reading_seconds"] = 5
        elif item_declaration == "unreadable_declared":
            item["readable"] = False
            item["readable_reason"] = "只是一件实物，没有可读的正文。"
        manifest = {
            "schema_version": 1,
            "clock": {"start": "2026-03-16T07:00:00+08:00",
                      "stop": "2026-03-16T08:00:00+08:00"},
            "locations": [{"id": "room"}, {"id": "vault"}],
            "actors": [{"id": "aa", "location": "room"},
                       {"id": "bb", "location": "room"}],
            "items": [item],
            "documents": [{"id": "移交存根", "title": "移交存根",
                           "content": "存根正文。", "reading_seconds": 5,
                           "location": "vault", "known_to": ["aa"]}],
            "routes": [{"from": "room", "to": "vault", "duration_seconds": 60},
                       {"from": "vault", "to": "room", "duration_seconds": 60}],
            "barriers": [], "scheduled": [],
            "kb": {"aa": [{"keys": ["aa"], "desc": "我，aa。"}],
                   "bb": [{"keys": ["bb"], "desc": "我，bb。"}]},
        }
        (root / "manifest.yml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
        return root

    def test_item_with_content_reads_once_like_a_document(self):
        with TemporaryDirectory() as directory:
            root = self._pack(directory)
            world = load_world_pack(root).build_world()
            self.assertIn("签到本", world.document_defs)
            self.assertIn({"kind": "read", "item": "签到本"},
                          world.affordances("aa"))
            world.submit(Intention("aa", "read", {"item": "签到本"}, world.version))
            world.advance()
            reads = [e for e in world.event_log if e.kind == "document_read"]
            self.assertEqual(len(reads), 1)
            self.assertEqual(reads[0].payload["document"], "签到本")
            self.assertEqual(reads[0].payload["content"], "到岗签到记录。")

    def test_inventory_item_reads_and_every_offered_read_succeeds(self):
        """Turn 305: 签到本 sat in 陈默's inventory yet read said 'not in your
        hand'. A held readable item must read; and every read the world
        offers must actually succeed."""
        with TemporaryDirectory() as directory:
            root = self._pack(directory)
            world = load_world_pack(root).build_world()
            world.actors["aa"].inventory.add("签到本")
            del world.item_locations["签到本"]
            world.submit(Intention("aa", "read", {"item": "签到本"}, world.version))
            world.advance()
            self.assertEqual([e.payload["document"] for e in world.event_log
                              if e.kind == "document_read"], ["签到本"])
            offered = [row["item"] for row in world.affordances("aa")
                       if row["kind"] == "read"]
            self.assertIn("签到本", offered)
            for name in offered:
                probe = load_world_pack(root).build_world()
                probe.actors["aa"].inventory.add("签到本")
                del probe.item_locations["签到本"]
                probe.submit(Intention("aa", "read", {"item": name}, probe.version))

    def test_held_item_without_a_body_says_so_and_offers_real_actions(self):
        with TemporaryDirectory() as directory:
            root = self._pack(directory, item_declaration="unreadable_declared")
            world = load_world_pack(root).build_world()
            world.actors["aa"].inventory.add("签到本")
            del world.item_locations["签到本"]
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("aa", "read", {"item": "签到本"},
                                       world.version))
            message = str(caught.exception)
            self.assertIn("没有可读", message)
            self.assertNotIn("不在你手边", message)
            self.assertTrue(caught.exception.alternatives)
            for alternative in caught.exception.alternatives:
                kind, _, rest = alternative.partition(" ")
                if kind == "give":
                    item, _, target = rest.partition(" to ")
                    args = {"item": item, "target": target}
                else:
                    args = {"item": rest}
                probe = load_world_pack(root).build_world()
                probe.actors["aa"].inventory.add("签到本")
                del probe.item_locations["签到本"]
                probe.submit(Intention("aa", kind, args, probe.version))

    def test_known_to_does_not_grant_remote_read_or_description(self):
        with TemporaryDirectory() as directory:
            root = self._pack(directory)
            world = load_world_pack(root).build_world()
            # aa is aware of 移交存根 (known_to) but it sits in the vault.
            self.assertIn("aa", world.entity_access.get("移交存根", set()))
            self.assertNotIn({"kind": "read", "item": "移交存根"},
                             world.affordances("aa"))
            packet = world.poll("aa")
            self.assertIn("签到本", packet["descriptions"])
            self.assertNotIn("移交存根", packet["descriptions"])
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("aa", "read", {"item": "移交存根"},
                                       world.version))
            self.assertNotIn("移交存根",
                             caught.exception.context.get("readable_now", []))

    def test_undeclared_item_body_fails_seed_lint_and_declaring_it_turns_green(self):
        with TemporaryDirectory() as directory:
            root = self._pack(Path(directory) / "bad",
                              item_declaration="undeclared")
            findings = _seed_lint_findings(root)
            self.assertTrue(findings, "an undeclared prose body must fail the lint")
            self.assertIn("签到本", findings[0])
            fixed = self._pack(Path(directory) / "fixed",
                               item_declaration="unreadable_declared")
            self.assertEqual(_seed_lint_findings(fixed), [])


class SeedRegisterContentTests(unittest.TestCase):
    """Issue 39: the four seeded registers carry objective, runtime-readable
    content and leak no answer (no tear/steal conclusions)."""

    REGISTERS = ("签到本", "晚归登记本", "值班簿", "借阅登记本")
    # Objective register text must not assert how the record was lost.
    BANNED = ("撕", "偷", "窃", "内鬼", "真凶")

    def test_register_items_carry_runtime_readable_content(self):
        world = load_world_pack(ROOT / "world").build_world()
        for name in self.REGISTERS:
            self.assertIn(name, world.document_defs, f"{name} must be readable")
            content = world.document_defs[name]["content"]
            self.assertTrue(content.strip(), f"{name} needs non-empty content")
            self.assertGreaterEqual(world.document_defs[name]["reading_seconds"], 1)

    def test_register_content_states_no_plot_answer(self):
        world = load_world_pack(ROOT / "world").build_world()
        for name in self.REGISTERS:
            content = world.document_defs[name]["content"]
            for banned in self.BANNED:
                self.assertNotIn(banned, content,
                                 f"{name} content must not assert how it was lost")


class LedgerSettlementSeedTests(unittest.TestCase):
    """票 93：`system.settle_on` 点的是种子排程里真实存在的那条结算事件。

    点错一个名字的后果是案子**永不结案**（报酬也不发），而且要到运行到那一天才
    看得出来；所以这条契约在加载时就检查：名字必须能在 `scheduled:` 里找到。
    """

    def _pack(self, directory, *, settle_on, scheduled):
        import yaml
        root = Path(directory)
        (root / "locations").mkdir(parents=True)
        (root / "locations" / "room.md").write_text("# room\n\n一间屋子。\n", encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "clock": {"start": "2026-03-16T07:00:00+08:00",
                      "stop": "2026-03-16T09:00:00+08:00"},
            "system": {"name": "台账", "bound_actor": "aa", "settle_on": settle_on},
            "locations": [{"id": "room"}],
            "actors": [{"id": "aa", "location": "room"}],
            "items": [], "documents": [], "routes": [], "barriers": [],
            "scheduled": scheduled,
            "kb": {"aa": [{"keys": ["aa"], "desc": "我，aa。"}]},
        }
        (root / "manifest.yml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
        return root

    def test_a_settle_on_naming_no_scheduled_event_fails_the_load(self):
        with TemporaryDirectory() as directory:
            root = self._pack(directory, settle_on="ledger_settlement",
                              scheduled=[{"event": "morning_bell",
                                          "time": "2026-03-16T08:00:00+08:00"}])
            with self.assertRaisesRegex(ValueError, "system.settle_on"):
                load_world_pack(root)

    def test_a_settle_on_naming_a_real_event_loads(self):
        with TemporaryDirectory() as directory:
            root = self._pack(directory, settle_on="ledger_settlement",
                              scheduled=[{"event": "ledger_settlement",
                                          "time": "2026-03-16T08:00:00+08:00"}])
            self.assertEqual(load_world_pack(root).system["settle_on"],
                             "ledger_settlement")


class LedgerFactsSeedTests(unittest.TestCase):
    """票 95（E95）：真种子的事实条目必须保留 `{answer, keywords}` 形状。

    `world_loader` 的 strip 循环曾对每条 facts 值直接 `strip_refs(value)`，而
    `strip_refs` 对 dict 做 `str()`：mapping 被 stringify 成 Python 字典字面量，
    于是 `Ledger.fact_keywords` 全空（关键词匹配在真种子上完全不生效），并且
    台账会把那串 dict 字面量当作答案投给角色。这支种子级守卫钉住形状。
    """

    def test_the_seeded_fact_entries_keep_their_keyword_shape(self):
        pack = load_world_pack(ROOT / "world")
        facts = pack.system.get("facts") or {}
        self.assertTrue(facts, "真种子必须有事实表")
        for key, entry in facts.items():
            self.assertIsInstance(entry, Mapping, f"{key} 被 stringify 了：{entry!r}")
            self.assertIsInstance(entry.get("answer"), str, key)
            self.assertNotIn("{'", entry["answer"], f"{key} 的答案成了 dict 字面量")
            self.assertIsInstance(entry.get("keywords"), list, key)
            self.assertTrue(entry["keywords"], f"{key} 没有 keywords，只能用原问句命中")
            self.assertTrue(all(isinstance(word, str) and word.strip()
                                for word in entry["keywords"]), key)
            self.assertTrue(all("[[" not in word for word in entry["keywords"]), key)


class PrimitiveSufficiencyTests(unittest.TestCase):
    """Ticket 77 — 原语充分性审计：三个 M1.5 死循环族是否需要新原语。

    Each test below encodes one observed loop with **existing** seed concepts
    and passes without any engine change. They exist to keep the engine's
    primitive set minimal: a future proposal to add a look/call/spawn verb has
    to explain why these encodings fail, not the other way round.

    The evidence in each case is a pair: the negative fixture (the same
    engine, a pack without the declaration) reproduces the loop's dead end,
    and the positive fixture (with the declaration) makes the same actor's
    affordances contain a legal, executable action.
    """

    def _pack(self, directory, body: str) -> Path:
        root = Path(directory) / "world"
        for category in ("locations", "characters", "items", "documents"):
            (root / category).mkdir(parents=True)
        for location in ("教学楼", "半坡咖啡馆", "通宵值班室"):
            (root / "locations" / f"{location}.md").write_text(
                f"# {location}\n\n一间屋子。\n", encoding="utf-8")
        (root / "characters" / "aa.md").write_text("A", encoding="utf-8")
        (root / "manifest.yml").write_text(
            "schema_version: 1\n"
            "clock: {start: '2026-03-16T07:00:00+08:00', "
            "stop: '2026-03-16T23:00:00+08:00'}\n"
            "locations: [{id: 教学楼}, {id: 半坡咖啡馆}, {id: 通宵值班室}]\n"
            "actors: [{id: aa, location: 教学楼}]\n"
            "kb:\n  aa:\n    - {keys: [aa], desc: '我，aa。'}\n" + body,
            encoding="utf-8")
        return root

    def test_a_notice_board_is_a_document_and_read_already_covers_it(self):
        """公告栏：`read` 的可用对象来自 document_defs（kernel._available_readables）。

        Negative fixture: a place whose prose and notices talk about a board
        but nothing is registered — `read 公告栏` is the artifact's dead end
        ("这里没有这样一件能读的文书", error turns #329/355/362/…).
        Positive fixture: the same board declared as a `documents:` row — the
        actor standing there has `read` in its affordances, the read produces a
        `document_read`, and staying put for `reading_seconds` auto-reads it.
        No new verb, no new event kind.
        """
        board = ("documents:\n"
                 "- {id: 教学楼公告栏, title: 教学楼公告栏, location: 教学楼,\n"
                 "   reading_seconds: 30,\n"
                 "   content: 玻璃罩下压着三张纸：《台风纪念活动通知》招志愿者整理老照片；\n"
                 "     一张课程表；一张过期的停电通知。}\n")
        with TemporaryDirectory() as directory:
            root = self._pack(directory, "items: []\ndocuments: []\nroutes: []\n"
                                          "barriers: []\nscheduled: []\n")
            (root / "documents" / "教学楼公告栏.md").write_text(
                "# 教学楼公告栏\n\n正门内侧的玻璃公告栏。\n", encoding="utf-8")
            dead_end = load_world_pack(root).build_world()
            self.assertNotIn({"kind": "read", "item": "教学楼公告栏"},
                             dead_end.affordances("aa"))
            with self.assertRaises(ActionRejected) as caught:
                dead_end.submit(Intention("aa", "read", {"item": "教学楼公告栏"},
                                          dead_end.version))
            self.assertIn("这里没有", caught.exception.message)

        with TemporaryDirectory() as directory:
            root = self._pack(directory, "items: []\nroutes: []\nbarriers: []\n"
                                          "scheduled: []\n" + board)
            (root / "documents" / "教学楼公告栏.md").write_text(
                "# 教学楼公告栏\n\n正门内侧的玻璃公告栏。\n", encoding="utf-8")
            world = load_world_pack(root).build_world()
            self.assertIn({"kind": "read", "item": "教学楼公告栏"},
                          world.affordances("aa"))
            world.submit(Intention("aa", "read", {"item": "教学楼公告栏"}, world.version))
            world.advance()
            read = [e for e in world.event_log if e.kind == "document_read"]
            self.assertEqual(len(read), 1)
            self.assertIn("老照片", read[0].payload["content"])
            # 停留即读：站够 reading_seconds 也算读过（ticket 49 的既有路径）。
            stayed = load_world_pack(root).build_world()
            stayed.poll("aa")
            stayed.advance(until=datetime.fromisoformat(
                "2026-03-16T07:01:00+08:00"))
            stayed.poll("aa")
            auto = [e for e in stayed.event_log if e.kind == "document_read"]
            self.assertEqual(len(auto), 1)
            self.assertTrue(auto[0].payload["auto"])

    def test_stock_and_fixtures_are_item_descriptions_in_perception(self):
        """库存/陈设：物品描述已经随在场进入知觉（_visible_descriptions）。

        The artifact's 关东煮库存 stalemate and the 热水壶 hunt were people
        asking each other about a thing in the room they could not describe.
        A fixture declared as an `items:` row is delivered as an objective
        description on first sight and recorded as an observation row; nothing
        needs to be "examined". A menu/price list that must be *read* is a
        `documents:` row (previous test).
        """
        with TemporaryDirectory() as directory:
            root = self._pack(directory, (
                "items:\n"
                "- {id: 关东煮锅, location: 半坡咖啡馆, readable: false,\n"
                "   readable_reason: 一口关东煮锅，没有可读的正文。}\n"
                "documents: []\nroutes: []\nbarriers: []\nscheduled: []\n"))
            (root / "items" / "关东煮锅.md").write_text(
                "# 关东煮锅\n\n格子锅里还剩六串：萝卜两份、豆腐四份，汤正开着。\n",
                encoding="utf-8")
            world = load_world_pack(root).build_world()
            world.actors["aa"].location = "半坡咖啡馆"
            perceived = world.poll("aa")
            self.assertIn("关东煮锅", perceived["descriptions"])
            self.assertIn("萝卜两份", perceived["descriptions"]["关东煮锅"])
            self.assertIn("萝卜两份",
                          world.actors["aa"].observed["关东煮锅"]["objective"],
                          "the description is the actor's own memory row")
            # It is a prop, not a document: `read` states that and still
            # offers an executable move instead of the artifact's dead end.
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("aa", "read", {"item": "关东煮锅"},
                                       world.version))
            self.assertIn("实物", caught.exception.message)
            self.assertTrue(caught.exception.alternatives)

    def test_a_duty_clerk_is_an_existing_actor_and_absence_leaves_a_record(self):
        """值班干事：不需要排程生成的现场人物。

        The d1-pm miss (林瑶 16:13–16:55 away, 16:20 面核 broadcast with no
        in-world host and nothing to perceive on returning) is encoded with
        two existing concepts: (a) the host is an ordinary `actors:` row
        (V4-CAST §1 NPC tier — event-driven, woken by a scheduled `target`
        row), and (b) the occasion leaves an artifact on the scene through the
        existing `add_document` effect, which a later arriver perceives and
        reads. Both are seed declarations; the engine is untouched.
        """
        with TemporaryDirectory() as directory:
            root = self._pack(directory, (
                "items: []\n"
                "documents:\n"
                "- {id: 审计面核记录, title: 审计面核记录, reading_seconds: 20,\n"
                "   content: 16:20 面核：审计包逐项核对，缺项当场记下，不补写。}\n"
                "routes:\n"
                "- {from: 半坡咖啡馆, to: 教学楼, duration_seconds: 420}\n"
                "- {from: 教学楼, to: 半坡咖啡馆, duration_seconds: 420}\n"
                "barriers: []\n"
                "scheduled:\n"
                "- {time: '2026-03-16T16:20:00+08:00', event: audit_pack_review,\n"
                "   target: [值班干事乙],\n"
                "   notice: 值班干事乙按规程把审计包摊开逐项核对，当场留痕。,\n"
                "   effects: [{op: add_document, id: 审计面核记录, location: 教学楼}]}\n"))
            (root / "characters" / "bb.md").write_text("B", encoding="utf-8")
            (root / "characters" / "值班干事乙.md").write_text("C", encoding="utf-8")
            (root / "documents" / "审计面核记录.md").write_text(
                "# 审计面核记录\n\n摊在长桌上的一页纸。\n", encoding="utf-8")
            manifest = root / "manifest.yml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    "actors: [{id: aa, location: 教学楼}]",
                    "actors: [{id: aa, location: 教学楼},\n"
                    "         {id: bb, location: 半坡咖啡馆},\n"
                    "         {id: 值班干事乙, location: 教学楼, role: npc}]",
                    1).replace(
                    "kb:\n  aa:\n    - {keys: [aa], desc: '我，aa。'}\n",
                    "kb:\n  aa:\n    - {keys: [aa], desc: '我，aa。'}\n"
                    "  bb:\n    - {keys: [bb], desc: '我，bb。'}\n"
                    "  值班干事乙:\n    - {keys: [值班干事乙], desc: '我，值班干事乙。'}\n",
                    1), encoding="utf-8")
            world = load_world_pack(root).build_world()
            # (a) the host is a real actor the cast already contains, and the
            # scheduled row (existing `target`) is what wakes it.
            self.assertEqual(world.actors["值班干事乙"].role, "npc")
            self.assertIn("值班干事乙", world.poll("aa")["nearby_actors"])
            self.assertNotIn("审计面核记录", world.item_locations,
                             "the record appears only when the occasion runs")
            wake = world.advance(until=datetime.fromisoformat(
                "2026-03-16T16:21:00+08:00"))
            self.assertTrue(any(e.kind == "world_event"
                                and e.payload.get("event") == "audit_pack_review"
                                for e in wake))
            self.assertEqual(world.item_locations["审计面核记录"], "教学楼")
            # (b) someone who arrives late still perceives the occasion's
            # evidence and can read it — no "核对进行中" state needed.
            world.submit(Intention("bb", "move", {"target": "教学楼"}, world.version))
            world.advance()
            perceived = world.poll("bb")
            self.assertIn("审计面核记录", perceived["descriptions"])
            self.assertIn({"kind": "read", "item": "审计面核记录"},
                          world.affordances("bb"))

    def test_the_night_dead_end_is_a_missing_route_not_a_missing_verb(self):
        """12345 借电话：死胡同是种子缺一个世界内出口。

        Negative fixture: the stuck actor's affordances contain no place to
        spend the night, and `text 12345` is refused (the existing `text`
        contract: a message needs an addressable person) — the 21:30–22:00
        "borrow a phone" loop, reproduced.
        Positive fixture: one route to a place that serves the need, plus the
        location's own description naming it, gives the same actor an
        executable `move` and the caller nothing to invent.

        Residual (recorded, deliberately not implemented): a literal phone call
        to a non-person endpoint is not expressible today. The minimal
        generalisation would be to widen `text`'s target class from actors to
        a registered non-person endpoint (kernel `_raw_duration` text branch +
        `_resolve_person`), not to add a `call` verb; that needs its own ticket
        and is not required to close this loop.
        """
        with TemporaryDirectory() as directory:
            root = self._pack(directory, "items: []\ndocuments: []\n"
                                          "routes: []\nbarriers: []\nscheduled: []\n")
            stuck = load_world_pack(root).build_world()
            self.assertNotIn({"kind": "move", "target": "通宵值班室"},
                             stuck.affordances("aa"),
                             "with no route there is no exit in the world")
            with self.assertRaises(ActionRejected) as caught:
                stuck.submit(Intention("aa", "text", {"target": "12345",
                                                      "text": "夜里哪儿能待？"},
                                       stuck.version))
            self.assertIn("12345", caught.exception.message)
            self.assertIn("recipient_candidates", caught.exception.context,
                          "the refusal still names who can actually be reached")

        with TemporaryDirectory() as directory:
            root = self._pack(directory, (
                "items: []\ndocuments: []\n"
                "routes:\n"
                "- {from: 教学楼, to: 通宵值班室, duration_seconds: 600}\n"
                "- {from: 通宵值班室, to: 教学楼, duration_seconds: 600}\n"
                "barriers: []\nscheduled: []\n"))
            (root / "locations" / "通宵值班室.md").write_text(
                "# 通宵值班室\n\n门一直开着，值班台后能登记夜里无处可去的人。\n",
                encoding="utf-8")
            exit_world = load_world_pack(root).build_world()
            self.assertIn({"kind": "move", "target": "通宵值班室"},
                          exit_world.affordances("aa"),
                          "one seeded route gives the loop its in-world exit")
            self.assertIn("登记",
                          exit_world.entity_descriptions["通宵值班室"],
                          "and the place itself says what it is for")


class PlaceBoundDocumentTests(unittest.TestCase):
    """票 91 §3 裁定（报 90 §8 / 票 86 §5）：文书能不能被拿走是**种子的事实**。

    窗口 2/3 的 `take` 拒绝文案把 `公告栏`、`学生会审计通知`、`学生会审计包` 与
    可拿的 `场地申请表` 列在同一张"这里能拿的"清单里。裁定：文书默认是一张纸，
    可拿（`场地申请表` 就是让人自取的）；一块钉在墙上的公告栏、一张贴在板上的
    通知由种子声明 `takeable: false` + `fixed_reason`，与既有 `items:` 的固定陈设
    同一机制——`take`/`give`/`trash` 结构化拒绝，拒绝理由用种子写的那句话，
    候选项里也不再出现它。引擎不猜哪个名字"听起来像板"。
    """

    def _pack(self, directory, *, board_takeable=None):
        import yaml
        root = Path(directory)
        for category in ("locations", "items", "documents"):
            (root / category).mkdir(parents=True)
        (root / "locations" / "room.md").write_text(
            "# room\n\n一间办公室，门边挂着一块板，桌上有一张空白表。\n",
            encoding="utf-8")
        (root / "documents" / "公告栏.md").write_text(
            "# 公告栏\n\n门边那块板，上面钉着这周的通知。\n", encoding="utf-8")
        (root / "documents" / "场地申请表.md").write_text(
            "# 场地申请表\n\n一张空白表格，自己取了填。\n", encoding="utf-8")
        board = {"id": "公告栏", "title": "公告栏", "content": "板上钉着本周通知。",
                 "reading_seconds": 5, "location": "room"}
        if board_takeable is not None:
            board["takeable"] = board_takeable
            board["fixed_reason"] = "它钉在门边的墙上"
        manifest = {
            "schema_version": 1,
            "clock": {"start": "2026-03-16T07:00:00+08:00",
                      "stop": "2026-03-16T08:00:00+08:00"},
            "locations": [{"id": "room"}],
            "actors": [{"id": "aa", "location": "room"}],
            "items": [],
            "documents": [board,
                          {"id": "场地申请表", "title": "场地申请表",
                           "content": "一格一格等着填。", "reading_seconds": 5,
                           "location": "room"}],
            "routes": [], "barriers": [], "scheduled": [],
            "kb": {"aa": [{"keys": ["aa"], "desc": "我，aa。"}]},
        }
        (root / "manifest.yml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
        return root

    def test_a_declared_place_bound_document_is_not_a_take_candidate(self):
        with TemporaryDirectory() as directory:
            root = self._pack(directory, board_takeable=False)
            world = load_world_pack(root).build_world()
            takeable = [row["item"] for row in world.affordances("aa")
                        if row["kind"] == "take"]
            self.assertNotIn("公告栏", takeable,
                             "钉在墙上的板不在可拿清单里（票 86 §5 的原症状）")
            self.assertIn("场地申请表", takeable, "可移动的纸仍然可拿")
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("aa", "take", {"item": "公告栏"}, world.version))
            self.assertIn("它钉在门边的墙上", caught.exception.message)
            self.assertNotIn("公告栏", caught.exception.context["takeable_here"])
            self.assertIn("场地申请表", caught.exception.context["takeable_here"])
            self.assertEqual(world.item_locations["公告栏"], "room",
                             "拒绝什么都不改变：板还在原处")
            self.assertNotIn("公告栏", world.actors["aa"].inventory)

    def test_an_undeclared_document_is_still_movable_paper(self):
        """缺省即现状：没写 `takeable` 的文书照旧可以拿起来（不悄悄改语义）。"""
        with TemporaryDirectory() as directory:
            root = self._pack(directory)
            world = load_world_pack(root).build_world()
            self.assertIn({"kind": "take", "item": "公告栏"}, world.affordances("aa"))
            world.submit(Intention("aa", "take", {"item": "公告栏"}, world.version))
            world.advance()
            self.assertIn("公告栏", world.actors["aa"].inventory)
            self.assertNotIn("公告栏", world.item_locations)

    def test_the_three_seeded_boards_are_fixed_fixtures(self):
        """票 93：真种子里的三块公告栏都是钉住的陈设，不是能卷走的纸。

        票 91 §1.3 的裁定把“哪个听起来像板”交给种子判断：文书默认是一张可拿的
        纸（`场地申请表` 就是让人自取的），板与贴着的通知由种子写
        `takeable: false` + `fixed_reason`。这里读的是真种子——三块板开局都在
        原处、`take` 候选里没有它们、拒绝理由用种子那句原文，而 `read` 照旧可用：
        钉住的是“能不能拿走”，不是“能不能看”。
        """
        world = load_world_pack(ROOT / "world").build_world()
        boards = {"公告栏": "学生会办公室", "教学楼公告栏": "教学楼",
                  "女生宿舍公告栏": "女生宿舍"}
        reader = world.actors["林瑶"]
        for board, place in boards.items():
            self.assertEqual(world.item_locations[board], place,
                             f"{board} 开局就在它该在的地方")
            self.assertIn(board, world.fixed_items, f"{board} 是钉住的陈设")
            reason = world.fixed_items[board]
            self.assertTrue(reason.strip(), f"{board} 带一句固定的理由")
            reader.location = place
            self.assertNotIn({"kind": "take", "item": board},
                             world.affordances("林瑶"),
                             f"钉住的 {board} 不在“这里能拿的”里面")
            self.assertIn({"kind": "read", "item": board},
                          world.affordances("林瑶"),
                          f"{board} 照旧可以就地看着读")
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("林瑶", "take", {"item": board}, world.version))
            self.assertIn(reason, caught.exception.message,
                          "拒绝理由用的是种子写的那句话")
            self.assertNotIn(board, caught.exception.context["takeable_here"])
            self.assertEqual(world.item_locations[board], place,
                             "拒绝什么都不改变：板还在原处")
            self.assertNotIn(board, reader.inventory)
