"""Window-2 (07:00→15:30) mechanical readout for the m1-window2 report.

Usage: python3 .scratch/v4-first-day/analyze_window2.py <trace.json> [section ...]
Sections: meta, kinds, paper, canteen, bakery, board, extras, empty, reject, story
No file is written; everything goes to stdout.
"""

from __future__ import annotations

import collections
import json
import re
import sys

PATH = sys.argv[1]
WANT = set(sys.argv[2:]) or {"meta", "kinds", "paper", "canteen", "bakery", "board",
                             "extras", "empty", "reject", "story"}
D = json.load(open(PATH))
EV = D["world_events"]
TURNS = D["agent_turns"]
SESS = D["sessions"]


def hhmm(ts: str) -> str:
    return ts[11:16] if ts else "?"


def hour(ts: str) -> str:
    return ts[11:13] if ts else "?"


def show(title: str) -> None:
    print(f"\n===== {title} =====")


if "meta" in WANT:
    show("META")
    print("run", D.get("run_id"), "format", D.get("format"))
    print("outcome", json.dumps(D.get("outcome"), ensure_ascii=False))
    print("events", len(EV), "turns", len(TURNS), "sessions", list(SESS))
    rp = D.get("replay") or {}
    print("replay", json.dumps({k: v for k, v in rp.items() if k != "events"}, ensure_ascii=False)[:600])
    print("first/last event time", hhmm(EV[0]["time"]), hhmm(EV[-1]["time"]))
    print("turns by actor", collections.Counter(t["actor"] for t in TURNS).most_common())
    print("turns by role", collections.Counter(t.get("role") for t in TURNS).most_common())
    print("turn results", collections.Counter(t.get("result") for t in TURNS).most_common())
    print("turn errors", sum(1 for t in TURNS if t.get("error")))

if "kinds" in WANT:
    show("EVENT KINDS")
    c = collections.Counter(e["kind"] for e in EV)
    for k, n in c.most_common():
        print(f"{k:24s} {n}")
    show("KINDS BY HOUR (selected)")
    sel = ["speech", "document_read", "enter", "leave", "item_given", "note_left",
           "note_read", "extra_arrived", "extra_removed", "item_dropped", "empty_turn",
           "world_event", "stranger_asked", "message_sent", "wait_woken", "time_advanced"]
    grid = collections.Counter((hour(e["time"]), e["kind"]) for e in EV if e["kind"] in sel)
    hours = sorted({hour(e["time"]) for e in EV})
    print("hour " + " ".join(f"{k[:6]:>7s}" for k in sel))
    for h in hours:
        print(f"{h}   " + " ".join(f"{grid[(h, k)]:7d}" for k in sel))

if "paper" in WANT:
    show("A. PAPER / PENS / NOTES")
    pat = re.compile(r"纸|笔|便条|字条|写")
    for t in TURNS:
        err = t.get("error") or ""
        if pat.search(err):
            print(f"[reject] {hhmm(t['perception']['time'])} {t['actor']} :: {err[:260]}")
    print("--- note_left ---")
    for e in EV:
        if e["kind"] == "note_left":
            p = e["payload"]
            print(f"{hhmm(e['time'])} {e['actor']} @{p.get('location')} len={len(p.get('text') or '')} :: {(p.get('text') or '')[:110]!r}")
    print("--- note_read ---")
    for e in EV:
        if e["kind"] == "note_read":
            p = e["payload"]
            print(f"{hhmm(e['time'])} {e['actor']} @{p.get('location')} author={p.get('author')} :: {(p.get('text') or '')[:90]!r}")
    print("--- 'cannot write' style inner/private lines ---")
    for t in TURNS:
        inner = t.get("inner") or ""
        if re.search(r"没有.{0,6}(工具|动作|方式).{0,8}写|写不到|写不进|纸上|纸面|没有纸|没纸|拿不到纸|找不到.{0,4}纸|无处可写", inner):
            print(f"{hhmm(t['perception']['time'])} {t['actor']} :: {inner[:200]}")
    print("--- paper item holds over time (item_given) ---")
    for e in EV:
        if e["kind"] == "item_given" and re.search(r"纸|笔|便签", e["payload"].get("item", "")):
            print(hhmm(e["time"]), e["actor"], e["payload"])

if "canteen" in WANT:
    show("B. CANTEEN DELIVERY")
    for e in EV:
        p = e["payload"]
        if e["kind"] in ("item_given", "item_dropped", "place") and (
                e["actor"] == "食堂大妈" or re.search(r"餐食|汤|饭|关东煮|饮料", str(p.get("item", "")))):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(p, ensure_ascii=False)[:200])
    print("--- 食堂大妈 actions ---")
    for e in EV:
        if e["actor"] == "食堂大妈" and e["kind"] in ("action_started", "action_completed"):
            print(hhmm(e["time"]), e["kind"], json.dumps(e["payload"], ensure_ascii=False)[:160])
    print("--- 食堂大妈 speech mentioning promise/food ---")
    for e in EV:
        if e["kind"] == "speech" and e["actor"] == "食堂大妈":
            txt = e["payload"]["text"]
            if re.search(r"打|给你|勺|汤|餐|饭|端|盛", txt):
                print(hhmm(e["time"]), "::", txt[:220])
    print("--- 勺子/汤 speech by anyone ---")
    for e in EV:
        if e["kind"] == "speech" and re.search(r"勺|盛不|找不着|挪", e["payload"]["text"]):
            print(hhmm(e["time"]), e["actor"], "::", e["payload"]["text"][:220])

