# 01 engine-immersive：中文系统提示 + 沉浸叙事 + inner + 宽松解析 + 别名遥测 + 无接受回执

Status: done

## Acceptance criteria
- 系统提示为中文，inner 在动作 JSON 示例中永远第一，协议指令压缩在末尾
- inner：第一人称心声，世界不读、他人不可见、入 trace（标记 private）、超长截断
- 宽松解析（单引号/尾逗号/True/None/全角标点），LLM judge 只留接口
- 参数别名命中即执行并计数（adapter.alias_telemetry），不静默
- 接受的动作零回执；拒绝/失败保留中文即时纠正消息

## Comments
- 2026-09-04 worker (claude/gpt fork, v4 engine): character_session.py 系统提示/初始化/纠正消息全部中文化，
  inner 前置写入提示；adapter.py 新增 WIRE_KEYS/ARG_ALIASES/TOPLEVEL_ALIASES、_tolerant_loads、
  _single_quote_strings、load_model_json（strict→tolerant→judge 接口）、alias_telemetry；
  runner.py _result_message 中文化且 submitted 返回空串（无回执）；Intention 增加 inner/interrupt/uninterruptable；
  trace.record_agent 记录 inner + private 标记。新增测试：V4PhysicsTests（test_kernel.py）+
  test_character_session 全套改 v4 语义。证据：229 tests OK。
