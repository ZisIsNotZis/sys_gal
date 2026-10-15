# 40 — `known_to` 被当作可用性授权：harness 会建议角色远程读没接触过的东西

Status: fixed
Need-review: yes
Need-test-cases: yes

## 复现与证据

`kernel._entity_available`（`harness/kernel.py:1252`）把三种语义揉成一个 bool：

```python
return (entity_id in actor.inventory
        or self.item_locations.get(entity_id) == actor.location
        or actor_id in self.entity_access.get(entity_id, set()))   # 即 known_to
```

`entity_access` 就是 manifest 的 `known_to`（`world_loader.py:151`）。于是 `known_to`
同时意味着"我听说过它"和"我在任何地方都能读它"，而 `_available_documents` 用它生成
建议列表。

本run尚未真正越界（13 次成功读全部符合"在手/在现场"），但 harness **主动递出了梯子**：
turn 305 陈默在食堂，建议清单里出现 `read 移交存根`（该文档在档案室，他并不持有）。
只要模型照建议执行，就会拿到一件它从未接触的文档的正文——**由 harness 引导的越界读**。

已知 `known_to` 被用于 11 个实体（含 `借阅登记本`、`移交存根`、`场地申请表`、`值班簿`
等剧情关键件），因此这不是边角。

## 根因

"知晓"与"可取用"是两种权限，被 `_entity_available` 合并；`read`/建议共用它。
设计文档只要求"能读手边的"，没有把"知道存在"当作物理可得。

## 验收方向

1. 拆开两个概念：`aware_of(entity)`（可提及、可回忆、可在建议里"你知道有这么一份东西"）
   与 `available_now(actor, entity)`（在手上或在现场）。`read` 只认后者。
2. 建议列表只列 `available_now` 为真的目标；若想让角色去取，就给 `move`/`take` 路线建议，
   不要给一个会越界成功的 read。
3. 回归（先红后绿）：`known_to` 含某人、但人不在场的实体，`read` 必须被拒；`take` 必须被拒；
   建议列表里不得出现它。加一条断言：任何给出的 read 建议执行后都成功且不产生越界读。
4. 复核 manifest 里 `known_to` 的语义注释，避免"知道"被继续读成"有权读"。
