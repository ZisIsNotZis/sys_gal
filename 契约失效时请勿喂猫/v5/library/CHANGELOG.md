# 库变更记录

概念与物性的破坏性变更升主版本，并在此写明迁移；一个概念的生命周期从"某个故事第一次用到"开始。

## 0.4 — M4

- 新增动词 `impound`（标签「收」）：有 `institution` 身份的人把一件东西从某个人或某个地方收走，并在带 `records` 的登记本上留下恰好一行。
- `speak` 增加可选参数 `to`（指称类参数，可省）：带 `to` 时只有那个人听见内容，旁人只感知到"两人在低声说话"；不带就是当众说。两句公共/私下的差从此是规则的一条分支，不是散文。
- `open` 对一扇地点门也认 `locked`：关上的门不再是"谁都能推开"。
- 新增状态键：`institution`（制度身份，物性）、`records`（能往上记一行的登记本）。
- 制度效果：`close`（到点关门上锁）、`open`（到点开门）、`pickup_due`（到点只提醒登记上的那个人）、`post`（把一张纸贴到某处，内容仍要读）。
- 物权（谁最后拿着）不进库：`container` 已经是唯一住所。

## 0.3 — M3

- 新增 `engine/prompt.py`：系统提示与工具表由种子的 `identity` 与库登记的动词生成（不再手写）。
- 新增 `engine/agent.py`：模型回合、拒绝回灌、`DecisionParseError`（一次坏调用记成失败回合，不崩整局）。
- `Rule` 增加 `label`（给人看的动词名）、`doc`（一句话说明）、`params`（额外参数与必填性）。

## 0.2 — M2

- 新增动词：`write`、`erase`、`copy`、`unlock`、`recognize`、`speak`。
- `inscription`/`medium` 两个状态键合并为 `marks`（一笔一条：文本、墨、字形），一眼只看见"有字"，细看看见"几笔、什么墨"，正文只能由 `read` 取得。
- 新增状态键：`smudge`、`imprint`、`locked`、`implement`、`hand`、`opens`、`accepts`、`copies`、`erases`。
- 命名解析支持描述性指称（"手里的空白纸"），并在带"手里"时优先手里那件。

## 0.1 — M1

- 首批动词：`examine`、`read`、`touch`、`take`、`place`、`give`、`open`、`knock`、`move`、`wait`。
- 首批状态键：`marks`、`door`、`closed`、`portable`、`silhouette`。
- 制度效果：`arrive`、`stops`（世界排程只准用这一层）。
