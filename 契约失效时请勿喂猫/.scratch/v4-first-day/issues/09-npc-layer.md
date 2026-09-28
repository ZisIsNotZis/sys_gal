# Ticket 09: 两层演员制引擎（NPC / 匿名路人）

Status: done
Need-review: true（行为变更：调度语义 + 新动作 ask_stranger + 事件 kinds）

## Issue

实现 V4-CAST.md（MC/NPC/匿名路人两层演员制）：NPC 事件驱动不占时钟调度；
四类唤醒触发器 + 冷清检测 + 唤醒预算；简报构造（绝不携带 MC 私有内容）；
NPC 滚动记忆有界；ask_stranger 对话期生命周期的匿名路人（地点路人池 +
weight/rarity 抽样 + 会话内记忆 + 结束销毁，生成/销毁走事件日志保 replay）。

## Acceptance criteria

- [x] role 字段（mc|npc|extra）贯穿 kernel/loader/checkpoint/restore/trace
- [x] NPC 永不被时钟轮询；四类唤醒触发器各有测试（点名/排程 target/
      同地 abandon 涟漪/冷清检测每沉默期一次）
- [x] 唤醒预算（默认 12/模拟小时）
- [x] 简报构造器结构上无 MC 私有内容（public_mc_digest 白名单事件种类 +
      断言测试：MC goals/inner 标记不出现在 NPC 上下文）
- [x] NPC 滚动记忆有界（默认 12 条，checkpoint 经 session snapshot 保存）
- [x] ask_stranger：affordance + schema + kernel 事件 + 路人池 weight 抽样
      + 多轮会话内记忆 + 伙伴离开/闲置超时/路人自己离开三种销毁路径 +
      extra_arrived/extra_removed 事件（replay 可重建）
- [x] world_primer 增加路人常识；trace 回合打 role 标记
- [x] 全套测试绿；dry_run/mock_run 到达 22:00；mock run 中 NPC 被导演节拍
      唤醒（班长/宿管阿姨 role=npc 回合入 trace）

## Knowhow learned

- runner 的 stop_at 检查在轮询之前：pending 唤醒必须发生在边界之前才会被
  处理；测试的心跳事件要放在 stop 之前。
- kernel 的 speak 原本只对 whisper 记录 to；normal 的点名信息现在也记录
  （可见性不变），供唤醒/起哄使用。
- checkpoint 恢复断言放宽：允许 checkpoint 里有 base 世界之外的 role=extra
  行（对话期生命周期的 extras 必须能过 checkpoint）。

## Comments

- 2026-09-07 agent (worker, pi, gpt-5.6-luna): 按 PO 修订实现对话期生命
  周期与 weight 抽样。导演笔记按与 seed worker 的契约从角色 md 第五段
  `## 导演笔记` 提取（load_character 剥离正文人设、捕获进
  CharacterSeed.director_notes，NpcAgent 优先用 seed 携带值）。
- 2026-09-07 agent (worker, pi, gpt-5.6-luna): 全套 243 tests OK
  （232 旧 + 11 新 test_npc_layer，1 skip 为 v3 锚点 scenario 测试）；
  dry_run/mock_run 到达 22:00。
- 2026-09-07 agent (worker, pi, gpt-5.6-luna): 越界发现并已修复的连带项
  （seed worker ticket 10 转交清单 + 6 个并发半成品失败）：ask_stranger
  schema、loader/view/runner 断言 3→10、route gate 跳过 remote 地点、
  historical gate 措辞对齐 v4 kernel（"不是一个你知道的地方/从男生宿舍
  可以到"）、morning_rush→breakfast_rush、known_contacts 地面真值、
  test_move 目标改中庭/女生宿舍（宿舍拆分后路由变化）。
- 2026-09-07 agent (worker, pi, gpt-5.6-luna): 与 seed worker 的遗留契约
  对齐完成：extras 池 {fragment, rarity, knowledge_notes, weight} 已按
  manifest 实际字段实现 weight 抽样；导演笔记读取已按 `## 导演笔记` 实现。
- 2026-09-07 agent (worker, pi, gpt-5.6-luna): 复活续跑收口：real_run 完成
  NPC 接线（role=npc → NpcAgent + 导演简报 context_provider + extra_call=
  provider）；全套 243 tests OK；dry_run/mock_run 冒烟通过（mock 中
  班长/宿管阿姨被导演节拍唤醒，role=npc 回合入 trace）。种子侧遗留缺口
  已清零（陈默家描述、route gate remote 跳过、6 个连带断言全部修复）。
