"""Window-6 (18:00→22:00) mechanical readout.

Usage: python3 .scratch/v4-first-day/analyze_window6.py <run.json|checkpoint.json> [section ...]
Sections: meta mom escort notes leak items reject loops story
No file is written; everything goes to stdout. Every number in
reports/m1-window6-18to22.md comes from this script.
"""

from __future__ import annotations

import collections
import json
import sys

PATH = sys.argv[1]
START = "2026-03-16T18:00:00"
ALL = {"meta", "mom", "escort", "notes", "leak", "items", "reject", "loops", "story"}
WANT = set(sys.argv[2:]) or ALL

D = json.load(open(PATH))
EV = D.get("world_events") or []
AT = D.get("agent_turns") or []
SYS = D.get("system_turns") or []
OUT = D.get("outcome") or {}
RP = D.get("replay") or {}
NE = [e for e in EV if e["time"] >= START]
NA = [t for t in AT if t["perception"]["time"] >= START]


def hhmm(ts: str) -> str:
    return ts[11:16] if ts else "?"


def calls(t: dict) -> list[dict]:
    it = t.get("intention") or {}
    return [c for c in ((it.get("args") or {}).get("calls") or []) if isinstance(c, dict)]


def show(title: str) -> None:
    print(f"\n===== {title} =====")


if "meta" in WANT:
    show("meta")
    print(f"run_id            {D.get('run_id')}")
    print(f"event ids         {EV[0]['id']}..{EV[-1]['id']}  night={len(NE)}  contiguous={RP.get('contiguous')}")
    print(f"world versions    contiguous={RP.get('world_versions_contiguous')} last={RP.get('last_event_id')}")
    print(f"agent turns       day={len(AT)} night={len(NA)}")
    print(f"turn kinds        {collections.Counter(t.get('result') for t in NA)}")
    zero = [t for t in NA if not calls(t)]
    print(f"zero-call turns   {len(zero)} {[(hhmm(t['perception']['time']), t['actor'], t.get('result')) for t in zero]}")
    print(f"error turns       {sum(1 for t in NA if t.get('error'))}/{len(NA)}")
    night_ids = {t['perception'].get('_turn_id') for t in NA} - {None}
    night_sys = [s for s in SYS if (s.get('result') or {}).get('turn_id') in night_ids]
    print(f"system turns      night records={[json.dumps(s.get('request'))[:60] for s in night_sys]}"
          f" day-empty_turn={sum(1 for s in SYS if s.get('request', {}).get('kind') == 'empty_turn')}"
          f" day-inflight={sum(1 for s in SYS if s.get('request', {}).get('kind') == 'inflight_released')}"
          f" dialogue={sum(1 for e in NE if e['kind'] == 'system_dialogue')}"
          f" answer={sum(1 for e in NE if e['kind'] == 'system_answer')}")
    print(f"outcome           reason={OUT.get('reason')} time={OUT.get('time')} unread_notes={len(OUT.get('unread_notes') or [])}")
    print(f"event kinds       {collections.Counter(e['kind'] for e in NE).most_common()}")

if "mom" in WANT:
    show("mom line (anchor d1-妈妈承诺)")
    for e in NE:
        p = e.get("payload") or {}
        blob = json.dumps(p, ensure_ascii=False)
        if e["kind"] == "world_event" and "mom" in str(p.get("event")):
            print(f"{hhmm(e['time'])} world_event {p.get('event')} vis={e.get('visible_to')}")
            print(f"    notice: {p.get('notice')}")
        if e["kind"] in ("speech", "message_delivered") and "陈默妈" in blob:
            print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} :: {p.get('text')}")
    print("-- anchor keywords in night text (承诺打听 / 问不到) --")
    hit = 0
    for e in NE:
        p = e.get("payload") or {}
        text = str(p.get("text") or p.get("notice") or "")
        for key in ("打听", "问不到", "没问到", "老街坊", "家属院", "签字"):
            if key in text:
                hit += 1
                print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} [{key}] :: {text[:160]}")
    if not hit:
        print("no 打听/问不到/老街坊/家属院/签字 token anywhere in the night window")

if "escort" in WANT:
    show("escort / companions")
    pairs = collections.Counter()
    for e in NE:
        p = e.get("payload") or {}
        who = p.get("escorted_by")
        if who:
            pairs[(who, e["actor"])] += 1
            print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} @{p.get('location')} escorted_by={who}")
    print(f"escort pairs      {dict(pairs)}")
    print(f"extra_removed     {[(hhmm(e['time']), (e.get('payload') or {}).get('extra'), (e.get('payload') or {}).get('reason')) for e in NE if e['kind'] == 'extra_removed']}")
    for t in NA:
        for c in calls(t):
            if c.get("name") == "move":
                a = c.get("args") or {}
                print(f"{hhmm(t['perception']['time'])} move {t['actor']} -> {a.get('target')} with={a.get('with')} err={str(t.get('error'))[:60]}")

