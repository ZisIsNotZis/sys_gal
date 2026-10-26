"""M5 的同一尺度判据：两支故事每条路**做成的事**不能差出一倍。

数的是 `ok is True` 的 turn——真的发生了的事。失败的动作不算数：它只说明剧本往
一天的空处里塞了一个够不到的动作，不说明这一天里多了一件事。上一版《婚礼》就是
这么骗过判据的：42 个动作里有 13–17 个"没成"（`走向 厅内 —— 没成：你已经在厅内里了`、
`拿起 菜 —— 没成：这里没有一样东西叫「菜」`），真正做成的是 25–29 个，对《夜班》的
45–48 个只有 0.55–0.63，而这一份却按 `kind == "turn"` 数，绿着报平安。

所以这里有两条一起成立的判据：
1. **失败的脚本动作必须为零**（有意的另计，见 `INTENTIONAL_REFUSALS`）；
2. 两边**做成的事**之比落在 [0.70, 1.30] 内。
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

PLAYS = {"s4_night_shop": play_night, "s5_wedding": play_wedding}

#: 这次定下的**做成的事**（`ok` 的脚本动作，不含世界事件）。
NIGHT_MADE = {"a": 48, "b": 45, "c": 47, "d": 45}
WEDDING_MADE = {"a": 54, "b": 50, "c": 51, "d": 55}

#: 故意留着不许成功的脚本动作：（故事, 路）→ 条数。
#: 某条路若要让角色去够一个够不到的东西（"想拿已经不在手里的东西"），在这里登记，
#: 并从下面"失败必须为零"里扣掉；现在一条也没有。
INTENTIONAL_REFUSALS: dict[tuple[str, str], int] = {}

#: 判据的两端：比值落在 [0.70, 1.30] 内才算同一个尺度。
LOW, HIGH = 0.70, 1.30


def turns(run) -> list[dict]:
    return [item for item in run.items if item["kind"] == "turn"]


def made(run) -> int:
    """做成的事：真的发生了的动作。"""
    return sum(1 for item in turns(run) if item["ok"])


def refused(run) -> list[dict]:
    return [item for item in turns(run) if not item["ok"]]


class SameScaleTests(unittest.TestCase):
    def test_no_scripted_action_is_a_failure(self):
        """脚本里的每一个动作都要物理做得到：人在对的地方，东西在够得到的地方。"""
        for story, play in PLAYS.items():
            for variant in VARIANTS:
                with self.subTest(story=story, variant=variant):
                    bad = refused(play(variant))
                    allowed = INTENTIONAL_REFUSALS.get((story, variant), 0)
                    self.assertEqual(
                        len(bad), allowed,
                        "；".join(f"{i['actor']} {i['verb']} {i['target']} —— {i['reason']}"
                                 for i in bad),
                    )

    def test_both_stories_keep_the_recorded_action_counts(self):
        self.assertEqual({v: made(play_night(v)) for v in VARIANTS}, NIGHT_MADE)
        self.assertEqual({v: made(play_wedding(v)) for v in VARIANTS}, WEDDING_MADE)

    def test_every_paths_action_ratio_stays_within_thirty_percent(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                night = made(play_night(variant))
                wedding = made(play_wedding(variant))
                ratio = wedding / night
                self.assertGreaterEqual(ratio, LOW, f"{variant}: {wedding}/{night}={ratio:.3f}")
                self.assertLessEqual(ratio, HIGH, f"{variant}: {wedding}/{night}={ratio:.3f}")

    def test_the_gap_that_motivated_this_package_is_gone(self):
        """按做成的事算，旧数字是 25–29 对 45–48（比值 0.55–0.63）；现在都不低于 0.70。"""
        for variant in VARIANTS:
            night = made(play_night(variant))
            wedding = made(play_wedding(variant))
            self.assertGreater(wedding / night, 0.63, variant)


if __name__ == "__main__":
    unittest.main()
