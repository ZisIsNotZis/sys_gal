"""《末班车》的模型试点：同一套回路、同一套检查，第二支故事。

人的答案把《末班车》的模型首轮报告放在下一个里程碑旁边，而不是演员试点的门前面
（`docs/V5-ROADMAP.md` §3）。这一份把回路接上这支故事的种子，使"这套机制能让模型
自己走出它的路"在一块第二个世界上可以被同一份检查重跑；真模型的那一次运行等 M5。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from stories.agent_loop import AgentRun, play, write_artifacts as write_run

from .scenario import DEFAULT_SEED, summary

HERE = Path(__file__).with_name("runs")
TITLE = "《末班车》"
ORDER = ("jia", "yi", "driver")


def play_agents(model: str, turns_each: int = 3, seed_path: Path = DEFAULT_SEED,
                order: tuple[str, ...] = ORDER,
                provider=None) -> AgentRun:
    return play(model, seed_path=seed_path, order=order, summary=summary,
                title=TITLE, turns_each=turns_each, provider=provider)


def write_artifacts(run: AgentRun, tag: str) -> Path:
    out = HERE / f"agent-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{tag}"
    return write_run(run, out, "《末班车》模型试点轨迹")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    model = argv[0] if argv else os.environ.get("V5_MODEL", "github_copilot/gpt-6-luna")
    turns = int(argv[1]) if len(argv) > 1 else 3
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
