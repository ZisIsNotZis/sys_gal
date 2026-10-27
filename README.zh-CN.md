# Sys Gal 🧠

[English](README.md) | 简体中文

这是一个中文叙事模拟实验工作区，研究自主角色、信息边界和可复现故事轨迹。

## 从哪里开始

- [AGENTS.md](AGENTS.md) — 仓库级 agent 工作政策；运行 provider 实验前先读。
- [`契约失效时请勿喂猫/`](契约失效时请勿喂猫/) — 主要实验，先读它自己的 [README](契约失效时请勿喂猫/README.md)。
- [CONTEXT.md](CONTEXT.md) — 共享领域词汇表。

## 文档按层分家

一个事实只有一个家。编号越小越靠目的。

| 层 | 文件 | 放什么 |
| --- | --- | --- |
| — | [docs/0_STAGING.md](docs/0_STAGING.md) | 值得留、还没落到它该在的层里的事实 |
| — | [docs/0_ROADMAP.md](docs/0_ROADMAP.md) | 里程碑、工作包、决定了什么、还开着什么 |
| 1 | [docs/1_PROBLEM.md](docs/1_PROBLEM.md) | 为什么值得做 |
| 2 | [docs/2_GOAL.md](docs/2_GOAL.md) | 成功长什么样，以及不宣称什么 |
| 3 | [docs/3_REQUIREMENT.md](docs/3_REQUIREMENT.md) | 虚构契约、五层分离、确定性、可重放 |
| 4 | [docs/4_USECASE.md](docs/4_USECASE.md) | 谁把什么做完；四条流程；七支故事作为价值切片 |
| 5 | [docs/5_PRODUCT.md](docs/5_PRODUCT.md) | 故事阶梯、覆盖矩阵、已知结论、拒绝过的分支 |
| 6 | [docs/6_ARCHITECTURE.md](docs/6_ARCHITECTURE.md) | 引擎/库/种子的边界与质量属性 |
| 7 | [docs/7_INTERFACE.md](docs/7_INTERFACE.md) | 种子形状、动词表、运行工件、命令行、错误语义 |
| 8 | [docs/8_DETAIL.md](docs/8_DETAIL.md) | 原始项、时钟、检查点、盘点、反作弊的内部 |
| 9 | [docs/9_IMPLEMENTATION.md](docs/9_IMPLEMENTATION.md) | 环境、门、测试策略、跑与打包的纪律 |

带拒绝分支的决定在 [docs/adr/](docs/adr/)。

## 状态与未来

这是持续演进的研究原型，不是完成的游戏，也不宣称具有人类级故事质量。当前活动线是 v5；目标是一个可复现的叙事实验室，能检查角色行为、知识、失败与因果连续性。进度见 [docs/0_ROADMAP.md](docs/0_ROADMAP.md)。

欢迎 Issue 和 PR。代理可以协助调查与文档工作；维护者负责审核与合并。
