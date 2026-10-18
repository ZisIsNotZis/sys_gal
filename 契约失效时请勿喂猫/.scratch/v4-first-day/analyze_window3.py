"""Window-3 (07:00→12:00) mechanical readout for the m1-window3 report.

Usage: python3 .scratch/v4-first-day/analyze_window3.py <trace.json|checkpoint.json> [section ...]
Sections: meta kinds paper notes canteen board empty reject story
Accepts either the final run artifact or a checkpoint (trace.* layout).
No file is written; everything goes to stdout.
"""

from __future__ import annotations

import collections
import json
import re
import sys

PATH = sys.argv[1]
WANT = set(sys.argv[2:]) or {"meta", "kinds", "paper", "notes", "canteen", "board",
                             "empty", "reject", "story"}
D = json.load(open(PATH))
if "trace" in D and "world_events" not in D:
    T = D["trace"]
    EV = T.get("world_events") or []
    TURNS = T.get("agent_turns") or []
    SYS = T.get("system_turns") or []
    SESS = T.get("sessions") or D.get("sessions") or {}
    OUT = T.get("outcome")
    RP = T.get("replay") or {}
    META = D.get("meta") or {}
else:
    EV = D["world_events"]
    TURNS = D["agent_turns"]
    SYS = D.get("system_turns") or []
    SESS = D.get("sessions") or {}
    OUT = D.get("outcome")
    RP = D.get("replay") or {}
    META = D.get("meta") or {}


def hhmm(ts: str) -> str:
    return ts[11:16] if ts else "?"


def hour(ts: str) -> str:
    return ts[11:13] if ts else "?"


def show(t: str) -> None:
    print(f"\n===== {t} =====")


if "meta" in WANT:
    show("META")
    print("run", D.get("run_id") or META.get("run_id"), "format", D.get("format"))
    print("outcome", json.dumps(OUT, ensure_ascii=False))
    print("events", len(EV), "agent_turns", len(TURNS), "system_turns", len(SYS))
    print("replay", json.dumps({k: v for k, v in RP.items() if k != "events"}, ensure_ascii=False)[:600])
    if EV:
        print("first/last event", hhmm(EV[0]["time"]), hhmm(EV[-1]["time"]))
    print("turns by actor", collections.Counter(t["actor"] for t in TURNS).most_common())
    print("turns by role", collections.Counter(t.get("role") for t in TURNS).most_common())
    print("turn results", collections.Counter(t.get("result") for t in TURNS).most_common())
    print("turn errors", sum(1 for t in TURNS if t.get("error")))
    print("sessions", {a: len(v.get("messages") or []) for a, v in SESS.items()})

if "kinds" in WANT:
    show("EVENT KINDS")
    for k, n in collections.Counter(e["kind"] for e in EV).most_common():
        print(f"{k:24s} {n}")
    show("KINDS BY HOUR")
    sel = ["speech", "document_read", "enter", "leave", "item_given", "item_taken",
           "note_left", "note_read", "extra_arrived", "extra_removed", "item_dropped",
           "empty_turn", "world_event", "stranger_asked", "message_sent", "time_advanced"]
    grid = collections.Counter((hour(e["time"]), e["kind"]) for e in EV if e["kind"] in sel)
    hours = sorted({hour(e["time"]) for e in EV})
    print("hour " + " ".join(f"{k[:6]:>7s}" for k in sel))
    for h in hours:
        print(f"{h}   " + " ".join(f"{grid[(h, k)]:7d}" for k in sel))

if "paper" in WANT:
    show("A. PAPER / PEN NOISE")
    # 只按"纸/笔/便条/字条"判定纸笔族；不要用单字"写"，它会命中拒绝回执里的
    # "你写下的原话不会被改发给别人"（09:02 的收件人误用），那是另一族缺陷。
    pat = re.compile(r"纸|圆珠笔|钢笔|铅笔|便条|字条")
    n = 0
    for t in TURNS:
        err = t.get("error")
        if err and pat.search(str(err)) and "speak recipient" not in str(err):
            n += 1
            print(f"[reject] {hhmm(t['perception']['time'])} {t['actor']} :: {str(err)[:260]}")
    print("paper-family rejections:", n)
    print("--- 'no tool to write' style lines (inner/speech) ---")
    sp = re.compile(r"没有.{0,8}(工具|动作|方式|办法).{0,10}写|写不到|写不进|纸上|纸面|没有纸|没纸|拿不到纸|找不到.{0,4}纸|无处可写|不能写|没法写")
    for t in TURNS:
        blob = (t.get("inner") or "") + " || " + json.dumps(t.get("intention"), ensure_ascii=False)
        if sp.search(blob):
            print(f"{hhmm(t['perception']['time'])} {t['actor']} :: {(t.get('inner') or '')[:220]}")
    for e in EV:
        if e["kind"] == "speech" and sp.search(e["payload"].get("text") or ""):
            print(f"[speech] {hhmm(e['time'])} {e['actor']} :: {e['payload']['text'][:220]}")
    print("--- item_given (paper family) ---")
    for e in EV:
        if e["kind"] == "item_given" and re.search(r"纸|笔|便签", e["payload"].get("item") or ""):
            p = e["payload"]
            print(hhmm(e["time"]), f"{p.get('from') or e['actor']} → {p.get('to')}", p.get("item"))
    print("--- all item_given ---")
    for e in EV:
        if e["kind"] == "item_given":
            p = e["payload"]
            print(hhmm(e["time"]), f"{p.get('from') or e['actor']} → {p.get('to')}", p.get("item"))

