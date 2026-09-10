"""Boundary between a model response and the neutral engine.

v4 wire shape (V4-DESIGN §2)::

    {"inner": "...", "type": "speak", "args": {...},
     "interrupt": ["gao-rui"], "uninterruptable": false}

``inner`` (心声) is the actor's private first-person monologue: parsed, carried
on the Intention, recorded in the trace as private, never shown to the world
or other actors. ``type`` is the canonical action key; ``kind`` is accepted as
the deterministic-agent spelling. Argument-name synonyms execute with
telemetry (permissive in the moment, loud in aggregate) so a frequently-hit
alias exposes a badly designed name instead of silently masking drift.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .kernel import Intention

# The model-facing wire protocol is the minimal envelope, matching the
# function-calling convention: ``inner`` first (think before acting), then
# ``name`` and ``arguments``. Action-specific switches such as
# ``interrupt``/``uninterruptable`` live inside ``arguments`` and are lifted
# into the Intention by the parser; legacy names stay as aliases with
# telemetry.
WIRE_KEYS = {"inner", "name", "arguments"}
IGNORED_KEYS = {"updates"}

# (action-kind, wrong-name) -> canonical argument name. A hit renames the
# argument, executes the action, and counts the hit for aggregate review.
ARG_ALIASES: dict[tuple[str, str], str] = {
    ("wait", "seconds"): "duration_seconds",
    ("read", "document"): "item",
    ("copy", "document"): "item",
    ("annotate", "document"): "item",
    ("annotate", "text_body"): "text",
    ("send_message", "to"): "target",
    ("give", "to"): "target",
    ("move", "seconds"): "duration_seconds",
    ("send_message", "content"): "text",
}

# Missing-argument defaults for chatter-grade actions. A woken NPC idling on a
# beat does not need to invent a duration; an approaching stranger may not
# have a formulated question. Injected with telemetry, never silently.
DEFAULT_ARGS: dict[tuple[str, str], Any] = {
    ("wait", "duration_seconds"): 300,
    ("sleep", "duration_seconds"): 300,
    ("ask_stranger", "question"): "",
}

# Legacy top-level key -> canonical wire key. Same policy: execute + count.
TOPLEVEL_ALIASES: dict[str, str] = {"action": "name", "type": "name", "kind": "name", "args": "arguments", "updates": "updates"}

# Optional external judge for text that defeats both the strict and tolerant
# parsers. Interface only in v4 slice: when set, it receives the raw text and
# must return a JSON string. Never required for well-formed output.
judge_fallback: Any = None

_ALIAS_HITS: Counter = Counter()


def alias_telemetry() -> dict[str, int]:
    """Cumulative alias-hit counts, keyed ``"kind:wrong->canonical"``."""
    return {f"{kind}:{wrong}->{canonical}": count
            for (kind, wrong, canonical), count in _ALIAS_HITS.items()}


def reset_alias_telemetry() -> None:
    _ALIAS_HITS.clear()


def _record_alias(kind: str, wrong: str, canonical: str) -> None:
    _ALIAS_HITS[(kind, wrong, canonical)] += 1


def _tolerant_loads(text: str) -> Any:
    """Parse near-JSON that strict json.loads rejects.

    Handles the common model slips: single-quoted strings, trailing commas,
    bare True/False/None, and full-width quotes/brackets. Structural errors
    still raise ValueError so the session retry path stays in charge.
    """
    cleaned = text.strip()
    for original, replacement in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"),
                                  ("（", "("), ("）", ")"), ("，", ","), ("：", ":")):
        cleaned = cleaned.replace(original, replacement)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    body = re.sub(r",\s*([}\]])", r"\1", cleaned)
    body = re.sub(r":\s*True\b", ": true", body)
    body = re.sub(r":\s*False\b", ": false", body)
    body = re.sub(r":\s*None\b", ": null", body)
    body = _single_quote_strings(body)
    return json.loads(body)


def _single_quote_strings(text: str) -> str:
    """Rewrite single-quoted JSON strings into double-quoted ones.

    Tracks which quote opened a string: inside a double-quoted string a
    single quote is content; inside a single-quoted string a double quote
    must be escaped.
    """
    out: list[str] = []
    in_string = False
    opener = ""
    index = 0
    while index < len(text):
        char = text[index]
        if not in_string:
            if char in {'"', "'"}:
                in_string = True
                opener = char
                out.append('"')
            else:
                out.append(char)
        elif char == "\\" and index + 1 < len(text):
            out.append(char + text[index + 1])
            index += 1
        elif char == opener:
            in_string = False
            out.append('"')
        elif char == '"' and opener == "'":
            out.append('\\"')
        else:
            out.append(char)
        index += 1
    return "".join(out)


def _strip_think_blocks(raw: str) -> str:
    """Qwen-family templates emit an empty <think> shell even when thinking is
    disabled; local llama-server output carries it verbatim. The shell is
    scaffolding, never content — strip it before parsing."""
    import re
    cleaned = re.sub(r"<think>\s*</think>", "", raw)
    cleaned = re.sub(r"^\s*<think>.*?</think>", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def load_model_json(raw: str | dict[str, Any] | None) -> Any:
    """Strict first, tolerant second, judge last; raise ValueError when dead."""
    if not isinstance(raw, str):
        return raw
    raw = _strip_think_blocks(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        return _tolerant_loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    if judge_fallback is not None:
        judged = judge_fallback(raw)
        if isinstance(judged, str):
            return json.loads(judged)
        return judged
    raise ValueError("output is not recognizable JSON")


def parse_decision(actor: str, raw: str | dict[str, Any] | None,
                   world_version: int) -> tuple[Intention | None, dict[str, Any]]:
    """Parse one action; private-state updates are no longer part of the
    protocol — ``updates`` is counted as telemetry and ignored (the actor's
    durable self lives in ``inner`` and the session transcript)."""
    value: Any = load_model_json(raw)
    if value is None:
        return None, {}
    if not isinstance(value, dict):
        raise ValueError("agent output must be a JSON object")
    renamed_top = {TOPLEVEL_ALIASES.get(key, key): item for key, item in value.items()}
    for original in value:
        if original in TOPLEVEL_ALIASES and original != TOPLEVEL_ALIASES[original]:
            _record_alias("*", original, str(TOPLEVEL_ALIASES[original]))
    for ignored in renamed_top.keys() & IGNORED_KEYS:
        _record_alias("*", ignored, "ignored")
        renamed_top.pop(ignored)
    unknown = set(renamed_top) - WIRE_KEYS
    if unknown:
        raise ValueError(
            "agent output has unexpected top-level keys: "
            f"{sorted(unknown)}; expected {sorted(WIRE_KEYS)}")
    kind = renamed_top.get("name")
    args = renamed_top.get("arguments", {})
    if not isinstance(kind, str) or not kind.strip() or not isinstance(args, dict):
        raise ValueError("intention needs a string name and object arguments")
    kind = kind.strip()
    renamed_args = {}
    for key, item in args.items():
        canonical = ARG_ALIASES.get((kind, key))
        if canonical is not None:
            _record_alias(kind, key, canonical)
            renamed_args[canonical] = item
        else:
            renamed_args[key] = item
    for (default_kind, default_key), default in DEFAULT_ARGS.items():
        if kind == default_kind and default_key not in renamed_args:
            _record_alias(kind, "<missing>", default_key)
            renamed_args[default_key] = default
    inner = renamed_top.get("inner")
    if inner is not None and not isinstance(inner, str):
        raise ValueError("inner must be a string (the actor's first-person inner monologue)")
    if inner:
        inner = _bound_inner(inner)
    # Action-specific switches live in arguments; the parser lifts them into
    # the Intention so schemas stay per-action minimal.
    interrupt = renamed_args.pop("interrupt", ())
    if interrupt in ("", None):
        interrupt = ()
    if (not isinstance(interrupt, (list, tuple))
            or not all(isinstance(x, str) for x in interrupt)):
        raise ValueError("interrupt must be a list of actor ids (in arguments)")
    uninterruptable = renamed_args.pop("uninterruptable", None)
    if uninterruptable is not None and not isinstance(uninterruptable, bool):
        raise ValueError("uninterruptable must be a boolean (in arguments)")
    intention = Intention(actor, kind, renamed_args, world_version,
                          inner=inner or None,
                          interrupt=tuple(interrupt),
                          uninterruptable=uninterruptable)
    return intention, {}


_INNER_LIMIT = 200
_INNER_MARKER = "……（心声过长，已截断）"


def _bound_inner(text: str) -> str:
    text = text.strip()
    if len(text) <= _INNER_LIMIT:
        return text
    return text[:_INNER_LIMIT - len(_INNER_MARKER)] + _INNER_MARKER


def parse_intention(actor: str, raw: str | dict[str, Any], world_version: int) -> Intention | None:
    """Parse only a typed concrete action; never infer a vague action."""
    return parse_decision(actor, raw, world_version)[0]
