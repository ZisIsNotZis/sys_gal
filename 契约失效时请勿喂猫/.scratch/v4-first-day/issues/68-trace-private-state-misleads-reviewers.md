# 68 — 轨迹里的 `private_state.memories` 恒为空，误导复盘者判"记忆写入丢失"

Status: ready-for-agent
Need-review: yes
Need-test-cases: yes

## 现象（2026-10-01 第二次对照跑，多条 reviewer 报告）
- 唐小岚的复盘者据 `private_state.memories` 全程 `[]`，判定 **P1「update_memory 报成功但静默丢写」**，
  并推断"checkpoint 后关键记忆会丢"。
- 陈默等角色的复盘者也多次记下 `memories: []`。
- **实为误判**：v4 的记忆落在**引擎侧 KB**（`runner.kb[actor].rows`）。该 run 检查点里唐小岚的 KB 有
  **38 行**，其中包含她运行中写的 `["!always","校报草稿"]` 等真实条目；`update_memory` 的 5 次调用
  返回 `submitted`、`memory_rejections: []`，写入确实成功。
- 也就是说：`private_state.memories` 是**遗留字段**，v4 不再使用，却在轨迹里保持为空且无任何说明。

## 影响
复盘者（人）与 reviewer（子代理）都会据它得出**错误的 P1**，浪费排查并可能引发错误修复；
这类"轨迹字段与实际存储不一致"的问题会持续污染审阅质量。

## 验收方向
1. **消歧**（三选一，说明理由并加测试）：
   - 让轨迹里的 `private_state` 反映真实KB（导出该角色当前的 KB 行/摘要）；或
   - 明确把 `memories` 从轨迹里移除/标为 deprecated；或
   - 在轨迹与文档里显式标注"记忆在 engine KB（`runner.kb`），本字段为空是正常"。
2. **文档**：`docs/V4-AGENT-INTERFACE.md` / `V4-ENGINE.md` 写清"记忆事实存放位置"，避免下一轮 reviewer 再误判。
3. **检查器**：可加一项"KB 行数 vs private_state.memories"的一致性读数（review-only），
   让人一眼看出"空的是遗留字段，不是丢写"。
4. 回归（先红后绿）：断言"写入 update_memory 后，轨迹/检查点里能查到该行"（用现有 KB 路径），
   并断言复盘可见的字段不再自相矛盾。
