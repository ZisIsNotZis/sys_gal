"""D1 全天验收机械读数（07:00→22:00）。

用法: python3 .scratch/v4-first-day/analyze_day1.py <run.json> [section ...]
section: meta ledger escort docs sleep mom daye vis items empty reject loops story
只打印，不写文件。
"""

from __future__ import annotations

import collections
import json
import sys

PATH = sys.argv[1]
ALL = {"meta", "ledger", "escort", "docs", "sleep", "mom", "daye", "vis",
       "items", "empty", "reject", "loops", "story"}
WANT = set(sys.argv[2:]) or ALL

D = json.load(open(PATH))
EV = D.get("world_events") or []
AT = D.get("agent_turns") or []
SYS = D.get("system_turns") or []
OUT = D.get("outcome") or {}
RP = D.get("replay") or {}


def hhmm(ts: str) -> str:
    return ts[11:16] if ts else "?"


def calls(t: dict) -> list[dict]:
    it = t.get("intention") or {}
    return [c for c in ((it.get("args") or {}).get("calls") or []) if isinstance(c, dict)]


def pay(e: dict) -> dict:
    return e.get("payload") or {}


def show(title: str) -> None:
    print(f"\n===== {title} =====")


def in_window(ts: str, lo: str, hi: str) -> bool:
    return ts is not None and lo <= ts <= hi


if "meta" in WANT:
    show("meta")
    print(f"run_id     {D.get('run_id')}")
    print(f"events     {EV[0]['id']}..{EV[-1]['id']} n={len(EV)} contiguous={RP.get('contiguous')} "
          f"versions_contiguous={RP.get('world_versions_contiguous')}")
    print(f"turns      {len(AT)}  system_turns={len(SYS)}  gm_turns={len(D.get('gm_turns') or [])}")
    print(f"first/last {hhmm(RP.get('first_time'))} -> {hhmm(RP.get('last_time'))}")
    print(f"outcome    reason={OUT.get('reason')} time={OUT.get('time')} version={OUT.get('world_version')}")
    print(f"turn kinds {collections.Counter(t.get('result') for t in AT).most_common()}")
    print(f"ev kinds   {collections.Counter(e['kind'] for e in EV).most_common()}")
    print(f"sys kinds  {collections.Counter((s.get('request') or {}).get('kind') for s in SYS).most_common()}")
    per = collections.Counter(t.get("actor") for t in AT)
    print(f"turns/actor {per.most_common()}")
    print(f"actors with turns {RP.get('actors_with_turns')}")
    print(f"errors     {sum(1 for t in AT if t.get('error'))}")

if "ledger" in WANT:
    show("A 台账: system_answer / system_dialogue / 结算")
    for e in EV:
        if e["kind"] in ("system_answer", "system_dialogue", "system_case_accepted"):
            print(f"{hhmm(e['time'])} {e['kind']} vis={e.get('visible_to')}")
            print(f"   payload: {json.dumps(pay(e), ensure_ascii=False)[:600]}")
    print("-- system_turns 原文 --")
    for s in SYS:
        r = s.get("request") or {}
        res = s.get("result") or {}
        print(f"{r.get('kind')} actor={r.get('actor')} at={str(r.get('time'))[11:16]} "
              f"ok={res.get('ok')} : {json.dumps(res, ensure_ascii=False)[:300]}")
    blame = ("结算", "结案", "settle", "判定", "裁定", "结清")
    hits = [(hhmm(e["time"]), e["kind"], e["actor"], json.dumps(pay(e), ensure_ascii=False)[:200])
            for e in EV if any(k in json.dumps(pay(e), ensure_ascii=False) for k in blame)]
    print(f"settlement-ish events ({len(hits)}):")
    for h in hits:
        print("   ", h)
    for t in AT:
        for c in calls(t):
            txt = json.dumps(c.get("args") or {}, ensure_ascii=False)
            if c.get("name") in ("query_system", "ask_system", "system_query") or "台账" in txt and c.get("name") != "speak":
                print(f"{hhmm(t['perception']['time'])} {c.get('name')} {t['actor']} {txt[:160]} |err| {str(t.get('error'))[:120]}")

