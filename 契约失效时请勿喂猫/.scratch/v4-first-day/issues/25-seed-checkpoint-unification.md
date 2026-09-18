# 25 — 种子与 Checkpoint 合一：历史入日志、检查点含全部状态

Status: done (1aa999b; business review PASS by independent subagent)

## 架构裁决（用户 2026-09-16）

1. **历史 ≠ 记忆，两套东西**：
   - **历史（History）**= 世界事件日志，真实、只追加、包含**前史**。2013 台风夜
     不是 concept 散文，而是日志里真实的事件条目（真实 2013 时间戳）。
     闪回=重放该角色可见的日志历史——前史与运行时事件无差别。
   - **记忆（Memory/KB）**= 角色可主动更新的**最新状态**（现在理解/相信什么），
     不是历史流水。update_memory 语义不变。
2. **Checkpoint 包含复现所需的全部信息**：世界状态、事件日志（含前史）、
   每角色 KB、每角色 session（含 system 消息）、**每角色的系统提示词与工具
   表快照**、meta（git hash / 编译来源 / 时间）。改了代码里的提示词也能从旧
   checkpoint 复现（数据级精确 + 代码版本标注）。
3. **种子 = 编译出的初始 checkpoint**。manifest + characters/*.md 仍是人写
   创作界面；加载器把种子**编译**成 v4-checkpoint-2 格式的初始检查点；引擎
   只读检查点。一条状态加载路径。
4. manifest 保留**唯一新增创作段**：`history:` —— 前史真事件列表（真实
   2013 时间戳、kind、actor、payload、visible_to）。

## 实现要求

### A. manifest `history:` 段 + 编译
- `world/manifest.yml` 新增顶层 `history:` 列表。用现有种子事实把 2013 台风夜
  编成 **10~15 条真事件**（时间 2013-03-16 晚真实时刻），至少覆盖：
  21:40 小学地下室进水电话；22:05 器材室借出两台抽水泵（经手人签名潦草）；
  23:30（导出件所载的借出时间）；地下室外老人目击（半句）；老赵头楼下喊人
  喊哑嗓子；家属院撤离；陈默（九岁）被带离的私有片段（visible_to=[陈默]，）
  红色哨子去向存疑的私有片段（visible_to=[陈默]）。
  visible_to 语义与运行时一致；历史公开事件默认 visible_to=当天在场的
  社区人群（可直接列角色 id 或全体）。
- 加载器把 `history:` 编译为事件日志的**最前段**（id 1..N，时间戳为 2013），
  所有 actor 的 cursor 初始化为 N（前史不是"新事件"，不重复投递；
  闪回扫描全日志不受 cursor 限制）。运行时事件 id 从 N+1 继续。

### B. Checkpoint v2（`v4-checkpoint-2`）
- 在现有 engine.checkpoint_state 之上补齐：
  - `history_count`（前史事件数，重放/校验用）；
  - `sessions`：每 actor 的 V4Session 快照（含 messages[0] 的 system 提示词）；
  - `prompts`：每 actor 的系统提示词字符串 + 工具表（`harness.action_schema.TOOLS`
    的当次快照）；
  - `meta`：git commit hash（subprocess 读取）、compiled_from（"manifest"或
    来源 checkpoint 路径）、created_at。
- `trace.checkpoint_snapshot` / engine.checkpoint_state / restore 全链路兼容；
  旧 `v3-trajectory-1` / 现行 v4 快照不要求向后可读（v4 尚未发布），但
  现有测试须全部更新并通过。

### C. 闪回统一
- `_flashback_query` 的历史来源改为**全日志可见事件扫描**（前史+运行时），
  删除"种子前史池"特殊来源；KB 行匹配仍为第一来源（记忆=最新状态）。
  `flashback_horizon_minutes` 只约束运行时事件段；前史（2013 时间戳）不受
  它限制。

### D. 编译入口
- `harness/seed.py`（或新 `harness/compile_seed.py`）提供
  `compile_initial_checkpoint() -> dict`（v4-checkpoint-2 形状）；
  real_run 启动时：编译 → 写 `runs/<runid>.seed-checkpoint.json` → 引擎从
  该 checkpoint 初始化（复用现有 restore 路径）。`--day`/resume 流程不变。

### E. 测试
- 前史编译：history 事件数/时间戳/可见性正确；actor cursor = N。
- 闪回：陈默 flashback 能从日志前史命中台风夜事件（如 老赵头/抽水泵），
  且不含不可见他人私有片段。
- checkpoint round-trip：编译→保存→恢复→再保存，事件与 KB 逐字段一致。
- sessions/prompts/tools 快照存在且恢复后不变。
- 全套现有测试更新后 **310+ 全绿**；`seed_lint` 不回归（history 段不参与
  标记检查，或参与——按现有 `[[ ]]` 规则处理并在 PR 说明选择）。

## 验收
- 真实短跑（V3_CLOCK_STOP=07:35）从编译 checkpoint 启动成功，日志可见
  前史事件；陈默 flashback 输出含 2013 前史行。
- 报告：改动文件清单、新 checkpoint 形状示例（截断）、测试输出。

## Business review (独立 subagent, 2026-09-17): PASS
- 前史忠实于种子事实（22:05 真相 vs 23:30 虚假时间的保留✓；13 年→陈默 22 岁✓）
- 闪回隐私无泄漏路径（可见性模型统一；唐小岚无法借闪回绕过台账线索）
- 复现性成立（runner 下 kb/sessions/prompts/tools/world 全捕获；漂移仅剩
  渲染函数/引擎行为，由 meta.git_hash 标注）
- history_log 独立日志（负 id）：导演/演员视角零损失
- 微调已应用：eye_witness 可见性 10 人 → [陈默, 林瑶]；`# #` 注释残留清理

## Day-3 续跑（resume schedule-merge 首战）
- merge 实现生效：3/18 四节拍全部触发（quest_washer 08:30 / admin_resolution
  09:40 / mom_son_visit 14:20 / matchmaking_reply 17:00）。
- 637 轮、15 错误、0 HTTP、0 泄漏；里程碑 4 项中 2 PASS（并肩核查✓ 相亲埋线✓），
  2 未达（抄件压力、登记本下落——当天剧本未推进到，路线网下记"未走到"）。
- 待查：outcome=None，19:31 后停止原因（疑似 merge 排程与 world_stops 22:00
  的处理顺序问题）——下轮诊断。

## Day-3/4 续跑（supersede 修复后，05392d8+012f3b3+8803c01）
- runs/real-20260918T105304+0800-3434691-154842870.json：merge+supersede 生效，
  3/19 六节拍全触发，至 22:00 world_stops 正常停止。
- 全程 0 HTTP 错误、0 泄漏；day-3/day-4 锚点全部达成（路线网判定：有效路线）。
- 亮点：猫/哨套场景（19:01 林瑶"只记录时间位置外观，不联系不拿不移动不翻看"
  → 辅导员/下棋大爷各自视角复述）——程序严谨性格 + 社区信息传播双在线。
- 待办：3/20 排程（管理员 W 返岗、王爷爷儿子讨说法、相亲前夜）；天台戏的
  人工审阅（REVIEW 项）。
