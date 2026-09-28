# 28 — 房间字条只供下一位进入者独见

Status: ready-for-agent
Need-review: yes
Need-test-cases: yes
Blocked by: 27-d1am-gpt6-trajectory-review.md（发现来源）

## 缺陷与验收
用户裁定：`leave_note` 产生房间留言属性，不是物品；**下一位进入房间的人**即时看到全文且留言销毁；想保留可重新留言。当前 `kernel.py` 在 `leave_note` 完成时向所有同场者发 `note_read`，`_consume_notes` 再将整个 readers 列表放进一次事件；3/16 12:34 林瑶的留言同时给六名读者，违背一次一人和“下一位进入者”。

修复方向：仅在确实发生 `enter` 时按事件顺序把房间内留言交给该进入者，清空已读留言并提示阅后即焚；同场者不可凭留言广播获知全文。若产品另有“放下时现场旁观者也能看”语义，需先与用户裁定对齐，不可静默采用当前群发。测试至少含多人同场留条、第一与第二进入者、连续多条、作者重留、checkpoint/replay、隐私投递。

- 2026-09-28, pi：源自 `real-20260928T111220+0800-336652-774700642.json` note_read readers 多人实例。暂停续跑。
