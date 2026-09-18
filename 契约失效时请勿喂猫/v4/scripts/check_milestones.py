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
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

DAY_DATES = {
    1: "2026-03-16", 2: "2026-03-17", 3: "2026-03-18", 4: "2026-03-19",
    5: "2026-03-20", 6: "2026-03-21", 7: "2026-03-22",
}

# 半天粒度（ticket：里程碑=检查点）：am = 07:00–12:59，pm = 13:00–22:00。
HALF_HOURS = {"am": (0, 13), "pm": (13, 24)}


def _in_half(ev, day: int, half: str) -> bool:
    lo, hi = HALF_HOURS[half]
    hour = int(str(ev.get("time", ""))[11:13])
    date_ok = str(ev.get("time", "")).startswith(DAY_DATES[day])
    return date_ok and lo <= hour < hi


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


def _mk_check(cid, desc, fn, half: str):
    return {"id": cid, "desc": desc, "fn": fn, "half": half}


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


def _d1_mutual_verification(ev, turns, sess):
    """现场互证程序路线（ticket 26）：陈默与林瑶在档案室相互核证（双向、
    多条、围绕登记本/台账/核对），并出现边界/留痕表述（不补写、按原样、
    边界清单）。这是"短信升级辅导员"之外的另一条有效路线。"""
    lines = _day_texts(ev, 1)
    chen = [(t, a, x) for t, a, x in lines if a == "陈默"
            and any(w in x for w in ("登记本", "台账", "导出件", "核对", "抽屉"))]
    lin = [(t, a, x) for t, a, x in lines if a == "林瑶"
           and any(w in x for w in ("登记本", "台账", "导出件", "核对", "抽屉"))]
    boundary = any(a in ("陈默", "林瑶")
                   and any(w in x for w in ("边界", "原样", "不补写", "留痕"))
                   for t, a, x in lines)
    ok = len(chen) >= 2 and len(lin) >= 2 and boundary
    evd = (f"陈默核证发言 {len(chen)} 条；林瑶核证发言 {len(lin)} 条；"
           f"边界/留痕表述：{'有' if boundary else '无'}")
    return ok, evd


def _d1_romance_presence(ev, turns, sess):
    """恋爱并肩（day-1 节拍，恋爱轴锚点）：陈默与林瑶当面双向对话。"""
    n = {"陈默": 0, "林瑶": 0}
    for e in _day_events(ev, 1):
        if e.get("kind") == "speech" and e.get("actor") in n:
            other = "林瑶" if e["actor"] == "陈默" else "陈默"
            if other in (e.get("payload") or {}).get("heard", []) or                other in (e.get("payload") or {}).get("to", []) or []:
                n[e["actor"]] += 1
    ok = n["陈默"] >= 1 and n["林瑶"] >= 1 and (n["陈默"] + n["林瑶"]) >= 3
    evd = f"陈默→林瑶 {n['陈默']} 条；林瑶→陈默 {n['林瑶']} 条（当面双向）"
    return ok, evd


def _d1_mom_thread(ev, turns, sess):
    """妈妈线进展（锚点，可跨日）：陈默↔妈妈任一方向的联系，或妈妈线
    发言提及（等待/打听/回信）。"""
    msgs = [e for e in _day_events(ev, 1)
            if e.get("kind") in ("message_sent", "message_delivered")
            and "陈默妈" in (str(e.get("payload", {}).get("target", ""))
                             + str(e.get("actor", "")))]
    mentions = [(t, a, x) for t, a, x in _day_texts(ev, 1)
                if a == "陈默" and "妈妈" in x]
    ok = bool(msgs) or len(mentions) >= 1
    evd = f"短信往来 {len(msgs)}；陈默的妈妈线发言 {len(mentions)} 条"
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


# ------------------------------------------------- romance (galgame axis)

