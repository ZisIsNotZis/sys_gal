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


if __name__ == "__main__":
    unittest.main()
