"""《夜市》的两个视图（排版在 stories/common.py）。"""

from __future__ import annotations

from stories import common
from stories.common import context_view, digest_row

from .scenario import Run

# `stories/common.py` 不归本包所有，它的排版用词表里还没有这个动词。
# 这里只补一个词，不动它已有的任何条目；见 M4 报告。
common.VERBS.setdefault("impound", "收")


def transcript(run: Run) -> str:
    return common.transcript(run, "《夜市》轨迹")


__all__ = ["context_view", "digest_row", "transcript"]
