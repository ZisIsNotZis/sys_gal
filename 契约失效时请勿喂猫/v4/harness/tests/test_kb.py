"""Unit tests for the per-actor KB row model (V4-AGENT-INTERFACE §3/§4/§6)."""

import unittest
from datetime import datetime, timedelta, timezone

from harness.kb import (ActorKB, KNOWLEDGE_REPLAY_MINUTES, REMINDER_REPLAY_MINUTES,
                        TODO_OPEN_LIMIT, format_reminder_time, parse_reminder_time)

T0 = datetime(2026, 3, 16, 7, 0, tzinfo=timezone(timedelta(hours=8)))  # 周一


def seed_rows():
    return [
        {"fields": {"person": "唐小岚", "self": True}, "id": "identity",
         "desc": "我，唐小岚，咖啡师。"},
        {"fields": {"todo": True}, "id": "draft_claim", "desc": "弄清草稿是谁放的"},
        {"fields": {"location": "半坡咖啡馆"}, "id": "scene", "desc": "校门口的独立咖啡馆"},
        {"fields": {"person": "陈默"}, "id": "chen", "desc": "常来的学生，最近在查账"},
        {"fields": {"reminder": "3/16(周一) 08:30"}, "id": "bread_run",
         "desc": "去后街糕点铺带话"},
    ]


class SeedValidationTests(unittest.TestCase):
    def test_exactly_one_self_row_is_enforced(self):
        for rows in ([], seed_rows() + [{"fields": {"self": True}, "id": "self2", "desc": "我"}]):
            with self.assertRaises(ValueError) as ctx:
                ActorKB("唐小岚", rows, T0)
            self.assertIn("唐小岚", str(ctx.exception))

    def test_duplicate_seed_id_rejected(self):
        with self.assertRaises(ValueError):
            ActorKB("唐小岚", seed_rows() + [seed_rows()[0]], T0)

    def test_turn_zero_rows_flood_first_message(self):
        # docs §6 (修订): turn-0 泛洪只覆盖无条件行（self/todo/reminder）；
        # 实体行（person/location/item）永远提及集门控——未提及的实体
        # （如不在场的哨子）不得在首轮浮现（用户裁决 2026-09-08）。
        kb = ActorKB("唐小岚", seed_rows(), T0)
        lines = kb.due_lines(T0, set(), limit=8)
        self.assertEqual(len(lines), 3)
        self.assertIn("[person=唐小岚]: 我，唐小岚，咖啡师。", lines)
        self.assertIn("[todo=true]: 弄清草稿是谁放的", lines)
        self.assertTrue(any(line.startswith("[reminder=") for line in lines))
        self.assertNotIn("[location=半坡咖啡馆]", str(lines))
        self.assertNotIn("[person=陈默]", str(lines))


class ReminderParsingTests(unittest.TestCase):
    def test_canonical_format_parses_and_checks_weekday(self):
        when = parse_reminder_time("3/16(周一) 08:30", T0)
        assert when is not None
        self.assertEqual(when, T0.replace(hour=8, minute=30))
        self.assertEqual(format_reminder_time(when), "3/16(周一) 08:30")

    def test_wrong_weekday_is_rejected(self):
        self.assertIsNone(parse_reminder_time("3/16(周二) 08:30", T0))

    def test_iso_format_parses(self):
        self.assertEqual(parse_reminder_time("2026-03-16T09:00:00+08:00", T0),
                         T0.replace(hour=9))

    def test_garbage_is_rejected(self):
        for value in ("", "明天早上", "13/16(周一) 08:30", None, 123):
            self.assertIsNone(parse_reminder_time(value, T0))

    def test_unparseable_reminder_rejects_the_row(self):
        kb = ActorKB("唐小岚", seed_rows(), T0)
        errors, telemetry = kb.apply_ops(
            [{"op": "open", "id": "bad_rem", "fields": {"reminder": "下周二"},
              "desc": "x"}], T0)
        self.assertEqual(errors, ["[id=bad_rem] unparseable reminder time: 下周二"])
        self.assertEqual(telemetry["applied"], 0)


