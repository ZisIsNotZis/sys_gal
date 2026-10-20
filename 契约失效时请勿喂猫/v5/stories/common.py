"""故事共用的轨迹视图：一个故事视图，一个上下文审计视图。

两支故事（以及后面的）都从这里出，避免每支故事重写一遍排版。
"""

from __future__ import annotations

from typing import Any

from engine.surface import render_block

DECIDERS = {"world": "世界", "script": "脚本", "agent": "角色"}

VERBS = {"examine": "细看", "read": "读", "touch": "碰了碰", "take": "拿起",
         "place": "放下", "give": "交给", "open": "打开", "knock": "敲了敲",
         "move": "走向", "wait": "等着", "write": "写", "erase": "擦",
         "copy": "复写", "unlock": "开锁", "recognize": "认字", "speak": "说"}


def clock_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _turns(run: Any) -> list[dict[str, Any]]:
    return [i for i in run.items if i["kind"] == "turn"]


def transcript(run: Any, title: str) -> str:
    turns = _turns(run)
    by_who = {key: sum(1 for i in turns if i["decided_by"] == key) for key in DECIDERS}
    n_world = sum(1 for i in run.items if i["kind"] == "world")
    names = {e: run.world.entities[e].name for e in run.world.entities}
    lines = [
        f"# {title}",
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

    summary = run.summary
    lines += ["## 结局", ""]

    def show(value: Any) -> Any:
        return "是" if value is True else "否" if value is False else value

    lines += [f"- {k}：{show(v)}" for k, v in summary.items() if k != "结局"]
    lines += ["", f"{summary['结局']}。", ""]
    return "\n".join(lines)


def context_view(run: Any) -> str:
    lines = [f"# {run.title}上下文审计", "",
             "每个动作前，这个角色实际拿到的全部上下文。",
             "M1/M2 的演员是脚本，不读这些上下文（`decided_by: script`）；这一份的作用是"
             "回答「他当时知道什么」，以及 M3 换成模型后把同一份块直接喂进去。", ""]
    for item in _turns(run):
        stamp = clock_label(item["at"])
        actor = run.world.entities[item["actor"]].name
        mark = DECIDERS[item["decided_by"]]
        lines += [f"## `[{mark}]` {stamp} {actor}：{VERBS.get(item['verb'], item['verb'])} "
                  f"{item.get('target','')}", ""]
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


def digest_row(run: Any) -> dict[str, Any]:
    turns = _turns(run)
    decided = "、".join(f"{DECIDERS[k]} {sum(1 for i in turns if i['decided_by'] == k)}"
                        for k in DECIDERS if any(i["decided_by"] == k for i in turns))
    return {
        "decided": decided,
        "turns": len(turns),
        "events": len(run.log),
        "ending": run.summary,
        "world": run.world.digest(),
    }
