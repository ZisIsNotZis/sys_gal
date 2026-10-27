# 《契约失效时请勿喂猫》— 中文叙事模拟实验

本目录是 `sys_gal` 的主要实验：一个**可复现的中文叙事模拟**。一个客观世界（校园），一组严肃自主的角色，一个绑定主角的非常规 System；角色按各自动机与合法获知的信息行动，世界按显式规则运行。目标是产出可检查、可回放的轨迹，而不是成品游戏。

12 个模拟日的剧情弧、目标结局与逐日检查点方法见 `v4/docs/V4-STORY-MILESTONES.md`（参考线，不是现行要求）。

**进度、 milestones 与工作包不在本文件**：它们在仓库根的 [`../docs/0_ROADMAP.md`](../docs/0_ROADMAP.md)。

## 版本线

| 版本 | 状态 | 说明 |
| --- | --- | --- |
| v1 | 历史归档 | 首个世界与角色草案；其文档不作为现行要求。 |
| v2 | 历史归档 | 引入引擎契约与领域词汇；同上。 |
| v3 | 历史归档 | story-neutral 引擎 + 世界包适配 + 大型运行；被 v4 取代。 |
| v4 | 参考线（归档） | 中文沉浸接口、两层演员制、半天检查点、剧情锚点检查器；保留用于溯源与运行纪律的出处。 |
| **v5** | **主线** | 重写世界模型：十条原始项 + 库 + 种子；短故事阶梯。见 `v5/README.md`。 |

v1–v4 都不得据以判断当前行为；只有 v5 是主线（`../docs/adr/0002-v5-becomes-the-main-line.md`）。

## 目录结构

```
契约失效时请勿喂猫/
├── README.md                 # 本文件：概览
├── v1/ v2/ v3/               # 历史版本（归档）
├── v4/                       # 参考线（归档）：docs/ harness/ world/ scripts/ runs/
├── v5/                       # 主线：engine/ library/ stories/ scripts/ tests/ runs/
└── ../AGENTS.md              # 运行后分析协议与预门（在仓库根；agent 必读）
```

## 每份事实的家（不在本文件里复述，只指过去）

| 主题 | 权威文档 |
| --- | --- |
| 最终目标 / 设计原则 | `../docs/1_PROBLEM.md`、`../docs/3_REQUIREMENT.md` |
| 领域词汇 | `../CONTEXT.md` |
| 里程碑 / 工作包 / 当前状态 | `../docs/0_ROADMAP.md` |
| 故事阶梯 / 场景清单 / 覆盖矩阵 | `../docs/5_PRODUCT.md`、`../docs/4_USECASE.md` |
| 引擎的概念边界与内部机制 | `../docs/8_DETAIL.md` |
| 三层与按需具体化 / 谁做的决定 | `../docs/6_ARCHITECTURE.md` |
| 种子形状、动词表、运行工件、命令行 | `../docs/7_INTERFACE.md` |
| 运行后分析协议 / 预门 / 中断续跑方法 | `../AGENTS.md`、`../docs/9_IMPLEMENTATION.md` |
| 版本线决策记录 | `../docs/adr/` |
| v4 产品与交互物理（设计真理） | `v4/docs/V4-DESIGN.md` |
| v4 线的历史计划（参考） | 已退役；过程账本是 git 历史 |
