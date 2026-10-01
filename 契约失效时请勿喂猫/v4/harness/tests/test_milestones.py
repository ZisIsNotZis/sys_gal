"""Story-milestone route-network gates (issue 36).

The d1 discrepancy anchor ("d1-台账差异记录") must be satisfied by a visible
evidence chain, not by one hard-coded route. Two legal routes:

  A 亲读互证 — both MCs personally read the paper ledger and the export.
  B 当面传达 — one reader states the specific discrepancy values (22:05/23:30)
    face-to-face to the other MC, who acknowledges the discrepancy as still
    pending in their own speech.

Anti-omniscient: the values must be spoken by someone who actually read the
originals and heard by the other MC. A global notice carrying the values, or a
line the other MC never heard, must not pass. The half and whole-day views of
the anchor must agree.

These tests fail against the pre-issue-36 checker, which required 陈默 *and*
林瑶 to read both originals and looked for the values in any day text.
"""
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).parents[2]
DAY1 = "2026-03-16"

TELL = "纸质台账和导出件对不上：两台抽水泵的时间从22:05变成23:30，呼入少了一通。"
ACK = "至于这份台账差异要交什么材料、由谁负责，我目前不知道。"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "check_milestones", ROOT / "scripts" / "check_milestones.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dt(hour, minute):
    return f"{DAY1}T{hour:02d}:{minute:02d}:00+08:00"


def _read(i, hour, minute, actor, document):
    return {"id": i, "time": _dt(hour, minute), "kind": "document_read",
            "actor": actor, "payload": {"document": document},
            "visible_to": [actor], "world_version": i}


def _speech(i, hour, minute, actor, text, heard):
    return {"id": i, "time": _dt(hour, minute), "kind": "speech", "actor": actor,
            "payload": {"text": text, "heard": list(heard), "to": list(heard)},
            "visible_to": [actor] + list(heard), "world_version": i}


def _global_notice(i, hour, minute, text):
    return {"id": i, "time": _dt(hour, minute), "kind": "world_event",
            "actor": None, "payload": {"event": "probe", "notice": text},
            "visible_to": [], "world_version": i}


def _am(events):
    """The --half d1-am event subset exactly as check_milestones.main filters it."""
    return [e for e in events
            if str(e["time"]).startswith(DAY1)
            and 0 <= int(str(e["time"])[11:13]) < 13]


class DiscrepancyRouteTests(unittest.TestCase):
    def setUp(self):
        # Instance attribute (not a class attribute) so the stored function is
        # not turned into a bound method.
        module = _load_module()
        self.fn = next(c["fn"] for c in module.MILESTONES[1]
                       if c["id"] == "d1-台账差异记录")

    def _ok(self, events):
        ok, _ = self.fn(events, [], {})
        return ok

    # ---- route A: 亲读互证 ------------------------------------------------
    def test_both_actors_reading_both_originals_pass(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _read(3, 7, 24, "林瑶", "2013年台风台账"),
            _read(4, 7, 29, "林瑶", "2013年外借记录导出件"),
        ]
        self.assertTrue(self._ok(events))

    # ---- route B: 当面传达 + 承认待核 ------------------------------------
    def test_reader_tells_and_hearer_acknowledges_pending_pass(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _speech(3, 7, 29, "陈默", TELL, ["林瑶"]),
            _speech(4, 7, 31, "林瑶", ACK, ["陈默"]),
        ]
        self.assertTrue(self._ok(events))

    def test_symmetric_reader_is_linyao_pass(self):
        events = [
            _read(1, 7, 23, "林瑶", "2013年台风台账"),
            _read(2, 7, 28, "林瑶", "2013年外借记录导出件"),
            _speech(3, 7, 29, "林瑶", TELL, ["陈默"]),
            _speech(4, 7, 31, "陈默", ACK, ["林瑶"]),
        ]
        self.assertTrue(self._ok(events))

    # ---- anti-omniscient / strictness ------------------------------------
    def test_global_notice_values_unseen_by_actors_do_not_pass(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _global_notice(3, 7, 30, "台账 22:05 与导出件 23:30 存在差异。"),
        ]
        self.assertFalse(self._ok(events))

    def test_values_not_heard_by_the_other_mc_do_not_pass(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _speech(3, 7, 29, "陈默", TELL, ["林瑶室友"]),
            _speech(4, 7, 31, "林瑶", ACK, ["陈默"]),
        ]
        self.assertFalse(self._ok(events))

    def test_non_reader_stating_values_does_not_pass(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _speech(3, 7, 29, "林瑶", TELL, ["陈默"]),
            _speech(4, 7, 31, "陈默", ACK, ["林瑶"]),
        ]
        self.assertFalse(self._ok(events))

    def test_reader_tells_without_specific_values_does_not_pass(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _speech(3, 7, 29, "陈默", "台账和导出件对不上，呼入少了一通。", ["林瑶"]),
            _speech(4, 7, 31, "林瑶", ACK, ["陈默"]),
        ]
        self.assertFalse(self._ok(events))

    def test_reader_tells_but_other_never_acknowledges_does_not_pass(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _speech(3, 7, 29, "陈默", TELL, ["林瑶"]),
            _speech(4, 7, 31, "林瑶", "好，我知道了。", ["陈默"]),
        ]
        self.assertFalse(self._ok(events))

    def test_acknowledgement_must_be_the_other_mc_in_their_own_speech(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _speech(3, 7, 29, "陈默", TELL, ["林瑶", "林瑶室友"]),
            _speech(4, 7, 31, "林瑶室友", ACK, ["陈默", "林瑶"]),
        ]
        self.assertFalse(self._ok(events))

    def test_acknowledgement_before_the_tell_does_not_pass(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _speech(3, 7, 27, "林瑶", ACK, ["陈默"]),
            _speech(4, 7, 29, "陈默", TELL, ["林瑶"]),
        ]
        self.assertFalse(self._ok(events))

    # ---- half / whole-day consistency ------------------------------------
    def test_half_subset_and_full_day_agree_on_am_evidence(self):
        events = [
            _read(1, 7, 23, "陈默", "2013年台风台账"),
            _read(2, 7, 28, "陈默", "2013年外借记录导出件"),
            _speech(3, 7, 29, "陈默", TELL, ["林瑶"]),
            _speech(4, 7, 31, "林瑶", ACK, ["陈默"]),
            _global_notice(5, 14, 5, "台账 22:05 与导出件 23:30 存在差异。"),
        ]
        self.assertEqual(self._ok(events), self._ok(_am(events)))
        self.assertTrue(self._ok(_am(events)))

    def test_pm_only_evidence_does_not_satisfy_the_am_anchor(self):
        events = [
            _read(1, 14, 23, "陈默", "2013年台风台账"),
            _read(2, 14, 28, "陈默", "2013年外借记录导出件"),
            _speech(3, 14, 29, "陈默", TELL, ["林瑶"]),
            _speech(4, 14, 31, "林瑶", ACK, ["陈默"]),
        ]
        self.assertFalse(self._ok(_am(events)))


