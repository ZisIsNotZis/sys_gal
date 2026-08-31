"""Deterministic visual-novel projection of authoritative events."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping

_BREAKS = {"system", "ledger_case_accepted", "ledger_cost"}
_TITLES = {
    "setup": "The Ledger Opens", "choice": "A Choice With a Cost",
    "disclosure": "What Can Be Put in Writing", "deadline": "The Deadline Arrives",
    "resolution": "The Record Closes", "epilogue": "After the Record Closes",
    "conversation": "A Passing Moment", "investigation": "Three Versions of the Same Number",
    "interview": "The Interview That Refuses to Be a Date",
    "institutional": "The Person Who Asked for a Presentable Number",
    "memory": "The Blue Umbrella Is Not Evidence of Love",
    "review": "The Meeting Has Minutes", "preparation": "Everyone Is Busy at the Same Time",
    "fair": "The Fair Opens Under Conditional Approval", "ending": "Settlement Is Not Forgiveness",
    "relationship": "No Contract Attached",
}


def project_vn(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return renderable chapters/scenes without inventing narrative facts."""
    ordered = [dict(e) for e in events]
    scenes: list[dict[str, Any]] = []
    current = None
    previous = None
    for event in ordered:
        now = datetime.fromisoformat(str(event["time"]))
        phase = _phase(event)
        if current is None or _breaks(current, event, previous, now):
            current = _scene(len(scenes) + 1, event, phase)
            scenes.append(current)
        record = _record(event)
        if record:
            current["records"].append(record)
            current["event_ids"].append(event["id"])
            current["end"] = event["time"]
        previous = now
    scenes = [s for s in scenes if s["records"]]
    for scene in scenes:
        scene["event_ids"] = list(dict.fromkeys(scene["event_ids"]))
        scene["record_count"] = len(scene["records"])
        scene["has_choice"] = any(r["type"] == "choice" for r in scene["records"])
    chapters = _chapters(scenes)
    records = [r for s in scenes for r in s["records"]]
    epilogue = _epilogue(ordered)
    if epilogue:
        epilogue_scene = _epilogue_scene(len(scenes) + 1, epilogue)
        epilogue_scene["chapter"] = chapters[-1]["id"]
        scenes.append(epilogue_scene)
        chapters[-1]["scene_ids"].append(epilogue_scene["id"])
        chapters[-1]["end"] = epilogue["time"]
    return {
        "format": "vn-projection-v2", "chapters": chapters, "scenes": scenes,
        "terminal_epilogue": epilogue,
        "dialogue_count": sum(r["type"] == "dialogue" for r in records),
        "choice_count": sum(r["type"] == "choice" for r in records),
        "state_change_count": sum(r["type"] == "state_change" for r in records),
    }


def _scene(number, event, phase):
    location = (event.get("payload") or {}).get("location")
    return {"id": f"scene-{number:03d}", "chapter": None, "phase": phase,
            "title": _TITLES.get(phase, _TITLES["conversation"]), "start": event["time"],
            "end": event["time"], "location": location,
            "background": None if location is None else f"background:{location}",
            "event_ids": [], "records": []}


def _breaks(current, event, previous, now):
    phase = _phase(event)
    arc_phases = {"setup", "choice", "deadline", "resolution", "investigation", "interview", "disclosure", "institutional", "memory", "review", "preparation", "fair", "ending", "relationship"}
    return (bool(current["records"]) and event.get("kind") in _BREAKS) or (bool(current["records"]) and phase in arc_phases and current["phase"] != phase) or (previous is not None and now - previous > timedelta(minutes=30))


def _phase(event):
    kind, payload = event.get("kind"), dict(event.get("payload") or {})
    if kind == "world_event" and payload.get("event") == "luo_reminder": return "deadline"
    if kind == "story_terminal": return "epilogue"
    if kind == "story_beat": return payload.get("phase", "conversation")
    if kind == "system" and payload.get("status") == "settled": return "resolution"
    if kind == "story_terminal": return "epilogue"
    if kind == "system" and payload.get("case") == "three-way-ambiguity": return "setup" if payload.get("status") is None else "choice"
    if kind in {"ledger_case_accepted", "ledger_cost"}: return "choice"
    if kind == "update_relationship": return "relationship"
    if kind in {"speech", "message_delivered", "update_belief"}: return "disclosure"
    return "conversation"


