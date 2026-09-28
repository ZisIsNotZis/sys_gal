# Ticket 08: 世界包实体 id 全面中文化

Issue: V4-DESIGN §0——除 action/param 名（工具调用惯例，保持英文）外，
实体 id 一律中文，显示层不再出现"storm-ledger：# 2013年台风台账"并列。
以现有地点/物品的中文标题为准（union 实为"学生会办公室"，非"学生会"）。

Status: done

## 改名映射

- 角色：chen-mo→陈默、lin-yao→林瑶、tang-xiaolan→唐小岚
- 地点：dorm→宿舍、archive→校史档案室、union→**学生会办公室**、cafe→半坡咖啡馆、courtyard→中庭
- 文档：storm-ledger→2013年台风台账、original-export→导出原件、union-audit→学生会审计包、old-permit-form→2013年邻居许可证、editor-draft→校报草稿
- 物品：red-whistle→红色哨子、blank-paper→空白纸、cracked-mug→裂纹马克杯
- 文件改名 16 个（loader 以文件名 stem 为实体 id，manifest id 已全部同步，
  含 system.bound_actor、copy_material_items、inventory、known_contacts、
  items/documents 的 location、routes、barriers、scheduled.target）

## Comments

- 2026-09-04 agent (seed worker, parent harness): `load_world_pack().build_world()`
  通过；actors=['陈默','林瑶','唐小岚']，locations 全中文。world/ 内 grep
  旧英文 id 零残留。
- **移交引擎侧**：v4 harness 测试套件 39 项失败，全部因测试硬编码英文 id
  （如 test_loader 找 characters/chen-mo.md、test_runner 断言 actor=="chen-mo"）。
  loader 本身对中文 id 无任何问题——需引擎 worker/主会话把测试断言同步为
  中文 id（在我授权范围外，未动 harness）。