if "escort" in WANT:
    show("B 同行: move with / escorted_by / 途中回收")
    mv = collections.Counter()
    for t in AT:
        for c in calls(t):
            if c.get("name") == "move":
                a = c.get("args") or {}
                mv[bool(a.get("with"))] += 1
                if a.get("with"):
                    print(f"{hhmm(t['perception']['time'])} move-with {t['actor']} -> {a.get('target')} with={a.get('with')} "
                          f"|err| {str(t.get('error'))[:100]}")
    print(f"move calls with-with={mv[True]} without={mv[False]}")
    pairs = collections.Counter()
    for e in EV:
        p = pay(e)
        if p.get("escorted_by"):
            pairs[(p.get("escorted_by"), e["actor"])] += 1
            print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} @{p.get('location')} escorted_by={p.get('escorted_by')} vis={e.get('visible_to')}")
    print(f"escort pairs {dict(pairs)}")
    print("-- 非正常离场/回收类事件 --")
    for e in EV:
        if e["kind"] in ("action_interrupted", "action_resumed", "extra_removed", "knock", "private_wake"):
            print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} {json.dumps(pay(e), ensure_ascii=False)[:160]}")
    print("-- 林瑶室友 位置轨迹（是否到过 302/305） --")
    loc = None
    for e in EV:
        if e["actor"] != "林瑶室友":
            continue
        p = pay(e)
        if e["kind"] in ("enter", "leave"):
            new = p.get("location")
            if new != loc:
                print(f"{hhmm(e['time'])} {e['kind']} {new}")
                loc = new
    for t in AT:
        if t.get("actor") == "林瑶室友":
            print(f"{hhmm(t['perception']['time'])} turn loc={ (t['perception'].get('location') or '?')}:: "
                  f"{[c.get('name') for c in calls(t)]}")

if "docs" in WANT:
    show("C 文稿: persist 便条 / document_annotated / give 便条")
    for e in EV:
        if e["kind"] == "note_left":
            p = pay(e)
            print(f"{hhmm(e['time'])} note_left {e['actor']} @{p.get('location')} id={p.get('note')} persist={p.get('persist')} on={p.get('on')!r} vis={e.get('visible_to')}")
            print(f"    text[:100]: {str(p.get('text'))[:100]!r}")
    print(f"note_left persist=True: {sum(1 for e in EV if e['kind']=='note_left' and pay(e).get('persist'))}"
          f" / total {sum(1 for e in EV if e['kind']=='note_left')}")
    print(f"document_annotated: {sum(1 for e in EV if e['kind']=='document_annotated')}")
    for e in EV:
        if e["kind"] == "document_annotated":
            print(f"{hhmm(e['time'])} annotate {e['actor']} {json.dumps(pay(e), ensure_ascii=False)[:200]} vis={e.get('visible_to')}")
    for e in EV:
        if e["kind"] == "document_read":
            p = pay(e)
            print(f"{hhmm(e['time'])} read {e['actor']} {p.get('document') or p.get('name') or p.get('item')} auto={p.get('auto')} vis={e.get('visible_to')}")
    print("-- give/leave_note 调用（含失败） --")
    for t in AT:
        for c in calls(t):
            if c.get("name") in ("give", "leave_note", "annotate", "sign"):
                a = c.get("args") or {}
                print(f"{hhmm(t['perception']['time'])} {c.get('name')} {t['actor']} {json.dumps(a, ensure_ascii=False)[:150]} "
                      f"|err| {str(t.get('error'))[:200]}")
    print(f"outcome.unread_notes {json.dumps(OUT.get('unread_notes'), ensure_ascii=False)[:600]}")

