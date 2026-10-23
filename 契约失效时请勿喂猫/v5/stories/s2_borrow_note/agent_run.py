"""《借条》的模型试点：三个角色各自决定，世界只负责裁。

回路本身在 `stories/agent_loop.py`（两支故事共用同一套）；这一份只提供《借条》的
种子、登场顺序、摘要与标题。每次运行一个唯一目录，绝不覆盖：
`runs/agent-<时间>-<pid>-<标签>/`。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from stories.agent_loop import AgentRun, play, write_artifacts as write_run

from .scenario import DEFAULT_SEED, summary

HERE = Path(__file__).with_name("runs")
TITLE = "《借条》"
ORDER = ("jia", "yi", "bing")


def play_agents(model: str, turns_each: int = 4, seed_path: Path = DEFAULT_SEED,
                order: tuple[str, ...] = ORDER,
                provider=None) -> AgentRun:
    return play(model, seed_path=seed_path, order=order, summary=summary,
                title=TITLE, turns_each=turns_each, provider=provider)


def write_artifacts(run: AgentRun, tag: str) -> Path:
    out = HERE / f"agent-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{tag}"
    return write_run(run, out, "《借条》模型试点轨迹")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    model = argv[0] if argv else os.environ.get("V5_MODEL", "github_copilot/gpt-6-luna")
    turns = int(argv[1]) if len(argv) > 1 else 4
    run = play_agents(model, turns_each=turns)
    out = write_artifacts(run, model.replace("/", "_"))
    role_turns = [i for i in run.items if i["kind"] == "turn"]
    refused = [i for i in role_turns if not i["ok"]]
    print(f"模型：{model}；{len(role_turns)} 个动作（{len(refused)} 次被拒）")
    print(f"结局：{run.summary['结局']}")
    print(f"轨迹目录：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
