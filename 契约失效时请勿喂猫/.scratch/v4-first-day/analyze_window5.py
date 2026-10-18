"""Window-5 (07:00→13:00 / →18:00) mechanical readout.

Usage: python3 .scratch/v4-first-day/analyze_window5.py <trace.json|checkpoint.json> [section ...]
Sections: meta escort ledger canteen notechain leak facecheck watchrelay statement boss
          reject loops story
No file is written; everything goes to stdout.
"""

from __future__ import annotations

import collections
import json
import re
import sys

PATH = sys.argv[1]
ALL = {"meta", "escort", "ledger", "canteen", "notechain", "leak", "facecheck",
       "watchrelay", "statement", "boss", "reject", "loops", "story"}
WANT = set(sys.argv[2:]) or ALL

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


def blob(e: dict) -> str:
    return json.dumps(e.get("payload") or {}, ensure_ascii=False)


if "meta" in WANT:
    show("META")
    print("run", D.get("run_id") or META.get("run_id"), "format", D.get("format"))
    print("outcome", json.dumps(OUT, ensure_ascii=False)[:800])
    print("events", len(EV), "agent_turns", len(TURNS), "system_turns", len(SYS))
    print("replay", json.dumps({k: v for k, v in RP.items() if k != "events"}, ensure_ascii=False)[:600])
    if EV:
        print("first/last event", hhmm(EV[0]["time"]), hhmm(EV[-1]["time"]))
    print("kinds", collections.Counter(e["kind"] for e in EV).most_common())
    print("turns by actor", collections.Counter(t["actor"] for t in TURNS).most_common())
    print("turn results", collections.Counter(t.get("result") for t in TURNS).most_common())
    print("turn errors", sum(1 for t in TURNS if t.get("error")))
    print("sessions", {a: len(v.get("messages") or []) for a, v in SESS.items()})

if "escort" in WANT:
    show("A. 搀扶/陪行 (move with)")
    esc = [e for e in EV if e["kind"] == "action_started"
           and (e["payload"] or {}).get("action") == "move"
           and (e["payload"] or {}).get("with")]
    print("move-with attempts (accepted)", len(esc))
    for e in esc:
        print(hhmm(e["time"]), e["actor"], "->", e["payload"].get("target"),
              "with", e["payload"].get("with"), "visible_to", e.get("visible_to"))
    print("--- leave with escorted_by ---")
    for e in EV:
        if e["kind"] == "leave" and (e["payload"] or {}).get("escorted_by"):
            print(hhmm(e["time"]), e["actor"], "escorted_by", e["payload"]["escorted_by"],
                  "from", e["payload"].get("location") or e["payload"].get("from"))
    print("--- enter of classroom locations ---")
    for e in EV:
        if e["kind"] == "enter" and re.search(r"302|305|三楼走廊", blob(e)):
            print(hhmm(e["time"]), e["actor"], blob(e)[:160])
    print("--- 305 / 302 talk: per-actor counts ---")
    talk = collections.defaultdict(int)
    for e in EV:
        if e["kind"] == "speech" and re.search(r"305|302|三楼|教室|搀|扶|陪", (e["payload"] or {}).get("text") or ""):
            talk[e["actor"]] += 1
    print(dict(talk), "total", sum(talk.values()))
    print("--- refusal family: 我不能/没法/不能 + 扶|搀|陪|带 ---")
    pat = re.compile(r"(不能|没法|无法|没办法)[^。！？]{0,12}(扶|搀|陪|带|扶您|扶着)|我扶不了|没人扶")
    n = 0
    per = collections.Counter()
    first = last = None
    for e in EV:
        if e["kind"] != "speech":
            continue
        t = (e["payload"] or {}).get("text") or ""
        if pat.search(t):
            n += 1
            per[e["actor"]] += 1
            first = first or e["time"]
            last = e["time"]
            if n <= 25:
                print(" ", hhmm(e["time"]), e["actor"], "::", t[:160])
    print("refusal sentences", n, "actors", per.most_common(), "window", hhmm(first or ""),
          "→", hhmm(last or ""))
    print("--- 305-family speech span (by 10-min bucket) ---")
    buckets = collections.Counter()
    for e in EV:
        if e["kind"] == "speech" and re.search(r"305|搀|扶|陪", (e["payload"] or {}).get("text") or ""):
            buckets[e["time"][11:15]] += 1
    print(sorted(buckets.items()))

if "ledger" in WANT:
    show("B. 台账 (system_answer / system_dialogue)")
    for e in EV:
        if e["kind"] in ("system_case_accepted", "system_answer", "system_reward_granted",
                         "system_dialogue"):
            print(hhmm(e["time"]), e["kind"], e["actor"], "visible_to=", e.get("visible_to"),
                  blob(e)[:420])
    print("--- turns: speak to 台账 ---")
    for t in TURNS:
        for c in calls_of(t):
            if (c.get("name") or "").lower() != "speak":
                continue
            to = (c.get("arguments") or {}).get("to") or []
            if isinstance(to, str):
                to = [to]
            if any("台账" in str(x) for x in to):
                print(hhmm(t["perception"]["time"]), t["actor"], t.get("result"),
                      "to=", to, "::", text_of(c)[:200], "err=", str(t.get("error"))[:200])

