# 03 engine-trace：会话分段 + 私有状态有界去重回显 + inner/遥测入 trace

Status: done

## Acceptance criteria
- compaction 边界记录 turn id（compacted_memories[].turn_id + Trace.compactions）
- 私有状态回显去重（同文本坍缩）+ 每节上限（默认 20，丢最旧）
- inner 与别名遥测入 trace（inner 标 private；Trace.record_alias_telemetry 聚合计数）

## Comments
- 2026-09-04 worker: character_session._compaction_turn_id 在 decide() 入口捕获并写入压缩记忆条目；
  compaction 请求与记忆前缀中文化；agent_state.bounded_state_snapshot() 去重+封顶，用于
  initialization 与每轮回显；trace.py 新增 alias_telemetry/record_compaction/record_alias_telemetry，
  record_agent 记录 inner+private。恢复路径（restore_checkpoint）补 observation_refresh_rounds。
  证据：229 tests OK。遗留：agent_view 的分段视图未消费 Trace.compactions（属 ticket 05 展示层）。