if "bakery" in WANT:
    show("C. BACK-STREET BAKERY (15:00 task)")
    for e in EV:
        p = e["payload"]
        loc = p.get("location") or p.get("where") or ""
        if "后街" in str(loc) or (e["actor"] == "唐小岚" and e["time"] >= "2026-03-16T14:00"):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(p, ensure_ascii=False)[:200])
    print("--- extras at 后街糕点铺 ---")
    for e in EV:
        if "老板娘" in str(e["actor"]) or "老板娘" in str(e["payload"]):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:260])
    print("--- 代话便条 reads / mentions ---")
    for e in EV:
        if "代话便条" in json.dumps(e, ensure_ascii=False):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:200])
    for t in TURNS:
        if t["actor"] == "唐小岚" and t["perception"]["time"] >= "2026-03-16T14:30":
            print("[inner]", hhmm(t["perception"]["time"]), t.get("inner", "")[:160])

if "board" in WANT:
    show("D. NOTICE BOARDS")
    for e in EV:
        if e["kind"] == "document_read" and re.search(r"公告栏|审计通知|程序|指引", e["payload"].get("title", "")):
            print(hhmm(e["time"]), e["actor"], e["payload"].get("title"), "::", (e["payload"].get("content") or "")[:100].replace("\n", " "))
    print("--- world_event notices (board postings) ---")
    for e in EV:
        if e["kind"] == "world_event":
            p = e["payload"]
            print(hhmm(e["time"]), p.get("event"), "::", (p.get("notice") or "")[:150])
    print("--- speech about 公告栏 content/循环 ---")
    for e in EV:
        if e["kind"] == "speech" and re.search(r"公告栏|板上|通知|读了板", e["payload"]["text"]):
            print(hhmm(e["time"]), e["actor"], "::", e["payload"]["text"][:200])

if "extras" in WANT:
    show("E. EXTRA ITEM CARRY")
    for e in EV:
        if e["kind"] in ("extra_arrived", "extra_removed", "item_dropped"):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:200])
    print("--- take/place by extras ---")
    extras = {e["actor"] for e in EV if e["kind"] == "extra_arrived"}
    print("extras:", sorted(extras))
    for e in EV:
        if e["actor"] in extras and e["kind"] in ("action_started", "action_completed"):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:160])
    print("--- 校报草稿 mentions ---")
    for e in EV:
        if "校报草稿" in json.dumps(e["payload"], ensure_ascii=False) and e["kind"] in (
                "action_started", "action_completed", "item_given", "item_dropped", "document_read"):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:160])

if "empty" in WANT:
    show("F. EMPTY TURNS")
    for e in EV:
        if e["kind"] == "empty_turn":
            print(hhmm(e["time"]), e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:200])
    print("--- turns with no inner and no intention ---")
    for t in TURNS:
        inner = (t.get("inner") or "").strip()
        intent = t.get("intention") or {}
        calls = (intent.get("args") or {}).get("calls") if isinstance(intent, dict) else None
        if not inner and not calls:
            print(hhmm(t["perception"]["time"]), t["actor"], t.get("result"), repr(t.get("error"))[:120])

if "reject" in WANT:
    show("G. REJECTIONS")
    n = 0
    for t in TURNS:
        err = t.get("error")
        if not err:
            continue
        for part in str(err).split("; "):
            n += 1
            print(f"{hhmm(t['perception']['time'])} {t['actor']} [{t.get('result')}] :: {part[:300]}")
    print("total rejection fragments", n)
    print("turns with result=rejected", sum(1 for t in TURNS if t.get("result") == "rejected"))

if "story" in WANT:
    show("H. STORY SHAPE")
    mcs = [a for a in SESS if (D["sessions"][a] or {}).get("messages")]
    print("sessions", {a: len(v.get("messages") or []) for a, v in SESS.items()})
    cop = collections.Counter()
    for t in TURNS:
        p = t["perception"]
        for o in p.get("nearby_actors") or []:
            cop[tuple(sorted((t["actor"], o)))] += 1
    print("co-presence turn pairs (top 20)")
    for pair, n in cop.most_common(20):
        print(n, pair)
    sp = [e["payload"]["text"] for e in EV if e["kind"] == "speech"]
    print("speech", len(sp), "unique", len(set(sp)))
    dup = [s for s, n in collections.Counter(sp).items() if n > 1]
    for s in dup[:10]:
        print("DUP", repr(s[:140]))
    print("--- document_read by doc ---")
    print(collections.Counter(e["payload"].get("title") for e in EV if e["kind"] == "document_read").most_common())
