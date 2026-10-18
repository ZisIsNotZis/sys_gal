"""D1 验收（第 2 次）关键读数：V1 夜间活性 / V2 说明交付 / V3 现场互证词。

用法: python3 .scratch/v4-first-day/analyze_acc2.py <run.json> [v1|v2|v3|all]
只打印，不写文件。
"""

from __future__ import annotations

import collections
import json
import sys

PATH = sys.argv[1]
WANT = set(sys.argv[2:]) or {"all"}

D = json.load(open(PATH))
EV = D.get("world_events") or []
AT = D.get("agent_turns") or []


def want(name: str) -> bool:
    return "all" in WANT or name in WANT


def hhmm(ts: str) -> str:
    return ts[11:16] if ts else "?"


def per(t: dict) -> dict:
    return t.get("perception") or {}


def calls(t: dict) -> list:
    it = t.get("intention") or {}
    return [c for c in ((it.get("args") or {}).get("calls") or []) if isinstance(c, dict)]


def talk(t: dict) -> str:
    """Spoken text of a turn: speak/text args plus, for NPC-free inspection, nothing else."""
    out = []
    for c in calls(t):
        a = c.get("args") or {}
        if c.get("name") in ("speak", "text"):
            out.append(str(a.get("text") or a.get("content") or ""))
    return " ".join(out)


def ptime(t: dict) -> str:
    return per(t).get("time") or ""


if want("v1"):
    print("\n===== V1 夜间活性 =====")
    hourly = collections.Counter(ptime(t)[11:13] for t in AT if ptime(t))
    hourly_sp = collections.Counter(ptime(t)[11:13] for t in AT if ptime(t) and talk(t))
    print("小时 回合/带发言:")
    for h in sorted(hourly):
        print(f"  {h}:00  turns={hourly[h]:4d}  speech={hourly_sp[h]:4d}")
    night = [t for t in AT if ptime(t)[11:] >= "18:30"]
    print(f"\n≥18:30 回合 {len(night)}（发言 {sum(1 for t in night if talk(t))}）")
    print("≥18:30 逐 actor:", collections.Counter(t.get("actor") for t in night).most_common())
    print("\n≥18:30 逐 10 分钟:")
    buckets = collections.Counter(ptime(t)[11:15][:4] + str(int(ptime(t)[14:16]) // 10) + "x"
                                  for t in night)
    print("  ", sorted(buckets.items()))

    print("\n-- 关键排程时刻的响应者（该时刻起 2 小时内出回合的角色）--")
    marks = ["19:00", "19:10", "19:30", "20:00", "20:40", "21:30"]
    for m in marks:
        hh, mm = int(m[:2]), int(m[3:])
        responders = collections.Counter(
            t.get("actor") for t in AT
            if m <= ptime(t)[11:16] <= f"{hh + 2:02d}:{mm:02d}")
        print(f"  {m}: {responders.most_common()}")

    print("\n-- 夜间 world_event / private_wake / reminder_due 与首个感知到它的回合 --")
    for e in EV:
        if e.get("kind") not in ("world_event", "private_wake", "reminder_due"):
            continue
        if hhmm(e["time"]) < "18:30":
            continue
        payload = e.get("payload") or {}
        tag = payload.get("event") or payload.get("reason") or payload.get("notice", "")
        print(f"{hhmm(e['time'])} {e['kind']} actor={e.get('actor')} vis={e.get('visible_to')} :: {str(tag)[:80]}")
        for t in AT:
            if t.get("actor") not in (e.get("visible_to") or []):
                continue
            if ptime(t)[11:16] < hhmm(e["time"]):
                continue
            print(f"      → 首个回合 {ptime(t)[11:16]} {t.get('actor')} result={t.get('result')}")
            break
        else:
            print("      → 无人出回合")
    print("\n-- 陈默 19:30 前后回合 --")
    for t in AT:
        if t.get("actor") == "陈默" and "19:0" <= ptime(t)[11:16] <= "20:20":
            seen = [str(x)[:90] for x in (per(t).get("sees") or per(t).get("visible") or [])][:6]
            print(f"{ptime(t)[11:16]} {t.get('result')} calls={[c.get('name') for c in calls(t)]} "
                  f"talk={talk(t)[:120]!r}")
            print(f"      sees={seen}")

if want("v2"):
    print("\n===== V2 三份说明：交付物证据（16:45 后）=====")
    for e in EV:
        if e.get("kind") not in ("note_left", "item_given", "document_annotated"):
            continue
        p = e.get("payload") or {}
        print(f"{hhmm(e['time'])} {e['kind']} {e.get('actor')} {json.dumps(p, ensure_ascii=False)[:220]}")
    print("\n-- 辅导员收件登记（document_annotated / note_left at 辅导员办公室）--")
    for t in AT:
        txt = talk(t)
        if "收件" in txt or "登记" in txt:
            print(f"{ptime(t)[11:16]} {t.get('actor')}: {txt[:200]}")

if want("v3"):
    print("\n===== V3 现场互证四个字面词 =====")
    words = ("边界", "原样", "不补写", "留痕")
    for e in EV:
        if e.get("kind") != "speech":
            continue
        p = e.get("payload") or {}
        txt = str(p.get("text") or "")
        hit = [w for w in words if w in txt]
        if hit:
            print(f"{hhmm(e['time'])} {e.get('actor')} {hit} :: {txt[:200]}")
