# 库变更记录

概念与物性的破坏性变更升主版本，并在此写明迁移；一个概念的生命周期从"某个故事第一次用到"开始。

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
