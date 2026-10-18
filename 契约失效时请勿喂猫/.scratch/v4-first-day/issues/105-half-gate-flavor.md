# 105 — --half 把 flavor（纹理）当阻断项，半天门被判红

Status: fixed
Need-review: yes
Need-test-cases: yes

## 复现
`v4/runs/real-20261016T212947+0800-438742-466169163.json` 上
`python3 scripts/check_milestones.py <工件> --half d1-pm`：9 项里两项 FAIL，
两项都属 `ROUTES[1]["flavor"]`（`d1-妈妈承诺`、`d1-林瑶自查审计包`），退出码 1，
结果行 `结果：未通过：d1-妈妈承诺、d1-林瑶自查审计包`。同一工件上
`d1-pm` 的锚点（`d1-审计催办转达`）与路线（`短信升级辅导员`：
`d1-辅导员介入`+`d1-三份个人说明`；`现场互证程序`：`d1-现场互证`）全部成立。

D1 全天并行运行的 d1-pm 工件 `runs/real-20261018T073833+0800-2019091-492642480.json`
同型：锚点与两条路线全过，只有 `d1-字条留痕程序`、`d1-老周托话`、
`d1-妈妈承诺` 三项纹理未达成，旧门判 FAIL。

## 根因
`main()` 的 `--half` 分支把 `MILESTONES[N]` 中该半天的**每个**检查项都放进
`failed` 并据此决定退出码，`ROUTES` 的 anchors/routes/flavor 分类只在
`--day` 分支使用。这与同文件 `ROUTES` 注释"flavor 是路线纹理，记录但不裁决"
以及 `docs/V4-STORY-MILESTONES.md` 的"纹理（flavor）……记录、复述、不裁决"
冲突：半天检查点是检查点边界，不是纹理审计。

## 验收
1. `--half` 只对 **锚点** 与（该日有路线时）**至少一条路线的 requires** 阻断；
   `flavor` 项照旧打印、标注"纹理（不裁决）"、不影响退出码。
2. 没有 `ROUTES` 定义的日期保持旧语义（半天内全部检查项阻断）并在输出说明。
3. `--day` 语义与输出不变。
4. 夹具：锚点与路线全过、仅 flavor 未达成 → 退出码 0；锚点未达成 → 1。
   新测试须在旧实现上红。
5. 文档半天检查点段落写明"--half 不裁决 flavor"。

## 实现（2026-10-18）
`scripts/check_milestones.py`：
- `half_check_category(day, id)` 是分类的唯一住所（anchor / route / flavor /
  unclassified）；既不是锚点、也不是路线 requires 或纹理的新增检查项按
  `unclassified` 阻断处理，避免新里程碑因为没归类而悄悄丢掉门禁。
- `half_gate_verdict(day, results)` 复用 `--day` 路线网的判定形状：锚点必须
  达成，且至少一条 requires 全部落在本半天内的路线成立；requires 在另一个
  半天时记"待后续"，不阻断（d1-am 因此不再要求下午才可能达成的路线）。
  该日无 `ROUTES` 定义时 `half_check_category` 全返回 `unclassified`，判定
  自动退回旧语义。
- `_print_half_gate` 打印"半天门判定"块：锚点状态、逐条路线状态、
  跨日锚点待后续、纹理清单（未达成的标"（未达成）"）。
- `main()`：`--half` 下逐项追加 `｜ 门禁·锚点 / 门禁·路线 / 纹理（不裁决）`
  标注；`failed` 改为 `verdict["blocking"]`；结果行保持
  `结果：全部通过 / 结果：未通过：…`，纹理未达成时追加以
  `（纹理未达成，不裁决：…）`。
- 向后兼容：参数不变；检查行前缀 `[PASS] <id> — <desc>`、证据缩进行、
  REVIEW 段、系统健康段、`--day` 的路线网段与退出码均未改（`--day` 输出与
  改前逐字节相同，见下）。

## 回归
`scripts/test_check_milestones_half_gate.py`（8 项；`python3 -m unittest
discover -s scripts -p 'test_*.py'` 或直接运行）：
- `test_flavor_only_failure_exits_zero_and_reports_the_texture`：d1-pm 夹具，
  锚点与路线[短信升级辅导员]过、路线[现场互证程序]与全部纹理未达成 →
  退出码 0，输出含 `纹理（不裁决）`、`d1-妈妈承诺`、`锚点：全部达成`、
  `路线[现场互证程序]：未成立`。旧实现上红：`AssertionError: 1 != 0`。
- `test_anchor_failure_exits_one`：去掉 16:10 催办单发言 → 退出码 1。
- `test_no_valid_route_blocks_even_when_anchors_hold`：锚点过但两条路线都
  不成立 → 1，输出 `路线网（无有效路线）`。
- `test_am_half_defers_routes_to_the_other_half`：上午门把下午的路线 requires
  记待后续，路线条件不阻断。
- `test_day_without_route_net_keeps_original_semantics`：临时移除
  `ROUTES[1]` → 退出码 1，输出 `无路线网定义`。
- `test_day_view_still_uses_the_route_network`：`--day` 仍走路线网（改前改后
  都绿，护住第 3 条验收）。
- `test_anchors_routes_and_flavor_partition_every_day`：12 天的
  anchors ∪ route-requires ∪ flavor 正好覆盖当天检查项（跨日锚点除外），
  且分类函数与之一致——门禁集合不会因为漏归类而漂移。
- `test_a_new_unclassified_milestone_still_blocks`。

红绿证据：同一测试模块指向 `git show HEAD:…scripts/check_milestones.py`
的旧副本 → 7/8 红（5 failures：`1 != 0` 等；2 errors：新函数不存在），
改后 8/8 绿。

## 既有输出影响
- `--day N`：与改前**逐字节相同**（`real-20261016T212947` 上 `--day 1`、
  `--day 2` diff 为空），退出码相同。
- `--half`：仅新增——检查行尾标注、`== 半天门判定（…）==` 块、结果行括号
  附表；既有 `[PASS]/[FAIL]` 行、证据行、REVIEW 段、系统健康段、`结果：`
  前缀全部保留，`drive_arc.sh` 的 `grep -E '结果' | tail -1` 仍取到最后一行
  判定。退出码只可能从 1 变 0（纹理不再阻断），不会新增红。
- 真实工件复核：`real-20261016T212947` 的 `--half d1-pm` 1→0；
  `real-20261018T073833`（D1 并行运行刚产出的 d1-pm）1→0
  （`结果：全部通过（纹理未达成，不裁决：d1-字条留痕程序、d1-老周托话、d1-妈妈承诺）`）；
  `--half d1-am` 仍为 0。

## 未决
新测试模块按本次边界放在 `scripts/`（不改 `harness/`），因此不在
`python3 -m unittest discover -s harness/tests` 这条预跑门禁里；是否把它
登记进 `harness/tests/test_historical_failures.py` 的台账由下一轮决定。
