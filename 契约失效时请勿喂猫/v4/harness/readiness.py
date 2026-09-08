"""Small, provider-independent checks used before expensive experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .seed import load_story_pack
from .world_loader import load_world_pack
from .character_loader import load_story_characters
from .trace import verify_event_log


def validate_trace(path: str | Path, *, require_complete: bool = False,
                   require_sessions: bool = False) -> dict[str, Any]:
    """Validate a saved trace's structure and actor/session coverage."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "v3-trajectory-1":
        raise ValueError("unsupported trajectory format")
    world_events = data.get("world_events")
    if not isinstance(world_events, list):
        raise ValueError("trajectory has no world event list")
    verify_event_log(world_events)
    pack = load_story_pack()
    expected = {str(row["id"]) for row in pack.actors}
    observed = {str(turn["actor"]) for turn in data.get("agent_turns", [])}
    if observed != expected:
        raise ValueError(f"trajectory actor coverage mismatch: {expected - observed}")
    if require_complete and set(data.get("sessions", {})) != expected:
        raise ValueError("completed trajectory session coverage mismatch")
    if require_sessions and set(data.get("sessions", {})) != expected:
        raise ValueError("trajectory session coverage mismatch")
    if any(turn.get("result") in {"agent_error", "decision_timeout", "engine_error"}
           for turn in data.get("agent_turns", [])):
        raise ValueError("trajectory contains agent execution errors")
    outcome = data.get("outcome")
    if require_complete and (not outcome or outcome.get("reason") != "stop_at_reached"):
        raise ValueError("trajectory is not a completed run")
    return data


def validate_story_pack(root: str | Path | None = None) -> None:
    """Validate that manifest entities and the story Markdown catalogs agree.

    ``load_world_pack`` checks that every declared visible entity has a file.
    This readiness-level check adds the inverse constraint (no unmanifested
    catalog entries) and applies the same rule to character seeds.  The engine
    remains data-driven: categories and their manifest fields are declared in
    this small catalog contract, rather than being embedded in simulation code.
    """
    if root is None:
        pack = load_story_pack()
    else:
        pack = load_world_pack(root)
    seeds = load_story_characters(pack.root)
    expected = {
        "locations": {str(row["id"]) for row in pack.locations},
        "items": {str(row["id"]) for row in pack.items},
        "documents": {str(row["id"]) for row in pack.documents},
        "characters": {str(row["id"]) for row in pack.actors},
    }
    actual = {category: _markdown_ids(pack.root / category)
              for category in expected}
    for category in expected:
        missing = sorted(expected[category] - actual[category])
        orphan = sorted(actual[category] - expected[category])
        if missing or orphan:
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if orphan:
                details.append("orphan " + ", ".join(orphan))
            raise ValueError(f"{category} Markdown catalog mismatch: " + "; ".join(details))
    if set(seeds) != expected["characters"]:
        raise ValueError("story pack and character catalog disagree")


def _markdown_ids(directory: Path) -> set[str]:
    """Return catalog IDs, rejecting duplicate IDs differing only in case."""
    paths = sorted(path for path in directory.iterdir()
                   if path.is_file() and path.suffix.lower() == ".md") \
        if directory.is_dir() else []
    folded: dict[str, Path] = {}
    ids: set[str] = set()
    for path in paths:
        key = path.stem.casefold()
        if key in folded:
            raise ValueError(f"{directory.name} has duplicate Markdown id: "
                             f"{folded[key].name}, {path.name}")
        folded[key] = path
        ids.add(path.stem)
    return ids


def validate_complete_trace(path: str | Path) -> dict[str, Any]:
    """Strict gate for a candidate full run, including the seeded stop event."""
    data = validate_trace(path, require_complete=True, require_sessions=True)
    pack = load_story_pack()
    endpoint = str(pack.manifest["clock"]["stop"])
    if data["outcome"].get("time") != endpoint:
        raise ValueError("completed trace stopped at the wrong time")
    if not any(event.get("kind") == "world_event"
               and event.get("payload", {}).get("event") == "world_stops"
               for event in data["world_events"]):
        raise ValueError("completed trace lacks world_stops")
    return data
