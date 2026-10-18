# 80 — E83：固定陈设拿不走（`items:` 的 `takeable`，一处最小泛化）

Status: fixed
Need-review: yes
Need-test-cases: no

> 2026-10-16，票 79 §8-5 的收尾。用户裁定：货物/陈设登记成 `items:` 之后，引擎的
> `take` 对任何 item 都成立，角色可以把一台冰柜端走——这是正确性缺陷，允许**一处**
> 最小泛化（不是新原语）：`items:` 增加可选布尔 `takeable`。

## 缺陷

票 78 G4 按票 77 的编码把 `货架`/`冰柜`/`柜台`/`关东煮`/`例汤` 登记成 `items:`
（在场者靠知觉拿到客观描写，E77）。但 `take` 的合法规则只有“物品在这个地点”
（`World._raw_duration` 的 take 分支）与 `give` 的就地分支（票 63 的就地递交）、
`trash`（持有或在此地），三条都只问位置、不问东西是不是能搬。于是：

- `take 冰柜` → 冰柜进背包，房间描写（“柜台边那台卧式冰柜”）与库存描写同时不成立；
- `give 冰柜 to <同地某人>` → 同上，绕过 take 也能把它从不持有的位置挪走；
- `trash 冰柜` → 直接从世界抹掉。

## 修法（一处泛化）

- `items:` 新增可选 `takeable`（缺省 true）。`takeable: false` = 固定陈设。
- `world_loader` 校验类型（`takeable` 必须是布尔、`fixed_reason` 必须是字符串），
  并把它们收成 `World.fixed_items = {id: fixed_reason}`；`fixed_items` 与 `routes`
  一样由种子派生，**不进检查点**。
- `World._reject_fixed_item` 是唯一判定：`take`（在此地时）、`give` 的就地分支、
  `trash`（未持有时）都走它；拒绝文案 `「X」拿不走：<fixed_reason 或“这是固定陈设”>。
  它一直在<地点>，只能就地看着、问起或使用。这里能拿的：…`，并以
  `alternatives=[take <真正可拿的>]` 给出下一步。
- 顺带三处一致性：`affordances` 不再把固定陈设列成 take 候选（模型不会被诱导）；
  take/give/trash/read 拒绝里的“这里能拿的/这里有的”与 `_fallback_next_actions`
  只列真正能拿的；`read <固定陈设>`（无正文的实物）改说“它固定在这里，拿不走，
  只能就地看着、问起或使用”，不再建议“先把它拿上”。
- 物品位置、`item_locations`、事件 kind、动作集合、检查点格式、`replay_world`
  一字未改：变的只有“接受还是拒绝”这一判定，replay 只重放已接受的后果。

## 种子

标 `takeable: false` 的 5 件（都是正文里被写成房间陈设的东西）：`货架`、`冰柜`、
`柜台`、`关东煮`（小卖部）、`例汤`（食堂）；各带一句 `fixed_reason`（例如冰柜：
“一台卧式冰柜通着电、压在墙根，不是能抱走的东西”）。

**`热水壶` 不标**：它是值班台上能提着走的日常物件（宿管阿姨的卡原文“热水壶是我的情”，
烧水、倒水、拎去水房都得经手它），世界事实是可携带，标成固定陈设反而不实。

## 证据

`harness/tests/test_historical_failures.py`
`SeedContractGateTests.test_a_fixed_fixture_cannot_be_taken_and_stays_put`（E83）：

- 红（实现前，本次实测）：`AssertionError: {'kind': 'take', 'item': '冰柜'}
  unexpectedly found in [...]` —— 冰柜出现在唐小岚的 take 候选里。
- 绿（实现后）：take/give/trash 三路都被拒（`context.reason == fixed_fixture`）、
  物品仍在小卖部、冰柜不在 take 候选、同地的 `一瓶饮料` 照旧拿得走；种子没写理由时
  用缺省“这是固定陈设”，写了就原样转达；装载器把 `takeable: 'no'` 判成类型错误
  （不许静默降级成可携带）。

```text
python3 -m unittest harness.tests.test_historical_failures.SeedContractGateTests.test_a_fixed_fixture_cannot_be_taken_and_stays_put
  Ran 1 test — OK
python3 scripts/seed_lint.py
  seed lint OK（两条通道 0 findings，exit 0）
python3 -m unittest harness.tests.test_kernel harness.tests.test_world_pack
  Ran 144 tests — OK
python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
  run1 Ran 148 tests — FAILED (failures=1)：唯一红是已知的 E73 extra 时序族
       （'07:02' != '07:01'，单跑 3/3 绿；票 73 已登记）
  run2/run3 Ran 148 tests — OK
python3 -m unittest discover -s harness/tests -p 'test_*.py'
  Ran 595 tests — OK (skipped=1)        ← 基线 594 + 本票的 E83 一支
```

检查点/replay 手测（同一进程）：`checkpoint_state()` 里**没有** `fixed_items` 键；
`World.from_checkpoint(build_world(), state)` 与 `replay_world(...)` 都从种子派生的
base 拿回同一张表，还原后的世界仍然拒绝 `take 冰柜`、replay 出的背包与事件一致。

## 文档

`docs/V4-ENGINE.md` §7.3 增两条：`items:` 有两种（可携带的东西与固定陈设）、
`takeable`/`fixed_reason` 的写法与“这不改检查点和 replay”的边界；§7.3 的“回归”
一条补上 E83 的看守测试。

## 未做（同族的其他门，避免顺手扩大范围）

`actionable_refs` 里声明 `action: take` 指向固定陈设不会被装载器拦住（今天的种子里
只有 `场地申请表`，是可携带的文书）。要拦就是 `_validate_actionable_refs` 里多一个
分支，等真出现这种声明再补。
