# v4 首验日（one-day slice）Spec

目标：V4-DESIGN §6 的首次验证 run —— 1 个模拟日、tick=1min、3 个角色
（唐小岚/陈默/林瑶）、只有第一天的审计事件。通过线：每人 ≥2 次共处对话、
唐小岚至少传递一条跨无关配对的秘密、零无内容读取循环。

设计真理：`v4/docs/V4-ENGINE.md`（引擎时序/并发 SSOT）+ `v4/docs/V4-DESIGN.md`
（产品与物理）+ `v4/docs/V4-AGENT-INTERFACE.md`（接口与常数）+
`v4/docs/V4-GOSSIP-CHARACTER.md`（角色）。
语言：内容层全中文，协议层（动作名/参数/id）保持 ASCII；中文文本里直接用
中文名（陈默），不写"陈默 (Chen Mo)"式并列。

## Tickets

- 01-engine-immersive: 中文系统提示 + 沉浸叙事 + inner 字段 + 宽松解析 +
  别名遥测 + 无接受回执（引擎 MVP 核心）
- 02-engine-physics: 全地点可见性 + whisper/normal + 中断语义 + 1 tick 消息
  延迟 + 最小动作接口（move{target} 时长自算、wait{duration}、observe）+
  变化驱动观察
- 03-engine-trace: 会话分段入 trace（compaction 边界记 turn id）+ 私有状态
  有界去重回显 + inner/别名遥测入 trace
- 04-seed-pack: 中文世界包（manifest/3 角色/地点/文档/一日事件）
- 05-integration: dry run + mock run 全绿 + 首验 run 启动

优先级：01 → 02/04（可并行）→ 03 → 05。
