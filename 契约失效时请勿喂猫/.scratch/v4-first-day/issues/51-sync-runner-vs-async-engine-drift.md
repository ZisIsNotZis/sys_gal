# 51 — 同步路径 `runner.py` 与 AsyncEngine 的 CAST 行为不一致（唤醒/重复监测等）

Status: needs-triage
Need-review: no
Need-test-cases: yes

## 背景
`real_run` 走 `AsyncEngine`；`runner.py` 是同步路径，供 `scenario_run` / `mock_run` / `dry_run`
使用（含我们的 `python3 -m harness.dry_run` 门禁）。两条路径各自维护一套 CAST 与监测逻辑，
历史上已多次出现"修了 AsyncEngine、同步路径仍旧"的情况：

- ticket 45（NPC 唤醒）：`reminder_due` 与"欠回应"两个唤醒输入只在 `AsyncEngine` 落地；
  `runner.py` 的 NPC 仍不会被自己的到期提醒或未回应的当面提问唤醒。
- ticket 43（反重复/停滞）：监测器接入点在两条路径各写一遍（`engine.py:1144` 与 `runner.py:284`），
  本次只确认了 AsyncEngine 一侧的 `monitor_result`/`location` 语义；同步路径未逐一复核。
- ticket 50（extra 检查点）：两条路径的 `system_prompt` 都不完整，已一并修；但这类"漏字段"问题
  本质是双实现漂移。

## 风险
`dry_run` 是我们每次改动都要过的门禁；若同步路径行为与生产路径偏离，门禁的"绿"就不能代表生产行为，
等于**用一个廉价替身验证生产核心**。目前已有至少一处确定漂移（唤醒）与一处未复核（重复监测）。

## 验收方向
1. 盘点两条路径的 CAST/唤醒/监测/字段持久化差异，列清单，判定哪些是**有意的**（例如同步路径不需要
   异步节拍），哪些是漂移。
2. 对漂移项：优先抽出**共享实现**（同一处判定逻辑被两条路径调用），而不是再抄一遍；
   若确实无法共享，加一条"一致性测试"——同一夹具在两条路径上断言同样的可观测行为。
3. 至少覆盖：NPC 的两个唤醒输入、重复监测的传入参数语义、extra 检查点字段完整性。
4. 完成后在 `docs/V4-ENGINE.md` 说明两条路径的**契约边界**（什么必须一致、什么允许不同）。