if "sleep" in WANT:
    show("D 睡眠: wait 次数/时长 + 夜间 wait 连打")
    waits = collections.Counter()
    total_wait = 0
    for t in AT:
        for c in calls(t):
            if c.get("name") == "wait":
                a = c.get("args") or {}
                dur = a.get("duration") or a.get("duration_seconds") or a.get("seconds")
                waits[dur] += 1
                total_wait += 1
    print(f"wait calls {total_wait} durations={waits.most_common()}")
    print("-- sleep/until 类参数出现 --")
    for t in AT:
        for c in calls(t):
            if c.get("name") == "wait":
                a = c.get("args") or {}
                extra = {k: v for k, v in a.items() if k not in ("duration", "duration_seconds", "seconds")}
                if extra:
                    print(f"{hhmm(t['perception']['time'])} {t['actor']} {json.dumps(a, ensure_ascii=False)[:140]}")
    night = [t for t in AT if t["perception"]["time"][11:16] >= "18:00"]
    nw = [c for t in night for c in calls(t) if c.get("name") == "wait"]
    print(f"night(>=18:00) turns={len(night)} wait_calls={len(nw)} share={len(nw)/max(1,len(night)):.0%}")
    print(f"window 19:14-21:24 turns={sum(1 for t in AT if in_window(t['perception']['time'][11:16],'19:14','21:24'))}")
    for e in EV:
        if e["kind"] == "wait_woken":
            print(f"{hhmm(e['time'])} wait_woken {e['actor']} {json.dumps(pay(e), ensure_ascii=False)[:120]}")
    print("-- 每小时回合数 --")
    per_hour = collections.Counter(t["perception"]["time"][11:13] for t in AT)
    print(dict(sorted(per_hour.items())))

if "mom" in WANT:
    show("E 妈妈 19:30")
    for e in EV:
        p = pay(e)
        blob = json.dumps(p, ensure_ascii=False)
        if e["kind"] == "world_event" and ("mom" in str(p.get("event")) or "妈" in blob[:80]):
            print(f"{hhmm(e['time'])} world_event {p.get('event')} vis={e.get('visible_to')}")
            print(f"    notice: {p.get('notice')}")
        if e["kind"] in ("speech", "message_delivered", "message_sent") and e["actor"] in ("陈默", "陈默妈"):
            if "妈" in str(p.get("text"))[:40] or e["actor"] == "陈默妈":
                print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} -> {p.get('target')}: {p.get('text')}")
    keys = ("打听", "问不到", "没问到", "老街坊", "家属院", "签字", "托")
    for e in EV:
        text = str(pay(e).get("text") or pay(e).get("notice") or "")
        hit = [k for k in keys if k in text]
        if hit:
            print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} {hit} :: {text[:200]}")

if "daye" in WANT:
    show("F 大爷过夜线")
    print(f"下棋大爷 turns: {sum(1 for t in AT if t.get('actor')=='下棋大爷')}")
    for t in AT:
        if t.get("actor") == "下棋大爷":
            print(f"{hhmm(t['perception']['time'])} loc={t['perception'].get('location')} {json.dumps([c.get('name') for c in calls(t)], ensure_ascii=False)} "
                  f"|err| {str(t.get('error'))[:100]}")
    for e in EV:
        if e["actor"] == "下棋大爷" or "大爷" in json.dumps(pay(e), ensure_ascii=False)[:120]:
            if e["kind"] in ("world_event", "enter", "leave", "extra_arrived", "extra_removed", "speech"):
                print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} {json.dumps(pay(e), ensure_ascii=False)[:200]}")
    print("-- 夜间(>=18:00) world_event --")
    for e in EV:
        if e["kind"] == "world_event" and e["time"][11:16] >= "18:00":
            print(f"{hhmm(e['time'])} {pay(e).get('event')}: {str(pay(e).get('notice'))[:160]}")

if "vis" in WANT:
    show("G visible_to 检查（15:50-17:00 + 全局宽播）")
    for e in EV:
        if in_window(e["time"][11:16], "15:50", "17:00"):
            if e["kind"] in ("world_event", "speech", "knock", "observed", "enter", "leave", "reminder_due"):
                print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} vis={e.get('visible_to')} :: "
                      f"{json.dumps(pay(e), ensure_ascii=False)[:180]}")
    print("-- visible_to 长度>=5 的事件 --")
    for e in EV:
        v = e.get("visible_to") or []
        if len(v) >= 5:
            print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} n={len(v)} vis={v} :: {json.dumps(pay(e), ensure_ascii=False)[:120]}")

