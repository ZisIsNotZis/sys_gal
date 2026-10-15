# Active work — 《契约失效时请勿喂猫》v4

Last updated: 2026-10-13 +0800

## Where we are

- **计划**：`../ROADMAP.md`（项目里程碑 M0–M4 与工作包）。当前在 **M1（第 1 天
  端到端验收）进行中**：d1-am 已过门并归档；d1-pm 未过门、最新一次重跑被中断。
- **活动线**：仅 v4。v1/v2/v3 已归档（各自 README 加 HISTORICAL 横幅）。
- **追踪器**：本目录（`契约失效时请勿喂猫/.scratch/`）。索引与状态对账见
  `README.md`。三个 feature 目录：`v4-first-day`（D1 建设/缺陷）、
  `v3-harness-followups`（v3 遗留，归档）、`v4-memorial-notice-grounding`（并入 M2）。
- **文档 SSOT**：项目 `README.md` + 根 `CONTEXT.md` + v4 `docs/`；地图见项目 README。

## 当前证据（2026-10-13 复跑）

- v4 回归 `Ran 571 tests ... OK (skipped=1)`；`scripts/seed_lint.py` → OK。
- d1-am 三锚点 PASS（`check_milestones.py --half d1-am`）。
- d1-pm 门禁 FAIL 6 项（`../v4/logs/gate-d1-pm.txt`）：
  辅导员介入、三份个人说明、老周托话、妈妈承诺、审计催办转达、林瑶自查审计包。
- 2026-10-06 d1-pm 重跑 `real-20261006T102015…` 被中断：`outcome=null`，
  最后世界事件 18:34，未复盘。

## 当前未完成工作（对应 ROADMAP）

- **M1.1** 复盘 10-06 半成品 run（issue 69）。
- **M1.2/M1.3** 6 个 FAIL 锚点根因与修复（issue 70）。
- **M1.4** d1-pm 重跑至 22:00 过门。
- 真实未修缺陷：issue 51（同步路径 `runner.py` 与 AsyncEngine 漂移）、
  issue 52（`move` 提交即广播 leave、`location` 完成才更新）。
- 工作区未提交残留（属用户）：`v4/checkpoints/d1-am.json` 改动、
  `v4/checkpoints/d1-pm.json`、`v4/logs/`、`v4/scripts/drive_arc.sh`、
  `v4/scripts/half_day_flow.sh` 改动。

## Traps

- 故事模型线路：默认 `github_copilot/gpt-6-luna`（Responses，`V3_PROVIDER_API=responses`）；
  备用 `zai/glm-4.7-flash`（chat）。需要本地 LiteLLM 代理（`localhost:4000`）。
- 墙钟上限曾被在飞等待饿死（ticket 67，已修）；仍按 ~3h/半天预算。
- v3/v4 套件需要 `OPENAI_MODEL` 已设置。
- 复盘前先自己核对工件证据：曾有 brief 把泄漏错记到 `speak` 通道。