class ApplyOpsTests(unittest.TestCase):
    def setUp(self):
        self.kb = ActorKB("唐小岚", seed_rows(), T0)

    def test_open_edit_close_lifecycle(self):
        errors, _ = self.kb.apply_ops(
            [{"op": "open", "id": "note1", "fields": {"item": "校报草稿"},
              "desc": "压在吧台"},
             {"op": "edit", "id": "note1", "desc": "压在吧台，无署名"}], T0)
        self.assertEqual(errors, [])
        # open/edit only refresh last_shown (docs §4) — no immediate echo;
        # the row resurfaces at its interval under a matching mention set.
        later = T0 + timedelta(minutes=KNOWLEDGE_REPLAY_MINUTES + 1)
        self.assertIn("[item=校报草稿]: 压在吧台，无署名",
                      self.kb.due_lines(later, {"校报草稿"}))
        errors, _ = self.kb.apply_ops([{"op": "close", "id": "note1"}], T0)
        self.assertEqual(errors, [])
        self.assertNotIn("note1", str(self.kb.due_lines(T0.replace(hour=23),
                                                       {"校报草稿"})))
        self.assertFalse(any("压在吧台" in line
                             for line in self.kb.force_recall(None, ["note1"])))
        self.assertTrue(any("压在吧台" in line for line in
                            self.kb.force_recall(None, ["note1"], closed=True)))

    def test_closed_row_cannot_be_edited_but_can_reopen(self):
        self.kb.apply_ops([{"op": "open", "id": "n1", "fields": {"person": "陈默"},
                            "desc": "a"}, {"op": "close", "id": "n1"}], T0)
        errors, _ = self.kb.apply_ops([{"op": "edit", "id": "n1", "desc": "b"}], T0)
        self.assertEqual(errors, ["[id=n1] wrong state: closed rows can only be reopened"])
        errors, _ = self.kb.apply_ops([{"op": "open", "id": "n1", "desc": "b"}], T0)
        self.assertEqual(errors, [])
        later = T0 + timedelta(minutes=KNOWLEDGE_REPLAY_MINUTES + 1)
        self.assertIn("[person=陈默]: b", self.kb.due_lines(later, {"陈默"}))

    def test_duplicate_open_in_one_patch(self):
        errors, _ = self.kb.apply_ops(
            [{"op": "open", "id": "n1", "fields": {"person": "陈默"}, "desc": "first"},
             {"op": "open", "id": "n1", "fields": {"person": "陈默"}, "desc": "second"}], T0)
        self.assertEqual(errors, ["[id=n1] duplicate row in patch"])
        later = T0 + timedelta(minutes=KNOWLEDGE_REPLAY_MINUTES + 1)
        self.assertIn("[person=陈默]: first", self.kb.due_lines(later, {"陈默"}))

    def test_open_on_open_row_is_tolerated_as_edit(self):
        errors, telemetry = self.kb.apply_ops(
            [{"op": "open", "id": "chen", "desc": "常来的学生，最近在查账，态度谨慎"}], T0)
        self.assertEqual(errors, [])
        self.assertEqual(telemetry["tolerated_open_on_open"], 1)
        later = T0 + timedelta(minutes=KNOWLEDGE_REPLAY_MINUTES + 1)
        self.assertIn("[person=陈默]: 常来的学生，最近在查账，态度谨慎",
                      self.kb.due_lines(later, {"陈默"}))

    def test_todo_open_limit_counts_open_rows_only(self):
        ops = [{"op": "open", "id": f"t{i}", "fields": {"todo": True}, "desc": f"t{i}"}
               for i in range(TODO_OPEN_LIMIT - 1)]
        errors, _ = self.kb.apply_ops(ops, T0)
        self.assertEqual(errors, [])
        errors, _ = self.kb.apply_ops(
            [{"op": "open", "id": "over", "fields": {"todo": True}, "desc": "x"}], T0)
        self.assertEqual(errors, [f"[id=over] todo limit reached ({TODO_OPEN_LIMIT})"])
        self.kb.apply_ops([{"op": "close", "id": "t0"}], T0)
        errors, _ = self.kb.apply_ops(
            [{"op": "open", "id": "over", "fields": {"todo": True}, "desc": "x"}], T0)
        self.assertEqual(errors, [])

    def test_free_fields_are_tolerated_with_telemetry(self):
        _, telemetry = self.kb.apply_ops(
            [{"op": "open", "id": "n1", "fields": {"mood": "紧张"}, "desc": "x"}], T0)
        self.assertEqual(telemetry["free_field"], 1)

    def test_missing_desc_or_fields_rejected(self):
        errors, _ = self.kb.apply_ops(
            [{"op": "open", "id": "n1", "fields": {"person": "陈默"}},
             {"op": "open", "id": "n2", "desc": "x"},
             {"op": "edit", "id": "ghost", "desc": "x"},
             {"op": "frobnicate", "id": "n3"}], T0)
        self.assertEqual(errors[0], "[id=n1] missing desc")
        self.assertEqual(errors[1], "[id=n2] missing fields")
        self.assertEqual(errors[2], "[id=ghost] no match")
        self.assertTrue(errors[3].startswith("[id=n3] unknown op"))


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.kb = ActorKB("唐小岚", seed_rows(), T0)
        self.kb.due_lines(T0, set())  # turn-0 flood: everything shown once

    def test_intervals_by_field_type(self):
        self.assertEqual(self.kb.due_lines(T0 + timedelta(minutes=29), set()), [])
        lines = self.kb.due_lines(T0 + timedelta(minutes=REMINDER_REPLAY_MINUTES), set())
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("[reminder="))
        lines = self.kb.due_lines(T0 + timedelta(minutes=60), set())
        # at exactly 60min both the todo (60) and the re-due reminder (30+30) fire
        self.assertIn("[todo=true]: 弄清草稿是谁放的", lines)

    def test_mention_set_gates_entity_rows(self):
        # close the time-driven rows (and the unconditional identity row) so
        # only entity-gated rows remain
        self.kb.apply_ops([{"op": "close", "id": "bread_run"},
                           {"op": "close", "id": "draft_claim"},
                           {"op": "close", "id": "identity"}], T0)
        now = T0 + timedelta(minutes=KNOWLEDGE_REPLAY_MINUTES + 1)
        self.assertEqual(self.kb.due_lines(now, set()), [])
        self.assertEqual(self.kb.due_lines(now, {"陈默"}),
                         ["[person=陈默]: 常来的学生，最近在查账"])

    def test_multifield_row_takes_max_interval(self):
        self.kb.apply_ops([{"op": "close", "id": "bread_run"},
                           {"op": "close", "id": "draft_claim"}], T0)
        self.kb.apply_ops([{"op": "open", "id": "mix",
                            "fields": {"todo": True, "person": "陈默"},
                            "desc": "问陈默草稿的事"}], T0)
        # todo alone would be due at 60min; person's 120min dominates (m3).
        self.assertEqual(self.kb.due_lines(T0 + timedelta(minutes=90), set()), [])
        lines = self.kb.due_lines(T0 + timedelta(minutes=121), {"陈默"})
        self.assertIn("[todo=true]: 问陈默草稿的事", lines)

    def test_overflow_lines_clear_first(self):
        now = T0 + timedelta(minutes=KNOWLEDGE_REPLAY_MINUTES + 1)
        lines = self.kb.due_lines(now, set(), limit=1)
        self.assertTrue(lines[0].startswith("[reminder="))
        # with an empty mention set only todo/reminder rows are candidates
        # (entity rows are mention-gated, docs M7) — the overflowed todo
        # clears first next turn, before any newly due row would.
        nxt = self.kb.due_lines(now + timedelta(minutes=1), set(), limit=8)
        # the overflowed todo clears first; the identity row (120min interval,
        # unconditional) is newly due and follows it
        self.assertEqual(nxt, ["[todo=true]: 弄清草稿是谁放的",
                               "[person=唐小岚]: 我，唐小岚，咖啡师。"],
                         "overflowed line must clear before new due rows")

    def test_due_reminders_and_auto_close(self):
        # reminder 08:30 = T0 + 90min (T0 is 07:00)
        due = self.kb.due_reminders(T0 + timedelta(minutes=31))
        self.assertEqual([d["id"] for d in due], [])
        due = self.kb.due_reminders(T0 + timedelta(minutes=91))
        self.assertEqual([d["id"] for d in due], ["bread_run"])
        self.assertEqual(due[0]["rendered"],
                         "[reminder=3/16(周一) 08:30]: 去后街糕点铺带话")
        self.kb.close_reminder("bread_run")
        self.assertEqual(self.kb.due_reminders(T0 + timedelta(hours=5)), [])


