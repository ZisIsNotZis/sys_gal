"""D2 的两条判据必须有区分力（ticket 113 = 112 §D1-3-E7/E8）。

两条旧判据在 D1 工件上都能 PASS，而它们描述的事情在 D1 一次也没发生：

- `d2-恋爱私人对话` 只要两人同场互有发言。D1 已有 65 条这样的回合，全部是任务性
  对话（催办单、纸、核实、老周）。照旧判据进 D2，第一个同场回合就 PASS，
  “第一次非任务私人对话”可以完全没发生。
- `d2-审计说明提交` 只要当天有一条发言同时含“说明”与“提交”——“我还没提交说明”
  也能 PASS；而一份真文稿当面交上去、只说不交、迟到交，都分不开。

所以每条判据都配两支负控：**只有任务性同场对话的 D1 形态必须 FAIL**，
**只有真交付物/真私人对话的形态必须 PASS**，外加一支“迟到不等于按时”。

运行：python3 -m unittest discover -s scripts -p 'test_*.py'
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check_milestones.py"
DAY2 = "2026-03-17"

STATEMENT = "个人情况说明（3月17日）：我只写自己经手的那一段，不替别人补写。"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_milestones_d2", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dt(hour, minute, second=0):
    return f"{DAY2}T{hour:02d}:{minute:02d}:{second:02d}+08:00"


def _speech(i, hour, minute, actor, text, heard):
    return {"id": i, "time": _dt(hour, minute), "kind": "speech", "actor": actor,
            "payload": {"text": text, "heard": list(heard)},
            "visible_to": [actor] + list(heard), "world_version": i}


def _note_left(i, hour, minute, actor, note_id, text, location, second=0):
    return {"id": i, "time": _dt(hour, minute, second), "kind": "note_left",
            "actor": actor,
            "payload": {"location": location, "text": text,
                        "persist": True, "note": note_id},
            "visible_to": [actor], "world_version": i}


def _item_given(i, hour, minute, item, giver, receiver):
    return {"id": i, "time": _dt(hour, minute), "kind": "item_given", "actor": giver,
            "payload": {"item": item, "from": giver, "to": receiver},
            "visible_to": [giver, receiver], "world_version": i}


class PrivateTalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_module()

    def _check(self, events):
        return self.module._d2_romance_private_talk(events, [], {})

    def test_d1_shape_task_talk_with_third_party_fails(self):
        """D1 形态：两人同场、互有发言，但说的全是案子，而且在场还有别人。"""
        events = [
            _speech(1, 9, 10, "陈默", "催办单上写着说明最迟明早交，我先核对台账。", ["林瑶", "班长"]),
            _speech(2, 9, 12, "林瑶", "登记本这一栏我核过，导出件对不上。", ["陈默", "班长"]),
            _speech(3, 9, 15, "班长", "那我们把纸先领了。", ["陈默", "林瑶"]),
        ]
        ok, evd = self._check(events)
        self.assertFalse(ok, evd)
        self.assertIn("任务", evd)

    def test_task_talk_without_third_party_still_fails(self):
        """没有第三个人，但说的仍是案子上的事——这不是私人对话。"""
        events = [
            _speech(1, 12, 0, "陈默", "收件档的说明要交到辅导员办公室。", ["林瑶"]),
            _speech(2, 12, 2, "林瑶", "我这边台账还没核完。", ["陈默"]),
        ]
        ok, evd = self._check(events)
        self.assertFalse(ok, evd)

    def test_genuine_private_exchange_passes(self):
        events = [
            _speech(1, 17, 12, "陈默", "你以前也总坐这个角落？", ["林瑶"]),
            _speech(2, 17, 13, "林瑶", "嗯。这里下午的风最好，我常来。", ["陈默"]),
        ]
        ok, evd = self._check(events)
        self.assertTrue(ok, evd)
        self.assertIn("17:12", evd)

    def test_one_sided_monologue_fails(self):
        """只有一方开口（另一方没接），不是“对话”。"""
        events = [_speech(1, 17, 12, "陈默", "今天的风真好。", ["林瑶"])]
        ok, evd = self._check(events)
        self.assertFalse(ok, evd)


class AuditStatementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_module()

    def _check(self, events):
        return self.module._d2_audit_statement_filed(events, [], {})

    def test_saying_I_did_not_submit_fails(self):
        """旧判据的漏洞：一句话里同时有“说明”和“提交”就 PASS。"""
        events = [_speech(1, 8, 30, "班长", "我还没提交情况说明，缺的那份我下午补。",
                          ["辅导员"])]
        ok, evd = self._check(events)
        self.assertFalse(ok, evd)

    def test_real_delivery_at_the_count_passes(self):
        events = [
            _note_left(1, 7, 40, "陈默", "note-陈默-9", STATEMENT, "辅导员办公室"),
            _item_given(2, 8, 10, "note-陈默-9", "陈默", "辅导员"),
        ]
        ok, evd = self._check(events)
        self.assertTrue(ok, evd)
        self.assertIn("陈默", evd)

    def test_delivery_written_by_someone_else_does_not_count(self):
        """别人的稿子转交不算“本人的书面说明”。"""
        events = [
            _note_left(1, 7, 40, "林瑶", "note-林瑶-3", STATEMENT, "辅导员办公室"),
            _item_given(2, 8, 10, "note-林瑶-3", "陈默", "辅导员"),
        ]
        ok, evd = self._check(events)
        self.assertFalse(ok, evd)

    def test_late_delivery_is_reported_but_not_on_time(self):
        events = [
            _note_left(1, 13, 40, "林瑶", "note-林瑶-4", STATEMENT, "辅导员办公室"),
            _item_given(2, 14, 20, "note-林瑶-4", "林瑶", "辅导员"),
        ]
        ok, evd = self._check(events)
        self.assertFalse(ok, evd)
        self.assertIn("迟到", evd)

    def test_unrelated_note_does_not_count(self):
        """只认“说明材料”自己的名称：核对记录、值班记录不算。"""
        events = [
            _note_left(1, 7, 40, "陈默", "note-陈默-10",
                       "核对记录：三层走廊那盏灯报过后勤。", "辅导员办公室"),
            _item_given(2, 8, 10, "note-陈默-10", "陈默", "辅导员"),
        ]
        ok, evd = self._check(events)
        self.assertFalse(ok, evd)


if __name__ == "__main__":
    unittest.main()
