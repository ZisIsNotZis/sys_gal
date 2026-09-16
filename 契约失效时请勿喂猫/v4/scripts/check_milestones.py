#!/usr/bin/env python3
"""Story milestone checker (V4-AGENT-INTERFACE companion).

Usage:
    python3 scripts/check_milestones.py runs/<artifact>.json --day N

Evaluates day N's story milestones for a trajectory artifact as pure
functions over its world_events / agent_turns / sessions — no LLM calls.
Prints PASS/FAIL per check with one-line evidence; exit 0 iff all STORY
checks pass. System-health checks are printed and must be reviewed, but
do not gate the exit code.

Milestone definitions live in MILESTONES below (data per day), mirrored in
docs/V4-STORY-MILESTONES.md. Day dates: day 1 = 2026-03-16 (Mon) …
day 7 = 2026-03-22 (Sun, 3·16台风纪念活动).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

DAY_DATES = {
    1: "2026-03-16", 2: "2026-03-17", 3: "2026-03-18", 4: "2026-03-19",
    5: "2026-03-20", 6: "2026-03-21", 7: "2026-03-22",
}


# ---------------------------------------------------------------- helpers

def _texts(ev) -> list[str]:
    """All human-visible text of an event (speech/message bodies)."""
    pay = ev.get("payload", {}) or {}
    out = []
    for key in ("text", "content", "notice", "title"):
        v = pay.get(key)
        if isinstance(v, str) and v.strip():
            out.append(v)
    return out


def _day_events(world_events, day: int) -> list[dict]:
    date = DAY_DATES[day]
    return [e for e in world_events
            if str(e.get("time", "")).startswith(date)]


def _day_texts(world_events, day: int) -> list[tuple[str, str, str]]:
    """(time, actor, text) for every speech/message body that day."""
    out = []
    for e in _day_events(world_events, day):
        if e.get("kind") in ("speech", "message_delivered", "message_sent"):
            for txt in _texts(e):
                out.append((e["time"][11:16], str(e.get("actor") or "世界"), txt))
    return out


def _reads(world_events, day: int) -> list[tuple[str, str, str]]:
    """(time, actor, document) for document_read events that day."""
    return [(e["time"][11:16], str(e.get("actor")), str((e.get("payload") or {}).get("document", "")))
            for e in _day_events(world_events, day)
            if e.get("kind") == "document_read"]


def _mentioning(lines, *needles, all_of=True):
    """Lines containing all/any needles. Returns (count, evidence list)."""
    hits = []
    for t, actor, txt in lines:
        ok = all(n in txt for n in needles) if all_of else any(n in txt for n in needles)
        if ok:
            hits.append((t, actor, txt))
    return len(hits), hits


def _distinct_actors(hits) -> list[str]:
    seen, order = set(), []
    for _, actor, _ in hits:
        if actor not in seen:
            seen.add(actor)
            order.append(actor)
    return order


def _mk_check(cid, desc, fn):
    return {"id": cid, "desc": desc, "fn": fn}


# ---------------------------------------------------------------- day 1
# Backwards-consistent with runs/real-20260916T203133+0800-*.json (3/16).

def _d1_register_missing_known(ev, turns, sess):
    lines = _day_texts(ev, 1)
    n, hits = _mentioning(lines, "登记本")
    actors = _distinct_actors(hits)
    ok = len(actors) >= 3
    ev_lines = "; ".join(f"{t} {a}" for t, a, _ in hits[:3]) if hits else "无"
    return ok, f"{len(actors)} 个角色提及：{ev_lines}"


def _d1_discrepancy_recorded(ev, turns, sess):
    reads = _reads(ev, 1)
    chen = [r for r in reads if r[1] == "陈默" and "台账" in r[2]]
    chen2 = [r for r in reads if r[1] == "陈默" and "导出件" in r[2]]
    lin = [r for r in reads if r[1] == "林瑶" and "台账" in r[2]]
    ok_reads = chen and chen2 and lin
    lines = _day_texts(ev, 1)
    n, hits = _mentioning(lines, "22:05")
    n2, _ = _mentioning(lines, "23:30")
    both = min(n, n2) >= 1
    ok = bool(ok_reads) and both
    evd = f"陈默读档 {chen[0][0] if chen else '-'}；林瑶读档 {lin[0][0] if lin else '-'}；22:05/23:30 提及 {n}/{n2} 次"
    return ok, evd


def _d1_counselor_intervention(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 1) if a == "辅导员"]
    n, hits = _mentioning(lines, "统一口径")
    n2, hits2 = _mentioning(lines, "个人情况说明")
    ok = len(lines) >= 5 and (n + n2) >= 1
    evd = f"辅导员当日 {len(lines)} 条发言；纪律语句命中 统一口径×{n}、个人情况说明×{n2}"
    return ok, evd


def _d1_three_statements(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 1)
             if a in ("陈默", "林瑶", "林瑶室友", "班长")
             and "情况说明" in x]
    actors = _distinct_actors(lines)
    ok = len(actors) >= 3
    evd = f"提交说明的角色：{'、'.join(actors) or '无'}"
    return ok, evd


def _d1_note_procedure(ev, turns, sess):
    reads = _reads(ev, 1)
    notes = [r for r in reads if r[2].startswith("字条")]
    lines = _day_texts(ev, 1)
    n, hits = _mentioning(lines, "字条-")
    ok = len(notes) >= 1 and n >= 1
    evd = f"字条被读取 {len(notes)} 次（{notes[0][0] if notes else '-'} 首次）；提及字条编号 {n} 次"
    return ok, evd


def _d1_anniversary_discussed(ev, turns, sess):
    notice = any((e.get("payload") or {}).get("event") == "typhoon_anniversary_notice"
                 for e in _day_events(ev, 1))
    lines = _day_texts(ev, 1)
    n, hits = _mentioning(lines, "纪念活动")
    ok = notice and n >= 1
    evd = f"通知播发：{notice}；讨论 {n} 次（{hits[0][1] if hits else '无'}）"
    return ok, evd


def _d1_laozhou_relay(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 1) if a == "食堂大妈"]
    n, hits = _mentioning(lines, "老周")
    lin = [(t, a, x) for t, a, x in _day_texts(ev, 1)
           if a == "林瑶" and "老周" in x]
    ok = n >= 1 and bool(lin)
    evd = (f"大妈转达 {hits[0][0] if hits else '-'}；"
           f"林瑶确认 {lin[0][0] if lin else '-'}")
    return ok, evd


def _d1_mom_promise(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 1) if a == "陈默妈"]
    n, hits = _mentioning(lines, "问不到")
    ok = n >= 1
    evd = f"妈妈的'问不到就告诉你'出现 {n} 次（{hits[0][0] if hits else '-'}）"
    return ok, evd


def _d1_audit_relayed(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 1)
             if a == "陈默" and int(t[:2]) >= 16]
    n, hits = _mentioning(lines, "催办单")
    ok = n >= 1
    evd = f"16:00 后陈默转达催办单 {n} 次（{hits[0][0] if hits else '-'}）"
    return ok, evd


def _d1_linyao_self_audit(ev, turns, sess):
    reads = _reads(ev, 1)
    aud = [r for r in reads if r[1] == "林瑶" and "审计包" in r[2]]
    lines = _day_texts(ev, 1)
    n, _ = _mentioning(lines, "凭证")
    n2, _ = _mentioning(lines, "未标用途")
    ok = len(aud) >= 1 and (n + n2) >= 1
    evd = f"林瑶读审计包 {len(aud)} 次；凭证/未标用途提及 {n}+{n2} 次"
    return ok, evd


# ---------------------------------------------------------------- day 2
def _d2_audit_statement_filed(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 2)
             if "书面说明" in x or ("说明" in x and "提交" in x)]
    ok = len(lines) >= 1
    evd = f"{len(lines)} 条提交/说明相关发言（{lines[0][0] if lines else '-'} {lines[0][1] if lines else '-'}）"
    return ok, evd


def _d2_admin_answer(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 2)
             if a in ("辅导员", "档案室管理员") and "管理员" in x
             and any(k in x for k in ("确认", "答复", "备案", "接手"))]
    ok = len(lines) >= 1
    evd = f"{len(lines)} 条正式答复（{lines[0][0] if lines else '-'}）"
    return ok, evd


def _d2_mom_result(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 2) if a == "陈默妈"]
    n, hits = _mentioning(lines, "问到了", "老街坊", all_of=False)
    ok = n >= 1
    evd = f"妈妈的打听结果 {n} 条（{hits[0][0] if hits else '-'}）"
    return ok, evd


# ---------------------------------------------------------------- day 3
def _d3_side_by_side(ev, turns, sess):
    reads = _reads(ev, 3)
    who = {r[1] for r in reads if "台账" in r[2] or "抄件" in r[2]}
    talk = [(t, a, x) for t, a, x in _day_texts(ev, 3)
            if a == "林瑶" and "陈默" in x and "台账" in x]
    ok = len(who) >= 2 or bool(talk)
    evd = f"当日读档者：{'、'.join(sorted(who)) or '无'}；林瑶-陈默台账对话 {len(talk)} 条"
    return ok, evd


def _d3_copy_pressure(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 3) if a == "林瑶"]
    n, hits = _mentioning(lines, "抄件")
    ok = n >= 1
    evd = f"林瑶提及抄件 {n} 次（{hits[0][0] if hits else '-'}）"
    return ok, evd


def _d3_register_trail(ev, turns, sess):
    lines = _day_texts(ev, 3)
    n, hits = _mentioning(lines, "借阅登记本")
    n2, _ = _mentioning(lines, "最后", "登记", all_of=False)
    ok = n >= 1
    evd = f"'借阅登记本'提及 {n} 次（{hits[0][0] if hits else '-'}）"
    return ok, evd


# ---------------------------------------------------------------- day 4
def _d4_laozhaotou_hook(ev, turns, sess):
    lines = _day_texts(ev, 4)
    n, hits = _mentioning(lines, "老赵头")
    ok = n >= 1
    evd = f"'老赵头'被提及 {n} 次（{hits[0][0] if hits else '-'} {hits[0][1] if hits else ''}）"
    return ok, evd


def _d4_old_route_walk(ev, turns, sess):
    enters = [(e["time"][11:16], e.get("actor"), (e.get("payload") or {}).get("location", ""))
              for e in _day_events(ev, 4) if e.get("kind") == "enter"]
    lin = [x for x in enters if x[1] == "林瑶" and x[2] in ("老家属院", "河堤", "后街")]
    ok = len(lin) >= 1
    evd = f"林瑶老路线足迹：{lin or '无'}"
    return ok, evd


def _d4_chen_confession(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 4) if a == "陈默"]
    n, hits = _mentioning(lines, "对不起", "当年", all_of=False)
    ok = n >= 1
    evd = f"陈默当年/对不起发言 {n} 条（{hits[0][0] if hits else '-'}）"
    return ok, evd


# ---------------------------------------------------------------- day 5
def _d5_pumps_confirmed(ev, turns, sess):
    lines = _day_texts(ev, 5)
    n, hits = _mentioning(lines, "抽水泵", "小学", all_of=True)
    ok = n >= 1
    evd = f"抽水泵→小学 同现 {n} 次（{hits[0][0] if hits else '-'}）"
    return ok, evd


def _d5_who_altered(ev, turns, sess):
    lines = _day_texts(ev, 5)
    n, hits = _mentioning(lines, "23:30")
    n2, _ = _mentioning(lines, "谁", "改", all_of=False)
    ok = n >= 1
    evd = f"23:30 追责讨论 {n} 次"
    return ok, evd


def _d5_audit_coop_link(ev, turns, sess):
    lines = _day_texts(ev, 5)
    n, _ = _mentioning(lines, "发票", "合作社", all_of=False)
    ok = n >= 1
    evd = f"发票/合作社 线索提及 {n} 次"
    return ok, evd


# ---------------------------------------------------------------- day 6
def _d6_prep_gathering(ev, turns, sess):
    enters = [(e["time"][11:16], e.get("actor"))
              for e in _day_events(ev, 6)
              if e.get("kind") == "enter"
              and (e.get("payload") or {}).get("location") == "中庭"]
    who = {a for _, a in enters}
    lines = _day_texts(ev, 6)
    n, _ = _mentioning(lines, "纪念活动")
    ok = len(who) >= 3 and n >= 1
    evd = f"中庭聚集 {len(who)} 人；纪念活动提及 {n} 次"
    return ok, evd


def _d6_chen_full_sentence(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 6) if a == "陈默"]
    n, hits = _mentioning(lines, "对不起")
    n2, _ = _mentioning(lines, "为什么", "走了", all_of=False)
    ok = n >= 1 and n2 >= 1
    evd = f"对不起×{n}、为什么/走了×{n2}"
    return ok, evd


def _d6_xiaolan_choice(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 6) if a == "唐小岚"]
    n, hits = _mentioning(lines, "草稿")
    ok = n >= 1
    evd = f"小岚谈草稿 {n} 次（{hits[0][0] if hits else '-'}）"
    return ok, evd


# ---------------------------------------------------------------- day 7
def _d7_finale_event(ev, turns, sess):
    lines = _day_texts(ev, 7)
    n, hits = _mentioning(lines, "纪念活动")
    ok = n >= 2
    evd = f"纪念活动当日提及 {n} 次"
    return ok, evd


def _d7_truth_named(ev, turns, sess):
    lines = _day_texts(ev, 7)
    n, _ = _mentioning(lines, "老赵头", "老街坊代表", all_of=False)
    who = {a for t, a, x in lines if "老赵头" in x or "老街坊代表" in x}
    ok = n >= 1 and len(who) >= 2
    evd = f"真相人名被 {len(who)} 个角色提及 {n} 次"
    return ok, evd


def _d7_keepsake(ev, turns, sess):
    lines = _day_texts(ev, 7)
    n, hits = _mentioning(lines, "哨子")
    ok = n >= 1
    evd = f"哨子被提及 {n} 次（{hits[0][0] if hits else '-'} {hits[0][1] if hits else ''}）"
    return ok, evd


def _d7_bond_tested(ev, turns, sess):
    enters = [(e["time"][11:16], e.get("actor"))
              for e in _day_events(ev, 7)
              if e.get("kind") == "enter"
              and (e.get("payload") or {}).get("location") == "中庭"
              and e.get("actor") in ("陈默", "林瑶")]
    who = {a for _, a in enters}
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 7) if a in ("陈默", "林瑶")]
    ok = len(who) >= 2 and len(lines) >= 2
    evd = f"中庭到场：{'、'.join(sorted(who)) or '无'}；双方发言 {len(lines)} 条"
    return ok, evd


# ---------------------------------------------------------------- registry
MILESTONES = {
    1: [
        _mk_check("d1-登记缺失知晓", "登记本/值班表缺失被 ≥3 角色知晓", _d1_register_missing_known),
        _mk_check("d1-台账差异记录", "陈默与林瑶都读台账+导出件，22:05/23:30 差异被发言记录", _d1_discrepancy_recorded),
        _mk_check("d1-辅导员介入", "辅导员 ≥5 条发言并出现程序纪律语句", _d1_counselor_intervention),
        _mk_check("d1-三份个人说明", "≥3 角色提交个人情况说明", _d1_three_statements),
        _mk_check("d1-字条留痕程序", "临时字条被读取且编号被提及", _d1_note_procedure),
        _mk_check("d1-纪念活动通知", "台风纪念活动通知播发并被讨论", _d1_anniversary_discussed),
        _mk_check("d1-老周托话", "食堂大妈转达老周托话且林瑶确认", _d1_laozhou_relay),
        _mk_check("d1-妈妈承诺", "陈默妈承诺回老家属院打听（问不到就说问不到）", _d1_mom_promise),
        _mk_check("d1-审计催办转达", "16:00 催办单被陈默原样转达辅导员", _d1_audit_relayed),
        _mk_check("d1-林瑶自查审计包", "林瑶自主核对审计包并记录凭证缺失事实", _d1_linyao_self_audit),
    ],
    2: [
        _mk_check("d2-审计说明提交", "审计书面说明按时提交", _d2_audit_statement_filed),
        _mk_check("d2-管理员正式答复", "管理员/接手方正式答复出现", _d2_admin_answer),
        _mk_check("d2-妈妈打听结果", "妈妈的打听结果回到陈默", _d2_mom_result),
    ],
    3: [
        _mk_check("d3-并肩核查", "陈默与林瑶并肩核查台账/抄件", _d3_side_by_side),
        _mk_check("d3-抄件压力", "林瑶的抄件秘密开始承压（被提及）", _d3_copy_pressure),
        _mk_check("d3-登记本下落", "借阅登记本的下落被追踪", _d3_register_trail),
    ],
    4: [
        _mk_check("d4-老赵头钩子", "老赵头被点名（大爷的钩子激活）", _d4_laozhaotou_hook),
        _mk_check("d4-林瑶走老路线", "林瑶亲赴老路线地点", _d4_old_route_walk),
        _mk_check("d4-陈默坦白窗口", "陈默的当年/对不起发言出现", _d4_chen_confession),
    ],
    5: [
        _mk_check("d5-抽水泵去向", "抽水泵→小学 被证实", _d5_pumps_confirmed),
        _mk_check("d5-23:30追责", "23:30 改动追责讨论", _d5_who_altered),
        _mk_check("d5-审计合作社线", "发票/合作社 线索与审计合流", _d5_audit_coop_link),
    ],
    6: [
        _mk_check("d6-筹备聚集", "纪念活动筹备在中庭聚集 ≥3 人", _d6_prep_gathering),
        _mk_check("d6-陈默完整的话", "对不起+当年/为什么 一句完整的话", _d6_chen_full_sentence),
        _mk_check("d6-小岚的抉择", "小岚面对草稿的抉择", _d6_xiaolan_choice),
    ],
    7: [
        _mk_check("d7-纪念活动举行", "3·16台风纪念活动当日举行", _d7_finale_event),
        _mk_check("d7-真相点名", "老赵头/老街坊代表 真相被 ≥2 角色点名", _d7_truth_named),
        _mk_check("d7-信物相认", "红色哨子被提及/相认", _d7_keepsake),
        _mk_check("d7-关系检验", "陈默与林瑶同在中庭并当面交换 ≥2 条发言", _d7_bond_tested),
    ],
}


# ---------------------------------------------------------------- health
def health_report(data, day: int):
    date = DAY_DATES[day]
    turns = [t for t in data.get("agent_turns", [])
             if str(t.get("perception", {}).get("time", "")).startswith(date)]
    errs = [t for t in turns if t.get("error")]
    http = [t for t in errs if "HTTP 4" in str(t.get("error")) or "HTTP 5" in str(t.get("error"))]
    leak = 0
    for s in (data.get("sessions") or {}).values():
        for m in s.get("messages", []):
            if "[[" in str(m.get("content", "")):
                leak += 1
    return {"当日在册轮次": len(turns), "错误轮次": len(errs),
            "提供商HTTP错误": len(http), "标记泄漏条数": leak}


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("artifact", type=Path)
    ap.add_argument("--day", type=int, required=True, choices=sorted(DAY_DATES))
    args = ap.parse_args()
    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    ev, turns, sess = data.get("world_events", []), data.get("agent_turns", []), data.get("sessions", {})

    checks = MILESTONES[args.day]
    print(f"== 第 {args.day} 天（{DAY_DATES[args.day]}）故事里程碑 ==")
    failed = []
    for c in checks:
        try:
            ok, evd = c["fn"](ev, turns, sess)
        except Exception as exc:  # a broken check must not kill the report
            ok, evd = False, f"检查器异常：{type(exc).__name__}: {exc}"
        print(f"  [{'PASS' if ok else 'FAIL'}] {c['id']} — {c['desc']}\n"
              f"          {evd}")
        if not ok:
            failed.append(c["id"])

    print(f"\n== 系统健康（第 {args.day} 天，不计入退出码）==")
    for k, v in health_report(data, args.day).items():
        print(f"  {k}: {v}")

    print(f"\n结果：{'全部通过' if not failed else '未通过：' + '、'.join(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
