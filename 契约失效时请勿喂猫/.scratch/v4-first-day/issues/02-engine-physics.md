# 02 engine-physics：全地点可见性 + whisper/normal + 中断 + 1 tick + 最小接口 + 变化驱动观察

Status: done

## Acceptance criteria
- 同地点角色感知全部公共事件；document_read 内容仅读者可见（隐私线）；他人 wait/sleep 不产生事件
- speak volume：whisper 仅 to 指定的在场者听见（ stranger whisper 可疑由人设常识承担）；normal 全地点
- 中断：interrupt 列表（仅同地生效）挂起可中断动作，目标下一轮 continue_action/abandon_action；
  uninterruptable 角色自声明（sleep 默认 true）；取消记 action_abandoned(failed)
- 消息延迟 1 tick=300s；move{target} 时长由地图算（无 duration_seconds 参数）；wait 自由数值有上限
- 观察：首次到达/observe 动作/同地每 N 回合（默认 6）给完整描述+knowledge，期间只推变化事件

## Comments
- 2026-09-04 worker: kernel.py 重写 _visibility（隐私线+co_located 辅助）、_hearing_actors（whisper/normal）、
  submit 中断处理（_apply_interrupts/_resume/_abandon，_cancelled 集合+checkpoint 序列化）、
  _duration（move 地图时长、wait 上限、message 300s、中文拒绝语全量翻译）、poll 观察模型
  （observed_locations/rounds_since_observation/observe_request）、affordances（observe/continue/abandon、
  通用 wait、move 无时长）。action_schema.py 更新 v4 形状。新增 V4PhysicsTests 11 项覆盖。
  证据：229 tests OK（含 historical gates F2/F5/I02 更新到 v4 语义）。
