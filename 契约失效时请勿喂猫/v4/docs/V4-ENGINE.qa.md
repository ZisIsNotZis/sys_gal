# V4-ENGINE.md 验证问答（作者时定稿，2026-09-08）

验证方式：fresh-context reviewer（无泄漏、仅凭 V4-ENGINE.md 单文）作答，作者核对一致；发现项已回修源文档。维护规则：改 V4-ENGINE.md 时同步核对下列问答仍成立。

**Q1：一个角色正在思考（意图在途），另一条已提交的移动链要在 12 分钟后完成。引擎此刻会做什么？如果那个角色的意图一直不来呢？**
A：超出 `oldest_pending_deadline + 1 tick` 的事件是冻结点，全钟暂停直到意图落地或静默弃权（§2.3）；等待最慢的思考者是有界的：在飞决定等过 `freeze_tolerance` 后该视界被释放（记 `inflight_released`），世界继续。意图一直不来：`decision_timeout`（= provider 最坏情况 + 小额余量）后静默弃权——发呆、挂起动作自动 continue、计时器重挂、失败计数 +1，世界继续（§3、§6）；`await hung` 的残留等待由 `hung_tolerance` 封顶，超界即放弃并恢复会话，该角色仍能参加后续回合。停顿以"连续无进展"墙钟计（`stall_threshold_seconds`，默认 300s）而非累积冻结。

**Q2：A 在时刻 T 说了一句公开的话，同地点的 B 何时能回应？B 的回应最早带什么时间戳？A 何时看到 B 的回应？**
A：光锥：T 提交 → B 最早 T+1 tick 感知（§2.2）；B 的 speak 恰 1 tick，回应最早时间戳 T+1（§4）；A 最早 T+2 看到（§2.2）。同 tick 多人各提交一句不受光锥限制（§4）。

**Q3：realtime_ratio > 0 时，同一种子重跑还能逐字复现吗？断点续跑还能用吗？**
A：种子级确定性只在 r=0 成立（wall 延迟不可复现）；journal 回放与断点续跑不受影响（§5、§7）。

**Q4：known_contacts 在引擎因果里扮演什么角色？靠什么假设替代逐对传播追踪？**
A：零角色——仅动作层门控（能否对某人 send_message）；因果用最大信息流假设：任何在场第三者都是潜在传话人，取"人人 ≤1 tick"保守上界（§2.2、§9）。

**Q5：两个角色同一 tick 内都想拿同一件物品，谁拿到？同种子重跑结果一样吗？**
A：按意图 wall 到达序串行判定，后者 rejected + 具体原因（§2.4）；同 tick 竞争不可种子复现——种子不得依赖它；journal 逐字记录实际序，回放不受影响。（窗口 5 实测这条当时并不成立：`take` 的归属只在完成时写进世界，同 tick 第二次提交也通过校验、回执照说成功；票 98 §7.9 在提交期补上在途占用检查后，此答案才与代码一致。）

**Q6：provider 的单次调用有墙钟上界吗？`urlopen` 的 timeout 到底是什么？如果上游只滴流、永不结束响应体呢？**
A：`urlopen` 的 timeout 是 **socket 级**的（约束单次连接/单次 recv 的静默），**不是**整次请求的上界（§6）。整次调用另有一个**墙钟总预算** `_call_budget_seconds()`：有 `max_duration`（`V3_PROVIDER_MAX_DURATION`，默认 600s）就取它，否则取重试策略的结构性最坏情况（`(retries+1)×timeout + 退避和`）。每次 attempt 的 socket 超时取 `min(timeout, 剩余预算)`，响应体按 recv 分块读取并在块间复查 deadline；上游只滴流或 hold 住连接时，超界即关闭连接并按既有可重试语义报错（`retryable=True`/`retry_exhausted=True`/`attempts=N`，文案写明第 N 次尝试与已用秒数/总预算），不会无限阻塞。`worst_case_seconds()`（= 总预算 + 最后一次 socket 静默）数值不变，仍是 `decision_timeout` 的真实上界；正常响应与重试语义不变。
