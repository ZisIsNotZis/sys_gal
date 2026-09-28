# Ticket 07: 引擎中文沉浸收口（system 合并 / 描述 M 轮 / 压缩禁令 / inner 遥测）

Status: done

## Issue

首验日审阅反馈（V4-DESIGN 首验日反馈 #3/#4/#5）：
- A. 身份在 user 初始化里、system 只有规则，且缺世界常识（地点/连通/耗时/tick/分寸）；
- B. 描述每 N=6 回合随全量观察重放，太频繁；应与状态刷新解耦（N=20 / M=99999，压缩重置）；
- C. 压缩提示词会把场景/物品固定信息写进记忆——应禁止（世界会自动重放）；
- D. inner 缺失无任何检测——需遥测 + 每角色一次性提醒（不硬拒绝）；
- 渲染：agent_view/prompt 的描述块内部空行导致条目归属含混。

## Acceptance criteria

- [x] A：身份+私人起点+私人状态+世界常识（world_primer，从 manifest 自动生成）全部
      在 system 消息；_initialization 缩为「第一天开始了。」
- [x] B：kernel 两层计数——state_refresh_rounds=20（knowledge/布局）、
      description_refresh_rounds=99999（描述）；首到/observe/notify_compaction 强制全量；
      两计数器均入 checkpoint/restore；manifest engine 键可覆盖
- [x] C：压缩请求新增「场景、物品、地点布局这类固定信息不要写进记忆——世界会在需要时
      自动重放它们；记忆只保留个人的想法、情绪、关系变化、承诺与未解之事」
- [x] D：runner 记 missing-inner 计数入 trace（{"kind":"inner_telemetry","missing":n}）；
      每角色一次性中文提醒经 record_world_result 通道送达；不拒绝动作
- [x] agent_view --history 与 prompt.py 实时路径：描述块去内部空行/去 markdown 标题行、
      条目之间空一行（共享 _clean_description）
- [x] 测试全绿：232 tests OK (skipped=1)；dry_run/mock_run 到达 22:00

## Comments

- 2026-09-04 agent (pi, gpt-5.6-luna)：
  - 改动：character_session.py（A/C/compaction flag）、world_loader.py（world_primer + N/M
    manifest 覆盖）、kernel.py（B 两层计数 + notify_compaction + checkpoint/restore 字段）、
    natural_agent.py（world_primer 透传 + consume_compaction）、real_run.py（primer 接线）、
    runner.py（D + compaction 接线 + 上一轮的 updates 移除）、trace.py
    （record_compaction 签名改 (actor, turn_id)）、agent_view.py/prompt.py（渲染修复）、
    system.py（Ledger bound_actor 默认值陈默——种子中文化连带）。
  - 种子 worker 已把全部实体 id 中文化（陈默/宿舍/2013年台风台账…），测试文件中 11 个文件的
    英文实体引用已全部对齐中文 id（sed 映射 + 手工修正）。
  - 新增测试：system prompt 含身份/常识（test_system_prompt_carries_identity_state_and_world_primer）、
    描述 M 轮策略（test_descriptions_ride_a_much_slower_counter_than_state）、压缩禁令+consume
    旗标（test_compaction_prompt_tells_model_to_skip_scene_facts_and_sets_flag）、inner 遥测+一次性
    提醒（test_missing_inner_is_counted_and_reminded_once）、world_primer 内容
    （test_world_primer_describes_places_routes_and_time_rules）。
  - 命令与结果：python3 -m unittest discover -s harness/tests -p 'test_*.py' → Ran 232, OK；
    dry_run/mock_run → 22:00 到达。
  - Park：无。