def _same_place_exchanged(ev, day, half, a: str, b: str,
                          task_words=("台账", "登记", "审计", "值班",
                                      "说明", "材料", "导出件", "字条")):
    """双方同地出现且互有发言；non-task 模式下排除案件关键词。"""
    enters = {}
    for e in _day_events(ev, day):
        if e.get("kind") == "enter" and e.get("actor") in (a, b):
            enters.setdefault(e["actor"], []).append(e["time"][11:16])
    if not (a in enters and b in enters):
        return False, "双方未同地"
    lines_a = [(x[0], x[2]) for x in _day_texts(ev, day) if x[1] == a]
    lines_b = [(x[0], x[2]) for x in _day_texts(ev, day) if x[1] == b]
    if half:
        h_lo, h_hi = HALF_HOURS[half]
        lines_a = [x for x in lines_a if h_lo <= int(x[0][:2]) < h_hi]
        lines_b = [x for x in lines_b if h_lo <= int(x[0][:2]) < h_hi]
    if task_words:
        lines_a = [x for x in lines_a if not any(w in x[1] for w in task_words)]
        lines_b = [x for x in lines_b if not any(w in x[1] for w in task_words)]
    ok = bool(lines_a) and bool(lines_b)
    return ok, (f"{a}×{len(lines_a)} / {b}×{len(lines_b)} 条非任务发言"
                + (f"（{lines_a[0][0]} 起）" if lines_a else ""))


def _d1_romance_side_by_side(ev, turns, sess):
    ok, evd = _same_place_exchanged(ev, 1, "am", "陈默", "林瑶")
    return ok, "档案室并肩：" + evd


def _d1_romance_review():
    return "恋爱温度：档案室并肩与'字条程序'中两人一致的谨慎——是默契还是回避？（人工审阅）"


def _d1_comedy_canteen(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 1)
             if a == "食堂大妈" and int(t[:2]) < 13]
    chen = [(t, x) for t, a, x in _day_texts(ev, 1)
            if a == "陈默" and int(t[:2]) < 13 and "排骨" in x or "茄子" in x
            and a == "陈默"]
    ok = len(lines) >= 3
    evd = f"食堂午饭戏：大妈 {len(lines)} 条（{lines[0][0] if lines else '-'} 起）"
    return ok, evd


def _d1_comedy_review():
    return "喜剧质量：食堂大妈的一本正经与大妈转达老周托话的Community gossip——哪个更有效？（人工审阅）"


def _d2_romance_private_talk(ev, turns, sess):
    ok, evd = _same_place_exchanged(ev, 2, None, "陈默", "林瑶")
    return ok, "首次私人对话（非任务）：" + evd


def _d2_comedy_review():
    return "喜剧质量：猫/路人的出场是否自然？（人工审阅；猫概念落地后升为机械检查）"


def _d3_romance_xiangqin_seed(ev, turns, sess):
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 3) if a == "陈默妈"]
    n, hits = _mentioning(lines, "相亲", "姑娘", "李阿姨", all_of=False)
    ok = n >= 1
    evd = f"相亲压力埋线 {n} 次（{hits[0][0] if hits else '-'}）"
    return ok, evd


def _d3_comedy_review():
    return "喜剧质量：本日设计笑点（室友起哄/猫）是否成立？（人工审阅）"


def _d5_romance_xiangqin_press(ev, turns, sess):
    lines = _day_texts(ev, 5)
    n, hits = _mentioning(lines, "相亲", "李阿姨", "见一面", all_of=False)
    ok = n >= 1
    evd = f"相亲逼问/压力 {n} 次（{hits[0][0] if hits else '-'}）"
    return ok, evd


def _d5_comedy_review():
    return "喜剧质量：大雨/室内场景的窘迫喜剧是否成立？（人工审阅）"


def _d6_romance_review():
    return "恋爱温度：'那句完整的话'的措辞与时机（人工审阅——本日核心 romance 节拍）"


def _d7_romance_date(ev, turns, sess):
    enters = [(e["time"][11:16], e.get("actor"))
              for e in _day_events(ev, 7)
              if e.get("kind") == "enter" and e.get("actor") in ("陈默", "林瑶")]
    who = {a for _, a in enters}
    lines = [(t, a, x) for t, a, x in _day_texts(ev, 7) if a in ("陈默", "林瑶")]
    non_task = [x for a, x in ((x[1], x[2]) for x in lines)
                if not any(w in x for w in ("台账", "登记", "审计", "说明"))]
    ok = len(who) >= 2 and len(non_task) >= 1
    evd = (f"纪念活动同游：{'、'.join(sorted(who))}；非任务交流 {len(non_task)} 条")
    return ok, evd


