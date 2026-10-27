# v5 — 重写的世界模型

v5 不是 v4 的续集，是同一实验室的**重造**：引擎只保留十条原始项，世界由库里的概念表达，故事只是使用它们的一份种子。代码在 `engine/`、`library/`、`stories/`；规矩与知识不在本文件里，按主题指过去：

| 想知道什么 | 读哪里 |
| --- | --- |
| 引擎、库、种子各拥有什么；按需具体化；谁做的决定 | `../../docs/6_ARCHITECTURE.md` |
| 种子形状、动词表、运行工件、命令行、错误语义 | `../../docs/7_INTERFACE.md` |
| 十条原始项、时钟、检查点、盘点、反作弊的内部 | `../../docs/8_DETAIL.md` |
| 跑之前必跑的门、测试策略、跑与打包的纪律 | `../../docs/9_IMPLEMENTATION.md` |
| 里程碑、工作包、决定了什么、还开着什么 | `../../docs/0_ROADMAP.md` |
| 故事阶梯、场景清单、覆盖矩阵、已知结论 | `../../docs/5_PRODUCT.md`、`../../docs/4_USECASE.md` |

## 目录

```text
v5/
├── engine/     # 十条原始项；不认识任何故事名词
├── library/    # 概念：物性 + 规则 + 渲染 + 失败；按需增长
├── stories/    # 每支故事：seed.yml + 演员/脚本 + 验收 + runs/
├── scripts/    # v5_lint.py、anti_cheat.py、pack_trajectory.py
├── runs/       # 打包后的轨迹工件（入 git）
└── tests/      # 引擎、门禁、重放、故事验收、历史失败台账
```

v5 是当前主线，v4 已归档为参考线（`../../docs/adr/0002-v5-becomes-the-main-line.md`）。两边共用的运行纪律（唯一工件、检查点、重放、运行后分析）见仓库根的 `AGENTS.md`。
