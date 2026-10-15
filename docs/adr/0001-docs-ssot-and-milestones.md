# ADR 0001 — 文档 SSOT 布局、追踪器归一与里程碑分层

- 状态：已采纳
- 日期：2026-10-13

## 背景

仓库积累了多个版本线（v1–v4）、分散的追踪器（根 `.scratch/` 与项目
`.scratch/`）、重复/过期的文档（v2 与 v3 的 `PHILOSOPHY.md` 逐字相同；根
`handoff.md` 是 2026-08 的 v3 监控叙事；`V4-GOSSIP-CHARACTER.md` 是被取代的
英文草案；`V4-CAST.md` §8 引用的 `runs/ab-analysis.md` 不存在）。README 指向
一个并不存在的项目 README。同时缺少领域词汇表与项目交付里程碑清单。

## 决定

1. **唯一追踪器**：所有 issue 归入 `契约失效时请勿喂猫/.scratch/`；根
   `.scratch/` 废弃。追踪器索引/状态词汇在 `契约失效时请勿喂猫/.scratch/README.md`。
2. **SSOT 地图**：项目 `README.md` 维护"每份事实一个家"的地图；根
   `CONTEXT.md` 是共享词汇表；`docs/archive/` 与 `docs/reference/` 存放历史与
   非权威资料，明确标注不可作为现行要求。
3. **版本归档**：只有 v4 是活动线；v1/v2/v3 的 README 加 HISTORICAL 横幅。
4. **两种里程碑分层**：**剧情里程碑**（半天/逐日锚点，`V4-STORY-MILESTONES.md`
   + `check_milestones.py`）与**项目里程碑**（交付垂直切片，`ROADMAP.md`）分离，
   不可混称。
5. **计划 SSOT**：`契约失效时请勿喂猫/ROADMAP.md` 承载项目里程碑 M0–M4 与
   每个里程碑下的工作包；进度在 `.scratch/active-work.md`。

## 后果

- 事实文档不再重复/冲突；过程历史只在票据里。
- 里程碑列表是提案，须用户确认后进入自动执行模式（`AGENTS.md`）。

## 未决

- `docs/adr/` 是否长期维护，取决于后续是否出现新的架构决策。
- `V4-CAST.md` §8 的模型 A/B 报告仍在补（`ROADMAP.md` M4.3）。
