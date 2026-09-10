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
_INNER = {"type": "string", "minLength": 1}
_NO_ARGS = {"type": "object", "required": ["inner"],
            "properties": {"inner": _INNER}, "additionalProperties": False}


def _schema(**properties: Any) -> dict[str, Any]:
    properties = {"inner": _INNER, **properties}
    return {"type": "object", "required": list(properties),
            "properties": properties, "additionalProperties": False}
_ONE_ITEM = {"type": "object", "required": ["inner", "item"],
             "properties": {"inner": _INNER, "item": _STR}, "additionalProperties": False}
_ONE_ITEM_CONTENT = {"type": "object", "required": ["inner", "item"],
                     "properties": {"inner": _INNER, "item": _STR},
                     "additionalProperties": False}
_ONE_TARGET = {"type": "object", "required": ["inner", "target"],
               "properties": {"inner": _INNER, "target": _STR}, "additionalProperties": False}


SCHEMAS: dict[str, dict[str, Any]] = {
    # Memory tools (V4-AGENT-INTERFACE §2): no world-time cost, but every
    # call carries a mandatory non-empty inner (this turn's 心声).
    "update_memory": {"type": "object", "required": ["inner", "rows"],
                      "properties": {"inner": _INNER,
                                     "rows": {"type": "array", "minItems": 1,
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
               "required": ["inner"],
               "properties": {"inner": _INNER,
                              "kinds": {"type": "array", "items": _STR},
                              "ids": {"type": "array", "items": _STR},
                              "closed": {"type": "boolean"},
                              "limit": {"type": "integer"}},
               "additionalProperties": False},
    "flashback": {"type": "object", "required": ["inner", "entity"],
                  "properties": {"inner": _INNER, "entity": _STR},
                  "additionalProperties": False},
    "wait": _schema(duration_seconds=_INT),
    # volume: whisper needs the co-located "to" list (kernel validates it).
    # Both volume and to are optional; only text is required.
    "speak": {"type": "object", "required": ["inner", "text"],
              "properties": {"inner": _INNER,
                             "text": {"type": "string", "minLength": 1},
                             "volume": {"type": "string", "enum": ["whisper", "normal"]},
                             "to": {"type": "array", "items": _STR}},
              "additionalProperties": False},
    "send_message": {"type": "object", "required": ["inner", "target", "text"],
                     "properties": {"inner": _INNER,
                                    "target": _STR,
                                    "text": {"type": "string", "minLength": 1}},
                     "additionalProperties": False},
    # V4-DESIGN §5.6: intent only - the walk time is the map's fact.
    "move": _schema(target=_STR),
    "open": _NO_ARGS,
    "close": _NO_ARGS,
    "ask_stranger": {"type": "object", "required": ["inner", "question"],
                     "properties": {"inner": _INNER,
                                    "question": {"type": "string", "minLength": 1}},
                     "additionalProperties": False},
    "take": _ONE_ITEM,
    "drop": _ONE_ITEM,
    "continue_action": _NO_ARGS,
    "abandon_action": _NO_ARGS,
    "knock": _ONE_TARGET,
    "give": _schema(target=_STR, item=_STR),
    "read": _ONE_ITEM_CONTENT,
    "copy": _ONE_ITEM_CONTENT,
    "annotate": {"type": "object", "required": ["inner", "item", "text"],
                 "properties": {"inner": _INNER, "item": _STR,
                                "text": {"type": "string", "minLength": 1}},
                 "additionalProperties": False},
    "compare": _schema(first=_STR, second=_STR),
    "system_query": _schema(question=_STR),
}

# 每个工具的中文一句话说明（docs §2）。注意：每个调用的 arguments 都必须带
# 非空 inner——这一动作当下的心声（感受、意图、为什么）；缺 inner 或空 inner
# 的调用不会被执行。
_TOOL_DESCRIPTIONS: dict[str, str] = {
    "update_memory":
        "把事实或要紧的事写进你的私人记事本（引擎保管，只有你能看）。"
        "【何时用】每获得值得记住的新信息就写：谁说了什么、你发现了什么、承诺或期限。"
        "【何时不写】世界会自动重现的事（你亲眼看到的事不用抄）；一时的感受写进 inner。"
        "rows=[{fields,id?,op,desc?}]：fields 是保留名 person:/location:/item:/todo:true/"
        "reminder:\"M/D(周X) HH:MM\" 或自由标签，id 可省略（fields 唯一匹配时自动定位）；"
        "op：open 新建（必须带 desc）/edit 改 desc/close 翻篇。部分成功，失败逐行报错",
    "recall":
        "立刻翻看记事本：匹配的行逐字回进这个调用的 tool 结果（closed 行需 closed=true）。"
        "平时不必用——到期的事会自动回到你眼前",
    "flashback":
        "手动闪回：重显某地点/物品/人物相关的、你亲历过的历史。想不起某段经历的具体细节时用",
    "wait": "唯一的时间流逝工具；时长向上取整到 tick 倍数；等待期间事件照常投递。想干等或边等边想时用",
    "speak": "当面说话；volume=normal 全地点听得见，whisper 仅 to 指定的在场者听得见文本。"
             "在场无他人时为自言自语。说话花一分钟",
    "send_message": "发消息（电话），异步，1 tick 后送达；收信人必须是熟人或在场的对象",
    "move": "走向 target；时长由引擎按路线图计算，不用填。离开时在场者会看见你离开",
    "read": "读一份在手边的内容型物品；正文和已有批注只在 tool 结果里给你自己看。他人只看见你在读",
    "copy": "复印一份内容型物品（需要复印材料）：原件留手，副本可交人或另存",
    "annotate": "在内容型物品上写批注——后续任何读它的人都会看见你的批注",
    "compare": "比对两份都在手边的物品内容是否一致；判定只在 tool 结果里给你自己看",
    "take": "拿起一件在这里的物品",
    "drop": "放下你拿着的一件物品",
    "give": "把一件物品递给在场的某人",
    "knock": "敲一个关闭地点的门，探里面有没有人",
    "open": "打开当前地点（需该地点可控）",
    "close": "关闭当前地点（需该地点可控）",
    "ask_stranger": "搭话在场的匿名路人；question 填你想问的话。本地点配置了路人才可用",
    "continue_action": "无损继续被打断的动作（被打断的回合必须先选这个或 abandon）",
    "abandon_action": "放弃被打断的动作（作废；被打断的回合必须先选这个或 continue）",
    "system_query": "问「台账」（本世界的一册客观记录，案件默认已接下）一件其事实表内的客观问题；受查询次数限制，判定只进 tool 结果",
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


def _describe(error: Any, schema: Any, args: Mapping[str, Any]) -> str:
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
