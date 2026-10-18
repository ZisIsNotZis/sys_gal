# 85 — 提示层：话语不改变世界、不得断言未见的世界变化、写记录不必先有纸笔

Status: fixed
Need-review: yes
Need-test-cases: yes

> 来源：票 83 §3 的"移交项 1"（`issues/83-engine-window1-fixes.md`）、票 81 §3、报告
> `reports/m1-window1-07to14.md` §P1/§P2（run `real-20261018T012247+0800-1592449-689352756`）。
> 边界：**只改提示组装、工具说明、测试与本票点名的三份文档**。`world/`、`scripts/`、
> `kernel.py` 的动作逻辑、事件/检查点/replay 语义一行未动；`engine.py` 的唯一改动是
> `_take_turn` 里渲染 `[director]` 块的那三行（提示组装，不是动作逻辑）。

## 0. 结论摘要

三类失效的判据都是引擎已经照实记账（E84–E87），缺口在"模型被告知了什么"：

| 失效 | 证据 | 落点 | 看守 |
|---|---|---|---|
| ① 把承诺当交付 | 食堂大妈 12:44–12:58 七次"我马上给你打"，零 `item_given`/`place` | NPC `[director]` 块首（`prompt.NPC_WAKE_RULES`）；extra 固定 prompt 的"你能做的事"；MC 的 `give`/`take` 工具说明 | E88 |
| ② 断言世界状态的改变 | 11:48–11:59 "长柄勺找不着/可能被挪到桶后头了"，而 `items/例汤` 原文是"桶边搭着一把长柄勺" | NPC `[director]` 块首；extra 固定 prompt | E88 |
| ③ 有纸笔却说"没有把记录写入纸面的工具" | 林瑶 13:13 `inner`："纸笔在我手上，但没有可用工具把个人事实记录实际写入纸面"（她 08:34 就用 `leave_note` 写过 400 字） | MC 的 `leave_note` 工具说明（在 E85 的"写记录/不需要先拿到纸笔"上补"书面记录"这座桥） | E88 |

分布是刻意的，不把三条塞进同一处（理由写进 `docs/V4-AGENT-INTERFACE.md` §2.3）：MC 没有
`[director]` 块，能告诉它动作语义的只有工具说明；NPC 的动作面与 MC 相同，缺的是唤醒当场
"承诺≠交付"的约束；extra 的固定 prompt 就是它全部的世界（无 KB、无记忆工具）。

## 1. 改了什么（逐处）

**A. NPC 唤醒的 `[director]` 块**（`harness/prompt.py` + `harness/engine.py` `_take_turn`）

- `prompt.NPC_WAKE_RULES`（新）：两条，短句、可执行、不训导——

```text
【说话不改变世界】
- 只有工具调用能改变世界：说「我给你」「我去拿」「我马上给你打」什么都不会发生。要交付就真的用 give 把东西递到在场的某人手上，要取物用 take，要放下用 place；做不到就直说做不到。
- 不许断言或否认世界状态的改变（「勺子没了」「已经登记好了」「东西被挪走了」），除非你亲眼看到那条事件；这条消息里你感知到的事实，就是此刻的事实。
```

- `prompt.director_block(brief)`（新）：`NPC_WAKE_RULES` 在前，种子写的本场简报接在其后。
- `engine._take_turn`：原来是 `director = self.director_brief(actor_id) if ... else None`，
  于是**种子没给该角色写 `beat_goals` 时连块都不存在**（`real_run.director_brief` 对该
  NPC 返回 `None`）——约束取不取决于种子，是这次要修的那个洞。现在 NPC 唤醒一定带块：
  先判"是 NPC 且是唤醒回合"，再把 `director_brief` 的结果（可为 `None`）交给
  `director_block`。MC 那条路径一字未改，MC 仍然拿不到 `[director]`。

**B. extra 的固定 prompt**（`harness/npc_agent.py` `build_extra_system_prompt`）

在"你能做的事"一段里补两句（紧接既有的"没做过的动作绝不能叙述成已经发生"）：

```text
只有这些工具调用改变世界：说“我给你”“我去拿”什么都不会发生。
也不许断言或否认世界的变化（东西没了、坏了、被人挪走了、事已经办好了），除非你亲眼看见那条事件——场景里给你的事实，就是此刻的事实。
```

这一处是 extra 的**生命周期提示**（会话创建时固定、整场对话逐字不变、随检查点持久化），
不是每回合的 briefing：静态约束放进静态前缀才不花每回合的 token。

**C. MC 的工具说明**（`harness/action_schema.py` `_TOOL_DESCRIPTIONS`）

