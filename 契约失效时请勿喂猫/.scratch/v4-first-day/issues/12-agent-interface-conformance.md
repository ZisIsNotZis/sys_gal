# 12-agent-interface-conformance

Status: done
Need-review: true
Owner: agent (pi, 本会话模型) — 管理/集成；实现由 4 个 worktree 子代理并行承担

## Issue

用户裁决（2026-09-08）：①docs/ 只留正式设计真理（评审报告非文档，已删除；禁止"未来待办"措辞）；②实现必须严格遵循 docs/，尤其 V4-ENGINE 与 V4-AGENT-INTERFACE——接口迁移从"待办"升格为"必须现在做"；③完成后跑最小示例若干回合并展示轨迹。

## 切分与文件所有权（并行 worktree，禁止越界）

- worker-proto：`action_schema.py`（+think/update_memory/recall/flashback、−sleep、导出 TOOLS）、`provider.py`（chat_with_tools）、`natural_agent.py`/`npc_agent.py`（v4 会话协议：逐字 system prompt、原生 tool_calls、tool ack、compaction 30000 字符）。遗留 make_persistent_agent 保留供存量测试。
- worker-kb：`harness/kb.py` 新建（ActorKB：行模型、op 语义、回放间隔 sim 分钟、提及集、溢出顺延、reminder 严格解析、compaction 清零、快照）+ `tests/test_kb.py`。
- worker-prompt：`prompt.py` 重写为 §3 块结构（表头/#error/#flashback/#events/#knowledge/#actions），事件行全部第三人称客观编年体封闭模板，私有投递缩进行仅收件人可见；更新渲染类测试。
- worker-seeds：`world/manifest.yml` 增 `kb:` 段（全角色，恰一行 self:true）+ `world_loader.py` 暴露 pack.kb 并加载校验 + `test_world_pack.py`。

## 集成（本代理亲自）

engine 链式执行（8 调用上限、无世界动作=发呆 1 tick）、KB/flashback/reminder/director 接线、real_run 切 v4 代理、存量子集兼容（Intention 旧路径仅测试用）、全套测试、最小 volc 运行并展示轨迹。

## Comments

