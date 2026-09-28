# 28 — 房间字条只供下一位进入者独见

Status: ready-for-human
Need-review: yes
Need-test-cases: yes
Blocked by: 27-d1am-gpt6-trajectory-review.md（发现来源）

## 缺陷与验收
用户裁定：`leave_note` 产生房间留言属性，不是物品；**下一位进入房间的人**即时看到全文且留言销毁；想保留可重新留言。当前 `kernel.py` 在 `leave_note` 完成时向所有同场者发 `note_read`，`_consume_notes` 再将整个 readers 列表放进一次事件；3/16 12:34 林瑶的留言同时给六名读者，违背一次一人和“下一位进入者”。

修复方向：仅在确实发生 `enter` 时按事件顺序把房间内留言交给该进入者，清空已读留言并提示阅后即焚；同场者不可凭留言广播获知全文。若产品另有“放下时现场旁观者也能看”语义，需先与用户裁定对齐，不可静默采用当前群发。测试至少含多人同场留条、第一与第二进入者、连续多条、作者重留、checkpoint/replay、隐私投递。

- 2026-09-28, pi：源自 `real-20260928T111220+0800-336652-774700642.json` note_read readers 多人实例。暂停续跑。

## Comments

- 2026-09-28, pi：修复只在 enter 事件上交付：写条时不再消费留言，同场 actor 的 `action_started` / `action_completed` / `note_left` perception 隐去正文；单一进入者收到并销毁该地点的全部待留留言。相同时间的多个 enter 按事件队列顺序只交付给第一个。更新了 V4 接口文档与 leave_note 工具说明；回归覆盖同场保密、作者重留多条、同刻多人进入、checkpoint/resume 与 replay。v4 全套 323 OK（1 skipped）、seed lint OK、dry_run 到 3/27 21:30；v3 历史套件 218 OK。未运行 provider story；等待独立 review 与 parent final acceptance。