- `give`：`…；东西只在这次调用之后才到对方手里——嘴上说“我给你”不会让任何东西移动；给不了就直说给不了`
- `take`：`拿起一件在这里的物品；嘴上说“我去拿”不会让东西到你手里，要拿到就得真的调用它`
- `leave_note`：在 E85 的"写记录/留字条""不需要先拿到纸笔"之间加一句
  `要留一份书面记录（比如写在纸上）就是这个动作。`（报告 §P1 说的"措辞桥"就缺这一句）

**D. 文档**

- `docs/V4-AGENT-INTERFACE.md`：新增 **§2.3 话语不改变世界（ticket 85）**——三条约束一次说全、逐条点名各自落点、说明为什么分三处、给出看守测试名；§2 工具表同步 `take`/`give`/`leave_note` 三行；§3 与 §5 各加一句指针（NPC 的 `[director]` 块以 §2.3 两条固定开头；extra 的断言边界含同样两条）。
- `docs/V4-CAST.md` §3：新增"简报的两条固定约束"，写清它们是提示层而非种子、没写目标的 NPC 也带着、以及两个真实失效作为来源，并指向 `PromptDeliveryConsistencyGates`（E88）。
- `docs/V4-ENGINE.md` §7.4：把"修在 `npc_agent` 的导演简报/角色卡"从"待办"改成已落地的三个具体位置。

## 2. 红 → 绿

测试类 `harness/tests/test_historical_failures.py::PromptDeliveryConsistencyGates`（4 支），
台账 E88。

红（实现前，本工作树）：

```text
python3 -m unittest harness.tests.test_historical_failures.PromptDeliveryConsistencyGates -v
FAIL: test_an_npc_wake_briefing_binds_delivery_to_tools
      AssertionError: '[director]' not found in '3/16(一) 7:01 @食堂\n在场：食堂大妈(you)，唐小岚…'
FAIL: test_an_extra_prompt_binds_delivery_to_tools
      AssertionError: '只有这些工具调用改变世界' not found in '你就是王阿姨，食堂里的一个打饭阿姨…'
FAIL: test_mc_tool_notes_say_words_are_not_delivery
      AssertionError: '不会让任何东西移动' not found in '把身上的一件物品递给在场的某人'
Ran 3 tests — FAILED (failures=3)
```

第一条红本身就是证据：那个 NPC 唤醒回合**连 `[director]` 块都没有**（种子里她没写
`beat_goals`），所以"承诺要用 `give` 兑现"这条约束此前完全取决于种子写没写本场目标。

绿（实现后）：

```text
Ran 4 tests in 1.210s — OK
```

四支断言读的是**组装后的提示文本**，不是函数名：

1. `test_an_npc_wake_briefing_binds_delivery_to_tools`：真跑一个 v4 引擎（唐小岚在食堂
   开口点名食堂大妈），记录每个角色实际收到的世界消息。断言食堂大妈的第一条消息里有
   `[director]`、"只有工具调用能改变世界"、`give`、"不许断言或否认世界状态的改变"；
   **负面**断言三位 MC 的每一条消息都没有 `[director]`，也没有这条约束的措辞。
   引擎在这一支里**不传 `director_brief`**——约束在，说明它不依赖种子。
2. `test_an_extra_prompt_binds_delivery_to_tools`：读 `build_extra_system_prompt` 的成品，
   断言两句都在；**负面**断言里面没有 `[director]`、没有 `leave_note`（路人没有这个工具）。
3. `test_mc_tool_notes_say_words_are_not_delivery`：读 `TOOLS` 的 `description`，断言
   `give`/`take` 各有一句"话不搬运东西"、`leave_note` 有"写记录"+"书面记录"+"不需要先拿到纸笔"；
   **负面**断言 `NPC_WAKE_RULES` 原文不混进任何工具说明。
4. `test_the_docs_name_the_same_three_bindings`：断言两份文档点名 `NPC_WAKE_RULES`、
   `PromptDeliveryConsistencyGates`、`leave_note`，改提示不改文档（或反过来）会被拦住。
   这一支是随文档一起加的，**没有单独留一次红跑**，如实记录（加文档前它必然红：两个
   锚点在旧文档里都不存在）。

### 负向控制（证明这几支真的会咬）

把三处提示各删一句后重跑（改完立即按 sha256 还原，三个文件逐字节回到改动后状态）：

```text
mutated: prompt.py 的"只有工具调用能改变世界"→"话语也能改变世界"；
         npc_agent.py 删掉"只有这些工具调用改变世界："；
         action_schema.py 删掉"——嘴上说“我给你”不会让任何东西移动；给不了就直说给不了"
Ran 4 tests — FAILED (failures=3)     ← 三支逐条抓住，第 4 支（文档）仍绿，符合预期
还原后：sha256sum -c → 3 个 OK；PromptDeliveryConsistencyGates → Ran 4 tests — OK
```

