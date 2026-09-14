"""Unit tests for the key-set KB row model (V4-AGENT-INTERFACE §3/§6).

A row is ``{keys, desc, status}``: the key set is both the row's identity and
its mention matcher. ``!always`` / ``!at=<time>`` are directive keys with
engine semantics; text keys are needles.
"""

import unittest
from datetime import datetime, timedelta, timezone

from harness.kb import (ALWAYS_OPEN_LIMIT, ActorKB, format_reminder_time, hits,
                        key_id, parse_reminder_time)

T0 = datetime(2026, 3, 16, 7, 0, tzinfo=timezone(timedelta(hours=8)))  # 周一


def seed_rows():
    return [
        {"keys": ["唐小岚"], "desc": "我，唐小岚，咖啡师。"},
        {"keys": ["!always", "草稿"], "desc": "弄清草稿是谁放的"},
        {"keys": ["半坡咖啡馆"], "desc": "校门口的独立咖啡馆"},
        {"keys": ["陈默", "常客"], "desc": "常来的学生，最近在查账"},
        {"keys": ["!at=3/16(周一) 08:30", "糕点铺"], "desc": "去后街糕点铺带话"},
    ]


class RowModelTests(unittest.TestCase):
    def test_identity_row_is_required(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            ActorKB("唐小岚", [{"keys": ["别人"]}], T0)

    def test_duplicate_key_set_rejected(self):
        rows = seed_rows() + [{"keys": ["半坡咖啡馆"], "desc": "重复"}]
        with self.assertRaisesRegex(ValueError, "duplicate key set"):
            ActorKB("唐小岚", rows, T0)

    def test_short_and_unknown_directive_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, "too short"):
            ActorKB("唐小岚", [{"keys": ["唐小岚"]}, {"keys": ["x"], "desc": "y"}], T0)
        with self.assertRaisesRegex(ValueError, "unknown directive"):
            ActorKB("唐小岚", [{"keys": ["唐小岚"]}, {"keys": ["!nope"], "desc": "y"}], T0)

    def test_unparseable_scheduled_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "unparseable scheduled"):
            ActorKB("唐小岚", [{"keys": ["唐小岚"]},
                               {"keys": ["!at=13/45(周八) 99:99"], "desc": "y"}], T0)

    def test_legacy_fields_rows_are_rejected_for_seeds(self):
        # V4-AGENT-INTERFACE §6: seeds and update_memory speak the key-set
        # model only; `fields` survives solely for old checkpoints.
        with self.assertRaisesRegex(ValueError, "needs at least one key"):
            ActorKB("唐小岚", [{"fields": {"person": "唐小岚"}, "desc": "我"}], T0)

    def test_legacy_fields_snapshot_still_restores(self):
        snapshot = {
            "actor_id": "唐小岚", "shown_seq": 1, "overflow": [], "pending_recall": [],
            "rows": [
                {"fields": {"person": "唐小岚", "self": True}, "id": "i",
                 "desc": "我，唐小岚。"},
                {"fields": {"todo": True}, "id": "t", "desc": "带话"},
                {"fields": {"reminder": "3/16(周一) 08:30"}, "id": "r", "desc": "别迟到"},
            ]}
        kb = ActorKB.from_snapshot(snapshot, T0)
        lines = kb.due_lines(T0, "", limit=8)
        self.assertTrue(any("!always" in line for line in lines))
        self.assertTrue(any("!at=" in line for line in lines))

    def test_render_labels_the_first_key_and_counts_the_rest(self):
        kb = ActorKB("唐小岚", [
            {"keys": ["唐小岚"], "desc": "我"},
            {"keys": ["老家属院", "家属院", "老街坊"], "desc": "旧居民区"},
        ], T0)
        line = next(l for l in kb.due_lines(T0, "老家属院", limit=8) if "旧居民区" in l)
        self.assertTrue(line.startswith("[老家属院 +2]"), line)

    def test_reminder_parsing_is_strict(self):
        self.assertEqual(parse_reminder_time("3/16(周一) 08:30", T0),
                         T0.replace(hour=8, minute=30))
        self.assertIsNone(parse_reminder_time("3/16(周二) 08:30", T0))
        self.assertIsNone(parse_reminder_time("不是时间", T0))
        self.assertEqual(format_reminder_time(T0), "3/16(周一) 07:00")