if "notes" in WANT:
    show("B. leave_note / persist")
    for e in EV:
        if e["kind"] == "note_left":
            p = e["payload"]
            print(hhmm(e["time"]), e["actor"], "@", p.get("location"),
                  "persist=", p.get("persist"), "id=", p.get("id") or p.get("note_id"),
                  "len=", len(p.get("text") or ""))
            print("      ", (p.get("text") or "")[:300].replace("\n", " "))
    print("--- read of persistent notes (document_read with note id) ---")
    for e in EV:
        if e["kind"] == "document_read":
            p = e["payload"]
            ttl = p.get("title") or p.get("item") or ""
            if "note-" in str(ttl) or "note-" in json.dumps(p, ensure_ascii=False):
                print(hhmm(e["time"]), e["actor"], ttl, "::", (p.get("content") or "")[:120].replace("\n", " "))
    print("--- turns whose intention mentions persist ---")
    for t in TURNS:
        blob = json.dumps(t.get("intention"), ensure_ascii=False)
        if "persist" in blob:
            print(hhmm(t["perception"]["time"]), t["actor"], t.get("result"), blob[:220])
    print("--- tool_events / interactions names for leave_note ---")
    for e in EV:
        if e["kind"] in ("action_started", "action_completed") and "leave_note" in json.dumps(e["payload"], ensure_ascii=False):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:200])

if "canteen" in WANT:
    show("C. CANTEEN")
    for e in EV:
        p = e["payload"]
        if e["kind"] == "world_event":
            print(hhmm(e["time"]), "world_event", p.get("event"), "::", (p.get("notice") or "")[:160])
    for e in EV:
        blob = json.dumps(e["payload"], ensure_ascii=False)
        if e["kind"] in ("item_taken", "item_given", "item_dropped", "place") and re.search(r"餐食|午饭|晚饭|例汤|饮料", blob):
            print(hhmm(e["time"]), e["kind"], e["actor"], blob[:200])
    print("--- 食堂大妈 actions/speech ---")
    for e in EV:
        if e["actor"] == "食堂大妈" and e["kind"] in ("action_started", "action_completed", "speech", "wait_woken", "enter", "leave"):
            print(hhmm(e["time"]), e["kind"], json.dumps(e["payload"], ensure_ascii=False)[:200])
    print("--- 食堂 visits ---")
    for e in EV:
        if e["kind"] in ("enter", "leave") and "食堂" in json.dumps(e["payload"], ensure_ascii=False):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:120])
    print("--- speech mentioning food ---")
    for e in EV:
        if e["kind"] == "speech" and re.search(r"饭|菜|餐|窗口|阿姨|打", e["payload"]["text"]):
            print(hhmm(e["time"]), e["actor"], "::", e["payload"]["text"][:200])

if "board" in WANT:
    show("D. NOTICE BOARD")
    for e in EV:
        if e["kind"] == "document_read":
            p = e["payload"]
            print(hhmm(e["time"]), e["actor"], p.get("title"), "::", (p.get("content") or "")[:90].replace("\n", " "))
    print("--- speech mentioning board / 当值 ---")
    for e in EV:
        if e["kind"] == "speech" and re.search(r"公告栏|板上|板面|当值|通知上|纸上", e["payload"]["text"]):
            print(hhmm(e["time"]), e["actor"], "::", e["payload"]["text"][:240])
    print("--- document_read of 学生会审计通知 / 个人情况说明程序 / 催办单 ---")
    for e in EV:
        if e["kind"] == "document_read" and re.search(r"审计通知|说明程序|催办单", str(e["payload"].get("title"))):
            print(hhmm(e["time"]), e["actor"], e["payload"].get("title"), "::", (e["payload"].get("content") or "")[:140].replace("\n", " "))

if "empty" in WANT:
    show("E. EMPTY TURNS / INFLIGHT")
    for e in EV:
        if e["kind"] in ("empty_turn", "inflight_released", "decision_timeout"):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:200])
    print("--- system_turns kinds ---")
    print(collections.Counter(json.dumps(s.get("request") or s, ensure_ascii=False)[:80] for s in SYS).most_common(12))
    print("--- turns with no inner and no calls ---")
    for t in TURNS:
        inner = (t.get("inner") or "").strip()
        calls = (t.get("intention") or {}).get("args", {}).get("calls") if isinstance(t.get("intention"), dict) else None
        if not inner and not calls:
            print(hhmm(t["perception"]["time"]), t["actor"], t.get("role"), t.get("result"), repr(t.get("error"))[:100])

if "reject" in WANT:
    show("F. REJECTIONS")
    n = 0
    for t in TURNS:
        err = t.get("error")
        if not err:
            continue
        for part in str(err).split("; "):
            n += 1
            print(f"{hhmm(t['perception']['time'])} {t['actor']} [{t.get('role')}] :: {part[:300]}")
    print("total rejection fragments", n,
          "| turns rejected", sum(1 for t in TURNS if t.get("result") == "rejected"))

if "story" in WANT:
    show("G. STORY SHAPE")
    cop = collections.Counter()
    for t in TURNS:
        for o in t["perception"].get("nearby_actors") or []:
            cop[tuple(sorted((t["actor"], o)))] += 1
    print("co-presence top 20", cop.most_common(20))
    sp = [e["payload"]["text"] for e in EV if e["kind"] == "speech"]
    print("speech", len(sp), "unique", len(set(sp)))
    for s, c in collections.Counter(sp).most_common(6):
        if c > 1:
            print("DUP", c, repr(s[:120]))
    print("locations per actor per hour")
    for a in sorted({e["actor"] for e in EV if e["actor"]}):
        seq = [(hhmm(e["time"]), (e["payload"] or {}).get("location") or (e["payload"] or {}).get("to"))
               for e in EV if e.get("actor") == a and e["kind"] in ("enter", "leave")]
        print(a, seq[:24])
