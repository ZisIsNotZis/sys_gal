# 55 — 检查点撞上"extra 正在回答"就 KeyError：`pending_question` 被 pop 掉而序列化用直接下标

Status: ready-for-agent
Need-review: yes
Need-test-cases: yes

## 观测（2026-10-01 重跑 `real-20261001T055020+0800-3066025-182796693`）

运行在模拟时钟 ~09:14–09:19 挂掉，`runs/real-20261001T055020….error.log`：

```
File "harness/engine.py", line 2153, in checkpoint_state
    "pending_question": x["pending_question"],
KeyError: 'pending_question'
```

调度器任务因此死亡、世界停住；而进程**仍显示 RUNNING**（卡在 provider 里的非守护线程
阻止了解释器退出），排查时容易被误导。

## 根因（已定位到行）

- `_extra_loop` 在开始回答前把问题**消费掉**：`harness/engine.py:2020`
  `asked = str(info.pop("pending_question", "") or "")`（下一行同样 pop `pending_heard_speech`）。
  于是"extra 正在应答"的窗口内，这两个键**按设计就不存在**。
- ticket 50 新增的 `checkpoint_state`（`engine.py:2148-2156`）对 extra 全部字段使用**直接下标**
  `x["pending_question"]` / `x["pending_heard_speech"]` / `x["context_cursor"]` / `x["system_prompt"]`。
  只要检查点落在这个窗口 → KeyError → 调度器任务死 → 整个运行停摆。
- 时间线吻合：09:14–09:19 extra 在应答，06:16 落了检查点。

同类风险：这三处"存活期字段"的 pop/缺失组合是**结构性**的，不是偶发；ticket 50 的往返测试
用的是"生成后立刻检查点"的路径，恰好绕过了这个窗口，所以测试绿但生产红——**测试没有覆盖真实
的瞬态形状**。

## 验收方向

1. **序列化必须防御**：`checkpoint_state` 对 extra 字段改用与 `_rehydrate_extra` 一致的
   `.get(...)` 缺省（`pending_question` → `""`、`pending_heard_speech` → `False`、
   `context_cursor` → `start`、`system_prompt` → 重建）。缺省必须与恢复侧**同义**，保证往返等价。
2. **瞬态不该破坏键的存在性**（更稳的做法，建议一并做）：`_extra_loop` 消费问题时把它**置空**
   而不是删除（`info["pending_question"] = ""`），让"全部运行时字段始终存在"成为可断言的不变量；
   若选择保留 pop，则必须在 `checkpoint_state`/`_rehydrate_extra`/`_extra_turn` 三处都写成 `.get`。
3. **崩溃不应留下僵尸**：引擎任务因异常退出时，运行进程必须能**及时终止**（不得让用户看到
   "RUNNING"却已死）。请查清并处理非守护执行线程（例如把 provider 调用放进守护线程/自定义
   ThreadPoolExecutor，或在 `run()` 的异常出口显式收尾并 `os._exit` 兜底），并加测试/说明。
4. **回归（先红后绿）**：
   (a) 构造"extra 正在应答"的瞬态（问题已被消费）→ `checkpoint_state()` 不得抛错，且往返后
       该 extra 仍能继续应答（**今天必红**）；
   (b) 生成后立刻检查点（ticket 50 已有路径）仍绿；
   (c) 一个会抛异常的引擎任务 → 进程/运行以非零状态**及时**结束，不留僵尸。
   历史失败登记进 `v4/harness/tests/test_historical_failures.py`（ledger 风格，引用 error.log 的
   KeyError 与 09:14–09:19 时间线）。
5. 顺带核对：`Runner`（同步路径）的 extra 序列化是否有同样问题（ticket 51 已记录两条路径漂移，
   本 lane 只需**不新增**漂移；发现同类问题就一并修）。
