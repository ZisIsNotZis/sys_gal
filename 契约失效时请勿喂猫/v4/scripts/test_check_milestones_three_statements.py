"""三份个人说明以交付物为证，不看话看物（ticket 108）。

`d1-三份个人说明` 旧判据只数 speech/message 里出现"情况说明"四个字的角色：
真实交付（把说明留在辅导员办公室、把稿子 give 给辅导员、在收件文书上签名）
一律不算，而口头提到四个字就算。它同时错两次——假阴性（交了没说）和假阳性
（只说不交）。

新判据仍然是"三份、来自三名不同角色"，但证据是交付物，任一即可、按角色
去重（候选 = 经手过审计材料的四人）：
  a 文稿——该角色 leave_note 产生、正文读作"说明"的纸，且留在收件地点
    （辅导员办公室）或由作者 give 给收件人（辅导员）；
  b 签字——该角色对收件文书（个人情况说明程序／收件表）的
    document_annotated；
  c 发言提及降为辅助——只进证据行、本身不计数。
不足三人时证据行点名缺谁、以哪种证据缺。

两处收紧（同票 Comments，2026-10-18）各自有一支负控：名称只认"个人情况
说明／情况说明／书面说明"（裸"说明"、《XX核对说明》不算），时点只认 16:45
`statement_request` 程序发布之后的交付物（发布前的稿、交件、签字都不算）。
两支负控互不代替：名称对但时点早的不算，时点对但名称不对的也不算。

第三处收紧（ticket 109 §E8，同日）：文稿类还要求**写作时间**也在 16:45 之后
——`note_left` 自身的时间。只看出手时间的话，12:38 写的旧稿 19:41 再交一遍
就算作提交（真实工件 `100115` 对林瑶就是这么读的），所以“旧稿重交”另立一类：
不计入，且证据行写明原因。

运行：python3 -m unittest discover -s scripts -p 'test_*.py'
（或在 v4 目录下 python3 scripts/test_check_milestones_three_statements.py）
"""
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check_milestones.py"
DAY1 = "2026-03-16"
CID = "d1-三份个人说明"

STATEMENT = "个人情况说明（3月16日）：我只写自己经手的那一段，不替别人补写。"
INTAKE = "辅导员办公室"
# 程序发布时刻（manifest 的 statement_request）与它之前之后的两侧时点。
EARLY = (11, 18)
LATE = (16, 50)


