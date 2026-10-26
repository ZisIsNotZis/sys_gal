"""跑四条路径，写出可通读的轨迹与上下文审计视图。

用法（在 `v5/` 目录下）：python3 -m stories.s5_wedding.run a b c d
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.events import dump_log
from stories.common import context_view, digest_row

from .scenario import play, summary
from .transcript import transcript


def main(argv: list[str] | None = None) -> int:
    variants = (argv if argv is not None else sys.argv[1:]) or ["a", "b", "c", "d"]
    out = Path(__file__).with_name("runs")
    out.mkdir(exist_ok=True)
    for variant in variants:
        run = play(variant)
        (out / f"{variant}.md").write_text(transcript(run), encoding="utf-8")
        (out / f"{variant}.context.md").write_text(context_view(run), encoding="utf-8")
        (out / f"{variant}.json").write_text(
            json.dumps({"events": run.log.to_json(), "summary": summary(run)},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        (out / f"{variant}.events.json").write_text(dump_log(run.log), encoding="utf-8")
        row = digest_row(run)
        end = run.summary
        print(f"{variant}: {row['turns']} 动作 / {row['events']} 事件 / {row['decided']} / "
              f"多出来的名字:{end['签到本上多出来的名字']} / 读过本子的人:{end['读过本子的人']} / "
              f"本子改过：{'是' if end['本子改过'] else '否'} / {end['结局']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