if "items" in WANT:
    show("H 采纳/重复: take 竞态 / give 一份二主 / extra 空回合")
    for e in EV:
        if e["kind"] in ("item_given", "item_taken", "item_trashed", "note_left"):
            print(f"{hhmm(e['time'])} {e['kind']} {e['actor']} {json.dumps(pay(e), ensure_ascii=False)[:180]}")
    for t in AT:
        for c in calls(t):
            if c.get("name") in ("take", "give", "place", "trash", "drop"):
                a = c.get("args") or {}
                print(f"{hhmm(t['perception']['time'])} {c.get('name')} {t['actor']} {json.dumps(a, ensure_ascii=False)[:120]} "
                      f"|err| {str(t.get('error'))[:160]}")

if "empty" in WANT:
    show("H2 extra 空回合 / no_request")
    empty = [t for t in AT if not calls(t)]
    print(f"zero-call turns {len(empty)}")
    for t in empty:
        print(f"{hhmm(t['perception']['time'])} {t.get('actor')} role={t.get('role')} result={t.get('result')} "
              f"inner={str(t.get('inner'))[:60]}")
    print(f"system empty_turn records {sum(1 for s in SYS if (s.get('request') or {}).get('kind')=='empty_turn')}")
    for s in SYS:
        r = s.get("request") or {}
        if r.get("kind") == "empty_turn":
            print(f"   {str(r.get('time'))[11:16]} {r.get('actor')} {json.dumps(s.get('result'), ensure_ascii=False)[:160]}")
    for e in EV:
        if e["kind"] == "observed":
            p = pay(e)
            if "no_request" in json.dumps(p) or "empty" in json.dumps(p):
                print(f"{hhmm(e['time'])} observed {e['actor']} {json.dumps(p, ensure_ascii=False)[:160]}")

if "reject" in WANT:
    show("J 拒绝分类")
    fam = collections.Counter()
    for t in AT:
        err = t.get("error")
        if not err:
            continue
        head = err.split("：")[0].split(":")[0].split("。")[0][:36]
        fam[head] += 1
    print(f"families {fam.most_common()}")
    for t in AT:
        if t.get("error"):
            print(f"{hhmm(t['perception']['time'])} {t['actor']} :: {str(t.get('error'))[:220]}")

if "loops" in WANT:
    show("I2 动作分布 / 重复")
    per = collections.defaultdict(collections.Counter)
    for t in AT:
        for c in calls(t):
            per[t["actor"]][c.get("name")] += 1
    for a, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"{a:6s} calls={sum(c.values()):4d} {dict(c)}")
    sp = [pay(e)["text"] for e in EV if e["kind"] == "speech"]
    print(f"speech {len(sp)} unique={len(set(sp))}")
    dup = [t for t, n in collections.Counter(sp).items() if n > 1]
    for d in dup[:15]:
        print("   repeat:", str(d)[:120], collections.Counter(sp)[d])

if "story" in WANT:
    show("I 故事时间线")
    for e in EV:
        p = pay(e)
        k = e["kind"]
        if k == "speech":
            print(f"{hhmm(e['time'])} {e['actor']}@{p.get('location') or ''}: {p.get('text')}")
        elif k in ("message_sent", "message_delivered"):
            print(f"{hhmm(e['time'])} [{k}] {e['actor']} -> {p.get('target')}: {p.get('text')}")
        elif k == "note_left":
            print(f"{hhmm(e['time'])} [note] {e['actor']} @{p.get('location')}: {str(p.get('text'))[:80]!r}")
        elif k == "world_event":
            print(f"{hhmm(e['time'])} [world] {p.get('event')}: {str(p.get('notice'))[:140]}")
        elif k in ("enter", "leave"):
            print(f"{hhmm(e['time'])} [{k}] {e['actor']} {p.get('location')} {('escorted_by='+str(p.get('escorted_by'))) if p.get('escorted_by') else ''}")
