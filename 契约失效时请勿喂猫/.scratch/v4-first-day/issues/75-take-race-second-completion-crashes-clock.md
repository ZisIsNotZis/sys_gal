# 75 — 同刻双人 take 竞态：第二笔完成 delete 已消失物品击穿世界时钟（E75）

Status: fixed
Need-review: yes
Need-test-cases: yes

> 2026-10-16 M1.4 运行中发现并按 AGENTS.md 中断续跑方法论就地修复（先红后绿）。
> 边界：`harness/kernel.py` `_complete` take 分支守卫 + `test_historical_failures.py`
> E75 回归 + 本票；未动种子、判定层与其它引擎路径。

## 现象（活体证据，run real-20261016T192137+0800-376758-587639572）

d1-pm 段（从新 d1-am 检查点续跑）于世界时 16:07 崩溃，`real_run` rc=1，
traceback 终点 `harness/kernel.py:1634`：

```
item = str(payload["item"]); a.inventory.add(item); del self.item_locations[item]
KeyError: '可用纸笔'
```

事件链（工件 `runs/real-20261016T192137….json`，error.log 同目录存档）：

- #2540 16:06 林瑶室友 `take 可用纸笔`（action_started）
- #2543 16:06 李学姐 `take 可用纸笔`（同一 tick；两人都在学生会办公室，且都在
  响应辅导员"用桌上的纸笔写下"的指令——两次提交均在物品在场时通过 submit 校验）
- #2545 16:07 林瑶室友完成 → inventory.add + `del item_locations['可用纸笔']`
- #2547 16:07 李学姐完成 → `del` 第二次 → **KeyError，时钟死亡**

## 根因

`World._complete` 的 take 分支无完成时守卫：同刻排队的两笔同物品 take（提交时
校验各自合法，竞态不可避免）先后完成时，第二笔对已消失物品做无条件
`del item_locations[item]`。同函数内 despawned-extra 的 move/text 分支早有同类
防御（"the event stands, nothing mutates"），take 分支是缺口。

## 修复（先红后绿）

1. 红：`test_take_race_second_completion_does_not_crash_the_clock`（E75，合成
   世界 a/b 同室同刻 take 同一物品）——修复前同点位同 `KeyError: '纸笔'`。
2. 绿：`kernel.py` `_complete` take 分支加守卫——物品已不在 `item_locations`
   时，完成事件照常立案（advance 先 commit 事件后调 `_complete`），不改任何
   状态（第二人扑空，抽屉已空）。
3. 定向复验：E75 单测 OK；`test_kernel` 74 tests OK。

## 全量套件观察（绑定本修复的工作树）

`OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover` →
`Ran 576 tests in 221.904s — FAILED (failures=1, skipped=1)`；唯一红为
`test_silent_abandonment_auto_continues_pending_action`（单跑 OK、模块 31 tests
合跑 OK、不含 take 路径，与守卫无语义交集）——即票 72 首遍归因、票 73 §6.1
预言的第二个负载敏感 flake 的第二次捕获，完整输出存档
`v4/logs/full-suite-20261016-run5-576tests.log`，续记见票 73 Comments。

## 残留（移交分诊，本票未动）

- `place` 分支存在对称风险（`a.inventory.remove(item)` 对已不在背包的物品会以
  同型 KeyError 击穿时钟；观测到 0 例，未守卫、未加测试）。
- 完成时守卫是"事件立案、不变更状态"的最小语义；第二 taker 的行动结果反馈
  （她只知道行动"完成"了）是否需要显式"扑空"告知，属 agent-view 层决策，
  未展开。
