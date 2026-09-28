# 34 — 路人简报绕过封闭地点的声音投递屏障

Status: claimed
Need-review: yes
Need-test-cases: yes
Blocked by: 32-extra-empty-question-rebrief.md

## 缺陷
独立 GPT-6 Luna 评审发现：kernel 对封闭地点的 speech event 仅向说话者本人 `visible_to` 投递，但原 `payload.heard` 仍按同场人填充；新 extra 唤醒和 transcript 又信任 `heard`，从而让路人获知自己在 world event 里未被授权听见的私语。这是隐私/因果 P1，禁止 provider 长跑。

## 不变量与验收
`visible_to` 是事件投递唯一权威；speech 的 `heard` 必须与其可投递的其他听众一致。extra 唤醒/简报从 `visible_to` 判定，可兼容仅测试合成事件的 heard fallback，但不能由 co-location 或 payload 反向授予真实事件听觉。封闭地点 normal/whisper 双例、恶意不一致 heard/visible_to 双例必须拒绝路人上下文；开放地点该听到的定向/广播保持可见。docs §3 模板和 extras 契约同步。

- 2026-09-28, pi：评审原 BLOCK；父代理修 kernel/engine/npc_agent 并加回归；351 测试 OK、lint OK。首个 reviewer diff 误存 repo-root `.scratch`，已改为 child `.scratch` 并全量复审。
- 2026-09-28, pi：第二次评审再发现 P1：封闭地点/耳语 `to=["陌生人"]` 仍可产生 stranger_asked，私问被转交给尚未听见的路人；P2：同步 Runner 仍信 payload.heard。父代理于 kernel._duration 拒绝无可听路人的搭话，Runner 用 visible_to 唤醒，新增封闭/whisper/字段不一致测试。v4 353 OK（1 skip）、lint OK；fresh reviewer 对 6f49ad8..bcc2983 的精确 diff 审阅为 OK with notes，P1/P2 均关闭，剩 V4-ENGINE.md 中一处旧文案，已同步修正。