# ---------------------------------------------------------------- registry
MILESTONES = {
    1: [
        _mk_check("d1-登记缺失知晓", "登记本/值班表缺失被 ≥3 角色知晓", _d1_register_missing_known, half="am"),
        _mk_check("d1-台账差异记录", "陈默与林瑶都读台账+导出件，22:05/23:30 差异被发言记录", _d1_discrepancy_recorded, half="am"),
        _mk_check("d1-辅导员介入", "辅导员 ≥5 条发言并出现程序纪律语句", _d1_counselor_intervention, half="pm"),
        _mk_check("d1-三份个人说明", "≥3 角色提交个人情况说明", _d1_three_statements, half="pm"),
        _mk_check("d1-字条留痕程序", "临时字条被读取且编号被提及", _d1_note_procedure, half="pm"),
        _mk_check("d1-现场互证", "陈默与林瑶相互核证 + 边界/留痕表述（现场互证路线）", _d1_mutual_verification, half="pm"),
        _mk_check("d1-恋爱并肩", "陈默与林瑶当面双向对话（恋爱轴 day-1 节拍）", _d1_romance_presence, half="am"),
        _mk_check("d1-纪念活动通知", "台风纪念活动通知播发并被讨论", _d1_anniversary_discussed, half="pm"),
        _mk_check("d1-老周托话", "食堂大妈转达老周托话且林瑶确认", _d1_laozhou_relay, half="pm"),
        _mk_check("d1-妈妈承诺", "陈默妈承诺回老家属院打听（问不到就说问不到）", _d1_mom_promise, half="pm"),
        _mk_check("d1-审计催办转达", "16:00 催办单被陈默原样转达辅导员", _d1_audit_relayed, half="pm"),
        _mk_check("d1-林瑶自查审计包", "林瑶自主核对审计包并记录凭证缺失事实", _d1_linyao_self_audit, half="pm"),
    ],
    2: [
        _mk_check("d2-审计说明提交", "审计书面说明按时提交", _d2_audit_statement_filed, half="am"),
        _mk_check("d2-恋爱私人对话", "陈默与林瑶第一次非任务私人对话（galgame轴）", _d2_romance_private_talk, half="pm"),
        _mk_check("d2-管理员正式答复", "管理员/接手方正式答复出现（未出现则滚入 day-3 路线）", _d2_admin_answer, half="am"),
        _mk_check("d2-妈妈打听结果", "妈妈的打听结果回到陈默", _d2_mom_result, half="pm"),
    ],
    3: [
        _mk_check("d3-并肩核查", "陈默与林瑶并肩核查台账/抄件", _d3_side_by_side, half="am"),
        _mk_check("d3-抄件压力", "林瑶的抄件秘密开始承压（被提及）", _d3_copy_pressure, half="pm"),
        _mk_check("d3-相亲埋线", "妈妈的相亲/姑娘压力埋线（阻力线）", _d3_romance_xiangqin_seed, half="pm"),
        _mk_check("d3-登记本下落", "借阅登记本的下落被追踪", _d3_register_trail, half="pm"),
    ],
    4: [
        _mk_check("d4-老赵头钩子", "老赵头被点名（大爷的钩子激活）", _d4_laozhaotou_hook, half="am"),
        _mk_check("d4-林瑶走老路线", "林瑶亲赴老路线地点", _d4_old_route_walk, half="am"),
        _mk_check("d4-陈默坦白窗口", "陈默的当年/对不起发言出现", _d4_chen_confession, half="pm"),
    ],
    5: [
        _mk_check("d5-抽水泵去向", "抽水泵→小学 被证实", _d5_pumps_confirmed, half="am"),
        _mk_check("d5-23:30追责", "23:30 改动追责讨论", _d5_who_altered, half="am"),
        _mk_check("d5-审计合作社线", "发票/合作社 线索与审计合流", _d5_audit_coop_link, half="pm"),
        _mk_check("d5-相亲逼问", "相亲压力逼问/正面提及（阻力线）", _d5_romance_xiangqin_press, half="pm"),
    ],
    6: [
        _mk_check("d6-筹备聚集", "纪念活动筹备在中庭聚集 ≥3 人", _d6_prep_gathering, half="am"),
        _mk_check("d6-陈默完整的话", "对不起+当年/为什么 一句完整的话", _d6_chen_full_sentence, half="pm"),
        _mk_check("d6-小岚的抉择", "小岚面对草稿的抉择", _d6_xiaolan_choice, half="pm"),
    ],
    7: [
        _mk_check("d7-纪念活动举行", "3·16台风纪念活动当日举行", _d7_finale_event, half="am"),
        _mk_check("d7-真相点名", "老赵头/老街坊代表 真相被 ≥2 角色点名", _d7_truth_named, half="am"),
        _mk_check("d7-信物相认", "红色哨子被提及/相认", _d7_keepsake, half="am"),
        _mk_check("d7-纪念活动同游", "纪念活动同游+非任务交流（关系确认，galgame轴）", _d7_romance_date, half="pm"),
        _mk_check("d7-关系检验", "陈默与林瑶同在中庭并当面交换 ≥2 条发言", _d7_bond_tested, half="pm"),
    ],
}


