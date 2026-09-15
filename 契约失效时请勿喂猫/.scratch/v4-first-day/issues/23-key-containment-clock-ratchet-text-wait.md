# 23 — key 包容去重、时钟棘轮（chain advance 泄漏）、text 自动等待 + NPC 回信

Status: done

## User findings (live trajectory review)
1. `[老家属院 家属院 老街坊 地下室 老家属院的地下室 家属院地下室]` — key 重叠
   没查：家属院 ⊂ 老家属院 ⊂ 老家属院的地下室，地下室 ⊂ 家属院地下室。
   ticket-22 的去重只删归一化重复，没查包含关系。
2. 7:35 的回合（text 给妈妈）7:41 才提交 —— ticket-22 只钉住了 extras 的
   回应，没堵住通用棘轮。
3. 妈妈没有回信 —— 她 07:41 醒来只调了 flashback（查记忆准备答案），
   之后没人再唤醒她，答案永远没发出去。
4. text（以及其他工具）应同样有 wait_response 默认 true。

## Root causes
- **时钟棘轮**：`_execute_chain` 的 `world.advance(until=busy_until)` 无视
  horizon —— 每个即时决策角色的链都把世界拖 1 tick（自己的完成时刻），
  连锁棘轮。调度器的冻结只管调度器路径；actor 协程内的同步链推进绕过它
  （7:35 的感知、7:40 的提交 = 陈默思考期间 13 个事件）。
- **NPC 回信断流**：被定向消息唤醒的 NPC 花一回合 flashback（世界动作
  零、无言语）后进入发呆——没有下一次唤醒，回复永远写不完。
- text 无自动等待。

## Fixes
- `_make_row` 两遍去重：归一化重复折叠 + **包容去重**（某 key 的归一化形
  包含另一 text key → 删——子串匹配下长变体零增益）。首 text key（行的
  名字）永不删；被删的长名仍可寻址（保留的短 key 以唯一子集命中 + 教学
  warning）。例：`[老家属院 家属院 老街坊 地下室]`。
- chain advance 钳到 horizon（他人 inflight + extras 在途 + 1 tick）。
  争用时链降级为每回合一个世界动作（后续调用被 busy 拒绝并教学）——
  这正是"世界等最慢的人"的语义。
- NPC 记忆回合跟进：npc + 零世界动作 + 无言语 + 用了 flashback/recall →
  恰一次 force_turn 补回合（把刚想起的答案发出去）。
- text 增加 wait_response（默认 true）+ 引擎自动等待（与 speak 同路径）。

## Gates (test_historical_failures)
- T1a test_deliberation_pins_the_world_clock：1.5s 决策在途时，任何事件
  不得晚于 wake+1tick（v4 协议 stub —— `__call__`，非 decide；此前两版
  手工复现 stub 用错协议跑在 legacy 错误路径上，结论无效）。
- T1b/T1c test_text_auto_wait_and_npc_reply_followup：text → 妈妈
  flashback → 跟进回合 → text back → 陈默收到。
- 308 passed / 1 skipped; seed_lint OK; dry_run 达终点。

## Live proof (litellm :4000, 07:00→08:30)
- 129 turns（84 MC + 45 NPC），0 标记泄漏，20 个拒绝全部为合法教学。
- 全部回合的首次调用提交延迟最大 **+1 分钟**（旧轨迹 7:35→7:40 = +5）。
- 陈默妈 6 个回合（此前 1 个就永久停摆）。
