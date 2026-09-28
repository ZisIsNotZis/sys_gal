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


def _schema(**properties: Any) -> dict[str, Any]:
    return {"type": "object", "required": list(properties),
            "properties": properties, "additionalProperties": False}
_ONE_ITEM = {"type": "object", "required": ["item"],
             "properties": {"item": _STR}, "additionalProperties": False}
_ONE_ITEM_CONTENT = {"type": "object", "required": ["item"],
                     "properties": {"item": _STR},
                     "additionalProperties": False}
_ONE_TARGET = {"type": "object", "required": ["target"],
               "properties": {"target": _STR}, "additionalProperties": False}


SCHEMAS: dict[str, dict[str, Any]] = {
    # Memory tools (V4-AGENT-INTERFACE §2): no world-time cost. A row is its
    # key set; the keys are both its handle and its mention needles.
    "update_memory": {"type": "object", "required": ["rows"],
                      "properties": {"rows": {"type": "array", "minItems": 1,
                                              "items": {"type": "object",
                                                        "required": ["keys", "op"],
                                                        "properties": {"keys": {"type": "array",
                                                                                  "minItems": 1,
                                                                                  "items": _STR},
                                                                       "op": {"type": "string",
                                                                              "enum": ["open", "edit", "close"]},
                                                                       "desc": _STR},
                                                        "additionalProperties": False}}},
                      "additionalProperties": False},
    "recall": {"type": "object", "required": ["keys"],
               "properties": {"keys": {"type": "array", "minItems": 1, "items": _STR},
                              "closed": {"type": "boolean"},
                              "limit": {"type": "integer"}},
               "additionalProperties": False},
    "flashback": {"type": "object", "required": ["entity"],
                  "properties": {"entity": _STR},
                  "additionalProperties": False},
    "wait": _schema(duration_seconds=_INT),
    # volume: whisper needs the co-located "to" list (kernel validates it).
    # Both volume and to are optional; only text is required.
    "speak": {"type": "object", "required": ["text", "volume", "to"],
              "properties": {"text": {"type": "string", "minLength": 1},
                             "volume": {"type": "string", "enum": ["whisper", "normal"]},
                             "to": {"type": "array", "minItems": 1, "items": _STR},
                             "wait_response": {"type": "boolean"}},
              "additionalProperties": False},
    "text": {"type": "object", "required": ["target", "text"],
             "properties": {"target": _STR,
                            "text": {"type": "string", "minLength": 1},
                            "wait_response": {"type": "boolean"}},
             "additionalProperties": False},
    # V4-DESIGN §5.6: intent only - the walk time is the map's fact.
    "move": _schema(target=_STR),
    "take": _ONE_ITEM,
    "place": _ONE_ITEM,
    "continue_action": _NO_ARGS,
    "abandon_action": _NO_ARGS,
    "knock": _ONE_TARGET,
    "give": _schema(target=_STR, item=_STR),
    "read": _ONE_ITEM_CONTENT,
    "leave_note": _schema(text={"type": "string", "minLength": 1}),
    "trash": _ONE_ITEM,
}

# 每个工具的中文一句话说明（docs §2）。注意：每个调用的 arguments 都必须带
# 非空 inner——这一动作当下的心声（感受、意图、为什么）；缺 inner 或空 inner
# 的调用不会被执行。
_TOOL_DESCRIPTIONS: dict[str, str] = {
    "update_memory":
        "把事实或要紧的事写进你的私人记事本（引擎保管，只有你能看）。"
        "【何时用】每获得值得记住的新信息就写：谁说了什么、你发现了什么、承诺或期限。"
        "【何时不写】世界会自动重现的事（你亲眼看到的事不用抄）。"
        "rows=[{keys,op,desc?}]：keys 是这行的关键词表（一个或多个，每个 ≥2 字），既是它的定位符也是它的唤起词"
        "——以后任何消息里出现其中一个词，这行就会回到你眼前。keys 直接写人名/物名/事名本身"
        "（如 \"2013年台风台账\"），**不要带 item:/person: 之类前缀**。"
        "特殊 key：!always = 不论提没提到都定期提醒你（要紧的事、欠着的承诺）；"
        "!at=M/D(周X) HH:MM = 到点提醒（会打断你手上的事）。"
        "op：open 新建（必须带 desc）/edit 只改 desc/close 翻篇。**keys 不可改**——要改 key 就 close 旧的、open 新的。"
        "定位顺序：整个 key 集先精确匹配，再唯一子集模糊匹配（你的 keys 是某行 keys 的子集也算命中）；"
        "都没有则报错并列出最接近的现有键。唤起匹配是双向子串（「2013年台风」命中「2013年台风夜」）。"
        "部分成功，失败逐行报错",
    "recall":
        "立刻翻看记事本：keys=[关键词]（必填），任何一行只要含其中一个关键词就逐字回进这个调用的 tool 结果"
        "（closed 行需 closed=true）。也可以用 !always 列出所有要紧的常提行。"
        "平时不必用——被提到的行会自动回到你眼前",
    "flashback":
        "手动闪回：关于某个地点/物品/人物/事件，把你知道的和亲历过的都翻出来——先是你自己记的事"
        "（前史、旧账、心结），再是这段日子里的经历。名字可用别名（如\"老街坊\"）。想不起某段往事时用",
    "wait": "唯一的时间流逝工具；时长向上取整到 tick 倍数；等待期间事件照常投递。想干等或边等边想时用",
    "speak": "对指定的人开口：to=在场的谁（可多个；也可以是 [\"陌生人\"] 向身边的路人搭话）。"
             "有什么话一次性说完——一个 speak 调用说完完整的话，不要一句一句地连发多个 speak。"

             "volume=normal 大家都听得见（to 记录话是对谁说的）；volume=whisper 仅 to 名单听得见。"
             "普通的全场发言不用工具——直接回复文字即可。"
             "话说出口需要 1 分钟；对方听到并回应最快也要再过 1 分钟。默认 wait_response=true："
             "说完你会自动原地等回应（最多约 2 分钟，有人回应会立刻叫醒你）；"
             "说完就走就 wait_response=false",
    "text": "发手机短信：target=收件人，无视距离，1 tick 后送达；正文只有收件人看得到。"
             "默认 wait_response=true：发出后自动原地等回应（约 2 分钟，对方回复会立刻叫醒你）——"
             "对方看到、想到、再回，最快也要两三分钟；发完就走用 wait_response=false",
    "move": "只用于地图中的大地点（世界消息 @地点、你知道的 location 行）：target=地点全名。"
            "不要用来靠近柜子、桌子、服务台、房间角落或物品——同一地点内无需 move，直接 read/take/knock/leave_note",
    "take": "拿起一件在这里的物品",
    "place": "把身上的一件物品放在当前地点——他人可见可拿；不是丢弃",
    "give": "把身上的一件物品递给在场的某人",
    "leave_note": "留一张字条在当前地点，写给后来者看。字条是房间的留言，不是物品：谁进入这里，"
                  "谁就立刻看到全文并阅后即焚（字条随即化去）；留字条时在场的其他人当场看到。"
                  "想留话就再 leave 一张新字条；递到手上用 give",
    "read": "读一份手边的内容型物品；正文和已有批注只在 tool 结果里给你自己看。他人只看见你在读",
    "knock": "敲一个关闭地点的门，探里面有没有人",
    "continue_action": "无损继续被打断的动作（被打断的回合必须先选这个或 abandon）",
    "abandon_action": "放弃被打断的动作（作废；被打断的回合必须先选这个或 continue）",
    "trash": "销毁一件自己身上或当前地点的物品（杂物），不可逆",
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
