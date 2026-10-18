const root = args.root, v4 = args.v4, scratch = args.scratch;
const common = `你是《契约失效时请勿喂猫》v4 叙事实验仓库的子代理。仓库根：${root}（cwd）。先读：${root}/AGENTS.md、${root}/契约失效时请勿喂猫/ROADMAP.md 的 M1 节。语言：中文。Python 3.14.8。只做契约内工作，越界即停并上报。`;

const [seedfix, flake] = await runs.all([
  {
    key: "seedfix",
    label: "Fix 6 anchor root causes in seed",
    agent: "worker",
    task: `${common}
【目标】M1.3：落地 ticket 70 六个 FAIL 锚点的种子层修复。权威输入：${scratch}/reports/70-d1pm-anchor-root-causes.md（先通读全文）与 ${scratch}/issues/70-d1pm-six-anchors-unmet.md。
【边界】只允许写 world/ 种子层文件（manifest.yml、角色页等）与新建票据 ${scratch}/issues/72-d1pm-seed-fixes.md。绝不改 harness/、scripts/check_milestones.py、docs/ 的任何文件——门禁判定层一律不碰；needle 措辞不匹配（涌现措辞化石）只能靠改种子侧措辞对齐，并在票据里逐条登记（含原措辞/新措辞/对应锚点）。
【要求】按报告逐项实施 6 个锚点的修法（审计催办转达优先）：给机制补路径（排程、道具落点/ target、知识注记、共同在场、D1 收集说明的排程、D2 跨日预设矛盾的对齐），遵循既有种子风格与"里程碑是下限不是剧本"的原则——铺时机与台阶，不写剧本台词。改完必须：1) cd ${v4} && python3 scripts/seed_lint.py 全绿（新具名 token 全部登记）；2) OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s harness/tests -p 'test_*.py'，记录结果（已知存在一个与本改动无关的 discover 顺序失败 test_extra_turns_are_recorded_and_conversational，另一代理在修；只要它失败且历史门全绿即可，如实记录）；3) 明确判定并写入票据：每处修复影响 D1 上午事件与否——据此判断从 checkpoints/d1-am.json 续跑是否安全，给出 M1.4 起点（原始种子 vs d1-am 检查点）与理由；若种子改动使 d1-am 检查点失配（加载报错或排程状态冲突），显式声明。4) 票据 72 记录：逐锚点改动、file:line 证据、lint/回归输出、M1.4 起点判定；Status: fixed，Need-review: yes。
【验收】lint 绿 + 历史门绿 + 票据落盘 + M1.4 起点判定明确。报告：改动清单与验证摘要。`,
  },
  {
    key: "flake",
    label: "Fix discover-order test flake",
    agent: "worker",
    task: `${common}
【目标】修复 ${v4}/harness/tests/test_historical_failures.py（或其依赖模块）中 test_extra_turns_are_recorded_and_conversational 的 discover 全量顺序依赖失败：单独跑、随模块跑、与前 6 个模块合跑均绿，全量 discover 下 failures=1（1≠2，异步时序/导入副作用）。已确认与 py3.14 计数器修复无关（stash 后基线同样失败）。
【步骤】1) 复现：OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s harness/tests -p 'test_*.py' 2>&1 | tail；用 -k 或二分模块组合定位最小触发组合。2) 判根因（模块导入副作用 / 事件循环残留 / 全局状态泄漏 / 时间敏感断言），做最小修复——优先修测试隔离（如剥离全局状态、显式关闭 loop、避免真实 asyncio 时序），不改产品行为语义。3) 验证：全量 discover 连续两遍全绿（573+ tests, OK skipped≥1），并单独跑一次确认未破坏。4) 新建票据 ${scratch}/issues/73-discover-order-flake-extra-turns.md：根因、最小触发组合、修复、两遍全绿证据；Status: fixed，Need-review: yes。
【边界】只写 harness/tests/ 与该票据；不动 harness 产品代码语义、world/、docs/、其它票据。
【验收】两遍全量 discover 全绿 + 票据落盘。报告：根因与证据。`,
  },
]);

const review = await runs.run({
  key: "review",
  label: "Independent review of M1.3 changeset",
  agent: "reviewer",
  task: `${common}
【角色】独立复核（fresh context，不做修复，不提交）。对象：当前未提交工作树相对基线 ea47781 的 scoped diff，含三部分：A) py3.14 计数器修复（harness/kernel.py、kb.py、tests，票据 71）；B) 六锚点种子修复（world/，票据 72 + 报告 reports/70-d1pm-anchor-root-causes.md）；C) discover 顺序 flake 修复（harness/tests，票据 73）。
【方法】git -C ${root} diff 与 status 看 scoped 改动；核对各票据声称的验收证据（你必须亲自重跑机械检查并给出命令与结果）：1) cd ${v4} && python3 scripts/seed_lint.py；2) OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s harness/tests -p 'test_*.py'（期望全绿）；3) 抽查票据 72 的 M1.4 起点判定是否有证据支撑（d1-am 检查点在新种子下能否加载/续跑）。语义审查重点：计数器替换是否严格保持 state 序列化语义与单调性；种子修复是否只铺机制路径而无剧本台词、是否触碰门禁判定层（不允许）；措辞对齐是否只改种子侧。
【产出】结构化结论：整体 verdict（PASS / PASS-with-notes / FAIL），逐部分判定，缺陷清单（每条：位置、违反的准则、证据），非阻塞备注。写入 ${scratch}/reports/m1-dot3-review.md 并在最终文本给出结论。
【边界】只读代码 + 可写上述报告文件；不改其它任何文件。预算：≤40 次工具调用；超过即按当前证据出结论并注明未覆盖项。`,
});

return {
  seedfix: { ok: seedfix.ok, summary: seedfix.result },
  flake: { ok: flake.ok, summary: flake.result },
  review: { ok: review.ok, verdict: review.result },
};
