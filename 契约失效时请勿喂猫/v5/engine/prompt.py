"""智能体接口：系统提示与工具表。

两样东西都**从库和种子生成**，不许每支故事手写一份：
- 系统提示 = 种子里那句第一人称身份 + 这个世界的常识（只知道自己感知到的）+ 行动方式；
- 工具表 = 库里的动词与它们的参数，一个字也不多。
"""

from __future__ import annotations

from typing import Any

from .core import World
from .rules import REGISTRY
from .surface import block, render_block


def _describe_args(verb: str) -> list[tuple[str, str, bool]]:
    """实体参数 + 额外参数，同名以额外参数为准（它可以声明为可选）。"""
    rule = REGISTRY[verb]
    merged: dict[str, tuple[str, bool]] = {
        name: ("要指称的东西：用你此刻看见或知道的名字", True)
        for name in rule.entity_args
    }
    for name, desc, required in rule.params:
        merged[name] = (desc, required)
    return [(name, desc, required) for name, (desc, required) in merged.items()]


def tool_specs() -> list[dict[str, Any]]:
    """OpenAI function-calling 形状的工具表，全部来自库里登记的动词。"""
    tools: list[dict[str, Any]] = []
    for verb in sorted(REGISTRY):
        rule = REGISTRY[verb]
        props: dict[str, Any] = {}
        required: list[str] = []
        for name, desc, is_required in _describe_args(verb):
            props[name] = {"type": "string", "description": desc}
            if is_required:
                required.append(name)
        tools.append({
            "type": "function",
            "function": {
                "name": verb,
                "description": rule.doc or verb,
                "parameters": {"type": "object", "properties": props, "required": required},
            },
        })
    return tools


def system_prompt(world: World, actor: str) -> str:
    ent = world.entities[actor]
    here = world.place_of(actor)
    place = world.entities[here].name if here else "某处"
    verbs = "、".join(f"{REGISTRY[v].label or v}（{v}）" for v in sorted(REGISTRY))
    return (
        f"{ent.identity or ent.prose}\n\n"
        f"你现在在{place}。你只知道你看见过、听见过、或者本来就相信的事："
        "纸上的字要读才知道写了什么，别人的东西要拿才知道是什么，"
        "不知道的就是不知道，世界不会替你补。\n\n"
        f"你能做的事只有这些：{verbs}。每次都用一个工具调用，一次一件。"
        "被拒绝时会告诉你为什么、眼前还有什么可用，你可以换个做法。"
        "不要叙述，不要替别人说话，不要长篇写心里的想法。\n\n"
        "工具参数里的名字必须是你能看见或知道的东西（比如「桌上那张纸」）。"
    )


def turn_message(world: World, actor: str, n_recent: int = 6) -> str:
    return render_block(block(world, actor, n_recent))