def _load_module():
    spec = importlib.util.spec_from_file_location("check_milestones", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dt(hour, minute):
    return f"{DAY1}T{hour:02d}:{minute:02d}:00+08:00"


def _speech(i, hour, minute, actor, text, heard):
    return {"id": i, "time": _dt(hour, minute), "kind": "speech", "actor": actor,
            "payload": {"text": text, "heard": list(heard), "to": list(heard)},
            "visible_to": [actor] + list(heard), "world_version": i}


def _note_left(i, hour, minute, actor, note_id, text, location):
    return {"id": i, "time": _dt(hour, minute), "kind": "note_left", "actor": actor,
            "payload": {"location": location, "text": text,
                        "persist": True, "note": note_id},
            "visible_to": [actor], "world_version": i}


def _item_given(i, hour, minute, item, giver, receiver):
    return {"id": i, "time": _dt(hour, minute), "kind": "item_given", "actor": giver,
            "payload": {"item": item, "from": giver, "to": receiver},
            "visible_to": [giver, receiver], "world_version": i}


def _annotated(i, hour, minute, actor, document, location, annotation):
    return {"id": i, "time": _dt(hour, minute), "kind": "document_annotated",
            "actor": actor,
            "payload": {"document": document, "location": location,
                        "annotation": annotation},
            "visible_to": [actor], "world_version": i}


def _left_at_intake(i, hour, minute, actor, note_id, text=STATEMENT):
    """a：文稿留在收件地点。"""
    return _note_left(i, hour, minute, actor, note_id, text, INTAKE)


def _handed_over(i, hour, minute, actor, note_id):
    """a：写别处、当面交给收件人——只有"交付"这一类。"""
    return [_note_left(i, hour, minute, actor, note_id, STATEMENT, "学生会办公室"),
            _item_given(i + 1, hour, minute + 2, note_id, actor, "辅导员")]


def _signed(i, hour, minute, actor, document="个人情况说明程序"):
    """b：在收件文书上签字/批注。"""
    return _annotated(i, hour, minute, actor, document, INTAKE, "已写，当面交过。")


def _red_events():
    """两人有交付物，第三个人只在对话里说了"情况说明"。"""
    return [
        _left_at_intake(1, 16, 50, "陈默", "note-陈默-1"),
        *_handed_over(2, 17, 0, "林瑶", "note-林瑶-2"),
        _speech(4, 17, 10, "班长", "我的个人情况说明写好了，等一下交给辅导员。",
                ["陈默"]),
    ]


def _green_events():
    """三人各有 a/b 证据（均在 16:45 之后）：陈默只留文稿、林瑶只交稿、班长只签字。"""
    return [
        _left_at_intake(1, 16, 50, "陈默", "note-陈默-1"),
        *_handed_over(2, 17, 0, "林瑶", "note-林瑶-2"),
        _signed(5, 17, 10, "班长"),
    ]


def _old_draft_redelivered():
    """真实工件 `100115` 的形态：稿写于 12:38（程序发布前）、19:41 才交给
    辅导员。只有“交出时间”在后，写作时间在前。"""
    return [
        _note_left(1, 12, 38, "林瑶", "note-林瑶-12",
                   "绿荫校园社无障碍改造项目情况说明（3/16）：中庭透水砖有几块塌陷。",
                   "学生会办公室"),
        _item_given(2, 19, 41, "note-林瑶-12", "林瑶", "辅导员"),
    ]


def _negative_events():
    """三名不同角色都写了说明稿，但没一份到收件处、也没 give 给收件人。"""
    return [
        _note_left(1, 16, 50, "陈默", "note-陈默-1", STATEMENT, "男生宿舍"),
        _note_left(2, 16, 51, "林瑶", "note-林瑶-2", STATEMENT, "中庭"),
        _note_left(3, 16, 52, "班长", "note-班长-3", STATEMENT, "305教室"),
    ]


class ThreeStatementsEvidenceTests(unittest.TestCase):
    def setUp(self):
        # 实例属性（不是类属性），避免存下来的函数被变成绑定方法。
        module = _load_module()
        self.fn = next(c["fn"] for c in module.MILESTONES[1] if c["id"] == CID)

    def _verdict(self, events):
        return self.fn(events, [], {})

    # ---- 三支验收夹具 ---------------------------------------------------
    def test_red_two_deliveries_and_a_third_who_only_says_it_fails(self):
        ok, evd = self._verdict(_red_events())
        self.assertFalse(ok, evd)
        self.assertIn("只有 2 人", evd)
        # 缺口要点名是缺谁、以哪种证据缺。
        self.assertIn("班长（仅发言提及，无文稿/交付/签字）", evd)

    def test_green_one_signature_one_hand_over_one_paper_passes(self):
        ok, evd = self._verdict(_green_events())
        self.assertTrue(ok, evd)
        self.assertIn("3 份", evd)
        self.assertIn("签字", evd)

    def test_green_fixture_says_nothing_so_the_old_criterion_scored_zero(self):
        """旧判据只看发言：这三个人在对话里一个"情况说明"都没说，旧口径下
        必然 0 分。修复确实改变了判定，而不是把旧的结论换个说法。"""
        spoke = [e for e in _green_events()
                 if e["kind"] in ("speech", "message_sent", "message_delivered")
                 and "情况说明" in str(e["payload"].get("text", ""))]
        self.assertEqual(spoke, [])

    def test_negative_papers_that_never_reached_the_intake_fail(self):
        ok, evd = self._verdict(_negative_events())
        self.assertFalse(ok, evd)
        self.assertIn("只有 0 人", evd)

    # ---- 单类证据的边界（时点都在 16:45 之后，只让被检查的那一条起作用）----
    def test_a_note_at_the_intake_place_that_reads_as_no_statement_does_not_count(self):
        events = [
            _left_at_intake(1, 16, 50, "陈默", "note-陈默-1"),
            *_handed_over(2, 17, 0, "林瑶", "note-林瑶-2"),
            _left_at_intake(4, 17, 10, "班长", "note-班长-4",
                            "图书室值班记录（3/16）：椅子少了三把，等管理员回来再清点。"),
        ]
        self.assertFalse(self._verdict(events)[0])

    def test_handing_it_to_someone_other_than_the_recipient_is_not_delivery(self):
        events = [
            _left_at_intake(1, 16, 50, "陈默", "note-陈默-1"),
            _note_left(2, 17, 0, "林瑶", "note-林瑶-2", STATEMENT, "学生会办公室"),
            _item_given(3, 17, 2, "note-林瑶-2", "林瑶", "唐小岚"),
            _left_at_intake(4, 17, 10, "班长", "note-班长-4"),
        ]
        self.assertFalse(self._verdict(events)[0])

    def test_handing_over_someone_elses_paper_is_not_delivery(self):
        events = [
            _left_at_intake(1, 16, 50, "陈默", "note-陈默-1"),
            _note_left(2, 17, 0, "林瑶", "note-林瑶-2", STATEMENT, "学生会办公室"),
            # 辅导员把林瑶的稿还回来、或别人代交——都不是林瑶的交付。
            _item_given(3, 17, 2, "note-林瑶-2", "辅导员", "林瑶"),
            _left_at_intake(4, 17, 10, "班长", "note-班长-4"),
        ]
        self.assertFalse(self._verdict(events)[0])

    def test_signing_a_document_that_is_not_an_intake_surface_does_not_count(self):
        events = [
            _left_at_intake(1, 16, 50, "陈默", "note-陈默-1"),
            *_handed_over(2, 17, 0, "林瑶", "note-林瑶-2"),
            _annotated(5, 17, 10, "班长", "签到本", "校史档案室", "到岗"),
        ]
        self.assertFalse(self._verdict(events)[0])

    def test_speech_alone_never_satisfies_the_anchor(self):
        events = [_speech(i, 17, 10 + i, actor, "个人情况说明我写好了。", ["辅导员"])
                  for i, actor in enumerate(("陈默", "林瑶", "班长"), start=1)]
        ok, evd = self._verdict(events)
        self.assertFalse(ok, evd)
        self.assertIn("只有 0 人", evd)

    def test_the_same_note_left_and_handed_over_counts_once(self):
        """同一份稿既是文稿又交到了手上：仍只算一个人、一份。"""
        events = [
            *_handed_over(1, 16, 50, "陈默", "note-陈默-1"),
            _left_at_intake(3, 16, 50, "陈默", "note-陈默-1"),
            *_handed_over(4, 17, 0, "林瑶", "note-林瑶-4"),
            _signed(6, 17, 10, "班长"),
        ]
        ok, evd = self._verdict(events)
        self.assertTrue(ok, evd)
        self.assertIn("3 份", evd)


class StatementTighteningTests(unittest.TestCase):
    """两处收紧各自一支负控，互不代替：名称对但时点早的不算，时点对但名称
    不对的也不算。另验三份合格交付物各带类别与时间。"""

    def setUp(self):
        module = _load_module()
        self.fn = next(c["fn"] for c in module.MILESTONES[1] if c["id"] == CID)

    def _verdict(self, events):
        return self.fn(events, [], {})

    def test_a_check_note_before_the_publish_time_does_not_count(self):
        """真实工件 `085705` 的形态：陈默 11:18 交的《学生会审计包核对说明》
        两条规则各自排除它（名称不是说明材料，时点也在 16:45 之前），且它
        连“发布前有过交付物”都不算——它不是这一判据认的证据类型。"""
        events = [
            _left_at_intake(1, *EARLY, "陈默", "note-陈默-1",
                            "学生会审计包核对说明（3/16）：汇总表有两个总额未标明用途。"),
            _item_given(2, 11, 20, "note-陈默-1", "陈默", "辅导员"),
        ]
        ok, evd = self._verdict(events)
        self.assertFalse(ok, evd)
        self.assertIn("只有 0 人", evd)
        self.assertIn("陈默（无任何交付物）", evd)

    def test_a_check_note_after_the_publish_time_does_not_count_either(self):
        """时点对了名称也不对：两条规则各自成立，不互相代替。"""
        events = [
            _left_at_intake(1, *LATE, "陈默", "note-陈默-1",
                            "学生会审计包核对说明（3/16）：行项目齐全。"),
        ]
        self.assertFalse(self._verdict(events)[0])

    def test_a_statement_left_before_the_publish_time_does_not_count(self):
        """名称完全合格（《书面说明》）但留在 16:45 之前：不是程序要求的交付。"""
        events = [
            _left_at_intake(1, 13, 46, "林瑶", "note-林瑶-1",
                            "书面说明：我核对到的学生会审计包可见情况为……"),
        ]
        ok, evd = self._verdict(events)
        self.assertFalse(ok, evd)
        self.assertIn("只有 0 人", evd)
        self.assertIn("16:45 前有文稿 13:46", evd)
        self.assertIn("不计入", evd)

    def test_delivery_before_the_publish_time_does_not_count(self):
        """文稿和交件都在 16:45 前（真实工件里林瑶的形态）：交付同样不计。"""
        events = [
            _note_left(1, 16, 9, "林瑶", "note-林瑶-1", STATEMENT, INTAKE),
            _item_given(2, 16, 43, "note-林瑶-1", "林瑶", "辅导员"),
        ]
        ok, evd = self._verdict(events)
        self.assertFalse(ok, evd)
        self.assertIn(
            "林瑶（16:45 前有文稿 16:09 留在辅导员办公室《个人情况说明》；"
            "交付 16:43 交给辅导员，不计入）", evd)

    def test_a_bare_explanation_note_after_the_publish_time_does_not_count(self):
        """时点合格、但名称不对（裸“说明”、《核对说明》）：不计。"""
        events = [
            _left_at_intake(1, *LATE, "陈默", "note-陈默-1",
                            "说明（3/16）：包内汇总表有两个总额未标明用途。"),
            _left_at_intake(2, 17, 0, "班长", "note-班长-2",
                            "学生会审计核对说明（3/16）：行项目齐全。"),
        ]
        ok, evd = self._verdict(events)
        self.assertFalse(ok, evd)
        self.assertIn("只有 0 人", evd)
        self.assertIn("陈默（无任何交付物）", evd)

    def test_three_classes_after_the_publish_time_each_named_with_its_time(self):
        ok, evd = self._verdict(_green_events())
        self.assertTrue(ok, evd)
        self.assertIn("16:45 程序发布后的交付物", evd)
        self.assertIn("文稿 16:50 留在辅导员办公室《个人情况说明》", evd)
        self.assertIn("交付 17:02 交给辅导员", evd)
        self.assertIn("签字 17:10 在《个人情况说明程序》签字/批注", evd)


class StatementWritingTimeTests(unittest.TestCase):
    """写作时间门槛（ticket 109 §E8）：重交旧稿不算，证据行写明原因。

    红绿对照：把 `SCRIPT` 指向一份去掉这道门槛的 `check_milestones.py`，
    `_old_draft_redelivered()` 会被计成 1 人（与真实工件 `100115` 的旧读数
    一致），配上另外两份真交付时旧实现就 PASS；现实现是 0 人／2 人——
    改动确实改变了判定，而不是换了个说法。"""

    def setUp(self):
        module = _load_module()
        self.fn = next(c["fn"] for c in module.MILESTONES[1] if c["id"] == CID)

    def _verdict(self, events):
        return self.fn(events, [], {})

    def test_an_old_draft_redelivered_after_the_publish_time_does_not_count(self):
        ok, evd = self._verdict(_old_draft_redelivered())
        self.assertFalse(ok, evd)
        self.assertIn("只有 0 人", evd)
        self.assertIn("林瑶（旧稿重交，不计：12:38 写的《情况说明》19:41 交给辅导员）", evd)
        # 交出在发布之后，不能被说成“16:45 前有过交付”。
        self.assertNotIn("16:45 前有交付 19:41", evd)

    def test_redelivering_an_old_draft_cannot_be_the_third_statement(self):
        """两人在发布后真交了稿，林瑶只重交旧稿：仍只有 2 人，FAIL。"""
        events = [
            _left_at_intake(1, 16, 50, "陈默", "note-陈默-1"),
            _left_at_intake(3, 17, 0, "班长", "note-班长-3"),
            *_old_draft_redelivered(),
        ]
        ok, evd = self._verdict(events)
        self.assertFalse(ok, evd)
        self.assertIn("只有 2 人", evd)
        self.assertIn("林瑶（旧稿重交，不计", evd)

    def test_a_draft_written_after_the_publish_time_still_counts_when_handed_over(self):
        """写作时间门槛不误杀正常交付：稿写于 17:00、17:02 交出，仍算一份。"""
        events = [
            *_handed_over(1, 17, 0, "林瑶", "note-林瑶-1"),
            _left_at_intake(3, 16, 50, "陈默", "note-陈默-3"),
            _signed(5, 17, 10, "班长"),
        ]
        ok, evd = self._verdict(events)
        self.assertTrue(ok, evd)
        self.assertIn("交付 17:02 交给辅导员", evd)


def _check_line(out):
    return next(line for line in out.splitlines() if line.strip().startswith(
        (f"[PASS] {CID}", f"[FAIL] {CID}")))


def _run_main(module, artifact, *args):
    argv = ["check_milestones.py", str(artifact), *args]
    buf = io.StringIO()
    old = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(buf):
            module.main()
    finally:
        sys.argv = old
    return buf.getvalue()


class ThreeStatementsCliTests(unittest.TestCase):
    """`--day 1` 与 `--half d1-pm` 跑同一个判定函数，两处口径一致；差别只在
    事件窗口（半天只看这一半），所以夹具事件都放在下午。"""

    def _lines(self, events):
        module = _load_module()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            path.write_text(json.dumps({"world_events": events, "agent_turns": [],
                                        "sessions": {}}, ensure_ascii=False),
                            encoding="utf-8")
            out = {}
            for mode in (["--day", "1"], ["--half", "d1-pm"]):
                out[mode[0]] = _check_line(_run_main(module, path, *mode))
        return out

    def test_green_fixture_passes_in_the_day_and_pm_views(self):
        for mode, line in self._lines(_green_events()).items():
            self.assertIn(f"[PASS] {CID}", line, (mode, line))

    def test_red_fixture_fails_in_the_day_and_pm_views(self):
        for mode, line in self._lines(_red_events()).items():
            self.assertIn(f"[FAIL] {CID}", line, (mode, line))


if __name__ == "__main__":
    unittest.main()
