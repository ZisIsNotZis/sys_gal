"""跑一支路径，写出可通读的轨迹与事件日志。

用法（在 `v5/` 目录下）：

    python3 -m stories.s1_last_bus.run a
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.events import dump_log

from .scenario import ending, play
from .transcript import context_view, digest_row, transcript


def main(argv: list[str] | None = None) -> int:
    variants = (argv if argv is not None else sys.argv[1:]) or ["a"]
    out = Path(__file__).with_name("runs")
    out.mkdir(exist_ok=True)
    for variant in variants:
        run = play(variant)
        (out / f"{variant}.md").write_text(transcript(run), encoding="utf-8")
        (out / f"{variant}.context.md").write_text(context_view(run), encoding="utf-8")
        (out / f"{variant}.json").write_text(
            json.dumps({"events": run.log.to_json(), "ending": ending(run)}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        (out / f"{variant}.events.json").write_text(dump_log(run.log), encoding="utf-8")
        row = digest_row(run)
        print(f"{variant}: {row['turns']} 回合 / {row['events']} 事件 / {row['ending']['结局']}")
        print(f"  轨迹：{out / f'{variant}.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