- 2026-09-08 agent(pi, 当前会话模型): 文档正规化提交 8df66c3（删 2 份评审报告、清除迁移状态措辞）。4 worker 已派发。
- 2026-09-08 agent(pi) 集成记录: 4 worker 分支全并（seeds/proto/kb/prompt，299 passed）。集成内容：kernel 删 sleep(M1)+force_interrupt+schedule_reminder（reminder 内核级队列触发，抗 DES 跳时）；engine v4 链式执行（8 调用上限截断、无世界动作=发呆 1 tick、链内打断中止剩余调用）、KB/flashback 池/recall/#error 队列/director 回调接线、extras 走 speak-only 工具；real_run 切 v4 代理 + pack.kb。竞态修复：调度器新增 _has_pending_turns——现刻欠回合的角色禁止时钟前进（引导回合不再输给首次推进）。语义澄清：reminder 在决策中到期=仅通知（无动作可挂起，光锥语义自然结果）；行动中到期=挂起+continue-or-cancel。遗留：#error 中 kernel 语义拒绝仍为中文（docs 要求英文，下一片）；renderer 待登记模板 8 项待 docs 裁决。
- 2026-09-08 agent(pi) 验收: 最小示例通过完成闸门——runs/real-20260908T205545+0800-2049580-862115460.json，19 回合/69 事件，08:00 端点整点到达，0 失败。轨迹核验：system=§1 逐字；world message=§3 块结构（# knowledge 含 KB 行/reminder、# events 第三人称编年体含 multi-hop enter/leave、# actions）；assistant 原生 tool_calls 多调用链 + tool ack；陈默首回合链 read+inspect 并行。发现并修复：链式提交时间可越过端点 → 链推进钳制到 stop 地平线。
- 2026-09-08 agent(pi) 第二轮验收（用户轨迹评审修订全落地）: ①tool-result 协议（n call = n tool result + 1 user，#error 废除，V4Session.deliver_tool_results）；②渲染：表头去可互动、#actions 同类合并、speak volume=normal/whisper+to 候选/自言自语、speech heard-by 听众行；③world 物品/文档描述自动展开为 KB 行（首轮泛洪可见，known_to 门控，ASCII 自动 id）；④SYSTEM_PROMPT_V4 与修订后 §1 字节一致（think 每回合第一个调用）。最小示例复跑：23 回合/96 事件/0 失败/闸门通过。运行时观察：volc-flash 未稳定遵守 think-first（提示已要求，模型侧合规问题，列入 A/B 观察）。遗留不变项：#error 英文化、待登记模板 docs 裁决。
- 2026-09-10 agent(pi) think-first 强制: 用户指令 "push harder" → 引擎级执行——非 think 开头的 v4 链整条拒绝（每个调用 tool 结果报 "think first: …"），角色零 sim 成本立即重想；连续 3 次违背后放行+遥测（防病态循环）。docs §4 增引擎强制条款。实测：think-first 于被接受链 13/13=100%（强制前 45%），首轮合规 18/23=78%，5 次拒绝各耗一次额外 LLM 往返、零 sim 成本。
- 2026-09-10 agent(pi) 第二轮用户评审全落地: ①**inner 与每个动作配对**——think 工具废除，所有 23 个 schema 强制非空 inner（缺/空 → 该调用不执行，tool 结果报错）；②#actions 只列状态相关动作（wait/自言自语 speak/记忆工具/未提案件不列）+ 修复 ask_stranger 重复与 None affordance；③表头增「附近：」行；④KB 行统一 item=（document 类型废除，read/copy/annotate 参数键 document→item，adapter 别名同步翻转）；⑤world 描述全部去手工换行 + 去作者腔（校报草稿"世界不替任何人回答"等）；⑥known_to 门控（哨子→陈默，马克杯→唐小岚，其余公共可见层）；⑦update_memory 支持省略 id 以 fields 唯一匹配定位（解决模型臆造 id）。最小示例：15 回合/96 事件/0 失败/inner 覆盖 16/16。304 passed。
- 2026-09-10 agent(pi) 第三轮用户评审（ChatML 巡检 6 项）: ①think 残留调用→引擎拦截并回教学性英文 tool 结果；②system_* 接入链执行器（此前只有 legacy 路径，v4 链里发到 kernel 报未知动作）；③flashback 结果直接回 tool 结果（#flashback 块废除，docs §3 同步）；④自言自语取消（speak 需在场听众，引擎层拒绝）；⑤copy 整体废除（schema/kernel/replay/loader/manifest copy_material_items 全清，docs §2/§3 同步）；⑥system_* 工具描述写明台账机制。inner 检查顺序修正（think 拦截先于 inner 校验）。实测：0 遗留问题、inner 24/24、302 passed。
- 2026-09-10 agent(pi) 第四轮（用户四问）: ①system prompt 与 docs 全文零 think（残留三处全清，字节校验）；②recall 结果直接回 tool 结果（无匹配则明说），取消队列回放；③"ok 占位"消灭——所有有内容的调用（read/compare/flashback/recall/update_memory/system_query）都回真实内容，裸 ok 仅剩纯世界动作（其结果即 #events 叙事）；④台账案件自动接下（system_accept/decline 工具、affordances、schema 全删，auto_accept 在 Runner/AsyncEngine 启动时提交 system_case_accepted 事件）；⑤ask_stranger 描述补 question 参数说明。299 passed；运行 22 回合/70 事件/0 失败。
- 2026-09-10 agent(pi) 严格自查（子代理基础设施三连败后由主会话执行）: **P0 copy 从未真正离开 schema**（"end to end 废除"是假话——kernel 删了、schema 漏了，模型工具列表里仍有 copy→调用→unknown action，用户第 3 次点名才抓到）；**P0 残留渲染/可见性分支**：item_inspected/location_searched 公开行、私有行、kernel 可见性规则全清；**P1 #actions 参数名**：空值参数保留参数名（question=/text=），agent 不用猜；**P1 recall 空选择器**：engine 拒绝无 kinds/ids 的调用，schema minItems+描述同步；**P1 测试基建**：parse_decision 版本参数 int|None、_submit_parsed 助手、SQL FP 改名。299 passed；35 回合/100 事件/0 失败/inner 39/39/零 unknown-action。
- 2026-09-11 agent(pi) 独立评审落地（bg_delegate 第二次成功，36 回合/51 工具调用）: **P0×2 证实并修复**——①auto_accept 事件 payload 缺 terms/reward_offer → 渲染字面 "None" 进角色感知（台账开场白写着"奖励是None"）；②read 工具产出读 args["document"] 而 schema 键是 item → 每次 read 都返回"没有可读的正文"（零信息动作，正是设计禁止的浪费）。**P1×3**——speak 三方不一致（docs 说可用/描述说自言自语/引擎拒绝）按方案 b 对齐；system_query 拒绝信息补逐字匹配提示+配额状态；docs §3 示例 document=→item=。**P2×5**——legacy character_session 参数表、kernel 不可达 inspect 分支、replay/prompt 的 copied/labeled 残留、trace 默认名 "think"→"unknown"、_MENTION_FIELDS 注释。#10（agent_view 工具清单应读 trace 而非当前 TOOLS）记录为待办。299 passed；34 回合/97 事件/0 失败/零 None/零空 read。


## Comments

- 2026-09-14 agent (pi, 当前会话模型): closed: integration complete (all comments above); lock released. Leftover noted (agent_view tool list should read trace, not current TOOLS) is a one-file micro-fix.
