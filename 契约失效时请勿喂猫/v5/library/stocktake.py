"""盘点：一次可复算的读数。

给定一个容器，把它里面看得见的份数加起来；封着的数不到。份数只有一个来源，
就是实体的 `count` 状态；读数是它的一份清单，总数是清单的和。

读数只有这一条路径：`count` 动词与故事的结局摘要都从这里取数，别处不许再拼一遍
同样的加法，否则"数出来的数"会多出一个能与世界脱钩的出口。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from engine.core import World
from engine.resolve import hidden_by_container


@dataclass(frozen=True)
class Reading:
    """一份盘点读数：一行一样东西的名字与份数，总数是这份清单的和。"""

    rows: tuple[tuple[str, int], ...] = ()

    @property
    def total(self) -> int:
        return sum(n for _name, n in self.rows)


def stocktake(world: World, eid: str, *, include_sealed: bool = False,
              keep: Callable[[str], bool] | None = None) -> Reading:
    """把 `eid` 里的份数数成一份清单。

    默认只数看得见的：封着口的容器里的份数数不到。`include_sealed=True` 时数到底
    （用于"这些钱还在不在店里"这类按物理位置算的总数）。`keep` 按实体 id 筛选要计入
    的份数（例如只数现金），筛选不改变遍历与封口规则。
    """
    rows: list[tuple[str, int]] = []
    _collect(world, eid, include_sealed, keep, rows)
    return Reading(tuple(rows))


def _collect(world: World, eid: str, include_sealed: bool,
             keep: Callable[[str], bool] | None, rows: list[tuple[str, int]]) -> None:
    if "count" in world.state.get(eid, {}) and (keep is None or keep(eid)):
        rows.append((world.entities[eid].name, int(world.get(eid, "count"))))
    for child in world.children(eid):
        if not include_sealed and hidden_by_container(world, child):
            continue
        _collect(world, child, include_sealed, keep, rows)
