"""Boundary between a model response and the neutral engine."""

from __future__ import annotations

import json
from typing import Any

from .kernel import Intention


def parse_decision(actor: str, raw: str | dict[str, Any] | None,
                   world_version: int) -> tuple[Intention | None, dict[str, Any]]:
    """Parse one action plus bounded private-state updates."""
    value: Any = json.loads(raw) if isinstance(raw, str) else raw
    if value is None:
        return None, {}
    if not isinstance(value, dict) or set(value) - {"kind", "args", "updates"}:
        raise ValueError("agent output must be an object with kind, args, and optional updates")
    updates = value.get("updates", {})
    if not isinstance(updates, dict) or set(updates) - {"beliefs", "memories", "interpretations", "private_notes"}:
        raise ValueError("updates contain an unsupported private-state field")
    for key in ("beliefs", "memories", "interpretations", "private_notes"):
        if key in updates and not isinstance(updates[key], (dict, list)):
            raise ValueError(f"updates.{key} must be an object or list")
    kind = value.get("kind")
    args = value.get("args", {})
    if not isinstance(kind, str) or not kind.strip() or not isinstance(args, dict):
        raise ValueError("intention needs a string kind and object args")
    return Intention(actor, kind.strip(), args, world_version), updates


def parse_intention(actor: str, raw: str | dict[str, Any], world_version: int) -> Intention | None:
    """Parse only a typed concrete action; never infer a vague action.

    The engine remains the authority: this function only turns model output
    into the same request object used by deterministic agents.
    """
    return parse_decision(actor, raw, world_version)[0]