if "canteen" in WANT:
    show("C. 食堂 (item_given / 大妈)")
    print("--- all item_given ---")
    for e in EV:
        if e["kind"] == "item_given":
            print(hhmm(e["time"]), e["actor"], blob(e)[:220])
    print("--- all item_taken involving food ---")
    for e in EV:
        if e["kind"] in ("item_taken", "item_trashed") and re.search(
                r"餐|饭|套餐|例汤|面包|糕点|馒头|包子|粥|面", blob(e)):
            print(hhmm(e["time"]), e["kind"], e["actor"], blob(e)[:220])
    print("--- 食堂大妈 event kinds ---")
    print(collections.Counter(e["kind"] for e in EV if e.get("actor") == "食堂大妈").most_common())
    print("--- 食堂大妈 speech ---")
    for e in EV:
        if e["kind"] == "speech" and e["actor"] == "食堂大妈":
            print(hhmm(e["time"]), "::", ((e["payload"] or {}).get("text") or "")[:200],
                  "to=", (e["payload"] or {}).get("to"))
    print("--- turns where 食堂大妈 uses give ---")
    for t in TURNS:
        if t["actor"] != "食堂大妈":
            continue
        for c in calls_of(t):
            if (c.get("name") or "").lower() in ("give", "take"):
                print(hhmm(t["perception"]["time"]), t.get("result"),
                      json.dumps(c, ensure_ascii=False)[:200], "err=", str(t.get("error"))[:200])

if "notechain" in WANT:
    show("D. 文稿链 (leave_note persist / on)")
    for t in TURNS:
        for c in calls_of(t):
            if (c.get("name") or "").lower() != "leave_note":
                continue
            a = c.get("arguments") or {}
            print(hhmm(t["perception"]["time"]), t["actor"], t.get("result"),
                  "on=", a.get("on"), "persist=", a.get("persist"),
                  "::", (a.get("text") or "")[:120], "err=", str(t.get("error"))[:220])
    print("--- note_left / document_annotated events ---")
    for e in EV:
        if e["kind"] in ("note_left", "document_annotated"):
            print(hhmm(e["time"]), e["kind"], e["actor"], "visible_to=", e.get("visible_to"),
                  blob(e)[:260])
    print("--- paper/pen refusals ---")
    for e in EV:
        if e["kind"] == "speech" and re.search(r"没有笔|没笔|纸上写不了|写不了|没有纸", (e["payload"] or {}).get("text") or ""):
            print(hhmm(e["time"]), e["actor"], "::", e["payload"]["text"][:160])

if "leak" in WANT:
    show("E. 泄漏 (world_event visible_to)")
    for e in EV:
        if e["kind"] == "world_event":
            p = e["payload"] or {}
            print(hhmm(e["time"]), "event=", p.get("event"), "location=", p.get("location"),
                  "target=", p.get("target"), "visible_to(", len(e.get("visible_to") or []), ")=",
                  e.get("visible_to"), "::", (p.get("notice") or "")[:160].replace("\n", " "))
    print("--- speech referencing 催办/说明/最迟明早 by people outside the office ---")
    for e in EV:
        if e["kind"] != "speech":
            continue
        t = (e["payload"] or {}).get("text") or ""
        if re.search(r"催办|说明|最迟明早|明早交|面核|审计包", t):
            print(hhmm(e["time"]), e["actor"], "::", t[:200])

if "facecheck" in WANT:
    show("F. 面核记录 / 审计包")
    for e in EV:
        if re.search(r"面核记录|学生会审计包", blob(e)) and e["kind"] in (
                "document_read", "document_annotated", "note_left", "item_given",
                "action_started", "world_event", "item_taken"):
            print(hhmm(e["time"]), e["kind"], e.get("actor"), blob(e)[:260])
    print("--- turns reading 面核记录 ---")
    for t in TURNS:
        for c in calls_of(t):
            if "面核" in json.dumps(c, ensure_ascii=False):
                print(hhmm(t["perception"]["time"]), t["actor"], t.get("result"),
                      json.dumps(c, ensure_ascii=False)[:200], "err=", str(t.get("error"))[:200])

