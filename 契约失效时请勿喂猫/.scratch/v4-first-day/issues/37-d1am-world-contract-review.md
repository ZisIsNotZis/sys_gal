# 37 — 世界契约版首个半天：逐人审阅与重大缺陷停止点

Status: ready-for-agent
Need-review: yes
Need-test-cases: yes
Blocked by: 35-actionable-claim-coverage-gap.md, 36-d1-evidence-route-checker.md

## 工件与验证
v4 `runs/real-20260928T205206+0800-1345945-532332572.json` + 同名前缀 `.checkpoint.json`，从原始 seed 到 3/16 12:59，`stop_at_reached`；428 轮、1371 events、0 GM、3 System（extra_removed），HTTP 0、标记泄漏 0、错误轮次 18。`check_milestones.py --half d1-am`：登记缺失知晓 PASS、恋爱并肩 PASS、台账差异记录 FAIL。世界契约相关 v3 历史门 218 OK、v4 353 OK、seed lint OK、dry_run 达 seeded endpoint，审阅 diff 87a7157..bcc2983 经独立 reviewer 审核听觉隐私 P1/P2 修复为 OK with notes，文档 P2 已修。运行终点和测试不能替代故事有效性。

按用户要求以 github-copilot/gpt-6-luna 为 15 个实际出场 actor 各生成独立轨迹报告，输出 `/home/z/.pi/agent/sessions/--home-z-vibe-sys_gal--/subagent-artifacts/outputs/a5de2c89-b9bf-4194-a1fa-cb129ebf137d/reviews/d1-am-contracts/person-{0..14}.md`。每份先全数组精确筛 actor，核对预期轮数与首末，再抽早中晚、错误、角色感知、会话、世界与 GM/System。父代理复核原始事件后确认：陈默/林瑶/班长/室友/宿管/唐小岚及 extras 报告共同指出客观通知与可操作状态冲突；一些低轮次 extra 只能审其出现窗，不推断未发生的长期行为。

## 真实轨迹
陈默 07:23、07:28 亲读纸账与导出件，07:29 当面向在场林瑶和室友说出 22:05→23:30、呼入少一通、目击行消失；林瑶 07:31 接话称“这份台账差异”仍待核，因未登记和签到本缺失选择不擅翻，两人保持知识来源边界。10:00 学生会审计通知作为真实注册文档出现，林瑶/班长 10:12 亲读、陈默 10:41 读，能够区分 16:00 审计任务和申请任务，显示公共文档改造有效。但通知没给负责人/收件渠道。林瑶和室友前后找场地表/材料/收件人，12:30 未提交并坦承逾期；12:52 何同学口头说去拿纸笔，到 12:59 仍没有实际 item/give/place/write 事件，林瑶反复询问是否已拿到。宿管/辅导员/班长支持她但同样找不到正式提交路径。临时人物多数能说不知道，但只能 speak，口头“去拿/交材料”不等于世界动作。关系仍主要是谨慎协作，没有足够情感推进。

## 因果问题
- P1 **客观世界不自洽（issue 35）**：07:30/08:10 两次陈默定向通知声称签到本在门口桌上，manifest 未注册此 item/document 或 placement；陈默 `read(签到本)`、林瑶 `take(档案室登记本)`失败。通知是世界权威叙述，不是角色未经核实传闻；若预期失踪须如此表述。申请表/纸笔/正式收件路径同型欠建模。新 `actionable_refs` 只验证自愿声明的条目，没覆盖未声明的客观物件断言，故门全绿仍漏此类。
- P1 **合法信息路线被检查器误判（issue 36）**：两人都获取差异，林瑶是亲耳听到并标为待核，不亲读是符合规程的选择。硬锚点“两人都读两份”误把单一路径当通用事实；不能为了 PASS 诱导她违反登记规则。需以可见证据链判事实锚点，以“亲读/当面转述”作可选路线，另防上帝视角泄漏。
- P2 **承诺/动作间断裂**：何同学说拿纸笔而没有实体交付；食堂大妈说装餐未见交易动作；多人寻找官方渠道的发言无法创造收件事件。应模型可见地提醒未兑现承诺，世界同时给合法取得/交付动作，不由引擎强迫履约。抽象剧情事实与物理小道具要分层建模。
- 已修好的点：未知收件人错误拒绝不再改发他人；本次没有 note_left/note_read，不能据此声称新字条规则在真实 run 得到验证（确定性测试已覆盖）；extra 数量为 5，未见上一段大规模重置问候的同型症状，但短时段仍不能证明长程稳定。

## 下一步与停车
**不续上午 checkpoint 之后的下午段，也不把此工件当健康 Demo。** 先建立客观具体物件声明的强制覆盖门（不依赖作者自愿列 `actionable_refs`），把签到本改成真实对象/状态或将通知准确写成“本应在、今天未见”；给场地申请一条可操作的表/文具/正式收件或有界拒收路径，并校对 deadline；修路线网检查器用人物实际可见信息。重新跑完整 v3/v4 预门、dry_run，重新从种子跑半天，再逐人审阅。原工件和 checkpoint 保留做因果对照。当前本地 LiteLLM 代理已主动关闭。

- 2026-09-28, pi：这是用户授权的“下一个重大缺陷/总结报告”停止点；所有 15 名实际出场人物的审阅结果已收齐并与世界事件核对。

- 2026-09-29, /worker（AREA A+B）：世界完备性覆盖门与种子修复已提交在
  `fix/v4-world-contracts`；issue 36（差异锚点路线网检查器）与
  V4-STORY-MILESTONES 属 AREA C，不在本次改动。全量 v3/v4 预门、seed lint、
  dry_run 均绿。

- 2026-09-29, /worker（AREA C）：issue 36 的差异锚点路线网检查器已实现并提交
  在同一 `fix/v4-world-contracts` 分支（AREA A+B 之后）。`_d1_discrepancy_recorded`
  改为“亲读互证 或 当面传达并被承认待核”，差异值必须由已读者说出、另一主角
  须实际听到；`harness/tests/test_milestones.py` 13 项 failing-first 回归（旧
  检查器 5 红）。问题工件 `real-20260928T205206…json` 的 `--half d1-am` 三项
  全绿。V4-STORY-MILESTONES §2.1/第 1 天已同步。
