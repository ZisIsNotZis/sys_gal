"""《借条》的两个视图（排版在 stories/common.py）。"""

from __future__ import annotations

from stories.common import context_view, digest_row
from stories.common import transcript as _transcript

from .scenario import Run


def transcript(run: Run) -> str:
    return _transcript(run, "《借条》轨迹")


__all__ = ["context_view", "digest_row", "transcript"]