class RecallTests(unittest.TestCase):
    def setUp(self):
        self.kb = ActorKB("唐小岚", seed_rows(), T0)
        self.kb.due_lines(T0, set())  # turn-0 flood

    def test_force_recall_surfaces_next_turn_exactly_once(self):
        lines = self.kb.force_recall(None, ["chen"], limit=8)
        self.assertEqual(lines, ["[person=陈默]: 常来的学生，最近在查账"])
        surfaced = self.kb.due_lines(T0 + timedelta(minutes=1), set(), limit=8)
        self.assertEqual(surfaced.count("[person=陈默]: 常来的学生，最近在查账"), 1)
        # refreshed by the surfacing: not due again inside the interval
        later = T0 + timedelta(minutes=1 + KNOWLEDGE_REPLAY_MINUTES - 2)
        self.assertNotIn("[person=陈默]: 常来的学生，最近在查账",
                         self.kb.due_lines(later, {"陈默"}))

    def test_force_recall_by_kind(self):
        lines = self.kb.force_recall(["reminder"], None, limit=8)
        self.assertEqual(lines, ["[reminder=3/16(周一) 08:30]: 去后街糕点铺带话"])

    def test_force_recall_closed_rows_gated(self):
        self.kb.apply_ops([{"op": "open", "id": "n1", "fields": {"person": "陈默"},
                            "desc": "a"}, {"op": "close", "id": "n1"}], T0)
        self.assertEqual(self.kb.force_recall(None, ["n1"]), [])
        self.assertEqual(len(self.kb.force_recall(None, ["n1"], closed=True)), 1)

    def test_recall_order_oldest_last_shown_first(self):
        # recall surfaces rows oldest-last_shown first (docs §2: 按创建游戏时
        # 刻倒序 → last_shown 最旧优先).
        self.kb.apply_ops([{"op": "open", "id": "p1", "fields": {"person": "甲"},
                            "desc": "1"}], T0)
        self.kb.apply_ops([{"op": "open", "id": "p2", "fields": {"person": "乙"},
                            "desc": "2"}], T0 + timedelta(minutes=10))
        lines = self.kb.force_recall(None, ["p1", "p2"], limit=8)
        self.assertEqual(lines, ["[person=甲]: 1", "[person=乙]: 2"])
        # touching p2 again makes it the most recent → it sorts last
        self.kb.apply_ops([{"op": "edit", "id": "p2", "desc": "2（更新）"}],
                          T0 + timedelta(minutes=20))
        self.kb.force_recall(None, ["p1", "p2"], limit=8)
        self.kb.due_lines(T0 + timedelta(minutes=21), set())  # consume the queue
        lines = self.kb.force_recall(None, ["p1", "p2"], limit=8)
        self.assertEqual(lines, ["[person=甲]: 1", "[person=乙]: 2（更新）"])


