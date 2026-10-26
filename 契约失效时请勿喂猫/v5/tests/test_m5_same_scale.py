"""M5 的同一尺度判据：两支故事每条路的动作数不能差出一倍。

观察自：两支新世界刚合入时，《夜班》每条路 35–38 个动作，《婚礼》每条路 12–16 个，
拿它们做「同尺度对照」等于比较两个不同的东西。这里把两边的数字钉死，
任何一边悄悄长回短故事或缩回长故事，比值都会掉出 ±30%。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401
from stories.s4_night_shop.scenario import play as play_night
from stories.s5_wedding.scenario import play as play_wedding

VARIANTS = ("a", "b", "c", "d")

#: 这次定下的动作数（脚本动作，不含世界事件）。
NIGHT_ACTIONS = {"a": 48, "b": 45, "c": 47, "d": 45}
WEDDING_ACTIONS = {"a": 42, "b": 42, "c": 39, "d": 43}

#: 判据的两端：比值落在 [0.70, 1.30] 内才算同一个尺度。
LOW, HIGH = 0.70, 1.30


def turns(run) -> int:
    return sum(1 for item in run.items if item["kind"] == "turn")


class SameScaleTests(unittest.TestCase):
    def test_both_stories_keep_the_recorded_action_counts(self):
        self.assertEqual({v: turns(play_night(v)) for v in VARIANTS}, NIGHT_ACTIONS)
        self.assertEqual({v: turns(play_wedding(v)) for v in VARIANTS}, WEDDING_ACTIONS)

    def test_every_paths_action_ratio_stays_within_thirty_percent(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                night = turns(play_night(variant))
                wedding = turns(play_wedding(variant))
                ratio = wedding / night
                self.assertGreaterEqual(ratio, LOW, f"{variant}: {wedding}/{night}={ratio:.3f}")
                self.assertLessEqual(ratio, HIGH, f"{variant}: {wedding}/{night}={ratio:.3f}")

    def test_the_gap_that_motivated_this_package_is_gone(self):
        """旧数字是 15 对 38（比值 0.395）；现在每一条路都不低于 0.70。"""
        for variant in VARIANTS:
            night = turns(play_night(variant))
            wedding = turns(play_wedding(variant))
            self.assertGreater(wedding / night, 0.395, variant)


if __name__ == "__main__":
    unittest.main()