# ------------------------------------------------- REVIEW items (non-gating)
# 人工审阅项：在每个半天检查点的审阅环节通读判定（喜剧质量、恋爱温度、
# NPC 表演质量）。只列出，不影响退出码。
# ---------------------------------------------------------------- 路线网
# 里程碑是多条可能路线组成的网（用户裁决 2026-09-17）：只要 anchors 全部
# 达成、且至少一条路线的 requires 全部达成（节奏与因果说得通），该日即为
# 通过。flavor 是路线纹理，记录但不裁决。
ROUTES = {
    1: {
        "anchors": ["d1-登记缺失知晓", "d1-台账差异记录", "d1-审计催办转达",
                    "d1-恋爱并肩", "d1-妈妈线"],
        "routes": [
            {"name": "短信升级辅导员",
             "requires": ["d1-辅导员介入", "d1-三份个人说明"]},
            {"name": "现场互证程序", "requires": ["d1-现场互证"]},
        ],
        "flavor": ["d1-字条留痕程序", "d1-老周托话", "d1-妈妈承诺",
                   "d1-纪念活动通知", "d1-林瑶自查审计包"],
    },
    2: {
        "anchors": ["d2-审计说明提交", "d2-恋爱私人对话", "d2-妈妈打听结果"],
        "routes": [],   # 管理员答复滚入 day-3 锚点（排程未接住时的余量设计）
        "flavor": ["d2-管理员正式答复"],
    },
}
# d1-妈妈线：复用 d2-妈妈打听结果（可跨日达成）——锚点在线程闭环。
ROUTES[1]["anchors"][4] = "d2-妈妈打听结果"

