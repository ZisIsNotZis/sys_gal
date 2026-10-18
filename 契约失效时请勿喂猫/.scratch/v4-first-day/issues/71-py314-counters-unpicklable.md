# 71 — Python 3.14 下 `itertools.count` 不可 pickle，replay/checkpoint 路径 deepcopy 世界即炸

Status: fixed
Need-review: yes
Need-test-cases: yes

## 环境变更（根因的触发条件）
- 机器 Python 升至 **3.14.8**（2026-10-13 全套曾绿于旧解释器）。3.14 取消了
  `itertools.count` 的 pickle 支持，`copy.deepcopy` 随之失效：
  `python3 -c "import copy,itertools; copy.deepcopy(itertools.count(1))"` →
  `TypeError: cannot pickle 'itertools.count' object`（本机已实测复现）。

## 现象与根因
- 受影响计数器（世界/KB 内部状态，均被 deepcopy 覆盖）：
  - `v4/harness/kernel.py` `World._sequence/_event_id`（state 键 `next_sequence`/`next_event_id`）
    与 `_history_id`（负向步进，正史 id 空间）；
  - `v4/harness/kb.py` `ActorKB._shown_seq`（state 键 `shown_seq`）。
- 触发路径：`replay.py::replay_world` 对初始世界 `deepcopy`；launch trace、checkpoint
  续跑等所有复制世界/KB 状态的路径同样命中。
- 套件红：全套 discover 报 **errors=9**（`test_multihop_event_sequence_and_visibility`、
  `test_launch_checkpoint_is_a_valid_loadable_trace`、test_kernel `WorldTests` 5 项、
  test_world_pack `DocumentInteractionTests` 2 项），定向跑
  `test_kernel.WorldTests.test_give_replay_preserves_inventory_transfer` 也以同一 TypeError 报错。

## 修复形态
- 新增 `kernel.Count`：`itertools.count` 的可 pickle 等价小类
  （`__init__/__next__/__iter__/__getstate__/__setstate__`，`__slots__`，int 起点与步进），
  行为单调：`next()` 依次返回 start、start+step、…；`Count(-1, -1)` 保持正史负 id 空间。
- 替换 6 处构造点（kernel 3+2、kb 1+1），调用点（`next(...)`）零改动；两文件的
  `import itertools` 随之移除。
- **state 模式零改动**：`checkpoint_state()` 仍写 `next_sequence`/`next_event_id`，
  `snapshot()` 仍写 `shown_seq`（均为"下一个值"的 int）；恢复端以
  `Count(int(...))` 播种，语义与 `itertools.count(int(...))` 完全一致。

## 红→绿证据
- 红（修复前，3.14.8）：
  `python3 -m unittest harness.tests.test_kernel.WorldTests.test_give_replay_preserves_inventory_transfer`
  → `TypeError: cannot pickle 'itertools.count' object`；全套 `Ran 571 tests … FAILED (errors=9, skipped=1)`。
- 绿（修复后）：
  - 定向：上述测试 + 新增回归
    `WorldTests.test_world_deepcopy_survives_and_event_ids_stay_unique`、
    `PersistenceTests.test_deepcopy_keeps_shown_seq_allocating` → OK；
    原红 9 项定向复跑（MultiHopMoveTests / launch_checkpoint / DocumentInteractionTests / WorldTests 60 项）→ OK。
  - 全套：`OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s harness/tests -p 'test_*.py'`
    → `Ran 573 tests … FAILED (failures=1, skipped=1)`，**errors 9→0**。
    （新增 2 个回归测试故 571→573。）
- 兼容性实测：`checkpoints/d1-am.json` 经 `load_checkpoint` + `pack.build_world()`
  + `world.restore_checkpoint()` 照常加载（now=2026-03-16T12:59:00+08:00，
  events=1962、queue=83），计数器精确从 `next_sequence=1136`/`next_event_id=1963` 续排；
  正史 id 从 -12 续排（seed 11 条正史已消费）；KB 快照恢复后 `shown_seq` 计数器原位
  （陈默 502 / 林瑶 527 / 唐小岚 327）。
- lint：`python3 scripts/seed_lint.py` → `seed lint OK`（仅供人判断的 warning，exit 0）。

## 残留（非本票据范围，需另行处置）
- 全套 discover 恒定存在 **1 个 failures**：`test_extra_turns_are_recorded_and_conversational`
  （`len(extra_turns)` 1 != 2）。已证实**先于本修复存在**：stash 本修复后在基线上全套复跑同样
  `failures=1, errors=9`；该测试单独跑、随 test_historical_failures 模块跑、与前 6 个字母序模块
  合跑均绿——为套件级顺序/导入副作用或异步时序依赖，与本票据的计数器修复无关。
  建议另开票据定位 discover 全量加载下的污染源。

## 回归防再发
- 台账 `test_historical_failures.py` 新增条目 **E71**，指向上述两个 deepcopy 回归测试；
  大跑前门禁套件已覆盖该失效模式。
