# 14: 接口激进简化——工具面/inner/#actions/台账 NPC 化

Status: needs-info（等用户裁决）
Labels: needs-triage, decision
来源：用户 2026-09-11 巡检，八点意见 + "tools are kind of inferable, maybe no actions at all"。

## 逐点裁决建议

1. **compare 删除**——同意。模型 read 两份后上下文里已知差异，compare 的增量只有"世界盖章"，实测大半是刷的废回合。删除后"发现被改"靠种子内容本身（导出件时间戳 vs 纸质页写法）+ 模型推理，编年体少一行但少了假动作。
2. **copy 维持删除**——用户确认无用例；分享内容= read 后口头转述或把原件递过去。
3. **drop 语义澄清**——现语义就是"放在当前地点"（item_locations[loc]，他人可拿），不是丢弃。改名为 **place**（放到这里）消歧义；give（递给人）与 place（放在此地）两 op 并存。
4. **annotate 删除**——写在世界物品上供后来者读，实测剧情不需要 actor 版本（种子批注是内容不是工具）；私人笔记有 update_memory。document_defs 的 annotations 机制保留（种子内容），工具删除。
5. **邻居许可证改名**——内容层问题。"2013年邻居许可证"语义不通。候选：2013年邻里撤离通知书 / 2013年邻里互助协议 / 2013年洪灾互助凭证。需要用户选或另起。
6. **台账 → 超自然 NPC**——同意，这是最优雅的一步。system_query 工具删除；台账成为一个具名超自然 NPC（复用 extras/NPC 机制 + 严格 director 简报：只准答事实表内条目、次数上限、答不了就说我不知道）。逐字匹配抽奖消失，问句泄漏问题消解为世界内对话（它答"这个我不知道"本身就是世界观）。事实上 docs 本来就写着 "A constrained supernatural participant"——现在把它做成真的。
7. **ask_stranger → ask，恒可用**——改名搭话；不再按地点 extras 池门控：没有路人时世界现场生成一个（extras 机制已有销毁语义）。
8. **send_message → text**——改名发短信，描述明确"手机短信、无视距离、1 tick 送达"。
9. **#actions 整块删除**——同意，这是最大胆也最自洽的一步：动作空间是静态知识（工具清单），实体是当前感知（表头在场/身上/附近）+ 信念（KB 地图行）。#actions 每回合枚举参数候选是冗余信息通道；删掉后世界消息 = 表头 + #events + #knowledge，token 大省。非法动作由引擎拒绝并教学（错误是可教的）。
10. **inner 废除 → 原生 reasoning(low) + 文本即说话**——同意，这是协议的根本简化：
    - inner 参数全删（schema/engine 校验/think 教学信息全清）；模型的原生思维链（reasoning=low）就是心声，trace 镜像 reasoning。
    - **模型输出的纯文本 = 当面说出的话**（volume normal）。对话不再是工具调用——写字就是说话，最自然的社交界面。whisper 等修饰仍走 speak 工具。
    - 附带收益：inner 合规性机器（检查/重试/遥测）全部消失；no-tool-call 回合不再"发呆"而是说话。

## 目标工具面（9 个）
wait, speak(仅 whisper 修饰用), text, move, take, place, give, read, knock, ask —— 记忆三件套 update_memory/recall/flashback 保留待议，open/close/compare/annotate/interact/system_* 删除。

## 风险
- 文本即说话的歧义（叙述意图 vs 说出的话）——system prompt 一句"你输出的文字就是你当面说出的"可教；错当说话的代价低（说了一句计划）。
- KB 地图信念行必须齐（move 无 #actions 提示后靠它）。
- 台账 NPC 化后 LLM 幻觉越界——严格 director 简报 + 次数上限硬计数。

## 决议
（全部待用户确认后实施；预计是一个大 slice：schema/kernel/engine/prompt/docs/种子全动）
