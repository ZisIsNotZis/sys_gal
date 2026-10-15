# 50 — extra 的检查点状态不完整：续跑时有活 extra 会 KeyError

Status: fixed
Need-review: yes
Need-test-cases: yes

## 复现与证据（代码级，已核实）

- 生成时 extra 的字典含全部运行时字段（`engine.py:1475-1491`）：`fragment`、`knowledge_notes`、
  `partner`、`last_active`、`rarity`、`start`、`context_cursor`、`pending_question`、
  `pending_heard_speech`、`system_prompt`。
- 但 `AsyncEngine.checkpoint_state()`（`engine.py:1624-1633`）只存
  `fragment / knowledge_notes / partner / last_active / rarity / start`，**漏掉
  `context_cursor` / `pending_question` / `pending_heard_speech` / `system_prompt`**。
- `_extra_turn`（`engine.py:1551`）读的是 `system = str(info["system_prompt"])`，**不在 try 里**。
  ⇒ 从一个"场上有活 extra"的检查点恢复后，该 extra 的循环抛 KeyError 直接死掉；
  `context_cursor`/`pending_question` 缺失还会让它复述窗口与待答问题错位。

## 为什么优先
本项目的检查点续跑是常规流程（半天分段：d1-am → d1-pm 从 `checkpoints/d1-am.json` 续）。
旧工件 d1-am 在 12:59 存档时场上就有活着的 extra（韩大叔 12:18 进店），因此**下一次续跑就会踩中**。
这不是本 lane 引入的回归，但属于"会打断运行"的类别，必须在重跑前修掉。

## 验收方向
1. `checkpoint_state` 持久化 extra 的全部可变字段；`restore` 完整重建（`system_prompt` 允许持久化，
   也允许由 `fragment`/`knowledge_notes`/地点/名字重建——二选一，但要确定且可测）。
2. `_extra_turn` 不得因缺字段抛异常：缺 `system_prompt` 时用重建兜底（**旧格式检查点向后兼容**），
   缺 `context_cursor`/`pending_question` 时给安全缺省。
3. 回归（先红后绿）：
   - 生成 extra → `checkpoint_state()` → 新引擎 `restore` → 该 extra 的回合仍能正常产出（无 KeyError）；
   - 待答问题与复述游标在往返后保持；
   - 喂一个**旧格式**检查点（缺 `system_prompt` 等字段）→ 断言重建而非抛错。
4. 历史失败登记进 `v4/harness/tests/test_historical_failures.py`。