class HitsTests(unittest.TestCase):
    def test_substring_matches_in_both_directions(self):
        self.assertTrue(hits(["陈默"], ["陈默的爸爸"]))
        self.assertTrue(hits(["2013年台风夜"], ["2013年台风"]))
        self.assertFalse(hits(["陈默"], ["林瑶"]))

    def test_particles_are_neutral_to_matching(self):
        self.assertTrue(hits(["老家属院地下室"], ["老家属院的地下室"]))

    def test_directives_are_not_needles(self):
        self.assertFalse(hits(["!always"], ["!always"]))


class ReplayTests(unittest.TestCase):
    def test_always_and_scheduled_replay_without_a_mention(self):
        kb = ActorKB("唐小岚", seed_rows(), T0)
        lines = kb.due_lines(T0, "无关的一句话", limit=8)
        self.assertTrue(any(line.startswith("[!always 草稿]") for line in lines))
        self.assertTrue(any(line.startswith("[!at=") for line in lines))
        self.assertFalse(any("独立咖啡馆" in line for line in lines))

    def test_mention_gates_text_rows(self):
        kb = ActorKB("唐小岚", seed_rows(), T0)
        lines = kb.due_lines(T0, "陈默走进来，问了一杯咖啡。", limit=8)
        self.assertTrue(any("常来的学生" in line for line in lines))
        self.assertFalse(any("独立咖啡馆" in line for line in lines))

    def test_haystack_accepts_a_list_of_queries(self):
        kb = ActorKB("唐小岚", seed_rows(), T0)
        lines = kb.due_lines(T0, ["今天很安静", "半坡咖啡馆里没人"], limit=8)
        self.assertTrue(any("独立咖啡馆" in line for line in lines))

    def test_overflow_drains_before_new_rows(self):
        rows = [{"keys": ["唐小岚"], "desc": "我"}] + [
            {"keys": ["!always", f"事{i}"], "desc": f"第{i}件"} for i in range(12)]
        kb = ActorKB("唐小岚", rows, T0)
        first = kb.due_lines(T0, "", limit=8)
        self.assertEqual(len(first), 8)
        self.assertEqual(len(kb.due_lines(T0, "", limit=8)), 4)

    def test_due_reminders_and_auto_close(self):
        kb = ActorKB("唐小岚", seed_rows(), T0)
        later = T0.replace(hour=9, minute=0)
        due = kb.due_reminders(later)
        self.assertEqual(len(due), 1)
        kb.close_scheduled(due[0]["id"])
        self.assertEqual(kb.due_reminders(later), [])
        self.assertEqual(key_id(["!at=3/16(周一) 08:30", "糕点铺"]), due[0]["id"])


