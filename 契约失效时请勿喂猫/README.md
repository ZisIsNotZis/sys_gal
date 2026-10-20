# 《契约失效时请勿喂猫》— 中文叙事模拟实验

本目录是 `sys_gal` 的主要实验：一个**可复现的中文叙事模拟**。一个客观世界
（校园），一组严肃自主的角色，一个绑定主角的非常规 System；角色按各自动机
与合法获知的信息行动，世界按显式规则运行。目标是产出可检查、可回放的轨迹，
而不是成品游戏。

12 个模拟日（2026-03-16 → 03-27）的剧情弧、目标结局与逐日检查点方法见
[`v4/docs/V4-STORY-MILESTONES.md`](v4/docs/V4-STORY-MILESTONES.md)。
**项目交付里程碑与工作包见 [`ROADMAP.md`](ROADMAP.md)**（面向用户同步与验收）。

## 版本线

| 版本 | 状态 | 说明 |
| --- | --- | --- |
| v1 | 历史归档 | 首个世界与角色草案；其文档不作为现行要求。 |
| v2 | 历史归档 | 引入引擎契约与领域词汇；同上。 |
| v3 | 历史归档 | story-neutral 引擎 + 世界包适配 + 大型运行；被 v4 取代。 |
| **v4** | **主线（维护中）** | 中文沉浸接口、两层演员制、半天检查点、剧情锚点检查器；v5 的 M2 通过前仍是主线。 |
| **v5** | **在建线（规格已冻结）** | 重写世界模型：十条原始项 + 库 + 种子；短故事阶梯 S1–S7。见 `v5/docs/V5-ROADMAP.md`。 |

v4 是当前可跑的主线，v5 是正在建的新线（尚无代码，只有规格）。历史版本的 README/文档保留用于溯源，请勿据其判断当前行为。

## 目录结构

```
契约失效时请勿喂猫/
├── README.md                 # 本文件：概览与 SSOT 地图
├── ROADMAP.md                # 项目里程碑与工作包（交付计划）
├── AGENTS.md                 # 本实验的运行后分析协议与预门（agent 必读）
├── v1/ v2/ v3/               # 历史版本（归档）
├── v4/
│   ├── docs/                 # v4 设计真理（见下方 SSOT 地图）
│   ├── harness/              # story-neutral 引擎 + 运行/回放/检查器测试
│   ├── world/                # 世界种子：manifest.yml + characters/ documents/ items/ locations/
│   ├── scripts/              # seed_lint.py, check_milestones.py, mark_seed.py, 运行脚本
│   ├── runs/                 # 运行工件（trajectory + checkpoint）；每次唯一，勿覆盖
│   ├── checkpoints/          # 半天检查点存档 dN-am.json / dN-pm.json
│   └── logs/                 # 推进器与门禁日志
└── .scratch/                 # issue/工作记录（过程记录，非事实文档）
```

## SSOT 地图（每份事实只有一个家）

| 主题 | 权威文档 |
| --- | --- |
| 最终目标 / 设计原则 | `../../docs/PRINCIPLE.md` |
| 领域词汇 | `../../CONTEXT.md` |
| v5 线的里程碑 / 故事阶梯 / 当前状态 | `v5/docs/V5-ROADMAP.md` |
| v5 引擎的概念边界 | `v5/docs/V5-PRIMITIVES.md` |
| 项目里程碑 / 工作包 / 当前进度（v4 线） | `ROADMAP.md` |
| 运行后分析协议 / 预门 / 中断续跑方法 | `AGENTS.md` |
| v4 产品与交互物理（设计真理） | `v4/docs/V4-DESIGN.md` |
| v4 引擎时序 / 并发 / 冻结语义 | `v4/docs/V4-ENGINE.md` |
| v4 agent 接口（prompt / 工具 / 响应 / KB 行） | `v4/docs/V4-AGENT-INTERFACE.md` |
| v4 演员分层 / NPC 班底 / 世界加厚 | `v4/docs/V4-CAST.md` |
| v4 剧情设计与逐日里程碑（剧情锚点） | `v4/docs/V4-STORY-MILESTONES.md` |
| 世界事实（可机读） | `v4/world/manifest.yml` + `v4/world/{characters,documents,items,locations}/` |
| 过程历史 / 证据 / 决定轨迹 | `.scratch/`（ticket；append，非事实文档） |

`V4-GOSSIP-CHARACTER.md` 是被取代的旧草案，已移入 `v4/docs/archive/`。

## 前置条件与检查（v4）

运行 provider-backed 实验前，必须满足 `AGENTS.md` 的预门：历史失败回归全绿。
需要本地 LiteLLM 代理（`OPENAI_BASE_URL=http://localhost:4000/v1`，
`OPENAI_API_KEY` 为代理 master key）。故事模型默认 `github_copilot/gpt-6-luna`
（`V3_PROVIDER_API=responses`）；备用 `zai/glm-4.7-flash`（chat）。

```bash
cd 契约失效时请勿喂猫/v4
export OPENAI_MODEL=github_copilot/gpt-6-luna

# 预门 1：历史失败 + 引擎/检查器回归（必须全绿）
python3 -m unittest discover -s harness/tests -p 'test_*.py'

# 预门 2：种子自洽（每个具名 token 都必须解析到实体/概念）
python3 scripts/seed_lint.py --verbose

# 无 provider 的确定性运行（跑到 world_stops）
python3 -m harness.dry_run

# 剧情锚点门：判定某个半天/整天的剧情里程碑
python3 scripts/check_milestones.py runs/<artifact>.json --half d1-am

# provider-backed 运行（唯一命名工件）与中断续跑
python3 -m harness.real_run
python3 -m harness.resume_run runs/<runid>.checkpoint.json
```

半天推进器（跑到边界 → 存档检查点 → 过门 → 续跑）见
`v4/scripts/half_day_flow.sh` 与整条弧线的 `v4/scripts/drive_arc.sh`。

## 硬性规则

- **每次 provider 运行后必须人工检查轨迹**并以具体行为与因果问题报告，不得
  用计数或 clean/failed 标签代替结论。见 `AGENTS.md`。
- 引擎必须保持 story-neutral：无剧情阶段、好感度、路线、主角特权。
- 一次运行只从种子与规则运行；作者可在两次重跑之间修订种子，不得静默修补
  正在跑的一局。
- 每份工件唯一命名，绝不覆盖。
