"""Formal JSON Schema validation for the executable action protocol.

This is the single source of truth for each action kind's argument shape.
Shape/type errors — signature drift such as ``read`` submitted with ``item``
instead of ``document`` — are caught here and reported by deriving the message
from the schema, instead of hand-written per-action strings. Semantic checks
(availability, routes, co-location, world state) still live in the kernel.

The rejections deliberately name the expected key and the key actually
provided, so an agent that guesses an argument name can self-correct.

V4-AGENT-INTERFACE §2 is the design truth this file mirrors: ``sleep`` is
merged into ``wait`` and the memory tools (think / update_memory / recall /
flashback) are declared here and consumed by the engine, never by the world
kernel. ``TOOLS`` is the static full-declaration tool array (cache-safe:
never add or remove tools mid-run) sent with every provider call.
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
    # Memory tools (V4-AGENT-INTERFACE §2): no world-time cost, but every
    # turn still costs at least one tick — enforced by the engine, not here.
    "think": {"type": "object", "required": ["inner"],
              "properties": {"inner": {"type": "string", "minLength": 1}},
              "additionalProperties": False},
    "update_memory": {"type": "object", "required": ["rows"],
                      "properties": {"rows": {"type": "array", "minItems": 1,
                                              "items": {"type": "object",
                                                        "required": ["fields", "id", "op"],
                                                        "properties": {"fields": {"type": "object"},
                                                                       "id": _STR,
                                                                       "op": {"type": "string",
                                                                              "enum": ["open", "edit", "close"]},
                                                                       "desc": _STR},
                                                        "additionalProperties": False}}},
                      "additionalProperties": False},
    "recall": {"type": "object",
               "properties": {"kinds": {"type": "array", "items": _STR},
                              "ids": {"type": "array", "items": _STR},
                              "closed": {"type": "boolean"},
                              "limit": {"type": "integer"}},
               "additionalProperties": False},
    "flashback": {"type": "object", "required": ["entity"],
                  "properties": {"entity": _STR},
                  "additionalProperties": False},
    "wait": _schema(duration_seconds=_INT),
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
    "annotate": {"type": "object", "required": ["document", "text"],
                 "properties": {"document": _STR,
                                "text": {"type": "string", "minLength": 1}},
                 "additionalProperties": False},
    "compare": _schema(first=_STR, second=_STR),
}

# One-line Chinese descriptions, one per tool, from V4-AGENT-INTERFACE §2.
_TOOL_DESCRIPTIONS: dict[str, str] = {
    "think": "inner 心声；保留在会话历史中；无世界事件、无世界状态效果",
    "update_memory":
    "把事实或要紧的事写进你的私人记事本（引擎保管，只有你能看）：rows=[{fields,id,op,desc?}]。"
    + "fields 是保留名 person:/location:/item:/todo:true/reminder:\"M/D(周X) HH:MM\" 或自由标签；id 用英文短横线小写。"
    + "op：open 新建/重开、edit 改 desc、close 翻篇（recall 指名可找回）。只写事实和要紧的事——发生的事世界会自动重现，此刻的感受用 think；部分成功，失败逐行报错",
    "recall":
    "想立刻翻看记事本：下一轮 #knowledge 显式包含指定的类型/条目（closed 行需 closed=true）",
    "flashback":
    "手动闪回：重显某地点/物品/人物相关的、你亲历过的历史",
    "wait": "唯一的时间流逝工具；时长向上取整到 tick 倍数；等待期间事件照常投递",
    "speak": "当面说话；volume=normal 全地点听得见，whisper 仅 to 指定的在场者听得见文本",
    "send_message": "发消息（电话），异步，1 tick 后送达",
    "move": "走向 target；时长由引擎按路线图计算，不用填",
    "read": "读一份在手边的文档；内容只有你能看到",
    "copy": "复印一份文档（需要复印材料）",
    "annotate": "在文档上写批注，后续读者都能看见",
    "compare": "比对两份都在手边的文档内容是否一致",
    "take": "拿起一件在这里的物品",
    "drop": "放下你拿着的一件物品",
    "give": "把一件物品递给在场的某人",
    "inspect": "细看一件物品（这里有的或你拿着的）",
    "search": "搜一搜当前地点",
    "knock": "敲一个地点的门",
    "interact": "与一个邻近地点互动（verb + parameters）",
    "open": "打开当前地点（需可控）",
    "close": "关闭当前地点（需可控）",
    "observe": "主动重看：下一回合消息强制全量回放场景状态与描述",
    "ask_stranger": "搭话在场的匿名路人",
    "continue_action": "无损继续被打断的动作",
    "abandon_action": "放弃被打断的动作（作废）",
}

TOOLS: list[dict[str, Any]] = [
    {"type": "function",
     "function": {"name": kind, "description": _TOOL_DESCRIPTIONS[kind],
                  "parameters": SCHEMAS[kind]}}
    for kind in SCHEMAS
]

SPEAK_TOOLS: list[dict[str, Any]] = [tool for tool in TOOLS
                                     if tool["function"]["name"] == "speak"]

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
