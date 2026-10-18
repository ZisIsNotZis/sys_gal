# M1.3 第二轮种子改动独立复核报告（m1-dot3-round2-review）

> 本文件由独立复核代理产出、经运行时代为落盘（该代理无写文件工具）。
> 复核代理会话：/home/z/.pi/agent/sessions/--home-z-vibe-sys_gal--/subagent-artifacts/6458b801-8098-4648-bf1c-32d0a452c0f5_reviewer_output.md

- 复核人：独立复核代理（fresh context，不修复、不提交）
- 日期：2026-10-16
- 对象：第一轮复核（`reports/m1-dot3-review.md`）之后的新增改动——`v4/world/manifest.yml` 五处（audit_pack_review 面核通知措辞、archive-keeper 常驻行、陈默托付钩子行、陈默妈知识行、各处 ticket 76 注记）、`world/characters/辅导员.md` 知识注记，及权威票据 `issues/76-d1pm-two-anchors-round2.md`
- 方法与边界：工作树未提交 diff 为两轮叠加（基线 `ea47781` 之后未再提交），逐 hunk 按票据 72/76 的记载与文件内注记归属两轮；定向实读 `scripts/check_milestones.py` 判定函数、两份 gate 工件、`V4-STORY-MILESTONES.md`、attempt1 存档目录与测试文件 diff 交叉验证。只读。

## Review — 总体 verdict：**PASS-with-notes**

本轮种子改动本身无 P0/P1 缺陷；五处措辞全部为"知识行/程序话术"，无台词化、无判定层触碰、来源全部有据。发现 **1 项 P1**（票 76 下轮建议与既有夹具 E72b 直接冲突——不阻塞本改动集，但必须在下轮实施该建议前先修订夹具）。

### 焦点 1：措辞"铺台阶而无剧本台词"——PASS（5/5 干净）
面核通知补句（规程陈述）、archive-keeper 保管规矩行（:1455）、陈默托付钩子（"可以托她……"许可式，attempt3 证其自主）、陈默妈认领规矩（条件式，attempt3 她"没问到"自述未被逐字复读——恰证是台阶）、辅导员知识注记。无新增直接引语。

### 焦点 2：措辞来源合法——PASS（4/4 有据）
辅导员（基线既有"当年坐过档案室角落"私设）；陈默妈（角色页既有分寸落进可检索行）；archive-keeper（规矩本人，am 窗 08:32 林瑶逐字引用先例）；面核通知（文书/规程引用先例同 `audit_relay_task`）。

### 焦点 3：判定层零触碰——PASS（实核）
`check_milestones.py`、`seed_lint.py` 不在改动集；判定函数计的是角色发言，attempt3 实测 13:34 陈默"不补写"先于 16:20 事件自主说出（出处 keeper 常驻知识行）。

### 焦点 4：排程敏感度记录——PASS，附 1 条 P2
逐轮通过组合漂移被如实记录（含对己不利回归），gate 工件逐项对拢；三类变异已命名（字序/名词/时段）。P2-2：未把"单轮 PASS 不构成稳定收敛证据"上升为显式系统结论。

### 焦点 5：两残留项性质认定——PASS（均准确，源码+工件双证）
"没问到 vs 问不到"＝措辞化石/字面失配，非行为缺失（行为链两要件齐备）；"林瑶 am 读/pm 窗"＝窗口设计+动线错过，非路径缺失。

## 缺陷清单

- **P0：无。P2 以下种子措辞问题：无。**
- **P1-1**：票 76 下轮建议（面核通知显式 target 四学生 / 16:10 对林瑶定向提醒）任一都会使第一轮夹具 `test_speech_anchor_requires_a_scheduled_occasion`（E72b：pm 窗含"审计包"的排程行须 `all(not target)`）变红。最小修法：实施前由 harness 所有者先按先红后绿修订夹具语义（允许 target 包含涉事学生、仅禁收窄排除），否则会出现无法归因的红测试或临场放宽夹具、静默丢掉"场合不得收窄"保护。
- **P2**：① 票 76 缺并行改动归属声明（+1 测试=票 75 E75；账目 571+2+2+1=576、130+2+1=133 已对拢）；② 敏感度口径未成文（"单轮 PASS 不作稳定收敛证据"）；③ M1.5 溯源义务须扩展覆盖本轮五处新词的活体言语出处；④ "常驻自述行"选项是更陡台阶，采纳前宜先走 needle 放宽裁决；⑤ E75 台账行"林瑶室发"→"林瑶室友"笔误；⑥ 建议后续轮次随票存当轮 diff 工件。

## 非阻塞备注
1. 被删 `checkpoints/d1-am.json` 已保全于 `runs/archive-20261016-attempt1/`（fail-loud 删除合规）。
2. 针词 SSOT 出处实核成立（V4-STORY-MILESTONES.md:67/:86）。
3. pm 非门禁区系统健康项（41/1776 错误轮、update_memory 失败 7、未注册具名物件 93 等）移交 M1.5/运行分析层（M1.5 报告已覆盖三族不可解循环）。
4. 第一轮 P2-1（mom_evening_call 直接引语）维持原状。
5. 角色页 hunk 归属为票据引用推定（已标注）。

## 待监督者复跑的机械检查（2026-10-16 已复跑，结果）
- seed_lint：**OK**（仅既有 advisory，无新增）
- 历史门：第一遍 **FAILED (failures=1)**——身份已捕获 = `test_extra_turns_are_recorded_and_conversational`（07:02≠07:01，票据 73 §6.1 已立案的 extra 时序间歇家族当日第二次复现，非本改动集缺陷，完整输出 /tmp/hist.log）；该家族此前多次全绿（含 576 全量两遍绿）
- 全量 discover：**Ran 576 tests — OK (skipped=1)**（297s，日志 logs/full-suite-20261016-run5.log）
- test_world_pack：**Ran 66 tests — OK**

## 结论
**PASS-with-notes**。放行下一轮的唯一前提：先修订 E72b 夹具语义（P1-1），再实施票 76 任一条定向建议；其余为记录完善与 M1.5 溯源义务，不阻塞。
