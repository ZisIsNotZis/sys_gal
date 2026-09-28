# 34 — 路人简报绕过封闭地点的声音投递屏障

Status: claimed
Need-review: yes
Need-test-cases: yes
Blocked by: 32-extra-empty-question-rebrief.md

## 缺陷
独立 GPT-6 Luna 评审发现：kernel 对封闭地点的 speech event 仅向说话者本人 `visible_to` 投递，但原 `payload.heard` 仍按同场人填充；新 extra 唤醒和 transcript 又信任 `heard`，从而让路人获知自己在 world event 里未被授权听见的私语。这是隐私/因果 P1，禁止 provider 长跑。

## 不变量与验收
`visible_to` 是事件投递唯一权威；speech 的 `heard` 必须与其可投递的其他听众一致。extra 唤醒/简报从 `visible_to` 判定，可兼容仅测试合成事件的 heard fallback，但不能由 co-location 或 payload 反向授予真实事件听觉。封闭地点 normal/whisper 双例、恶意不一致 heard/visible_to 双例必须拒绝路人上下文；开放地点该听到的定向/广播保持可见。docs §3 模板和 extras 契约同步。

- 2026-09-28, pi：评审原 BLOCK；父代理已按这一不变量修 kernel/engine/npc_agent 并加回归，full v4 gate 运行中。原 reviewer diff 误存 repo-root `.scratch` 而非 child `契约失效时请勿喂猫/.scratch`，需提供正确位置的更新 diff 后复审。
