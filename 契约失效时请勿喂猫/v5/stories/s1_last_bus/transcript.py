"""把一次运行写成可通读的轨迹。

轨迹只写角色实际感知到的东西（以及他做了什么），不写引擎真相。
"""

from __future__ import annotations

from typing import Any

from engine.surface import render_block

from .scenario import Run, ending


DECIDERS = {"world": "世界", "script": "脚本", "agent": "角色"}

VERBS = {"examine": "细看", "read": "读", "touch": "碰了碰", "take": "拿起",
         "place": "放下", "give": "交给", "open": "打开", "knock": "敲了敲",
         "move": "走向", "wait": "等着"}


def clock_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def transcript(run: Run) -> str:
    w = run.world
    names = {e: w.entities[e].name for e in w.entities}
    turns = [i for i in run.items if i["kind"] == "turn"]
    by_who = {key: sum(1 for i in turns if i["decided_by"] == key) for key in DECIDERS}
    n_world = sum(1 for i in run.items if i["kind"] == "world")
    lines = [
        "# 《末班车》轨迹",
        "",
        f"- 路径：{run.variant}",
        f"- 事件数：{len(run.log)}，动作数：{len(turns)}",
        "",
        "> **标记**：`[世界]` 排程与制度产生的；`[脚本]` 由剧本指定的动作；"
        "`[角色]` 由模型自己决定的动作。",
        f"> **这里**：{by_who['script']} 个动作为 `[脚本]`，"
        f"{by_who['agent']} 个为 `[角色]`，另有 {n_world} 个 `[世界]` 事件。"
        "脚本动作不代表角色的意愿，只证明这件事物理上做得到。",
        "",
    ]
    for item in run.items:
        stamp = clock_label(item["at"])
        if item["kind"] == "world":
            if not item["perceived"]:
                lines.append(f"`[世界]` **{stamp}** · *（没有人感知到）*")
            else:
                who = "、".join(names.get(w, w) for w, _ in item["perceived"])
                lines.append(f"`[世界]` **{stamp}** · *{item['perceived'][0][1]}*（{who}感到）")
            lines.append("")
            continue
        actor = names.get(item["actor"], item["actor"])
        verb = VERBS.get(item["verb"], item["verb"])
        target = item["target"]
        if item.get("to"):
            target = f"{target} → {item['to']}"
        head = f"`[{DECIDERS[item['decided_by']]}]` **{stamp}** {actor} {verb}"
        if target:
            head += f" {target}"
        if not item["ok"]:
            lines.append(f"{head} —— 没成：{item['reason']}")
            for hint in item["hints"]:
                lines.append(f"  - {hint}")
            lines.append("")
            continue
        lines.append(head)
        for text in item["texts"]:
            lines.append(f"> {text}")
        if item["note"]:
            lines.append(f"（{item['note']}）")
        lines.append("")
    end = ending(run)
    lines += ["## 结局", ""]
    def show(value):
        return "是" if value is True else "否" if value is False else value

    lines += [f"- {k}：{show(v)}" for k, v in end.items() if k != "结局"]
    lines += ["", f"{end['结局']}。", ""]
    return "\n".join(lines)


def context_view(run: Run) -> str:
    """审计视图：每一回合，这个角色当时拿到的全部上下文。"""
    w = run.world
    lines = ["# 《末班车》上下文审计", "",
             "每个动作前，这个角色实际拿到的全部上下文。",
             "M1 的演员是脚本，不读这些上下文（`decided_by: script`）；这一份的作用是"
             "回答「他当时知道什么」，以及 M3 换成模型后把同一份块直接喂进去。", ""]
    for item in run.items:
        if item["kind"] != "turn":
            continue
        stamp = clock_label(item["at"])
        actor = w.entities[item["actor"]].name
        mark = DECIDERS[item["decided_by"]]
        lines += [f"## `[{mark}]` {stamp} {actor}：{VERBS.get(item['verb'], item['verb'])} {item.get('target','')}", ""]
        if item["decided_by"] == "script":
            lines += [f"这一步由脚本指定（第 {item['step']} 步），不是他读了上文之后的决定。", ""]
        lines += ["```", render_block(item["context"]), "```", ""]
        if item["ok"]:
            for text in item["texts"]:
                lines.append(f"- 结果：{text}")
        else:
            lines.append(f"- 没成：{item['reason']}")
        lines.append("")
    return "\n".join(lines)


def digest_row(run: Run) -> dict[str, Any]:
    turns = [i for i in run.items if i["kind"] == "turn"]
    decided = "、".join(f"{DECIDERS[k]} {sum(1 for i in turns if i['decided_by'] == k)}"
                        for k in DECIDERS if any(i["decided_by"] == k for i in turns))
    return {
        "decided": decided,
        "variant": run.variant,
        "events": len(run.log),
        "turns": len(run.receipts),
        "ending": ending(run),
        "world": run.world.digest(),
    }