class MutationTests(unittest.TestCase):
    def setUp(self):
        self.kb = ActorKB("唐小岚", seed_rows(), T0)

    def test_open_edit_close_by_exact_keys(self):
        for op, desc in (("open", "记一笔"), ("edit", "改一笔"), ("close", None)):
            row = {"keys": ["新事", "笔记"], "op": op}
            if desc:
                row["desc"] = desc
            errs, _, _ = self.kb.apply_ops([row], T0)
            self.assertEqual(errs, [], f"{op}: {errs}")

    def test_fuzzy_unique_match_applies_with_a_warning(self):
        errs, telemetry, warnings = self.kb.apply_ops(
            [{"keys": ["草稿"], "op": "edit", "desc": "改了"}], T0)
        self.assertEqual(errs, [])
        self.assertTrue(warnings)
        self.assertEqual(telemetry["fuzzy_match"], 1)

    def test_ambiguous_match_reports_candidates(self):
        self.kb.apply_ops([{"keys": ["陈默", "甲事"], "op": "open", "desc": "1"},
                           {"keys": ["陈默", "乙事"], "op": "open", "desc": "2"}], T0)
        errs, _, _ = self.kb.apply_ops([{"keys": ["陈默"], "op": "close"}], T0)
        self.assertTrue(any("ambiguous" in e for e in errs))

    def test_no_match_and_unknown_op(self):
        errs, _, _ = self.kb.apply_ops([{"keys": ["没有的"], "op": "close"}], T0)
        self.assertTrue(any("no row keyed" in e for e in errs), errs)
        errs, _, _ = self.kb.apply_ops([{"keys": ["草稿"], "op": "rename"}], T0)
        self.assertTrue(any("unknown op" in e for e in errs))

    def test_identity_row_cannot_be_closed(self):
        errs, _, _ = self.kb.apply_ops([{"keys": ["唐小岚"], "op": "close"}], T0)
        self.assertTrue(any("identity" in e for e in errs))

    def test_always_limit_counts_open_always_rows(self):
        rows = [{"keys": ["唐小岚"], "desc": "我"}] + [
            {"keys": ["!always", f"事{i}"], "desc": "x"} for i in range(ALWAYS_OPEN_LIMIT)]
        kb = ActorKB("唐小岚", rows, T0)
        errs, _, _ = kb.apply_ops(
            [{"keys": ["!always", "多一件"], "op": "open", "desc": "y"}], T0)
        self.assertTrue(any("limit" in e for e in errs))

    def test_reopen_after_close(self):
        self.kb.apply_ops([{"keys": ["新事"], "op": "open", "desc": "x"}], T0)
        self.kb.apply_ops([{"keys": ["新事"], "op": "close"}], T0)
        errs, _, _ = self.kb.apply_ops([{"keys": ["新事"], "op": "open", "desc": "回来了"}], T0)
        self.assertEqual(errs, [])


class RecallTests(unittest.TestCase):
    def setUp(self):
        self.kb = ActorKB("唐小岚", seed_rows(), T0)

    def test_recall_by_keyword(self):
        self.assertTrue(any("独立咖啡馆" in line
                            for line in self.kb.force_recall(["咖啡馆"])))

    def test_recall_can_list_always_rows(self):
        self.assertTrue(any("弄清草稿" in line
                            for line in self.kb.force_recall(["!always"])))

    def test_recall_closed_rows_are_gated(self):
        self.kb.apply_ops([{"keys": ["新事"], "op": "open", "desc": "内容"}], T0)
        self.kb.apply_ops([{"keys": ["新事"], "op": "close"}], T0)
        self.assertFalse(any("内容" in line for line in self.kb.force_recall(["新事"])))
        self.assertTrue(any("内容" in line
                            for line in self.kb.force_recall(["新事"], closed=True)))

    def test_match_rows_returns_matches_and_empty_without_query(self):
        self.assertTrue(self.kb.match_rows(["陈默"]))
        self.assertEqual(self.kb.match_rows([]), [])

    def test_recall_surfaces_next_turn_exactly_once(self):
        self.kb.force_recall(["咖啡馆"])
        first = self.kb.due_lines(T0, "", limit=8)
        self.assertTrue(any("独立咖啡馆" in line for line in first))
        second = self.kb.due_lines(T0, "", limit=8)
        self.assertFalse(any("独立咖啡馆" in line for line in second))


class PersistenceTests(unittest.TestCase):
    def test_snapshot_round_trip(self):
        kb = ActorKB("唐小岚", seed_rows(), T0)
        kb.apply_ops([{"keys": ["新事"], "op": "open", "desc": "记"}], T0)
        kb.due_lines(T0, "陈默", limit=8)
        restored = ActorKB.from_snapshot(kb.snapshot(), T0)
        self.assertEqual(restored.snapshot()["rows"], kb.snapshot()["rows"])

    def test_compaction_resets_last_shown(self):
        kb = ActorKB("唐小岚", seed_rows(), T0)
        kb.due_lines(T0, "", limit=8)
        kb.on_compaction()
        self.assertIsNone(kb._rows[frozenset({"唐小岚"})].last_shown)
