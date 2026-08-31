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
    # Private notes are advisory and are validated atomically by Runner. Keep
    # the physical intention parseable so a bad note cannot discard a valid
    # action; Runner records and rejects only the note.
    updates = value["updates"] if "updates" in value else {}
    kind = value.get("kind")
    args = value.get("args", {})
    # Accept the documented v3 wire shape only.  Legacy action/target output
    # must fail visibly and be retried; silently translating it hides prompt
    # or provider drift and can turn an actor's intent into a different act.
    if not isinstance(kind, str) or not kind.strip() or not isinstance(args, dict):
        raise ValueError("intention needs a string kind and object args")
    return Intention(actor, kind.strip(), args, world_version), updates


def parse_intention(actor: str, raw: str | dict[str, Any], world_version: int) -> Intention | None:
    """Parse only a typed concrete action; never infer a vague action.

    The engine remains the authority: this function only turns model output
    into the same request object used by deterministic agents.
    """
    return parse_decision(actor, raw, world_version)[0]