if "watchrelay" in WANT:
    show("G. 留守接力")
    pat = re.compile(r"留守|接力|当值|替班|顶班|闭馆|17:00|五点")
    per10 = collections.Counter()
    for e in EV:
        if e["kind"] == "speech" and pat.search((e["payload"] or {}).get("text") or ""):
            per10[(e["time"][11:15], e["actor"])] += 1
    for k in sorted(per10):
        print(k, per10[k])
    print("--- world_event carrying 留守口径 ---")
    for e in EV:
        if e["kind"] == "world_event" and pat.search(blob(e)):
            print(hhmm(e["time"]), blob(e)[:400])

if "statement" in WANT:
    show("H. 个人情况说明程序")
    for e in EV:
        if re.search(r"个人情况说明|说明程序|情况说明", blob(e)):
            print(hhmm(e["time"]), e["kind"], e.get("actor"), "visible_to=", e.get("visible_to"),
                  blob(e)[:300])
    for t in TURNS:
        blobt = json.dumps(calls_of(t), ensure_ascii=False)
        if re.search(r"个人情况说明|情况说明", blobt):
            print("[turn]", hhmm(t["perception"]["time"]), t["actor"], t.get("result"),
                  blobt[:240], "err=", str(t.get("error"))[:160])

if "boss" in WANT:
    show("I. 老板娘")
    for e in EV:
        if re.search(r"老板娘|糕点铺", blob(e)):
            print(hhmm(e["time"]), e["kind"], e.get("actor"), "visible_to=", e.get("visible_to"),
                  blob(e)[:280])

if "reject" in WANT:
    show("J. REJECTIONS")
    n = 0
    fam = collections.Counter()
    for t in TURNS:
        err = t.get("error")
        if not err:
            continue
        for part in str(err).split("; "):
            n += 1
            if re.search(r"扶|搀|陪|带", part):
                fam["escort"] += 1
            elif re.search(r"笔|纸|写不了", part):
                fam["paper"] += 1
            elif re.search(r"不是.{0,6}地方|知道的地方", part):
                fam["place"] += 1
            elif re.search(r"收件人|不认识|没有这个人", part):
                fam["recipient"] += 1
            elif re.search(r"手上没有|不在你|找不到", part):
                fam["item"] += 1
            else:
                fam["other"] += 1
            print(f"{hhmm(t['perception']['time'])} {t['actor']} [{t.get('role')}] :: {part[:240]}")
    print("total fragments", n, "| turns rejected",
          sum(1 for t in TURNS if t.get("result") == "rejected"), "| families", fam.most_common())

if "loops" in WANT:
    show("K. LOOPS / repeated speech")
    sp = [(e["time"], e["actor"], (e["payload"] or {}).get("text") or "") for e in EV
          if e["kind"] == "speech"]
    print("speech", len(sp), "unique", len({s[2] for s in sp}))
    for s, c in collections.Counter(x[2] for x in sp).most_common(10):
        if c > 1:
            print("DUP", c, repr(s[:150]))
    print("--- same-actor same-topic within 30 min (topic keyword co-occurrence) ---")
    topics = {"escort": r"305|搀|扶|陪", "watch": r"留守|接力|当值", "ledger": r"台账",
              "schedule": r"课表|教室", "audit": r"审计|面核|说明"}
    for name, pat in topics.items():
        per = collections.defaultdict(list)
        for ts, a, t in sp:
            if re.search(pat, t):
                per[a].append(ts)
        for a, ts in per.items():
            print(name, a, len(ts), hhmm(ts[0]), "→", hhmm(ts[-1]))
    print("--- empty / timeout events ---")
    print(collections.Counter(e["kind"] for e in EV if e["kind"] in (
        "empty_turn", "decision_timeout", "inflight_released", "hung_decision_abandoned")).most_common())
    print("system_turn results", collections.Counter(
        json.dumps(s.get("result") or s, ensure_ascii=False)[:70] for s in SYS).most_common(8))

if "story" in WANT:
    show("L. STORY SHAPE")
    cop = collections.Counter()
    for t in TURNS:
        for o in t["perception"].get("nearby_actors") or []:
            cop[tuple(sorted((t["actor"], o)))] += 1
    print("co-presence top 20", cop.most_common(20))
    print("--- locations over time per actor ---")
    for a in sorted({e["actor"] for e in EV if e.get("actor")}):
        seq = [(hhmm(e["time"]), (e["payload"] or {}).get("location") or (e["payload"] or {}).get("to"))
               for e in EV if e.get("actor") == a and e["kind"] in ("enter",)]
        print(a, seq[:24])
    print("--- 陈默×林瑶 ---")
    for e in EV:
        if e["kind"] in ("action_started",) and e.get("actor") in ("陈默", "林瑶") and \
                (e["payload"] or {}).get("action") in ("speak", "text", "message_sent"):
            tgt = (e["payload"] or {}).get("to") or (e["payload"] or {}).get("target")
            if re.search(r"林瑶|陈默", str(tgt)):
                print(hhmm(e["time"]), e["actor"], "→", tgt, "::",
                      ((e["payload"] or {}).get("text") or "")[:140])
