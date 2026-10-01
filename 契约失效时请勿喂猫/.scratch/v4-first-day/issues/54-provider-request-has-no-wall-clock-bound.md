# 54 — provider 单次请求没有真正的墙钟上界：服务端滴流/keep-alive 可绕过超时与重试预算

Status: ready-for-agent
Need-review: yes
Need-test-cases: yes

## 现象与证据（由 ticket 53 的排查定位）

2026-10-01 的重跑在模拟时钟 11:32 被挂死（详见 ticket 53）。排查证据指向**上游把单个请求静默挂住**：

- 冻结时刻 `辅导员` 的 live 会话（检查点 `runner.sessions`）末尾是一条 11:32 的 `user` 世界消息、
  **没有 assistant 回复** ⇒ 挂在 `V4Session.decide` 的 `chat_with_tools` 里；
- 同一角色在 11:13、11:16 已经两次 `RuntimeError: provider retry deadline exhausted after 4 attempts`
  ⇒ 上游对那一路早就出问题；
- 当时直连代理用大提示实测 1.8s 返回 ⇒ 不是模型普遍变慢。

## 根因（代码级）

`harness/provider.py` 的 `_run_request`：

```python
with urlopen(request, timeout=self.timeout) as response:
    raw_response = response.read()
```

- `timeout` 是 **socket 级**：它约束"单次连接/单次 recv 的静默时长"，**不是整个请求的上界**。
  服务端只要持续滴流、或保持连接不断开，`response.read()` 就能一直不返回；
- 预算检查（`max_duration` / `retry deadline`）只在**每次 attempt 的顶部**做，单次调用内部**不再检查**；
- 于是"单次调用永久挂住"在 provider 层没有被任何东西阻止，只能靠引擎侧兜底（ticket 53 的
  freeze tolerance / hung timeout 现已补上，但那是第二层，且会浪费一整个回合）。

## 验收方向

1. **给整次请求一个真正的墙钟上界**：例如把每次 attempt 的 socket 超时取
   `min(self.timeout, 剩余预算)`，并用**分块读取 + 逐块检查 deadline**（或等价的连接级看门狗）
   保证请求总时长不超过预算；超界时关闭连接、按可重试/不可重试语义报错并计入 attempt。
2. **预算语义要可见**：报错信息说明"总预算耗尽（第 N 次尝试，已用 X 秒）"，便于复盘区分
   "上游慢"与"上游挂死"。
3. **不改变既有重试语义**：可重试错误照旧退避重试，`retry_exhausted` 标记与既有调用点契约不变。
4. 回归（先红后绿），用**本地假服务器**（`http.server` 起一个滴流/永不完成的端点）：
   - 一个只滴流不结束的响应：必须在预算内返回错误，不得无限阻塞；
   - 一个正常响应：行为与现在一致（含重试计数、错误类型）；
   - 一个慢但最终完成的响应（在预算内）：**必须成功**，不得被误杀。
   历史失败登记进 `v4/harness/tests/test_historical_failures.py`（ledger 风格，引用 11:32 观测）；
   测试必须能在 CI 里快速跑完（用秒级预算，不要写分钟级的睡眠）。
5. 文档：`docs/V4-ENGINE.md` / `docs/V4-ENGINE.qa.md` 里 provider 预算一节写清"总预算 vs socket 超时"的区别。
