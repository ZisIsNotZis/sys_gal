# 74 — extra 生命周期产品侧候选缺陷：_horizon_bound 不含 _extra_inflight；idle-despawn 静默丢弃在途回答与 pending 问题

Status: needs-triage
Need-review: no
Need-test-cases: yes

> 2026-10-16 由票据 73 的 flake 活体诊断分出（其 §6.2"产品侧两项建议另开引擎票"）。
> 票据 73 的边界只许动 harness/tests，本票只做登记与修法草案，不改任何代码；
> 是否修、何时修、优先级与修复窗口由分诊裁决。证据链归票据 73。

## 缺陷 A：`_horizon_bound()` 不含 `_extra_inflight`（ticket 22 的时钟钉不完整）

- 位置：`harness/engine.py:709-715`——`_horizon_bound()` 只取 `_active_inflight()`
  的最小在途 wake + 1 tick；extra 的在途回答（`_extra_inflight`，engine.py:355）
  不在其集合内。
- 后果：ticket 22 的"回答在途时钟钉"只在 `_quiescent()` 的两个 stop_at 分支生效
  （engine.py:609/618；`_quiescent` 在 :683 确实检查 `_extra_inflight`），而正常
  `world.advance(until=next_event)` 路径走 :627 的 `_horizon_bound()`，不受约束
  ——世界时钟可越过在途 extra 回答直抵 despawn 阈值。
- 活证：票据 73 §2 探针 trace（07:01 spawn → 07:01 追问落地 → 07:03
  `extra_removed {reason: idle}`，provider `stub_calls=0`、`extra_turns=0`）。
- 修法草案：`_horizon_bound()` 把 `_extra_inflight` 的预期完成期限并入 bound
  （或让在途 extra 回答同样推进 horizon），使任何 advance 路径都不越过在途回答。

## 缺陷 B：idle-despawn 静默丢弃在途回答与 pending 问题

- 位置：`harness/engine.py` `_handle_extras` 顶部的 idle 判定与 `_despawn`
  （~:2147-2152，`now - last_active > extra_idle_seconds`）——在途回答被取消且
  永不执行；`extra_removed` 事件只带 location/reason，不记录被丢弃的
  pending_question / pending_heard_speech。
- 后果：E1 类"静默丢失"在引擎层仍未设门——角色问出的话可能永远没有回音，
  轨迹上只剩一条无法与任何因果相连的 `extra_removed`。
- 修法草案：despawn 前若存在在途 extra 调用或未答 pending 问题，要么推迟
  despawn（等回答落地再判 idle），要么让 `extra_removed` 显式携带被丢弃的问题
  与在途回答（fail_loud），并配回归钉。
- 回归：引擎修复后，把票据 73 §3 测试的 `extra_idle_seconds` 从 3600 恢复贴近
  生产默认，该测试应先红（复现 despawn 吞答）后绿（修复后不再吞）。

## 证据链

- 根因诊断与活体复现：票据 73 §2（探针 trace、机制链、代码出处）。
- 2026-10-16 全量层两例红（E42 envelope、E73 tick 迟到）与缺陷 A/B 同族：
  `v4/logs/full-suite-20261016-run4.log`（票据 73 Comments 2026-10-16 条目）。
