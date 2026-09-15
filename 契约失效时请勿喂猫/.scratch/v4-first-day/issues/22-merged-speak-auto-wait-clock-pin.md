# 22 — T6 裁决：合并 speak、自动等待、对话钉钟（live-run 用户裁决）

Status: done

## User rulings (2026-09-15)
1. KB 行标签 `+N` 缩写废除：LLM 无法展开缩写，全部 key 逐字显示
   （种子审计：322/323 行 key 归一化后无重叠，唯一重复是陈默妈联系人行把
   林瑶写成自己的别名——已修，`_make_row` 现按归一化形式去重）。
2. `ask` 废除，并入 `speak`：`to` 必填（在场的名字，容错解析——"大爷"唯一
   命中"下棋大爷"；或 `["陌生人"]` 向路人搭话）；volume=normal 全场可闻、
   whisper 仅 to 名单；纯文本仍是全场广播（T1）。
3. 自动等待默认开：说完带 to 的话自动原地等 ~2 tick，回应（wake-class）
   提前叫醒；`wait_response=false` 跳过。控制权回来时回应要么已听到、
   要么明确"没有人接话"。
4. 对话钉住世界时钟：路人回应在途时（墙钟延迟）时钟钉在问题时刻、最多
   前进 1 tick——墙钟延迟不再兑换成世界时间快进（旧轨迹里回应曾迟 17 个
   世界分钟；7:12 的 ask 7:16 才回来）。
5. 路人在**话音落地那一 tick**（说话动作的完成时刻）才出现——`extra_arrived`
   与"话被听到"同时刻；从不在提交时刻。
6. NPC 环境唤醒：附近发生 wake-class 事件（说话/进入/给物/拿放东西）即唤醒
   在场 NPC，按人设自由反应——通常什么都不做，但可以管闲事（例：有人拿了
   属于该地点的东西）。预算照旧。
7. 串行链写入文档与提示词：同消息多调用按序执行、各自计时、后者看到前者
   之后的世界。

## Live-run driven fixes (same ticket)
- 严格网关（github_copilot）拒绝无 call_id 的 tool 消息 → HTTP 400 风暴
  （33 个死回合）。修复：自动等待教学语折进 speak 调用自身的 tool 结果；
  truncated/endpoint 弃用调用逐个出具真实 id 的结果；引擎为缺 id 的调用
  合成 id。另修 `calls.index(call)` 对相同调用永远命中首个的 bug（enumerate）。
- KB 模糊命中的 warning 渲染 Python list repr（`[['!always','x']]`）——形似
  `[[ ]]` 标记泄漏；改为空格连接的干净渲染（英文机制错误保留）。

## Gates
- test_extra_turns_are_recorded_and_conversational 更新至 merged speak 协议
  并新增时序断言：路人在 ask 完成tick（07:01）出现、回应 ≤1 tick 落地。
- test_render_lists_every_key_fully（全 key 渲染 + 归一化去重）、
  test_solo_speak_when_nobody_present（solo 也可 to=["陌生人"]）、
  truncation 测试改按逐调用结果断言。
- 306 passed / 1 skipped; seed_lint OK; dry_run 达终点。

## Live proof (litellm :4000, gpt-5.6-luna, 07:00→08:10)
- 41 turns（27 MC + 14 NPC），1 个错误（合法拒绝：对不在场的林瑶 speak），
  0 标记泄漏。宿管阿姨以人设连续对答；林瑶室友环境唤醒后主动加入对话并
  陪同林瑶去档案室；陈默独立完成台账线并在 08:00 与林瑶交换 22:05/23:30
  矛盾——多方自然对话首次成型。
