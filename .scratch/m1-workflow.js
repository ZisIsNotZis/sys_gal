const root = args.root, v4 = args.v4, scratch = args.scratch;
const common = `你是《契约失效时请勿喂猫》v4 叙事实验仓库的子代理。仓库根：${root}（cwd）。先读：${root}/AGENTS.md（运行协议）、${root}/契约失效时请勿喂猫/ROADMAP.md 的 M1 节、相关票据。语言：中文。环境：Python 3.14.8；LiteLLM 代理已在 localhost:4000，模型 github_copilot/gpt-6-luna，无需鉴权。只做契约内工作，越界即停并上报。`;

const [fix, analysis] = await runs.all([
  {
    key: "fix",
    label: "Fix unpicklable counters (py3.14 gate)",
    agent: "worker",
    task: `${common}
【目标】修复 v4 引擎在 Python 3.14 下的门禁红：replay/checkpoint 路径 deepcopy 世界时抛 TypeError: cannot pickle 'itertools.count' object（已实测复现：python3 -c "import copy,itertools; copy.deepcopy(itertools.count(1))"）。受影响计数器：${v4}/harness/kernel.py:278-283 与 452-453（_sequence/_event_id/_history_id，state 键 next_sequence/next_event_id 等）、${v4}/harness/kb.py:416 与 800（_shown_seq，state 键 shown_seq）。
【步骤】1) 先在当前代码上运行失败测试确认红：python3 -m unittest harness.tests.test_kernel.WorldTests.test_give_replay_preserves_inventory_transfer。2) 用可 pickle 的等价计数器替换 itertools.count（小类：__init__/__next__/next/__iter__/__getstate__/__setstate__，或 int 字段），保持行为单调、保持已序列化检查点的 state 键与格式完全兼容——绝不改 state 模式，旧检查点 checkpoints/d1-am.json 必须照常加载。3) 全套回归绿：cd ${v4} && OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s harness/tests -p 'test_*.py'（预期 571 tests OK skipped=1；当前 errors=9：test_multihop_event_sequence_and_visibility、test_launch_checkpoint_is_a_valid_loadable_trace、test_kernel WorldTests 5 项、test_world_pack DocumentInteractionTests 2 项——全部须转绿）。4) python3 scripts/seed_lint.py → OK。5) 新建票据 ${scratch}/issues/71-py314-counters-unpicklable.md：记录环境变更（机器 Python 升至 3.14.8，2026-10-13 曾全绿）、根因、红→绿证据（原 errors=9 → OK）、修复形态与兼容性说明；Status: fixed，Need-review: yes。只在 ${scratch}/issues/71-*.md 与 ${v4}/harness/（含如需要的新增断言）写文件；绝不碰 .scratch 其它文件、world/、docs/。
【验收】套件绿 + lint OK + 票据落盘。报告：改动文件清单、红绿证据命令与输出摘要。`,
  },
  {
    key: "analyze",
    label: "Root-cause 6 FAIL anchors; record artifact loss",
    agent: "worker",
    task: `${common}
【只读边界】对 ${v4}/ 代码、种子、日志只读；可写文件仅限：${scratch}/issues/69-oct6-interrupted-d1pm-run-unreviewed.md、${scratch}/issues/70-d1pm-six-anchors-unmet.md（各自追加 ## Comments、更新顶部 Status 行）、以及新建 ${scratch}/reports/70-d1pm-anchor-root-causes.md（reports/ 目录不存在则创建）。不得改任何其它文件。
【背景事实（已核实，直接引用）】v4/runs/ 目录与 checkpoints/d1-pm.json 已不在磁盘上（全盘 find 无 real-20261005*/real-20261006* 工件）；仓库只有一个初始快照提交 ea47781（2026-10-15，commit 信息称工件留在盘上但被 ignore），其后工件被删除。幸存证据：${v4}/logs/gate-d1-pm.txt（10-05 run 1605 回合的完整门禁读数）、ROADMAP/issues 的记录。
【任务 A（issue 70 主体）】对 6 个 FAIL 锚点逐项做根因归类（种子/引擎/提示/provider 四选一，可主因+次因），给出代码或种子证据（引用文件:行），并给具体修法（改哪个文件的什么）。锚点：d1-辅导员介入、d1-三份个人说明、d1-老周托话、d1-妈妈承诺、d1-审计催办转达、林瑶自查审计包。方法：读 gate-d1-pm.txt 全文 → 读 scripts/check_milestones.py 中这 6 个锚点的判定模式 → 追溯每条模式依赖的可执行路径（谁被排程唤醒、有没有道具/可发言通道/概念注册）→ 读 world/ 种子里对应排程与道具 → 结论"机制没给路径"还是"角色没走到"。票据提示的相邻线索（issue 48/49/57/63/65/66）逐条核对并写明是否仍适用。证据缺失处（原轨迹工件已丢）显式标注"不可建立"，不得臆测。产出：reports/70-d1pm-anchor-root-causes.md（逐项：根因层级、证据、修法、置信度）+ ticket 70 Comments 摘要。
【任务 B（issue 69 收口）】把上述工件丢失事实（含你复行的 find/ls 证据）记入 Comments，声明：该工件不可复盘（declared missing），复盘义务转由 M1.4 新工件 + M1.5 运行后分析承担；Status 行改为 wontfix 并写明理由（工件丢失，非放弃复盘义务）。报告里单独一节。`,
  },
]);

return { fix: { ok: fix.ok, summary: fix.result }, analysis: { ok: analysis.ok, summary: analysis.result } };