class CheckMilestonesCliTests(unittest.TestCase):
    """Half-day checkpoint gate end to end: the anchor passes for the shipped
    route (one reader tells, the other acknowledges) without requiring both to
    personally read the originals."""

    def _artifact(self, directory):
        events = [
            _speech(1, 7, 5, "宿管阿姨", "登记本的事我们还在问。", ["陈默"]),
            _speech(2, 7, 6, "班长", "登记本我去核对。", ["陈默"]),
            _speech(3, 7, 7, "辅导员", "登记本按规矩登记。", ["陈默"]),
            _read(4, 7, 23, "陈默", "2013年台风台账"),
            _read(5, 7, 28, "陈默", "2013年外借记录导出件"),
            _speech(6, 7, 29, "陈默", TELL, ["林瑶"]),
            _speech(7, 7, 31, "林瑶", ACK, ["陈默"]),
            _speech(8, 7, 32, "林瑶", "我们先按规矩来。", ["陈默"]),
        ]
        path = Path(directory) / "artifact.json"
        path.write_text(json.dumps({"world_events": events,
                                    "agent_turns": [], "sessions": {}}),
                        encoding="utf-8")
        return path

    def test_half_d1_am_passes_with_route_b_evidence(self):
        module = _load_module()
        with TemporaryDirectory() as directory:
            path = self._artifact(directory)
            argv = ["check_milestones.py", str(path), "--half", "d1-am"]
            buf = io.StringIO()
            old = sys.argv
            sys.argv = argv
            try:
                with contextlib.redirect_stdout(buf):
                    code = module.main()
            finally:
                sys.argv = old
        out = buf.getvalue()
        self.assertIn("[PASS] d1-台账差异记录", out, out)
        self.assertEqual(code, 0, out)


class InnerHealthMetricTests(unittest.TestCase):
    """Ticket 38: the system-health block reports the inner fill rate and a
    conservative count of inner monologue that leaked into broadcast speech.
    Printed for review, never gating the exit code."""

    def _health(self, data):
        return _load_module().health_report(data, 1)

    def test_inner_fill_rate_and_suspected_speech_leak_are_counted(self):
        data = {
            "agent_turns": [
                {"perception": {"time": _dt(7, 0)}, "inner": "我在盘算。",
                 "error": None},
                {"perception": {"time": _dt(7, 1)}, "inner": None,
                 "error": None},
            ],
            "world_events": [
                _speech(1, 7, 2, "陈默", "（记性这东西……）", ["林瑶"]),
                _speech(2, 7, 3, "陈默", '{"inner":"漏出来了","name":"speak"}', []),
                _speech(3, 7, 4, "陈默", "正常的一句话", []),
            ],
            "sessions": {},
        }
        report = self._health(data)
        self.assertEqual(report["inner填充率"], "1/2")
        self.assertEqual(report["疑似心声混进speech"], 2)


