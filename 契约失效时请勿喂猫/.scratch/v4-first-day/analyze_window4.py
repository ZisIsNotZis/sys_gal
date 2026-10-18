"""Window-4 (07:00→17:00) mechanical readout for the m1-window4 report.

Usage: python3 .scratch/v4-first-day/analyze_window4.py <trace.json|checkpoint.json> [section ...]
Sections: meta ledger schedule canteen tang alias audit16 empty reject story
Accepts either the final run artifact or a checkpoint (trace.* layout).
No file is written; everything goes to stdout.
"""

from __future__ import annotations

import collections
import json
import re
import sys

PATH = sys.argv[1]
WANT = set(sys.argv[2:]) or {"meta", "ledger", "schedule", "canteen", "tang",
                             "alias", "audit16", "empty", "reject", "story"}
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


def calls_of(turn: dict) -> list[dict]:
    it = turn.get("intention")
    if not isinstance(it, dict):
        return []
    args = it.get("args") or it.get("arguments") or {}
    c = args.get("calls")
    if isinstance(c, list):
        out = []
        for x in c:
            if not isinstance(x, dict):
                continue
            out.append({"name": x.get("name"),
                        "arguments": x.get("args") or x.get("arguments") or {}})
        return out
    return [{"name": it.get("name") or it.get("kind"), "arguments": args}]


def text_of(call: dict) -> str:
    a = call.get("arguments") or {}
    for k in ("text", "content", "query", "question", "note", "body"):
        if isinstance(a.get(k), str):
            return a[k]
    return ""


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

if "ledger" in WANT:
    show("A. LEDGER (system_answer / case)")
    for e in EV:
        if e["kind"] in ("system_case_accepted", "system_answer", "system_reward_granted",
                         "system_penalty_applied"):
            print(hhmm(e["time"]), e["kind"], e["actor"], "visible_to=", e.get("visible_to"),
                  json.dumps(e["payload"], ensure_ascii=False)[:300])
    print("--- turns whose speak targets 台账 ---")
    for t in TURNS:
        for c in calls_of(t):
            if (c.get("name") or "").lower() != "speak":
                continue
            to = (c.get("arguments") or {}).get("to") or []
            if isinstance(to, str):
                to = [to]
            if any("台账" in str(x) for x in to):
                print(hhmm(t["perception"]["time"]), t["actor"], t.get("result"),
                      "to=", to, "text=", text_of(c)[:120], "err=", str(t.get("error"))[:160])
    print("--- session: assistant speaks to 台账 and the tool reply ---")
    for actor, sess in SESS.items():
        msgs = sess.get("messages") or []
        for i, m in enumerate(msgs):
            blob = json.dumps(m, ensure_ascii=False)
            if "台账" not in blob or m.get("role") != "assistant":
                continue
            for tc in (m.get("tool_calls") or []):
                fn = tc.get("function") or {}
                if "台账" not in str(fn.get("arguments")):
                    continue
                reply = ""
                for j in range(i + 1, min(i + 6, len(msgs))):
                    if msgs[j].get("role") == "tool":
                        reply = str(msgs[j].get("content"))[:400]
                        break
                print(actor, "::", str(fn.get("arguments"))[:160])
                print("    REPLY:", reply.replace("\n", " "))

if "schedule" in WANT:
    show("B. SCHEDULE / CLASSROOM")
    pat = re.compile(r"课表|教室|上课|教学楼|房号|第[一二三四五六七八九]节|几点上课|哪间")
    print("--- document_read titles mentioning 课表/通知/排班 ---")
    for e in EV:
        if e["kind"] == "document_read" and re.search(r"课表|通知|排班|值班表|安排", str(e["payload"].get("title"))):
            p = e["payload"]
            print(hhmm(e["time"]), e["actor"], p.get("title"), "::", (p.get("content") or "")[:260].replace("\n", " "))
    print("--- speech mentioning schedule ---")
    n = 0
    for e in EV:
        if e["kind"] == "speech" and pat.search(e["payload"].get("text") or ""):
            n += 1
            print(hhmm(e["time"]), e["actor"], "::", e["payload"]["text"][:220])
    print("schedule speech count", n)
    print("--- who mentioned 课表 at all (first/last) ---")
    per = collections.defaultdict(list)
    for e in EV:
        if e["kind"] == "speech" and pat.search(e["payload"].get("text") or ""):
            per[e["actor"]].append(e["time"])
    for a, ts in per.items():
        print(a, len(ts), hhmm(ts[0]), "→", hhmm(ts[-1]))