## 3. 回归读数（本工作树）

```text
OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s harness/tests -p 'test_*.py'
  run1  Ran 608 in 94.4s  FAILED (failures=1)：test_silent_abandonment_auto_continues_pending_action
  run2  Ran 608 in 85.2s  FAILED (failures=1)：同一支
  run3  Ran 608 in 96.2s  OK (skipped=1)      ← 全量绿读数
  run4  Ran 608 in 93.3s  FAILED (failures=1)：同一支
  run5  Ran 608 in 92.6s  FAILED (failures=2)：同一支 +
        test_uncovered_concrete_prop_claim_blocks_the_seed（并行 lane 正在改 world/ 与
        world_loader.py；该支单跑 3/3 OK，属其 P10 种子契约门）
  run6  Ran 608 in 76.9s  OK (skipped=1)      ← 收尾绿读数（第二支全绿）

python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
  Ran 161 tests in 55.4s — OK（157 + 本票 4）

python3 -m unittest harness.tests.test_historical_failures.PromptDeliveryConsistencyGates
  Ran 4 tests — OK

# 相邻模块（未受影响的回归）
python3 -m unittest harness.tests.test_action_schema harness.tests.test_npc_layer \
  harness.tests.test_proto harness.tests.test_character_session     Ran 86 — OK
python3 -m unittest harness.tests.test_engine harness.tests.test_kernel \
  harness.tests.test_world_pack harness.tests.test_milestones        Ran 194 — OK
python3 -m unittest harness.tests.test_document_contracts \
  harness.tests.test_historical_failures.PromptDeliveryConsistencyGates  Ran 11 — OK

python3 scripts/seed_lint.py     seed lint OK（exit 0；仅提示级 warning）
```

608 = 604（票 83 收尾读数）+ 4（本票）。

### 那支 `test_silent_abandonment_auto_continues_pending_action` 是不是本票引入的

不是。它是票 72/73/77/83 已登记的负载/时序敏感 flake（legacy `_submit` 路径），而本票在
`engine.py` 里改的是 `if v4:` 分支内的 `[director]` 组装，那一支测试根本不经过它。
定量对照（同一台机器、交替跑 10 轮，`python3 -m unittest harness.tests.test_engine`）：

```text
本工作树（含本票改动）：    10 轮 2 红
影子树（只把本票那 3 行 engine 改动还原，其余逐字节相同）：10 轮 4 红
单支隔离跑本工作树：       10/10 OK
```

即改动前后同族同率（甚至更低），不随本票变化。

## 4. 残留与未做

- **不做 NLP 闸**：没有实现任何"检测模型是否在断言世界变化"的运行时拦截（ticket 48 已裁定
  语言层不设闸）。本票只改"模型被告知了什么"，说话仍永不产生动作。
- **旧的两层演员路径未加**：`npc_agent._DIRECTOR_RULES` / `build_npc_system_prompt`（旧
  `NpcAgent`，只在存量测试里用）没有复制这两条——同一事实只留一处（`prompt.NPC_WAKE_RULES`）。
  生产入口 `real_run`/`resume_run` 走的是 `make_npc_agent_v4` + `AsyncEngine`。
- **未验证的部分**：本票只证明"提示文本里有这三条"，不证明模型会照做。要证明后者需要一次
  新的 provider-backed 运行并按 `AGENTS.md` 的运行后分析协议人读轨迹——建议下一窗口
  （食堂午饭段）复跑，专看食堂大妈是否真的 `give`、是否再出现自造障碍。
- `test_the_docs_name_the_same_three_bindings` 没有自己的红跑（见 §2）。
- `test_uncovered_concrete_prop_claim_blocks_the_seed` 的一次红来自并行 lane 的种子半成品，
  单跑绿，本票未动 `world/`。

## 5. 改动文件

- `harness/prompt.py`：`NPC_WAKE_RULES`、`director_block()`；`render_world_message` 的 docstring 指向它。
- `harness/engine.py`：`_take_turn` 里 `[director]` 块的组装（+ 一行 import）。
- `harness/npc_agent.py`：`build_extra_system_prompt` 的两句约束（+ docstring 记票 85）。
- `harness/action_schema.py`：`give`/`take`/`leave_note` 的工具说明。
- `harness/tests/test_historical_failures.py`：台账 E88 + `PromptDeliveryConsistencyGates`（4 支）。
- `docs/V4-AGENT-INTERFACE.md`（§2.3 新增、§2 表三行、§3/§5 指针）、`docs/V4-CAST.md`（§3 两条固定约束）、`docs/V4-ENGINE.md`（§7.4 落地位置）。
- **未动**：`world/`、`scripts/`、`harness/kernel.py`、`harness/replay.py`、检查点格式、事件 kind。
