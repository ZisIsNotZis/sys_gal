"""Formal JSON Schema validation for the executable action protocol.

This is the single source of truth for each action kind's argument shape.
Shape/type errors — signature drift such as ``read`` submitted with ``item``
instead of ``document`` — are caught here and reported by deriving the message
from the schema, instead of hand-written per-action strings. Semantic checks
(availability, routes, co-location, world state) still live in the kernel.

The rejections deliberately name the expected key and the key actually
provided, so an agent that guesses an argument name can self-correct.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from jsonschema import Draft202012Validator

_STR = {"type": "string"}
_INT = {"type": "integer"}
_NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}
_ONE_ITEM = {"type": "object", "required": ["item"],
             "properties": {"item": _STR}, "additionalProperties": False}
_ONE_DOC = {"type": "object", "required": ["document"],
            "properties": {"document": _STR}, "additionalProperties": False}
_ONE_TARGET = {"type": "object", "required": ["target"],
               "properties": {"target": _STR}, "additionalProperties": False}


def _schema(**properties: Any) -> dict[str, Any]:
    return {"type": "object", "required": list(properties),
            "properties": properties, "additionalProperties": False}


SCHEMAS: dict[str, dict[str, Any]] = {
    "wait": _schema(duration_seconds=_INT),
    "sleep": _schema(duration_seconds=_INT),
    # volume: whisper needs the co-located "to" list (kernel validates it).
    # Both volume and to are optional; only text is required.
    "speak": {"type": "object", "required": ["text"],
              "properties": {"text": {"type": "string", "minLength": 1},
                             "volume": {"type": "string", "enum": ["whisper", "normal"]},
                             "to": {"type": "array", "items": _STR}},
              "additionalProperties": False},
    "send_message": {"type": "object", "required": ["target", "text"],
                     "properties": {"target": _STR,
                                    "text": {"type": "string", "minLength": 1}},
                     "additionalProperties": False},
    # V4-DESIGN §5.6: intent only - the walk time is the map's fact.
    "move": _schema(target=_STR),
    "open": _NO_ARGS,
    "close": _NO_ARGS,
    "ask_stranger": {"type": "object", "required": ["question"],
                     "properties": {"question": {"type": "string", "minLength": 1}},
                     "additionalProperties": False},
    "take": _ONE_ITEM,
    "drop": _ONE_ITEM,
    "inspect": _ONE_ITEM,
    "search": _NO_ARGS,
    "observe": _NO_ARGS,
    "continue_action": _NO_ARGS,
    "abandon_action": _NO_ARGS,
    "interact": _schema(target=_STR, verb=_STR, parameters={"type": "object"}),
    "knock": _ONE_TARGET,
    "give": _schema(target=_STR, item=_STR),
    "read": _ONE_DOC,
    "copy": _ONE_DOC,
    "label": {"type": "object", "required": ["document", "label"],
              "properties": {"document": _STR,
                             "label": {"type": "string", "minLength": 1}},
              "additionalProperties": False},
    "annotate": {"type": "object", "required": ["document", "text"],
                 "properties": {"document": _STR,
                                "text": {"type": "string", "minLength": 1}},
                 "additionalProperties": False},
    "compare": _schema(first=_STR, second=_STR),
}

_VALIDATORS: dict[str, Draft202012Validator] = {
    kind: Draft202012Validator(schema) for kind, schema in SCHEMAS.items()}


def _property_name(error: Any) -> str:
    path = list(error.path)
    return str(path[0]) if path else ""


def _describe(error: Any, schema: Mapping[str, Any], args: Mapping[str, Any]) -> str:
    expected = sorted(schema.get("properties", {}))
    validator = error.validator
    if validator == "required":
        name = error.message.split("'")[1] if "'" in error.message else "?"
        return f"needs the '{name}' argument"
    if validator == "additionalProperties":
        unexpected = sorted(set(args) - set(schema.get("properties", {})))
        rendered = ", ".join(repr(key) for key in unexpected) or "?"
        if expected:
            return (f"got an unexpected argument {rendered}; "
                    f"expected one of: {', '.join(expected)}")
        return f"got an unexpected argument {rendered}; this action takes no arguments"
    if validator == "type":
        wanted = error.validator_value
        prop = _property_name(error)
        return f"expects '{prop}' to be {wanted}"
    if validator == "enum":
        prop = _property_name(error)
        return f"expects '{prop}' to be one of: {', '.join(map(str, error.validator_value))}"
    if validator == "minLength":
        return f"expects '{_property_name(error)}' to be non-empty"
    return error.message


def validate_action_args(kind: str, args: Mapping[str, Any]) -> str | None:
    """Return a human, schema-derived reason if ``args`` violate the action shape."""
    validator = _VALIDATORS.get(kind)
    if validator is None:
        return None
    errors = list(validator.iter_errors(args))
    if not errors:
        return None
    problems: list[str] = []
    for error in errors:
        text = _describe(error, validator.schema, args)
        if text not in problems:
            problems.append(text)
    return f"{kind}: {'; '.join(problems)}. Your args were: {json.dumps(dict(args), ensure_ascii=False)}."
