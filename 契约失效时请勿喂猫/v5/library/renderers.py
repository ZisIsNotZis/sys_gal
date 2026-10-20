"""库：状态键的渲染。

每个状态键都必须在这里登记。登记为 `None` 表示它不产生可见文字：
它是物性，改变的是"能做什么"，不是"看见什么"。
"""

from __future__ import annotations

from typing import Any

from engine.render import register_state_renderer


INK = {"ink": "钢笔", "graphite": "铅笔", "printed": "印刷"}


def _marks_glance(value) -> str:
    return "上面有字" if value else ""


def _marks_detail(value) -> str:
    if not value:
        return ""
    inks = [INK.get(m.get("ink", ""), m.get("ink", "")) for m in value]
    if set(inks) == {"印刷"}:
        return "印上去的"
    if len(value) == 1:
        return f"手写的，用的是{inks[0]}"
    return f"上面有 {len(value)} 笔字：" + "、".join(inks)


def _register_all() -> None:
    # 一眼看得见"有字"，凑近看得见"几笔、什么墨"，只有"读"才得到内容。
    register_state_renderer("marks", _marks_glance, _marks_detail)
    register_state_renderer("smudge", None, lambda v: "纸面上有擦过的痕迹" if v else "")
    register_state_renderer("imprint", None, lambda v: "背面有复写纸压出来的印子" if v else "")
    register_state_renderer("locked", lambda v: "锁着" if v else "")
    register_state_renderer("implement",
                            lambda v: "写墨水字的" if v == "ink" else "写铅笔字的")
    register_state_renderer("hand", None)        # 一个人的字形：看不见，只能被认得出来
    register_state_renderer("opens", None)       # 这把钥匙能开什么
    register_state_renderer("accepts", None)     # 这个面能接受什么手段
    register_state_renderer("copies", None)      # 复写纸
    register_state_renderer("erases", None)      # 橡皮
    register_state_renderer("closed", lambda v: "封着口" if v else "")
    register_state_renderer("door", lambda v: "门关着" if v == "closed" else "门开着")
    register_state_renderer("portable", None)
    register_state_renderer("silhouette", lambda v: "玻璃后面有个人影" if v else "")
    register_state_renderer("presence", None)


_register_all()