if "canteen" in WANT:
    show("C. CANTEEN")
    for e in EV:
        p = e["payload"]
        if e["kind"] == "world_event":
            print(hhmm(e["time"]), "world_event", p.get("event"), "::", (p.get("notice") or "")[:160])
        if e["kind"] in ("wait_woken", "private_wake") and e.get("actor") == "食堂大妈":
            print(hhmm(e["time"]), e["kind"], json.dumps(p, ensure_ascii=False)[:200])
    print("--- 食堂大妈 events ---")
    for e in EV:
        if e.get("actor") == "食堂大妈" and e["kind"] in (
                "enter", "leave", "action_started", "action_completed", "speech", "item_given", "item_taken"):
            print(hhmm(e["time"]), e["kind"], json.dumps(e["payload"], ensure_ascii=False)[:220])
    print("--- item_given / item_taken involving food ---")
    for e in EV:
        blob = json.dumps(e["payload"], ensure_ascii=False)
        if e["kind"] in ("item_given", "item_taken") and re.search(r"餐|饭|套餐|例汤|面包|糕点|馒头|包子", blob):
            print(hhmm(e["time"]), e["kind"], e["actor"], blob[:240])
    print("--- speech mentioning food ---")
    for e in EV:
        if e["kind"] == "speech" and re.search(r"饭|打饭|窗口|阿姨|餐食|午饭", e["payload"]["text"]):
            print(hhmm(e["time"]), e["actor"], "::", e["payload"]["text"][:200])

if "tang" in WANT:
    show("D. 唐小岚 缺口杯 / 备品清单")
    pat = re.compile(r"缺口|缺角|备品|杯子|茶壶|泡茶")
    for e in EV:
        if e["kind"] == "speech" and e["actor"] == "唐小岚" and pat.search(e["payload"]["text"]):
            print("[speech]", hhmm(e["time"]), "::", e["payload"]["text"][:240])
    for t in TURNS:
        if t["actor"] != "唐小岚":
            continue
        blob = (t.get("inner") or "") + json.dumps(t.get("intention"), ensure_ascii=False)
        if pat.search(blob):
            print("[turn]", hhmm(t["perception"]["time"]), t.get("result"), (t.get("inner") or "")[:200])
    print("--- document_read of 备品清单 ---")
    for e in EV:
        if e["kind"] == "document_read" and "备品" in json.dumps(e["payload"], ensure_ascii=False):
            print(hhmm(e["time"]), e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:300])

if "alias" in WANT:
    show("E. 15:00 后街糕点铺 / aliases 老板娘")
    for e in EV:
        if e["kind"] in ("extra_arrived", "extra_removed") and (e["time"][11:13] >= "15" or "糕点" in json.dumps(e["payload"], ensure_ascii=False)):
            print(hhmm(e["time"]), e["kind"], e.get("actor"), json.dumps(e["payload"], ensure_ascii=False)[:200])
    print("--- speech to/from 老板娘 (or mentioning 糕点铺) ---")
    for e in EV:
        blob = json.dumps(e["payload"], ensure_ascii=False)
        if e["kind"] == "speech" and re.search(r"老板娘|糕点铺|糕点", blob):
            print(hhmm(e["time"]), e["actor"], "::", (e["payload"].get("text") or "")[:240],
                  "to=", e["payload"].get("to"))
    print("--- 唐小岚 speech after 14:30 mentioning 话/带话/李/回话 ---")
    for e in EV:
        if e["kind"] == "speech" and e["actor"] == "唐小岚" and e["time"][11:13] >= "14" \
                and re.search(r"话|带|转达|原话|点心|糕点", e["payload"]["text"]):
            print(hhmm(e["time"]), "::", e["payload"]["text"][:240])
    print("--- stranger_asked after 14:30 ---")
    for e in EV:
        if e["kind"] == "stranger_asked" and e["time"][11:13] >= "14":
            print(hhmm(e["time"]), e.get("actor"), json.dumps(e["payload"], ensure_ascii=False)[:200])