class CompactionTests(unittest.TestCase):
    def test_compaction_resets_last_shown_but_not_closed(self):
        kb = ActorKB("唐小岚", seed_rows(), T0)
        kb.due_lines(T0, set())
        kb.apply_ops([{"op": "open", "id": "n1", "fields": {"person": "陈默"},
                       "desc": "a"}, {"op": "close", "id": "n1"}], T0)
        kb.on_compaction()
        lines = kb.due_lines(T0, {"唐小岚", "半坡咖啡馆", "陈默"})
        self.assertEqual(len(lines), 5)
        self.assertNotIn("n1", str(lines))


class SnapshotTests(unittest.TestCase):
    def test_round_trip_preserves_rows_status_and_overflow(self):
        kb = ActorKB("唐小岚", seed_rows(), T0)
        kb.due_lines(T0, set(), limit=2)  # turn-0 flood truncated → overflow
        kb.apply_ops([{"op": "open", "id": "n1", "fields": {"person": "陈默"},
                       "desc": "a"}, {"op": "close", "id": "n1"}], T0)
        state = kb.snapshot()
        clone = ActorKB.from_snapshot(state, T0)
        self.assertEqual(clone.snapshot(), state)
        later = T0 + timedelta(hours=6)
        self.assertEqual(len(clone.due_lines(later, {"陈默", "半坡咖啡馆"}, limit=8)), 5)


