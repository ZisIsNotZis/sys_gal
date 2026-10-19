"""一沓纸有容量；值班 npc 在排程里就位（ticket 113 = 112 §D1-3-E1/E2）。

E1（纸是单件耗材）：`leave_note on=<沓>` 把整叠纸写成一张便条。真实工件
（D1 第三次全天验收）里 18:25 陈默取走唯一一份「说明用纸」，18:27 写掉，
18:42 起班长/林瑶室友/林瑶/陈默/辅导员依次 `take` 失败，19:00–22:00 收件档
零交件。根因不是缺 id（票 110 加了六个 id 也没解决），是“一沓”在世界里只有
一张纸的容量。

现在一件纸可以声明 `sheets: N`：写一张只少一张，纸还是纸，别人拿去还能接着
写；用到最后一张时，那张纸才变成那份文稿（旧语义，不写 `sheets` 时也仍是它）。

E2（收件人不在收件档）：18:00–22:00 辅导员在自己的办公室里 0 回合。制度、通知、
她自己的知识行都写着“十九点到二十一点我在办公室”，但世界没有任何机制把她放到
岗位上。新排程效果 `place_actor` 只允许 npc——把玩家角色“放”到某处就是替他做主。
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from harness.engine import AsyncEngine
from harness.kernel import ActorState, Intention, LocationState, World
from harness.replay import replay_world
from harness.world_loader import _validate, load_world_pack

START = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
SHEET_DESC = "一沓空白纸，正面还空着，可以顺手写一张。"


def _world(*, sheets: int | None = 3, item_at: str = "room") -> World:
    """One room, two actors, one stack of paper (unless `sheets=None`: a single
    sheet, i.e. the pre-ticket-113 semantics)."""
    return World(
        start=START,
        actors=[ActorState("a", "room"), ActorState("b", "room")],
        locations=[LocationState("room")],
        item_locations={"空白纸": item_at},
        entity_descriptions={"空白纸": SHEET_DESC},
        item_sheets={"空白纸": sheets} if sheets is not None else None)


def _write(world: World, actor: str, text: str = "情况说明：当天的班是我顶的。") -> None:
    world.submit(Intention(actor, "leave_note",
                           {"text": text, "on": "空白纸"}, world.version))
    world.advance()


class StackCapacityTests(unittest.TestCase):
    def test_one_write_spends_one_sheet_and_leaves_the_paper_usable(self):
        w = _world(sheets=3)
        _write(w, "a")
        # 写一张只少一张：纸还在原地，别人还能拿、还能写。
        self.assertEqual(w.item_sheets["空白纸"], 2)
        self.assertEqual(w.item_locations.get("空白纸"), "room")
        # 写出来的那份文稿是独立、可读、可递的东西，在作者手上。
        notes = list(w.persistent_notes)
        self.assertEqual(len(notes), 1)
        self.assertIn(notes[0], w.actors["a"].inventory)
        # 第二个人接着写同一沓纸：不再“已经被拿走或销毁”。
        _write(w, "b")
        self.assertEqual(w.item_sheets["空白纸"], 1)
        self.assertEqual(len(w.persistent_notes), 2)

    def test_last_sheet_is_consumed_into_the_note(self):
        w = _world(sheets=2)
        _write(w, "a")
        _write(w, "b")
        self.assertNotIn("空白纸", w.item_sheets)
        self.assertNotIn("空白纸", w.item_locations)
        notes = sorted(w.persistent_notes)
        self.assertEqual(len(notes), 2)
        # 纸用完了，第三个人确实拿不到——这是一条真实的“没有了”，不是误报。
        self.assertNotIn("空白纸", [o.get("item") for o in w.affordances("a")])

    def test_single_sheet_item_keeps_the_old_semantics(self):
        """不写 `sheets` 的纸仍然是一张纸：写一次就用完，那张纸就是文稿。"""
        w = _world(sheets=None)
        _write(w, "a")
        self.assertNotIn("空白纸", w.item_locations)
        self.assertNotIn("空白纸", w.actors["a"].inventory)
        notes = list(w.persistent_notes)
        self.assertEqual(len(notes), 1)
        self.assertIn(notes[0], w.actors["a"].inventory)

    def test_held_stack_stays_in_the_holders_hand(self):
        """写在自己的那沓纸上，纸还在自己手上——不是“变没了”，也不是“留在原地”。"""
        w = _world(sheets=5)
        w.submit(Intention("a", "take", {"item": "空白纸"}, w.version))
        w.advance()
        _write(w, "a")
        self.assertIn("空白纸", w.actors["a"].inventory)
        self.assertEqual(w.item_sheets["空白纸"], 4)

    def test_checkpoint_round_trip_keeps_the_sheet_count(self):
        w = _world(sheets=4)
        _write(w, "a")
        state = w.checkpoint_state()
        restored = World.from_checkpoint(_world(sheets=4), state)
        self.assertEqual(restored.item_sheets, {"空白纸": 3})

    def test_replay_rebuilds_the_same_sheet_count(self):
        w = _world(sheets=3)
        _write(w, "a")
        _write(w, "b", "情况说明：我也写一张。")
        log = [{"id": e.id, "time": e.time.isoformat(), "kind": e.kind,
                "actor": e.actor, "payload": dict(e.payload), "cause": e.cause,
                "visible_to": sorted(e.visible_to), "world_version": e.world_version}
               for e in w.event_log]
        rebuilt = replay_world(_world(sheets=3), log)
        self.assertEqual(rebuilt.item_sheets, w.item_sheets)
        self.assertEqual(sorted(rebuilt.persistent_notes),
                         sorted(w.persistent_notes))

    def test_receipt_states_how_many_sheets_remain(self):
        """回执必须说清“这张纸还剩几张”——旧回执不说，作者以为整沓都归了自己。"""
        w = _world(sheets=3)
        _write(w, "a")
        event = next(e for e in w.event_log if e.kind == "note_left")
        receipt = AsyncEngine.__new__(AsyncEngine)._leave_note_yield(
            w, "a", persist=True, note_id=str(event.payload["note"]),
            on="空白纸", sheets_left=int(event.payload["sheets_left"]))
        self.assertIn("还剩 2 张", receipt)

    def test_receipt_on_the_last_sheet_says_the_paper_became_the_note(self):
        w = _world(sheets=1)
        _write(w, "a")
        event = next(e for e in w.event_log if e.kind == "note_left")
        receipt = AsyncEngine.__new__(AsyncEngine)._leave_note_yield(
            w, "a", persist=True, note_id=str(event.payload["note"]),
            on="空白纸", sheets_left=int(event.payload["sheets_left"]))
        self.assertIn("最后一张", receipt)


class SeedCapacityTests(unittest.TestCase):
    """种子侧：纸的容量要真的写在种子里，否则引擎的修法在真工件上是死代码。"""

    @classmethod
    def setUpClass(cls):
        cls.pack = load_world_pack("world")
        cls.items = {str(row["id"]): row for row in cls.pack.items}

    def test_every_paper_stack_declares_capacity(self):
        for paper in ("空白纸", "可用纸笔", "一叠空白纸", "一包打印纸",
                      "草稿纸", "说明用纸"):
            with self.subTest(paper=paper):
                sheets = self.items[paper].get("sheets")
                self.assertIsInstance(sheets, int)
                self.assertGreater(sheets, 1)

    def test_declared_capacity_cannot_be_non_positive(self):
        fields = {name: tuple(dict(row) for row in getattr(self.pack, name))
                  for name in ("locations", "actors", "items", "documents",
                               "routes", "barriers", "scheduled")}
        items = [dict(row) for row in fields["items"]]
        items[0]["sheets"] = 0
        fields["items"] = tuple(items)
        with self.assertRaises(ValueError):
            _validate(fields, self.pack.manifest)


class PlaceActorTests(unittest.TestCase):
    def _world(self, scheduled):
        return World(start=START,
                     actors=[ActorState("老师", "家", role="npc"),
                             ActorState("学生", "教室", role="mc")],
                     locations=[LocationState("家"), LocationState("教室"),
                                LocationState("办公室")],
                     entity_descriptions={"办公室": "值班的办公室。"},
                     scheduled=scheduled)

    def test_scheduled_place_actor_puts_the_npc_on_duty(self):
        w = self._world([{"event": "intake", "time": (START + timedelta(hours=1)).isoformat(),
                          "notice": "十九点，办公室里有人值守。",
                          "effects": [{"op": "place_actor", "id": "老师",
                                       "location": "办公室"}]}])
        self.assertEqual(w.actors["老师"].location, "家")
        w.advance(until=START + timedelta(hours=2))
        self.assertEqual(w.actors["老师"].location, "办公室")
        # 牌子上写的是岗位，不是学生：玩家角色一步没动。
        self.assertEqual(w.actors["学生"].location, "教室")

    def test_replay_reproduces_the_placement(self):
        scheduled = [{"event": "intake", "time": (START + timedelta(hours=1)).isoformat(),
                      "notice": "十九点，办公室里有人值守。",
                      "effects": [{"op": "place_actor", "id": "老师",
                                   "location": "办公室"}]}]
        w = self._world(scheduled)
        w.advance(until=START + timedelta(hours=2))
        log = [{"id": e.id, "time": e.time.isoformat(), "kind": e.kind,
                "actor": e.actor, "payload": dict(e.payload), "cause": e.cause,
                "visible_to": sorted(e.visible_to), "world_version": e.world_version}
               for e in w.event_log]
        rebuilt = replay_world(self._world(scheduled), log)
        self.assertEqual(rebuilt.actors["老师"].location, "办公室")

    def test_loader_rejects_placing_a_player_character(self):
        pack = load_world_pack("world")
        fields = {name: tuple(dict(row) for row in getattr(pack, name))
                  for name in ("locations", "actors", "items", "documents",
                               "routes", "barriers", "scheduled")}
        fields["scheduled"] = fields["scheduled"] + ({
            "event": "ticket-113-illegal", "time": "2026-03-16T19:00:00+08:00",
            "effects": [{"op": "place_actor", "id": "陈默",
                         "location": "辅导员办公室"}]},)
        with self.assertRaises(ValueError):
            _validate(fields, pack.manifest)


if __name__ == "__main__":
    unittest.main()
