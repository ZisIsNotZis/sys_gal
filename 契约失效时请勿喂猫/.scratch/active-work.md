# Active work — 《契约失效时请勿喂猫》v4

Last updated: 2026-10-19

## Where we are

- **计划**：`../ROADMAP.md`（项目里程碑 M0–M4 与工作包）。当前在 **M1（第 1 天
  端到端验收）进行中**：D1 已过门禁（第三次全天验收三门禁全 exit 0），但那次运行的
  轨迹已丢失；D1 的人工验收材料要等 M1.9 重跑一次留下可复核的工件。
- **活动线**：仅 v4。v1/v2/v3 已归档（各自 README 加 HISTORICAL 横幅）。
- **追踪器**：本目录（`契约失效时请勿喂猫/.scratch/`）。索引与状态对账见
  `README.md`。三个 feature 目录：`v4-first-day`（D1 建设/缺陷，最新票 113）、
  `v3-harness-followups`（v3 遗留，归档）、`v4-memorial-notice-grounding`（并入 M2）。
- **文档 SSOT**：项目 `README.md` + 根 `CONTEXT.md` + v4 `docs/`；地图见项目 README。

## 当前证据（2026-10-19 复跑）

- v4 回归 `Ran 707 tests ... OK (skipped=2)`（`--half` 门禁与历史失败台账全绿）。
- `scripts` 套件 38 支全绿（含新增 `test_artifacts.py`、`test_check_milestones_d2_anchors.py`）。
- `scripts/seed_lint.py` → `seed lint OK`（仅剩名字碰撞/单向通讯录/known_to 缺省三类 warning）。
- `scripts/pack_trajectory.py check` → `trajectory OK：55 件紧凑工件与原始文件逐件一致`
  （一行一条记录 + zstd -19；整天轨迹 20.2 MB ↔ 638 KB，检查点 26.8 MB ↔ 338 KB）。
- D1 第三次全天验收（`real-20261018T113143`）：`--day 1`/`--half d1-am`/`--half d1-pm`
  **均 exit 0**，5435 事件 / 1571 回合。**该工件已丢失**，只剩报告与门禁读数。

## 当前未完成工作（对应 ROADMAP）

- **M1.9** d1-am 重跑（07:00–12:59）留下可复核的验收工件，过门并人工复盘后再
  **M1.10** 从它的检查点续跑 d1-pm（13:00–22:00）；每段跑完立刻
  `python3 scripts/pack_trajectory.py pack` + `check`。半天一局，不带着问题往下跑。
- **M1.6/M1.7/M1.10** 独立复核与 D1 人工验收材料。
- 票 112 剩余：E4（老周夜里“没地方睡”）已按“NPC 到点退场”改成收场（票 115）；
  E5（班长夜间没有回合）是设计使然——NPC 无心跳，3/17 08:00 的清点已点名他；
  E9 妈妈“挨户问”没有第二户可敲（种子层，可直接交 agent）；E10–E16 纹理项可带债进 M2。
- 真实未修缺陷：issue 51（同步路径 `runner.py` 与 AsyncEngine 漂移）、
  issue 52（`move` 提交即广播 leave、`location` 完成才更新）。
- 工作区残留：仅 `v4/checkpoints/d1-pm.json`（gitignore，已归档到第二处位置）。
  `v4/runs/` 里的旧工件同样已归档，可按 `runs/README.md` 的规则清理。

## Traps

- 故事模型线路：默认 `github_copilot/gpt-6-luna`（Responses，`V3_PROVIDER_API=responses`）；
  备用 `zai/glm-4.7-flash`（chat）。需要本地 LiteLLM 代理（`localhost:4000`）。
- 墙钟上限曾被在飞等待饿死（ticket 67，已修）；仍按 ~3h/半天预算。
- v3/v4 套件需要 `OPENAI_MODEL` 已设置。
- 复盘前先自己核对工件证据：曾有 brief 把泄漏错记到 `speak` 通道。
- **轨迹工件的事实形态是紧凑件**：`runs/<run-id>.jsonl.zst`（一行一条记录 + zstd -19，
  内容一条不少）进 git；原始 `.json` 只是本地可读副本，跑完一局先
  `scripts/pack_trajectory.py pack`，预跑门的 `check` 会挡住未打包/过期。
- **件数是件数**：一件纸写 `count: N`，写一张少一张，拿走最后一张这沓就出账；写好的
  文稿从一开始就是作者手上另一样东西，不是纸“变成”的。
- **`advance()` 不带上限会走完整个排程**，所以排程现在也能移动 npc（`place_actor`）：
  测试里摆好场景后要清掉排程或传 `until=`，否则值班排程会把角色挪走。
