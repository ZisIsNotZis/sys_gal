# 69 — 2026-10-06 的 d1-pm 半成品 run 被中断且未按协议复盘

Status: wontfix
Need-review: yes
Need-test-cases: no

## 现象与工件

2026-10-06 10:20 由 `v4/scripts/drive_arc.sh` 启动的 d1-pm 重跑（模型
`github_copilot/gpt-6-luna`）留下：

- `v4/runs/real-20261006T102015+0800-1122910-443283035.json`（21 MB，`outcome=null`，
  1688 agent turns、4616 world events；末条世界事件时间 `2026-03-16T18:34:00+08:00`）
- 同名前缀 `.checkpoint.json`（28 MB）
- `v4/logs/drive.log` 只有 `[10-06 10:20:12] ... driver start` 与 `[d1-pm] ...`
  启动行，**没有 reached-endpoint / gate / STOP 行**；工件 mtime 10:58 后无写入，
  当前无进程在跑。

即：这是一次**未完成、未过门、未复盘**的 d1-pm 运行。它既不是有效样本，
也不能当作代码回归证据。

## 为什么必须处理

根 `AGENTS.md` 规定：**每次 provider-backed 运行后必须人工检查保存的轨迹**，
以具体行为与因果问题报告，不得用计数或 clean/failed 标签代替。此 run 违反了
该义务至今。它也可能携带 D1 下午缺陷的新证据（例如 FAIL 锚点的表现）。

## 验收方向

1. 按 `AGENTS.md` 的运行后分析格式产出报告（进入票据 Comments 或独立文档）：
   实际经历了什么（具体早/中/晚/失败边界回合）、观察到的问题及根因、修复方向、
   以及该 run 作为故事实验是否有用。
2. 明确它为何中断（进程被杀 / 上游 429 / 宿主关机 / 脚本自身），依据日志与
   工件时间戳，不臆测。
3. 决定工件去留：保留为诊断样本并标注"半成品"，或按需清理（不得删除仍在
   引用的证据）。
4. 若发现新的 D1 缺陷，转成独立票据或并入 issue 70 的根因清单。

## Comments

### 2026-10-16 — 工件丢失核实；declared missing；复盘义务转由 M1.4/M1.5 承担（agent）

**复行核实证据（2026-10-16，本机）**：

- `find /home/z/vibe/sys_gal -type d -name runs` → 无命中：`v4/` 下已无 `runs/` 目录（`ls v4/` 仅 checkpoints/docs/harness/logs/scripts/world）。
- `find /home/z/vibe/sys_gal \( -name 'real-20261005*' -o -name 'real-20261006*' -o -name 'd1-pm*' \)` → 无命中：本票引用的 `real-20261006T102015…` 工件与 checkpoint、以及 10-05 完整工件 `real-20261005T005934…`，均不在磁盘上。
- `ls v4/logs/` → 仅 `gate-d1-pm.txt`；本票引用的 `v4/logs/drive.log` 亦已不存在。
- `ls v4/checkpoints/` → 仅 `d1-am.json`（14,323,341 B，mtime 2026-10-16 08:24）；无 d1-pm checkpoint、无 archive。
- git：仓库仅一个快照提交 `ea47781`（2026-10-15 15:21:48 +0800，"Record v4 work state and ignore interrupted run outputs"），提交信息自述 d1-pm checkpoint 与 driver 启动日志"on disk but ignored"（未纳入版本控制）——其后工件从磁盘被删，无法从版本历史找回。

**声明**：10-05 完整工件与 10-06 中断工件均为 **declared missing**，本票要求的运行后分析对象已不存在，不可复盘。

**处置**：复盘义务不消失，转由 **M1.4**（从 `checkpoints/d1-am.json` 或原始种子重跑 d1-pm，产出唯一新工件 + `checkpoints/d1-pm.json`）与 **M1.5**（对新工件的运行后分析，含中断/失败边界检查）承担。相应地，本票原本可能携带的 D1 下午缺陷新证据改由 issue 70 的根因报告（`reports/70-d1pm-anchor-root-causes.md`）以静态证据补足——该报告已注明哪些判断因轨迹丢失而"不可建立"。

**Status 改为 wontfix 的理由**：复盘对象（工件）已丢失且不可再生，本票的原始诉求无法执行；这是对象消失，不是放弃复盘义务——义务已显式转至 M1.4/M1.5。`Need-review: yes` 保留，供独立复核本 Comments 的证据与处置。
