"""《末班车》的两个视图：故事视图与上下文审计视图（排版在 stories/common.py）。"""

from __future__ import annotations

from stories.common import DECIDERS, VERBS, clock_label, context_view, digest_row
from stories.common import transcript as _transcript

from .scenario import Run


def transcript(run: Run) -> str:
    return _transcript(run, "《末班车》轨迹")


__all__ = ["DECIDERS", "VERBS", "clock_label", "context_view", "digest_row", "transcript"]
