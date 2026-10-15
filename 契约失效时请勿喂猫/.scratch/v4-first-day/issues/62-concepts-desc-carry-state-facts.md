# 62 — `concepts` 的 desc 夹带状态/事实，且 known_to 覆盖面过大

Status: fixed
Need-review: yes
Need-test-cases: yes

## 现象（ticket 61 排查后报告的最大残余面）
`concepts` 的 `desc` 里写着**状态与事实**（不是"知道有这么个东西"的程度），而 `known_to` 又列得很宽：
- `flood-route-note`：`known_to` 全 10 人 → 人人都"知道"通知书页边有**未画完**的洪水路线旁注；
- `equipment-room`：`known_to` 含食堂大妈 → 她知道台账/导出件的**借出时间对不上**；
- `old-neighbor-rep`：直接给出**签名人**。

## 根因
与 ticket 61 同族：`known_to` 的语义是"知道有这么个东西"（ticket 40 已定），但 concept 的 desc 被当作知识行
原样下发，于是"知道存在"被写成了"知道细节/结论"。

## 验收方向
1. **区分身份与事实**：concept 的 desc 只写"这是什么"（可公开的身份）；凡属状态/结论/细节（未画完、时间对不上、
   签名人是谁）必须由**来源**获得（读到、被展示、被告知）——复用 ticket 49 的 observed 机制与 ticket 61 的 known_to 规则。
2. **收窄 known_to**：默认不写（=默认无人知道），只有剧情确需时显式列出；lint 对"concept 的 desc 含状态/结论词
   而 known_to 过宽"给出可见提示（非阻断）。
3. **回归（先红后绿）**：未接触来源的角色其 KB/primer 不得含上述状态/事实（用现有工件里的角色做夹具）；接触后必须能获得；
   既有需要该知识的角色不受损。
4. 历史失败登记进 `test_historical_failures.py`。
