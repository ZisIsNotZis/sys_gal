"""库：状态键的渲染。

每个状态键都必须在这里登记。登记为 `None` 表示它不产生可见文字：
它是物性，改变的是"能做什么"，不是"看见什么"。
"""

from __future__ import annotations

from typing import Any

from engine.render import register_state_renderer


def _register_all() -> None:
    register_state_renderer("inscription", lambda v: f"上面写着：{v}")
    register_state_renderer("closed", lambda v: "封着口" if v else "")
    register_state_renderer("door", lambda v: "门关着" if v == "closed" else "门开着")
    register_state_renderer("portable", None)
    register_state_renderer("presence", None)


_register_all()