if "audit16" in WANT:
    show("F. 16:00 催办 / 16:20 面核 / 16:45 程序")
    for e in EV:
        if e["kind"] == "world_event" and e["time"][11:13] >= "15":
            print(hhmm(e["time"]), "world_event", json.dumps(e["payload"], ensure_ascii=False)[:300])
    print("--- document_read after 15:00 ---")
    for e in EV:
        if e["kind"] == "document_read" and e["time"][11:13] >= "15":
            print(hhmm(e["time"]), e["actor"], e["payload"].get("title"), "::",
                  (e["payload"].get("content") or "")[:200].replace("\n", " "))
    print("--- notes / annotate after 15:00 ---")
    for e in EV:
        if e["kind"] in ("note_left", "document_annotated", "annotate") and e["time"][11:13] >= "15":
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:300])
    print("--- speech after 15:30 mentioning 催办/面核/说明程序/当值 ---")
    for e in EV:
        if e["kind"] == "speech" and e["time"][11:13] >= "15" and \
                re.search(r"催办|面核|说明程序|程序|当值|签字|签", e["payload"]["text"]):
            print(hhmm(e["time"]), e["actor"], "::", e["payload"]["text"][:240])

if "empty" in WANT:
    show("G. EMPTY TURNS / INFLIGHT / NO_ACTION_NOTE")
    et = [e for e in EV if e["kind"] == "empty_turn"]
    print("empty_turn events", len(et))
    for e in et:
        print(hhmm(e["time"]), e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:200])
    print("--- inflight_released / decision_timeout / abandoned ---")
    for e in EV:
        if e["kind"] in ("inflight_released", "decision_timeout", "decision_abandoned",
                         "hung_decision_abandoned", "actor_task_crash"):
            print(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(e["payload"], ensure_ascii=False)[:200])
    print("--- system_turn kinds ---")
    print(collections.Counter(json.dumps(s.get("result") or s, ensure_ascii=False)[:90] for s in SYS).most_common(10))
    print("--- no-action note occurrences per session ---")
    for a, sess in SESS.items():
        n = 0
        for m in sess.get("messages") or []:
            if m.get("role") == "user" and "没有调用任何工具" in str(m.get("content")):
                n += 1
        if n:
            print(a, n)
    print("--- per-actor max consecutive zero-call turns ---")
    seq = collections.defaultdict(list)
    for t in TURNS:
        seq[t["actor"]].append(1 if not calls_of(t) else 0)
    for a, bits in seq.items():
        best = cur = 0
        start = None
        best_at = None
        for i, b in enumerate(bits):
            if b:
                cur += 1
                if cur == 1:
                    start = i
                if cur > best:
                    best, best_at = cur, start
            else:
                cur = 0
        if best >= 2:
            print(a, "max streak", best, "at turn", best_at)

if "reject" in WANT:
    show("H. REJECTIONS")
    n = 0
    for t in TURNS:
        err = t.get("error")
        if not err:
            continue
        for part in str(err).split("; "):
            n += 1
            print(f"{hhmm(t['perception']['time'])} {t['actor']} [{t.get('role')}] :: {part[:280]}")
    print("total rejection fragments", n,
          "| turns rejected", sum(1 for t in TURNS if t.get("result") == "rejected"))

if "story" in WANT:
    show("I. STORY SHAPE")
    cop = collections.Counter()
    for t in TURNS:
        for o in t["perception"].get("nearby_actors") or []:
            cop[tuple(sorted((t["actor"], o)))] += 1
    print("co-presence top 20", cop.most_common(20))
    sp = [e["payload"]["text"] for e in EV if e["kind"] == "speech"]
    print("speech", len(sp), "unique", len(set(sp)))
    for s, c in collections.Counter(sp).most_common(8):
        if c > 1:
            print("DUP", c, repr(s[:140]))
    print("--- locations per actor (enter/leave) ---")
    for a in sorted({e["actor"] for e in EV if e.get("actor")}):
        seq = [(hhmm(e["time"]), (e["payload"] or {}).get("location") or (e["payload"] or {}).get("to"))
               for e in EV if e.get("actor") == a and e["kind"] in ("enter", "leave")]
        print(a, seq[:40])
