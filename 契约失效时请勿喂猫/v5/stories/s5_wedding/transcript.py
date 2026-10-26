"""《婚礼》的两个视图（排版在 stories/common.py）。"""

from __future__ import annotations

from stories import common
from stories.common import context_view, digest_row

from .scenario import Run

# `stories/common.py` 不归本包所有，它的排版用词表里还没有这几个动词。
# 这里只补词，不动它已有的任何条目。
for _verb, _label in (("sign", "记上"), ("announce", "高声说"),
                      ("retell", "转述"), ("hail", "喊住")):
    common.VERBS.setdefault(_verb, _label)


def transcript(run: Run) -> str:
    return common.transcript(run, "《婚礼》轨迹")


__all__ = ["context_view", "digest_row", "transcript"]
