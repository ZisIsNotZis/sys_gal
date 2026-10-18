"""半天检查点门只裁决锚点与路线，纹理（flavor）不裁决（ticket 105）。

`--half` 是检查点门，不是纹理审计：该日 anchors 必须达成，且（该日有路线
时）至少一条路线的 requires 达成；`ROUTES[N]["flavor"]` 的项只打印、标注
"纹理（不裁决）"，不影响退出码。这些测试在 ticket 105 之前的检查器上红——
旧实现把半天内每个检查项都当阻断项，于是只有纹理没达成的半天门直接判 FAIL
（真实 d1-pm 工件：d1-妈妈承诺、d1-林瑶自查审计包）。

运行：python3 -m unittest discover -s scripts -p 'test_*.py'
（或在 v4 目录下 python3 scripts/test_check_milestones_half_gate.py）
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


def _load_module(script=None):
    spec = importlib.util.spec_from_file_location(
        "check_milestones", SCRIPT if script is None else script)
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


def _counselor_lines():
    """路线[短信升级辅导员] 的前半：辅导员 ≥5 条发言 + 程序纪律语句。"""
    return [
        (13, 5, "统一口径先对齐：先交个人情况说明。"),
        (13, 10, "程序上按规矩来，别自己补写。"),
        (13, 20, "谁经手谁写，写清时间。"),
        (13, 30, "情况不明的就写情况不明。"),
        (13, 40, "材料交到我这里登记。"),
    ]


def _note_left(i, hour, minute, actor, note_id, text, location):
    return {"id": i, "time": _dt(hour, minute), "kind": "note_left",
            "actor": actor,
            "payload": {"location": location, "text": text,
                        "persist": True, "note": note_id},
            "visible_to": [actor], "world_version": i}


def _item_given(i, hour, minute, item, giver, receiver):
    return {"id": i, "time": _dt(hour, minute), "kind": "item_given",
            "actor": giver,
            "payload": {"item": item, "from": giver, "to": receiver},
            "visible_to": [giver, receiver], "world_version": i}


def _statement_deliveries():
    """路线[短信升级辅导员] 的后半：≥3 名角色交付个人情况说明。

    ticket 108 起这个判据以**交付物为证**（文稿留在辅导员办公室／give 给
    辅导员）；光在对话里说“情况说明”不再算，所以这里留的是真稿、交的是
    真件，而不是三条发言。时点全部放在 16:45 `statement_request` 程序发布
    之后——发布前的稿不是程序要求的交付（ticket 108 Comments）。"""
    return [
        (16, 50, "班长", "note-班长-1", "辅导员办公室"),
        (16, 55, "林瑶室友", "note-林瑶室友-2", "学生会办公室"),
        (17, 0, "陈默", "note-陈默-3", "辅导员办公室"),
    ]


def _pm_events(with_counselor=True, with_anchor=True):
    """d1-pm 夹具：锚点（d1-审计催办转达）与路线[短信升级辅导员]全过，
    路线[现场互证程序]与全部 flavor 未达成。"""
    events, i = [], 0
    for hour, minute, text in (_counselor_lines() if with_counselor else []):
        i += 1
        events.append(_speech(i, hour, minute, "辅导员", text, ["陈默", "林瑶"]))
    for hour, minute, actor, note_id, place in _statement_deliveries():
        i += 1
        events.append(_note_left(i, hour, minute, actor, note_id,
                                 "个人情况说明（3月16日）：只写自己经手的那一段。",
                                 place))
        if place != "辅导员办公室":
            i += 1
            events.append(_item_given(i, hour, minute + 2, note_id, actor, "辅导员"))
    if with_anchor:
        i += 1
        events.append(_speech(i, 16, 10, "陈默",
                             "16:00 的催办单我原样转达给辅导员了。", ["辅导员"]))
    return events


def _artifact(directory, events):
    path = Path(directory) / "artifact.json"
    path.write_text(json.dumps({"world_events": events, "agent_turns": [],
                                "sessions": {}}, ensure_ascii=False),
                    encoding="utf-8")
    return path


def _run_main(module, artifact, *args):
    argv = ["check_milestones.py", str(artifact), *args]
    buf = io.StringIO()
    old = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(buf):
            code = module.main()
    finally:
        sys.argv = old
    return code, buf.getvalue()


class HalfGateFlavorTests(unittest.TestCase):
    """只有纹理未达成的半天必须放行，锚点未达成必须拦下。"""

    def test_flavor_only_failure_exits_zero_and_reports_the_texture(self):
        module = _load_module()
        with TemporaryDirectory() as directory:
            path = _artifact(directory, _pm_events())
            code, out = _run_main(module, path, "--half", "d1-pm")
        self.assertEqual(code, 0, out)
        # 纹理项照旧逐项打印，并标注不裁决。
        self.assertIn("[FAIL] d1-妈妈承诺", out)
        self.assertIn("纹理（不裁决）", out)
        self.assertIn("d1-妈妈承诺", out.split("纹理（不裁决）：")[1])
        self.assertIn("结果：全部通过", out)
        self.assertIn("纹理未达成，不裁决", out)
        # 锚点与路线成立是放行的前提，不是绕开它们。
        self.assertIn("锚点：全部达成", out)
        self.assertIn("路线[短信升级辅导员]：成立", out)
        # 另一条路线未成立不阻断（路线网是"至少一条"）。
        self.assertIn("路线[现场互证程序]：未成立", out)

    def test_anchor_failure_exits_one(self):
        module = _load_module()
        with TemporaryDirectory() as directory:
            path = _artifact(directory, _pm_events(with_anchor=False))
            code, out = _run_main(module, path, "--half", "d1-pm")
        self.assertEqual(code, 1, out)
        self.assertIn("[FAIL] d1-审计催办转达", out)
        self.assertIn("锚点：未达成 d1-审计催办转达", out)
        self.assertIn("结果：未通过：d1-审计催办转达", out)

    def test_no_valid_route_blocks_even_when_anchors_hold(self):
        module = _load_module()
        with TemporaryDirectory() as directory:
            path = _artifact(directory, _pm_events(with_counselor=False))
            code, out = _run_main(module, path, "--half", "d1-pm")
        self.assertEqual(code, 1, out)
        self.assertIn("锚点：全部达成", out)
        self.assertIn("路线网（无有效路线）", out)

    def test_am_half_defers_routes_to_the_other_half(self):
        module = _load_module()
        with TemporaryDirectory() as directory:
            path = _artifact(directory, [])
            code, out = _run_main(module, path, "--half", "d1-am")
        self.assertIn("待后续（requires 在另一个半天）", out)
        self.assertIn("本半天没有可完整判定的路线：路线条件不阻断", out)
        self.assertIn("结果：未通过：", out)   # 上午锚点仍未达成
        self.assertEqual(code, 1, out)

    def test_day_without_route_net_keeps_original_semantics(self):
        module = _load_module()
        net = module.ROUTES.pop(1)
        try:
            with TemporaryDirectory() as directory:
                path = _artifact(directory, _pm_events())
                code, out = _run_main(module, path, "--half", "d1-pm")
        finally:
            module.ROUTES[1] = net
        self.assertEqual(code, 1, out)
        self.assertIn("无路线网定义", out)
        self.assertIn("退回旧语义", out)

    def test_day_view_still_uses_the_route_network(self):
        module = _load_module()
        with TemporaryDirectory() as directory:
            path = _artifact(directory, _pm_events())
            code, out = _run_main(module, path, "--day", "1")
        self.assertIn("路线网判定（第 1 天）", out)
        self.assertEqual(code, 1, out)   # 上午锚点没有证据


class RouteNetCategoryTests(unittest.TestCase):
    """分类是门禁的唯一依据，所以每天的三类必须正好覆盖当天检查项。"""

    def test_anchors_routes_and_flavor_partition_every_day(self):
        module = _load_module()
        for day, checks in module.MILESTONES.items():
            net = module.ROUTES[day]
            day_ids = {c["id"] for c in checks}
            route_requires = [r for route in net["routes"] for r in route["requires"]]
            combined = list(net["anchors"]) + route_requires + list(net["flavor"])
            self.assertEqual(len(combined), len(set(combined)), day)
            # 跨日锚点（如 d1 的妈妈线指向 d2）不在当天检查项里，记待后续。
            crossday = {a for a in net["anchors"] if a not in day_ids}
            self.assertEqual(set(combined) - crossday, day_ids, day)
            self.assertEqual(
                {c["id"]: module.half_check_category(day, c["id"]) for c in checks},
                {c["id"]: ("anchor" if c["id"] in net["anchors"]
                          else "route" if c["id"] in route_requires
                          else "flavor")
                 for c in checks}, day)

    def test_a_new_unclassified_milestone_still_blocks(self):
        module = _load_module()
        verdict = module.half_gate_verdict(1, {"d1-未归类的新项": False})
        self.assertEqual(verdict["blocking"], ["d1-未归类的新项"])
        self.assertEqual(module.half_check_category(1, "d1-未归类的新项"),
                         "unclassified")


if __name__ == "__main__":
    unittest.main()
