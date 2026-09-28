"""Unit tests for the key-set KB row model (V4-AGENT-INTERFACE §3/§6).

A row is ``{keys, desc, status}``: the key set is both the row's identity and
its mention matcher. ``!always`` / ``!at=<time>`` are directive keys with
engine semantics; text keys are needles.
"""

import unittest
from datetime import datetime, timedelta, timezone

from harness.kb import (ALWAYS_OPEN_LIMIT, ActorKB, format_reminder_time, hits,
                        key_id, parse_reminder_time, resolve_name)

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

    def test_unknown_directive_is_rejected_with_supported_shapes(self):
        kb = ActorKB("唐小岚", [{"keys": ["唐小岚"], "desc": "我"}], T0)
        errors, telemetry, _ = kb.apply_ops(
            [{"keys": ["!contactx", "李阿姨"], "op": "open", "desc": "联系人"}], T0)
        self.assertEqual(telemetry["applied"], 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown directive key", errors[0])
        self.assertIn('keys=["!always", "要紧的事"]', errors[0])
        self.assertIn('keys=["!contact", "<exact formal name you know>"', errors[0])
        self.assertFalse(any("李阿姨" in row["keys"] for row in kb.snapshot()["rows"]))

    def test_invalid_directives_explain_valid_actor_visible_shapes(self):
        kb = ActorKB("唐小岚", [{"keys": ["唐小岚"], "desc": "我"}], T0)
        errors, _, _ = kb.apply_ops(
            [{"keys": ["!always"], "op": "open", "desc": "记得"},
             {"keys": ["!contact"], "op": "open", "desc": "联系人"}], T0)
        self.assertEqual(len(errors), 2)
        self.assertIn('["!always", "要紧的事"]', errors[0])
        self.assertIn('["!contact", "<exact formal name you know>", "<your nickname>"]', errors[1])
        self.assertIn('"op": "open"', errors[1])

    def test_contact_must_name_a_registered_person_without_revealing_roster(self):
        kb = ActorKB("a", [{"keys": ["a"], "desc": "我"}], T0,
                     valid_contact_names={"a", "全局秘密角色甲", "全局秘密角色乙"})
        errors, _, _ = kb.apply_ops(
            [{"keys": ["!contact", "姨妈"], "op": "open", "desc": "认识的人"}], T0)
        self.assertEqual(len(errors), 1)
        self.assertIn("not another registered actor", errors[0])
        self.assertIn("exact formal name you know", errors[0])
        self.assertNotIn("全局秘密角色甲", errors[0])
        self.assertNotIn("全局秘密角色乙", errors[0])

    def test_weekday_mismatch_error_includes_a_valid_scheduled_key(self):
        kb = ActorKB("唐小岚", [{"keys": ["唐小岚"], "desc": "我"}], T0)
        errors, _, _ = kb.apply_ops(
            [{"keys": ["!at=3/16(周二) 08:30", "糕点铺"],
              "op": "open", "desc": "带话"}], T0)
        self.assertEqual(len(errors), 1)
        self.assertIn("!at=3/17(周二) 08:30", errors[0])
        self.assertIn('["!at=3/17(周二) 08:30", "要办的事"]', errors[0])

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

    def test_render_lists_every_key_fully(self):
        # Ticket 22: the model cannot expand a `+N` abbreviation — every
        # addressable key is spelled out on the label.
        kb = ActorKB("唐小岚", [
            {"keys": ["唐小岚"], "desc": "我"},
            {"keys": ["老家属院", "家属院", "老街坊"], "desc": "旧居民区"},
            {"keys": ["重复", "重复"], "desc": "normalize 去重"},
        ], T0)
        line = next(l for l in kb.due_lines(T0, "老家属院", limit=8) if "旧居民区" in l)
        self.assertTrue(line.startswith("[老家属院 家属院 老街坊]"), line)
        self.assertNotIn("+", line.split("]")[0])
        dup_line = next(l for l in kb.due_lines(T0, "重复", limit=8) if "去重" in l)
        self.assertEqual(dup_line.split("]")[0].count("重复"), 1)

    def test_reminder_parsing_is_strict(self):
        self.assertEqual(parse_reminder_time("3/16(周一) 08:30", T0),
                         T0.replace(hour=8, minute=30))
        self.assertIsNone(parse_reminder_time("3/16(周二) 08:30", T0))
        self.assertIsNone(parse_reminder_time("不是时间", T0))
        self.assertEqual(format_reminder_time(T0), "3/16(周一) 07:00")


class HitsTests(unittest.TestCase):
    def test_name_resolution_rejects_exact_normalization_collisions(self):
        resolved, note = resolve_name("妈妈", {"妈妈", "妈 妈"})
        self.assertIsNone(resolved)
        self.assertIn("ambiguous exact name", note or "")
        self.assertIn("妈妈", note or "")

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

    def test_no_match_error_suggests_nearest_keys_and_ops(self):
        """Ruling 2026-09-22: the no-row error is actionable — per unmatched
        key it lists the nearest existing keys and the open/edit guidance."""
        self.kb.apply_ops([{"keys": ["2013年台风台账"], "op": "open", "desc": "旧账"}],
                          T0)
        errs, _, _ = self.kb.apply_ops(
            [{"keys": ["2013年台风台账", "2013年外借记录导出件"], "op": "edit"}], T0)
        self.assertEqual(len(errs), 1)
        message = errs[0]
        self.assertIn("no row keyed", message)
        self.assertIn("最接近的现有键", message)
        self.assertIn("2013年台风台账", message)  # a real existing key is suggested
        self.assertIn("op=open", message)
        self.assertIn("op=edit", message)

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

    def test_update_memory_rejects_a_contact_alias_already_owned_by_another_person(self):
        rows = [{"keys": ["陈默妈"], "desc": "我"},
                {"keys": ["!contact", "林瑶", "李阿姨"], "desc": "认识林瑶"}]
        kb = ActorKB("陈默妈", rows, T0,
                     valid_contact_names={"陈默妈", "林瑶", "陈默"})
        errors, telemetry, _ = kb.apply_ops(
            [{"keys": ["!contact", "陈默", "李阿姨"],
              "op": "open", "desc": "认识陈默"}], T0)
        self.assertEqual(telemetry["applied"], 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("already tied to '林瑶'", errors[0])
        self.assertFalse(any("陈默" in row["keys"]
                             for row in kb.snapshot()["rows"]
                             if "!contact" in row["keys"]))

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