class NpcSleepHealthMetricTests(unittest.TestCase):
    """Ticket 45: the system-health block must surface a whole-day NPC sleep
    (zero turns), not only the gap between turns — the gap metric alone made
    the very failure class it was built for invisible."""

    def _health(self, data):
        return _load_module().health_report(data, 1)

    def test_zero_turn_and_single_turn_npcs_are_named(self):
        def npc_turn(actor, hour, minute):
            return {"actor": actor, "role": "npc",
                    "perception": {"time": _dt(hour, minute)}}

        data = {
            "agent_turns": [
                {"actor": "陈默", "role": "mc", "perception": {"time": _dt(7, 0)}},
                npc_turn("宿管阿姨", 7, 5),
                npc_turn("宿管阿姨", 9, 30),        # 2h25m gap
                npc_turn("陈默妈", 8, 0),            # only one turn today
                # 食堂大妈: role is known from another day, zero turns today.
                {"actor": "食堂大妈", "role": "npc",
                 "perception": {"time": "2026-03-17T08:00:00+08:00"}},
            ],
            # 陈默爸 has a session but never turned in the whole artifact.
            "sessions": {"陈默": {}, "宿管阿姨": {}, "陈默妈": {},
                         "食堂大妈": {}, "陈默爸": {}},
            "world_events": [],
        }
        report = self._health(data)
        self.assertEqual(report["NPC最长沉寂（相邻回合间隔）"], "2h25m（宿管阿姨）")
        zero = report["零回合NPC"]
        self.assertIn("食堂大妈", zero)
        self.assertIn("陈默爸", zero)
        self.assertNotIn("宿管阿姨", zero)
        self.assertEqual(zero.split("（")[0], "2")
        self.assertEqual(report["回合最少NPC"], "1（陈默妈）")

    def test_no_npc_turns_is_reported_as_zero_gap_with_the_roster(self):
        data = {
            "agent_turns": [
                {"actor": "陈默", "role": "mc", "perception": {"time": _dt(7, 0)}},
            ],
            "sessions": {"陈默": {}, "宿管阿姨": {}},
            "world_events": [],
        }
        report = self._health(data)
        self.assertEqual(report["NPC最长沉寂（相邻回合间隔）"], "0")
        self.assertEqual(report["零回合NPC"], "1（宿管阿姨）")
        self.assertEqual(report["回合最少NPC"], "0")


class HandoverClaimHealthMetricTests(unittest.TestCase):
    """Ticket 65: the system-health block reports a review-only count of a
    same-day hand-over assertion with no corresponding `item_given` event.
    Printed for review, never gating the exit code."""

    @staticmethod
    def _item_given(i, hour, minute, item, giver, receiver):
        return {"id": i, "time": _dt(hour, minute), "kind": "item_given",
                "actor": giver,
                "payload": {"item": item, "from": giver, "to": receiver},
                "visible_to": [giver, receiver], "world_version": i}

    def test_a_real_handover_the_same_day_suppresses_the_reading(self):
        """The exact line from real-20261001T121425 where 食堂大妈 said "豆浆
        包子趁烫，端好" with no item event behind it — counted — and the same
        line with a real `item_given` that day — not counted."""
        module = _load_module()
        claim = _speech(1, 9, 34, "食堂大妈",
                        "来——你的，豆浆包子趁烫，端好。刷卡啊小伙子。", ["陈默"])
        hits = module.delivery_claims_without_a_handover([claim], 1)
        self.assertTrue(hits, "食堂大妈的端好没有对应 item_given，却未报出")
        self.assertEqual(hits[0]["actor"], "食堂大妈")
        self.assertEqual(hits[0]["phrase"], "端好")

        given = self._item_given(2, 9, 33, "一份餐食", "食堂大妈", "陈默")
        self.assertEqual(
            module.delivery_claims_without_a_handover([claim, given], 1), [],
            "当天真的递过东西时不得误报")

    def test_ordinary_completeness_and_conditional_phrases_do_not_fire(self):
        """Conservative by construction: "四样齐了", "三方到齐了" and a
        second-person conditional "你拿到了" must never count as a hand-over."""
        module = _load_module()
        benign = [
            _speech(1, 11, 4, "辅导员", "草稿可以定，四样齐了，签名落日期。", ["唐小岚"]),
            _speech(2, 12, 27, "班长", "三方到齐了。先答陈默那句要紧的。", ["陈默"]),
            _speech(3, 12, 38, "辅导员", "你拿到了，咱们一页一页看；你拿不出来就照实说。", ["唐小岚"]),
        ]
        self.assertEqual(module.delivery_claims_without_a_handover(benign, 1), [])

    def test_report_carries_the_handover_reading(self):
        module = _load_module()
        data = {
            "agent_turns": [],
            "world_events": [_speech(
                1, 11, 40, "食堂大妈",
                "闺女！你的齐了——荤菜给你挑的带脆骨那块。端好了找个座儿。",
                ["林瑶"])],
            "sessions": {},
        }
        report = module.health_report(data, 1)
        self.assertIn("1（", report["断言交付/取得但无item_given"])
        self.assertIn("食堂大妈", report["断言交付/取得但无item_given"])


if __name__ == "__main__":
    unittest.main()