def _base(event):
    return {"event_id": event["id"], "source_event_id": event["id"], "time": event["time"]}


def _record(event):
    kind, payload = event.get("kind"), dict(event.get("payload") or {})
    base = _base(event)
    if kind == "speech": return {**base, "type": "dialogue", "speaker": event.get("actor"), "text": payload["text"], "audience": list(event.get("visible_to") or []), "source": "speech"}
    if kind == "message_delivered": return {**base, "type": "dialogue", "speaker": event.get("actor"), "recipient": payload["target"], "text": payload["text"], "audience": list(event.get("visible_to") or []), "source": "message"}
    if kind == "ledger_case_accepted": return {**base, "type": "choice", "actor": event.get("actor"), "choice": payload["choice"], "options": list(payload["options"]), "case": payload.get("case"), "voluntary": True}
    if kind == "ledger_cost": return {**base, "type": "consequence", "actor": event.get("actor"), "text": payload["cost"]}
    if kind in {"update_belief", "update_relationship"}: return {**base, "type": "state_change", "actor": event.get("actor"), "payload": payload, "source": kind, "evidence_event_id": payload.get("evidence_event_id")}
    if kind == "world_event" and payload.get("event") == "luo_reminder": return {**base, "type": "system", "status": "deadline", "target": payload.get("target"), "text": payload.get("text")}
    if kind == "story_beat": return {**base, "type": "scene_beat", "phase": payload.get("phase"), "event": payload.get("event"), "text": payload.get("text")}
    if kind == "story_terminal": return {**base, "type": "terminal", "phase": payload.get("phase"), "event": payload.get("event") or ("story_end" if payload.get("resolved_actors") else None), "reason": payload.get("terminal_reason"), "resolutions": dict(payload.get("resolutions") or payload.get("resolved_actors") or {})}
    # The kernel emits one authoritative terminal event after applying the beat.
    if kind == "system" and payload.get("case") == "three-way-ambiguity" and payload.get("status") is None: return {**base, "type": "system", "status": "setup", "case": payload["case"], "terms": list(payload.get("terms", [])), "deadline": payload.get("acceptance_deadline")}
    if kind == "system" and payload.get("status") in {"accepted", "settled"}: return {**base, "type": "system", "status": payload["status"], "text": payload.get("reward") or payload.get("cost") or payload.get("case")}
    return None


def _chapters(scenes):
    chapters = []
    for scene in scenes:
        if not chapters or scene["phase"] in {"setup", "investigation", "interview", "institutional", "memory", "review", "preparation", "fair", "ending", "resolution"}:
            chapters.append({"id": f"chapter-{len(chapters)+1:02d}", "title": _TITLES.get(scene["phase"], "The Record Moves"), "scene_ids": [], "start": scene["start"], "end": scene["end"]})
        chapter = chapters[-1]; chapter["scene_ids"].append(scene["id"]); chapter["end"] = scene["end"]; scene["chapter"] = chapter["id"]
    return chapters


def _epilogue(events):
    for event in reversed(events):
        payload = dict(event.get("payload") or {})
        if event.get("kind") == "story_terminal":
            return {"type": "epilogue", "event_id": event["id"], "source_event_id": event["id"], "time": event["time"], "status": "terminal", "event": payload.get("event"), "reason": payload.get("terminal_reason"), "resolutions": dict(payload.get("resolutions") or payload.get("resolved_actors") or {})}
    # Compatibility for short unit fixtures that have settlement but no full
    # story terminal. A real run must provide story_terminal.
    for event in reversed(list(events)):
        payload = dict(event.get("payload") or {})
        if event.get("kind") == "system" and payload.get("status") == "settled":
            return {"type": "epilogue", "event_id": event["id"], "source_event_id": event["id"], "time": event["time"], "status": "settled", "case": payload.get("case"), "reward": payload.get("reward")}
    return None


def _epilogue_scene(number, record):
    scene = {"id": f"scene-{number:03d}", "chapter": None, "phase": "epilogue", "title": _TITLES["epilogue"], "start": record["time"], "end": record["time"], "location": None, "background": None, "event_ids": [record["event_id"]], "records": [record]}
    scene["record_count"] = 1; scene["has_choice"] = False; scene["chapter"] = "chapter-02"
    return scene