REVIEWS = {
    1: {"am": ["恋爱温度：档案室并肩与字条程序中两人一致的谨慎——默契还是回避？",
               "喜剧质量：食堂午饭戏的一本正经"],
        "pm": ["喜剧/温度：老周托话的转达戏与'只记已确认事实'的谨慎反差",
               "阻力线：妈妈催婚电话与恋爱轴的对照"]},
    2: {"am": ["正式答复到来时各角色的程序感（导演视角：机构压力是否到位）"],
        "pm": ["喜剧质量：猫/路人出场是否自然（猫概念落地后升为机械检查）",
               "恋爱温度：首次私人对话的内容与分寸"]},
    3: {"am": ["并肩核查的默契程度"],
        "pm": ["喜剧质量：室友起哄/相亲埋线的尴尬喜剧",
               "恋爱阻力：相亲压力下陈默的反应是否真实"]},
    4: {"am": ["老赵头钩子的讲古质量（大爷分寸线：传说不是证词）"],
        "pm": ["恋爱温度：陈默坦白窗口的措辞"]},
    5: {"am": ["抽水泵证实的揭示节奏"],
        "pm": ["喜剧质量：大雨/室内窘迫喜剧；相亲逼问的张力"]},
    6: {"am": ["筹备聚集的群像感"],
        "pm": ["恋爱核心节拍：'那句完整的话'的措辞与时机（本弧最重要 romance 审阅）",
               "喜剧质量：小岚抉择前夜的自我调侃"]},
    7: {"am": ["纪念活动的群像与真相点名的分量"],
        "pm": ["恋爱终局：同游与关系确认的 galgame 收束感",
               "喜剧收束：猫在终局的出现"]},
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
    ap.add_argument("--day", type=int, choices=sorted(DAY_DATES))
    ap.add_argument("--half", help="dN-am | dN-pm：半天里程碑（检查点边界）")
    args = ap.parse_args()
    if bool(args.day) == bool(args.half):
        ap.error("请二选一：--day N 或 --half dN-am|dN-pm")
    if args.half:
        m = re.fullmatch(r"d(\d+)-(am|pm)", args.half)
        if not m or int(m.group(1)) not in DAY_DATES:
            ap.error(f"无效的 --half：{args.half}")
        args.day, half = int(m.group(1)), m.group(2)
    else:
        half = None
    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    ev, turns, sess = data.get("world_events", []), data.get("agent_turns", []), data.get("sessions", {})

    if half:
        lo, hi = HALF_HOURS[half]
        ev = [e for e in ev
              if str(e.get("time", "")).startswith(DAY_DATES[args.day])
              and lo <= int(str(e.get("time", ""))[11:13]) < hi]

    checks = [c for c in MILESTONES[args.day] if half is None or c["half"] == half]
    label = f"第 {args.day} 天 {'上午' if half == 'am' else '下午' if half else ''}（{DAY_DATES[args.day]}）"
    print(f"== {label}故事里程碑 ==")
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

    review_half = half or "am"
    reviews = REVIEWS.get(args.day, {}).get(review_half, [])
    if reviews:
        print(f"\n== REVIEW（人工审阅项，{review_half}，不计入退出码）==")
        for r in reviews:
            print(f"  [REVIEW] {r}")

    print(f"\n== 系统健康（第 {args.day} 天，不计入退出码）==")
    for k, v in health_report(data, args.day).items():
        print(f"  {k}: {v}")

    # ---- 路线网判定（--day 模式；--half 是检查点门，不套用路线网）----
    network_note = ""
    if half is None:
        net = ROUTES.get(args.day)
        if net:
            passed_ids = {c["id"] for c in checks if c["id"] not in failed}
            # 跨日锚点（如 d1 的妈妈线锚点指向 d2 的线程闭环）：用全量事件补评；
            # 工件尚未覆盖其日期时记为待后续（不裁决，不阻断当天判定）。
            last_seen = max((str(e.get("time", "")) for e in ev), default="")
            pending = []
            for a in net["anchors"]:
                if a in passed_ids or a in failed:
                    continue
                a_day = next((DAY_DATES[d] for d, cks in MILESTONES.items()
                              for c in cks if c["id"] == a), None)
                if a_day and a_day > last_seen[:10]:
                    pending.append(a)
                    continue
                for day, cks in MILESTONES.items():
                    for c in cks:
                        if c["id"] != a:
                            continue
                        try:
                            ok, _ = c["fn"](ev, turns, sess)
                        except Exception:
                            ok = False
                        if ok:
                            passed_ids.add(a)
            anchor_fails = [a for a in net["anchors"] if a not in passed_ids
                            and a not in pending]
            route_ok = []
            for route in net["routes"]:
                missing = [r for r in route["requires"] if r not in passed_ids]
                route_ok.append((route["name"], not missing, missing))
            # 无路线分歧的日（routes 为空）按锚点判定即可。
            any_route = any(ok for _, ok, _ in route_ok) if net["routes"] else True
            flavor_fails = [f for f in net["flavor"] if f in failed]
            print(f"\n路线网判定（第 {args.day} 天）：")
            print(f"  锚点：{'全部达成' if not anchor_fails else '未达成 ' + '、'.join(anchor_fails)}"
                  + (f"；待后续 {'、'.join(pending)}" if pending else ""))
            for name, ok, missing in route_ok:
                print(f"  路线[{name}]：{'成立' if ok else '未成立'}"
                      + (f"（缺 {'、'.join(missing)}）" if missing else ""))
            print(f"  纹理（不裁决）：{'、'.join(net['flavor'])}")
            if anchor_fails or not any_route:
                failed.append(f"路线网：锚点{anchor_fails}；有效路线{[n for n, ok, _ in route_ok if ok] or '无'}")
                network_note = "路线网判定未通过（详见上）"
            else:
                valid = "、".join(n for n, ok, _ in route_ok if ok)
                network_note = f"有效路线：{valid}"

    if network_note:
        print(f"\n结果：{network_note}")
        return 0 if "有效路线" in network_note else 1
    print(f"\n结果：{'全部通过' if not failed else '未通过：' + '、'.join(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
