# 38 — 私有心声通道（inner）在任何传输下都不可达：内心独白被当作台词广播

Status: fixed
Need-review: yes
Need-test-cases: yes

## 复现与证据（2026-09-30 zai-coding/glm-5.3-flash，3/16 上午工件
`v4/runs/real-20260930T160727+0800-522904-846830380.json`）

`inner` 是协议里写明的"第一人称心声，谁也听不见"，且 `arguments` 被要求"必须带非空
inner，缺 inner 的调用不会被执行"（`harness/action_schema.py:94`）。实测：

- 该工件 317 个回合里 `inner` 非空的回合 = **0**。
- 对照 9/28 两次 gpt-6-luna 工件：611 回合 0 个、428 回合 0 个。三次运行共 1356
  回合，**inner 从未被填充过**。这不是本次模型的问题，是通道结构问题。
- 结果：模型把独白写进 `speak` 文本，世界按台词广播。世界事件可证：
  - #221（08:09）`action_completed 陈默` 文本即内心盘算"下棋大爷一进门就说要'瞅一眼那本子'——这话说得也太巧了……正好，当面问清楚。"
  - #234/#235（08:11）`下棋大爷`："（记性这东西，越想越没影儿——先把这糊涂账记下来，省得一会儿又忘了）"——连"要去改记事本"的盘算都被说出口。
  - #270/#271（08:19）`陈默`："瑶姐把签到本递过来了，还主动揽下了中午去学生会查值周表和审批记录的活儿——这忙帮到我心里去了。"
  - 四名独立复盘者（陈默/下棋大爷/韩大叔/食堂大妈）各自独立报出同一现象。

## 根因

`TOOLS` 用原生 function calling 声明（`action_schema.py:149`），每个 schema 都是
`additionalProperties: false` 且**不含 `inner` 属性**；而解析器在**信封顶层**
取 `inner`（`adapter.py:217`，`WIRE_KEYS = {"inner","name","arguments"}`）。原生
tool_call 只有 `function.arguments`，没有放 `inner` 的位置；写进 args 又会被
schema 判为 unexpected key。于是：**声明的要求无法满足，且"缺 inner 不执行"这条
规则从未被强制执行**，所以没有任何反馈把模型拉回正道。

## 验收方向

1. `inner` 进入每个 action schema（required string），或在 `arguments` 之外提供一个
   名正言顺的私有槽位；解析器从该位置读取并写入 `Intention.inner`。
2. 兑现文档承诺：缺/空 `inner` 的调用被拒绝，并给出可自纠的近失提示（不要只说
   "schema 错"）。
3. 回归（先红后绿）：schema 声明含 `inner`；带 `inner` 的调用被接受且不进 args；
   不带 `inner` 的调用被拒；一个最小 run 断言"私人推理不会出现在 `speech` 事件里"
   （至少断言 `inner` 被填充且不并入 speak 文本）。
4. 检查器补一条世界健康指标：`inner` 填充率与"speech 文本疑似心声"计数，别让这类
   全局边界破损再靠人眼发现。

## 裁决（2026-09-30，用户）
给**所有 tool 都加 `inner` 字段**（不采用 plain message 方案）：
- 动作 args schema 保持动作形状；线上 schema = `{inner, ...动作参数}`，`inner` 为 required string。
- 解析时先摘 `inner` → `Intention.inner`，再校验动作参数（`inner` 不得留在 args 里被当 unknown key）。
- 若 provider 返回 `reasoning_content`（开源模型的 reasoning），作为 inner 的兜底来源吸收。
- 兑现"缺 inner / 空 inner 的调用不会被执行"，并给出可自纠提示。
- 新增健康指标：inner 填充率 + "疑似心声混进 speech" 计数。
