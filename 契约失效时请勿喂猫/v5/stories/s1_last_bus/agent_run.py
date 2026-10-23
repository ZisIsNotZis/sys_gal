"""《末班车》的模型试点：同一套回路、同一套检查，第二支故事。

人的答案把《末班车》的模型首轮报告放在下一个里程碑旁边，而不是演员试点的门前面
（`docs/V5-ROADMAP.md` §3）。这一份把回路接上这支故事的种子，使"这套机制能让模型
自己走出它的路"在一块第二个世界上可以被同一份检查重跑。

真模型的那一次运行在人给的授权之内：一次运行、一个模型、一个上限；授权、模型、上限
与真实花掉的 tokens 都写进这次运行的 `run.json` 的 `spend` 栏。花到上限就停，不接着花。
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

# 人给的授权（root，2026-10-23）：这一次运行、这个模型、这个上限；没有第二次运行。
# 账按 tokens 记，钱按网关自己的价折。价读自（2026-10-23T12:55Z，读到 github_copilot/gpt-6-luna）：
#   curl -s "$LITELLM_BASE_URL/model/info" -H "Authorization: Bearer $LITELLM_MASTER_KEY"
#   → input_cost_per_token 1e-07 USD，output_cost_per_token 5e-07 USD（每 token）
# 汇率是一个写明了的假设：1 美元 = 7.2 元。换成哪个汇率都不改结论：这一局只有九回合。
GRANT = {
    "granted_by": "root, 2026-10-23",
    "grant": "one real-model run of 《末班车》 through the local gateway; a second run needs a new yes",
    "ceiling_cny": 2.0,
    "cny_per_usd": 7.2,
    "input_cost_per_token": 1e-07,
    "output_cost_per_token": 5e-07,
    "price_read_utc": "2026-10-23T12:55Z",
}


def authorized_spend(model: str) -> dict:
    """把这次运行的授权整理成一份可记的账：谁批的、哪个模型、上限多少。"""
    grant = dict(GRANT)
    grant["model"] = model
    grant["ceiling_usd"] = round(grant["ceiling_cny"] / grant["cny_per_usd"], 6)
    return grant


def play_agents(model: str, turns_each: int = 3, seed_path: Path = DEFAULT_SEED,
                order: tuple[str, ...] = ORDER,
                provider=None, spend: dict | None = None) -> AgentRun:
    return play(model, seed_path=seed_path, order=order, summary=summary,
                title=TITLE, turns_each=turns_each, provider=provider, spend=spend)


def write_artifacts(run: AgentRun, tag: str) -> Path:
    out = HERE / f"agent-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{tag}"
    return write_run(run, out, "《末班车》模型试点轨迹")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    model = argv[0] if argv else os.environ.get("V5_MODEL", "github_copilot/gpt-6-luna")
    turns = int(argv[1]) if len(argv) > 1 else 3
    run = play_agents(model, turns_each=turns, spend=authorized_spend(model))
    out = write_artifacts(run, model.replace("/", "_"))
    role_turns = [i for i in run.items if i["kind"] == "turn"]
    refused = [i for i in role_turns if not i["ok"]]
    spend = run.spend
    print(f"模型：{model}；{len(role_turns)} 个动作（{len(refused)} 次被拒）")
    print(f"结局：{run.summary['结局']}")
    print(f"授权：{spend['grant']}；上限 ¥{spend['ceiling_cny']:.2f}（按 {spend['cny_per_usd']} 元/美元 ≈ ${spend['ceiling_usd']:.4f}）")
    print(f"花了：{spend.get('prompt_tokens', 0)} 输入 + {spend.get('completion_tokens', 0)} 输出"
          f" = {spend.get('total_tokens', 0)} tokens；≈ ${spend.get('spent_usd', 0.0):.6f}")
    print(f"轨迹目录：{out}")
    if spend.get("stopped_by"):
        print(f"停在上限：{spend['stopped_by']}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