class FieldsLookupTests(unittest.TestCase):
    """docs §6 (修订): update_memory rows may omit id and locate by fields
    unique match among open rows (zero → "no match", multiple → "ambiguous")."""

    def setUp(self):
        self.kb = ActorKB("唐小岚", seed_rows(), T0)

    def test_id_less_edit_matches_unique_fields(self):
        errors, _ = self.kb.apply_ops(
            [{"op": "edit", "fields": {"todo": True}, "desc": "改了"}], T0)
        self.assertEqual(errors, [])
        todos = [r for r in self.kb._rows.values() if r.id == "draft_claim"]
        self.assertEqual(todos[0].desc, "改了")

    def test_id_less_lookup_covers_open_rows_only(self):
        # docs §6: fields 定位只在 open 行中查找——closed 行重开必须带 id。
        self.kb.apply_ops([{"op": "close", "id": "draft_claim"}], T0)
        errors, _ = self.kb.apply_ops(
            [{"op": "open", "fields": {"todo": True}, "desc": "重新翻开"}], T0)
        self.assertEqual(errors, ["[fields={'todo': True}] no match"])
        # with the id the reopen works
        errors, _ = self.kb.apply_ops(
            [{"op": "open", "id": "draft_claim", "desc": "重新翻开"}], T0)
        self.assertEqual(errors, [])
        self.assertEqual(self.kb._rows["draft_claim"].status, "open")

    def test_id_less_zero_match_reports_no_match(self):
        errors, _ = self.kb.apply_ops(
            [{"op": "edit", "fields": {"person": "不存在的人"}, "desc": "x"}], T0)
        self.assertEqual(len(errors), 1)
        self.assertIn("no match", errors[0])
        self.assertIn("不存在的人", errors[0])

    def test_id_less_ambiguous_match_reports_ambiguous(self):
        self.kb.apply_ops(
            [{"op": "open", "id": "p1", "fields": {"person": "陈默"}, "desc": "1"},
             {"op": "open", "id": "p2", "fields": {"person": "陈默"}, "desc": "2"}], T0)
        errors, _ = self.kb.apply_ops(
            [{"op": "edit", "fields": {"person": "陈默"}, "desc": "x"}], T0)
        self.assertEqual(len(errors), 1)
        self.assertIn("ambiguous", errors[0])

    def test_explicit_id_still_works(self):
        errors, _ = self.kb.apply_ops(
            [{"op": "edit", "id": "draft_claim", "desc": "用 id 定位"}], T0)
        self.assertEqual(errors, [])
        self.assertEqual(self.kb._rows["draft_claim"].desc, "用 id 定位")