if "notes" in WANT:
    show("notes / documents")
    for e in NE:
        p = e.get("payload") or {}
        if e["kind"] == "note_left":
            print(f"{hhmm(e['time'])} note_left {e['actor']} @{p.get('location')} id={p.get('note')} persist={p.get('persist')} on={p.get('on')!r}")
            print(f"    text[:80]: {str(p.get('text'))[:80]!r}")
        if e["kind"] == "document_read":
            print(f"{hhmm(e['time'])} read {e['actor']} {p.get('document') or p.get('name') or p.get('item')}")
    print(f"outcome.unread_notes {json.dumps(OUT.get('unread_notes'), ensure_ascii=False)[:400]}")
    for t in NA:
        for c in calls(t):
            if c.get("name") in ("leave_note", "give") and t.get("error"):
                a = c.get("args") or {}
                print(f"{hhmm(t['perception']['time'])} {c['name']} {t['actor']} args={json.dumps(a, ensure_ascii=False)[:120]}")
                print(f"    err: {t.get('error')[:220]}")

if "leak" in WANT:
    show("leak / impossible knowledge")
    wide = [(hhmm(e["time"]), e["kind"], e.get("actor"), e.get("visible_to"))
            for e in NE if e.get("visible_to") and len(e["visible_to"]) > 4]
    print(f"events with visible_to>4: {wide}")
    meta_tokens = ("系统", "引擎", "参数", "接口", "下一位进入者", "也被拒绝", "刷新", "回合", "工具")
    for t in NA:
        for c in calls(t):
            if c.get("name") != "speak":
                continue
            text = str((c.get("args") or {}).get("text") or "")
            bad = [k for k in meta_tokens if k in text]
            if bad:
                print(f"{hhmm(t['perception']['time'])} SPEECH meta={bad} {t['actor']} :: {text[:180]}")
    for e in NE:
        if e["kind"] == "speech":
            p = e["payload"] or {}
            bad = [k for k in meta_tokens if k in str(p.get("text") or "")]
            if bad:
                print(f"{hhmm(e['time'])} HEARD-BY-ALL meta={bad} {e['actor']} :: {str(p.get('text'))[:180]}")

if "items" in WANT:
    show("items: take / give / trash")
    for e in NE:
        if e["kind"] in ("item_given", "item_taken", "item_trashed"):
            print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} {json.dumps(e.get('payload'), ensure_ascii=False)[:160]}")
    for t in NA:
        for c in calls(t):
            if c.get("name") in ("take", "give", "place", "trash"):
                a = c.get("args") or {}
                print(f"{hhmm(t['perception']['time'])} {c['name']} {t['actor']} {json.dumps(a, ensure_ascii=False)[:100]}"
                      f" |err| {str(t.get('error'))[:140]}")

if "reject" in WANT:
    show("rejections")
    fam = collections.Counter()
    for t in NA:
        err = t.get("error")
        if not err:
            continue
        fam[err.split("：")[0].split(":")[0][:40]] += 1
    print(f"families {fam.most_common()}")
    for t in NA:
        if t.get("error"):
            print(f"{hhmm(t['perception']['time'])} {t['actor']} :: {str(t.get('error'))[:180]}")

if "loops" in WANT:
    show("loops / idling")
    per = collections.defaultdict(collections.Counter)
    for t in NA:
        for c in calls(t):
            per[t["actor"]][c.get("name")] += 1
    for a, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"{a:6s} turns={sum(c.values()):3d} {dict(c)}")
    waits = collections.Counter()
    for t in NA:
        for c in calls(t):
            if c.get("name") == "wait":
                a = c.get("args") or {}
                waits[a.get("duration") or a.get("duration_seconds")] += 1
    print(f"wait durations {waits.most_common()}")
    sp = [e["payload"]["text"] for e in NE if e["kind"] == "speech"]
    print(f"speech {len(sp)} unique={len(set(sp))}")

if "story" in WANT:
    show("story timeline (speech + messages + notes + world events)")
    for e in NE:
        p = e.get("payload") or {}
        if e["kind"] == "speech":
            print(f"{hhmm(e['time'])} {e['actor']}: {p.get('text')}")
        elif e["kind"] == "message_delivered":
            print(f"{hhmm(e['time'])} [msg] {e['actor']} -> {p.get('target')}: {p.get('text')}")
        elif e["kind"] == "note_left":
            print(f"{hhmm(e['time'])} [note] {e['actor']} @{p.get('location')}: {str(p.get('text'))[:60]!r}")
        elif e["kind"] == "world_event":
            print(f"{hhmm(e['time'])} [world] {p.get('event')}: {str(p.get('notice'))[:120]}")
