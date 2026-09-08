"""Private character state; never attached to the objective World."""

from dataclasses import dataclass, field
import json
from typing import Any


def validate_private_updates(updates: Any) -> dict[str, Any]:
    """Validate and normalize advisory character notes atomically."""
    if not updates:
        return {}
    if not isinstance(updates, dict):
        raise ValueError("private-state updates must be an object")
    allowed = {"goals", "beliefs", "memories", "interpretations", "private_notes"}
    unknown = set(updates) - allowed
    if unknown:
        raise ValueError("updates contain an unsupported private-state field")
    normalized = dict(updates)
    if "goals" in updates:
        values = updates["goals"]
        if not isinstance(values, list) or not all(
                (isinstance(x, str) and x.strip())
                or (isinstance(x, dict) and isinstance(x.get("text"), str) and x["text"].strip())
                for x in values):
            raise ValueError("goals update must be a list of non-empty strings or text objects")
        normalized["goals"] = [x if isinstance(x, str) else x["text"] for x in values]
    if "beliefs" in updates:
        values = updates["beliefs"]
        if isinstance(values, dict):
            normalized["beliefs"] = dict(values)
        elif isinstance(values, list) and all(
                isinstance(x, dict) and isinstance(x.get("key"), str)
                and "value" in x for x in values):
            normalized["beliefs"] = {x["key"]: x["value"] for x in values}
        else:
            raise ValueError("beliefs update must be an object or key/value list")
    for key in ("memories", "interpretations"):
        if key in updates:
            values = updates[key]
            if not isinstance(values, list) or not all(
                    isinstance(x, dict) or (isinstance(x, str) and x.strip())
                    for x in values):
                raise ValueError(f"{key} update must be a list of objects or non-empty strings")
            normalized[key] = [dict(x) if isinstance(x, dict) else {"text": x}
                               for x in values]
    if "private_notes" in updates:
        values = updates["private_notes"]
        if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
            raise ValueError("private_notes update must be a list of strings")
        normalized["private_notes"] = list(values)
    return normalized

@dataclass
class PrivateState:
    actor_id: str
    goals: tuple[str, ...] = ()
    # Beliefs are character-owned propositions; their value may be a
    # confidence number or a short qualification. The kernel never interprets
    # either form.
    beliefs: dict[str, Any] = field(default_factory=dict)
    memories: list[dict[str, Any]] = field(default_factory=list)
    interpretations: list[dict[str, Any]] = field(default_factory=list)
    private_notes: list[str] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "goals": list(self.goals),
            "beliefs": dict(self.beliefs),
            "memories": [dict(x) if isinstance(x, dict) else {"text": str(x)}
                         for x in self.memories],
            "interpretations": [dict(x) if isinstance(x, dict) else {"text": str(x)}
                                 for x in self.interpretations],
            "private_notes": list(self.private_notes),
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "PrivateState":
        """Restore only this actor's private state from a session checkpoint."""
        return cls(actor_id=str(snapshot["actor_id"]),
                   goals=tuple(snapshot.get("goals", ())),
                   beliefs=dict(snapshot.get("beliefs", {})),
                   memories=[dict(x) for x in snapshot.get("memories", ())],
                   interpretations=[dict(x) for x in snapshot.get("interpretations", ())],
                   private_notes=list(snapshot.get("private_notes", ())))


def bounded_state_snapshot(state: "PrivateState", *, per_section: int = 20) -> str:
    """JSON snapshot for the live context echo: deduplicated and section-capped.

    Identical entries collapse; beyond ``per_section`` the oldest drop first.
    The lossless archive stays in the trace; this only bounds what the model
    re-reads every turn (V4-DESIGN §5.3).
    """
    snap = state.snapshot()

    def dedupe_list(values: list) -> list:
        seen: set[str] = set()
        out: list = []
        for value in values:
            text = value if isinstance(value, str) else str(value)
            if text in seen:
                continue
            seen.add(text)
            out.append(value)
        return out[-per_section:]

    snap["goals"] = dedupe_list(list(snap["goals"]))
    snap["memories"] = dedupe_list(snap["memories"])
    snap["interpretations"] = dedupe_list(snap["interpretations"])
    snap["private_notes"] = dedupe_list(snap["private_notes"])
    return json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
