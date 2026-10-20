"""把一次运行写成可通读的轨迹。

轨迹只写角色实际感知到的东西（以及他做了什么），不写引擎真相。
"""

from __future__ import annotations

from typing import Any

from .scenario import Run, ending


VERBS = {"look": "看了看周围", "read": "读", "touch": "碰了碰", "take": "拿起",
         "place": "放下", "give": "交给", "open": "打开", "knock": "敲了敲",
         "move": "走向", "wait": "等着"}


def clock_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def transcript(run: Run) -> str:
    w = run.world
    names = {e: w.entities[e].name for e in w.entities}
    lines = [
        "# 《末班车》轨迹",
        "",
        f"- 路径：{run.variant}",
        f"- 事件数：{len(run.log)}，回合数：{len(run.receipts)}",
        "",
    ]
    for item in run.items:
        stamp = clock_label(item["at"])
        if item["kind"] == "world":
            if not item["perceived"]:
                lines.append(f"**{stamp}** · *（没有人感知到）*")
            else:
                who = "、".join(names.get(w, w) for w, _ in item["perceived"])
                lines.append(f"**{stamp}** · *{item['perceived'][0][1]}*（{who}感到）")
            lines.append("")
            continue
        actor = names.get(item["actor"], item["actor"])
        verb = VERBS.get(item["verb"], item["verb"])
        target = item["target"]
        if item.get("to"):
            target = f"{target} → {item['to']}"
        head = f"**{stamp}** {actor} {verb}"
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


def digest_row(run: Run) -> dict[str, Any]:
    return {
        "variant": run.variant,
        "events": len(run.log),
        "turns": len(run.receipts),
        "ending": ending(run),
        "world": run.world.digest(),
    }
