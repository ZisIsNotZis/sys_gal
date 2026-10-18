# 99 — 同行途中的 extra 被当成“闲”回收（E104）

Status: fixed
Need-review: yes
Need-test-cases: yes

> 输入：票 98 §5.3（“本票不修，登记给下一窗口”的那条顺带发现）、票 97 §4 的 15:06–15:33 事件链、
> run `v4/runs/real-20261018T062031+0800-1910732-547128242.json`（窗口 5）。
> 范围：`v4/harness/engine.py`（`AsyncEngine._handle_extras` 的 idle 判据 + 一个新判据方法）、
> `v4/harness/tests/test_historical_failures.py`（`EscortIdleGates` + 台账 E104）、`v4/docs/`
> （`V4-ENGINE.md` §7.9、`V4-CAST.md` §1 各一句）。**`v4/world/`、`v4/scripts/` 一行未动**；
> 不新增动作种类，不新增世界状态字段（判据读的是各 actor 既有的 `current_action`/`busy_until`
> 与本就在检查点里的 `_extras` 行，旧检查点照常加载）。

## 0. 一句话

`extra_idle_seconds` 把“没人跟它说话”当成了“它站在原地”：张学长应下“愿意陪你去”之后一路沉默地
跟着唐小岚走，15:19 在下一跳途中被 `extra_removed reason: idle` 静默收走，唐小岚 15:28 独自到夜市、
15:33 独自到后街糕点铺——一次真实的陪行被引擎半路掐断。修法只有一处判据：idle 先问“它此刻是不是
在场”，在飞同行（自己走或别人 `with` 里带着）与没结的对话都不算闲；被携带者要离开仍走既有的
“途中可脱离”路径，回收不再是他离开的出口。

## 1. 证据（窗口 5，全部可从 run 逐条复核）

| 事件 | 时刻 | 内容 |
|---|---|---|
| #3684/#3685 | 15:06 | 张学长（extra）：“愿意啊。老板娘还留了话：……” |
| #3708 | 15:08 | 唐小岚 `action_started move 后街糕点铺 with ["张学长"]`，path 半坡咖啡馆→小卖部→夜市→后街糕点铺，hop 420/780/300 |
| #3709/#3710 | 15:08 | 两人各自 `leave 半坡咖啡馆`（张学长那条带 `escorted_by: 唐小岚`） |
| #3753/#3754 | 15:15 | 两人同到小卖部（张学长 `enter`/`leave` 都带 `escorted_by`） |
| #3780 | 15:19 | **`extra_removed 张学长 {"location": "小卖部", "reason": "idle"}`** |
| #3812 | 15:28 | 唐小岚独自 `enter 夜市`（move 的 hop 仍在跑） |
| #3851/#3852 | 15:33 | 唐小岚独自 `enter 后街糕点铺`，`action_completed move … with ["张学长"]` |

- 15:19 时 `alive` 为真（两人都在小卖部），只命中 `idle`：`last_active` 停在 15:09（它最后一次开口/
  提交动作），而 `extra_idle_seconds` 默认 600 秒——**被携带的整段路上它没有也不该有动作事件**，
  于是“沉默”被判成了“闲置”。
- 修前这个读数是错的而不是运气：判据只看 `last_active`，任何被携带超过阈值的同行都必然在途中被收走。

## 2. 根因

`AsyncEngine._handle_extras` 的 idle 判定是一行时间差：

```python
idle = (self.world.now - info["last_active"]).total_seconds() > self.extra_idle_seconds
```

它不区分“没人跟它说话”与“它正跟着人赶路”，也不区分“它还有一笔没结的对话”。两种在场的状态都被这
一行抹平了：

1. **在飞同行**：`move` 的同行者没有自己的动作事件（票 95 明文：走路是发起者的事，不给被携带者伪造
   动作），所以 `last_active` 不会因为赶路而刷新——这恰恰是“在场”最该有的证据，判据却读不到。
2. **在飞对话**：`pending_question` / `pending_heard_speech` / `_extra_inflight`（供给方还在写的那一句）
   都表示它欠世界一个回合，但旧判据照样把它当闲收走（这正是票 74 缺陷 B 的“idle-despawn 静默丢弃
   在途回答与 pending 问题”，本票按同一条判据一并收口）。

## 3. 修法

| 位置 | 改动 |
|---|---|
| `engine.AsyncEngine._extra_is_idle`（新） | idle 的唯一判据，逐条排除在场状态：① 还有没结的对话（`pending_question` 非空、`pending_heard_speech`、`_extra_inflight` 里有它）→ 不是闲；② 它自己也在一段 `move` 里（`busy_until > now` 且 `current_action.payload.action == "move"`）→ 不是闲；③ 场上有人在飞 `move` 且 `with` 里有它 → 不是闲；三条都不命中才落到原判据 `now - last_active > extra_idle_seconds`。 |
| `engine.AsyncEngine._handle_extras` | `idle = self._extra_is_idle(name, info)`；`partner_gone` 语义不动（伙伴真的不在同一地点时照旧回收，与闲不闲无关）。 |
| `docs/V4-ENGINE.md` §7.9 | 新增 E104 条目（证据、成因、判据、边界），回归清单加 `EscortIdleGates`。 |
| `docs/V4-CAST.md` §1 | 路人生命周期那一句补一行：正被带着赶路或还有一笔没结的对话时不算“闲置超时”，判据与脱离边界见 V4-ENGINE §7.9。 |

**被携带者要离开仍是显式动作**：他自己开始走另一段 `move`，`_follows_escort` 便不再带他（票 95 的
“中途可脱离”，本轮没有改它，只给它配了回归钉）；到站站定后 idle 照常计时。本轮**没有**新增任何回收
路径，也没有让同行变成永久豁免。改完的实际轨迹（探针，`extra_idle_seconds=60`）：

```text
07:01 extra_arrived 宋学长 / move 后街糕点铺 with ["宋学长"]
07:08 enter 宋学长 小卖部 (escorted_by 唐小岚)   ← 修前 07:03 就在这之前被 idle 收走
07:21 enter 宋学长 夜市   (escorted_by 唐小岚)
07:26 enter 宋学长 后街糕点铺 (escorted_by 唐小岚) + action_completed move
07:26 extra_removed 宋学长 {reason: idle}        ← 到站站定后才按原语义回收
```

## 4. 红→绿

`harness/tests/test_historical_failures.py` 的 `EscortIdleGates`（5 支）。两支引擎级测试用
`extra_idle_seconds=300`：它小于路线的第一跳（420s），但比“路人生成 → 角色回应”的回合延迟宽
（票 73 §6.1 的 extra 时序族曾把这一声推到 120s），所以红了就是真缺陷，不是那支已知间歇族。

| 测试 | 钉住的事 |
|---|---|
| `test_a_carried_extra_rides_out_the_idle_threshold` | 同行在飞超过阈值不被回收：每一跳都跟上（小卖部→夜市→糕点铺），`escorted_by` 全为发起者，最后一跳与 `action_completed move` 同一时刻；move 完成前没有任何 `reason: idle` 的 `extra_removed` |
| `test_a_silent_extra_with_no_walk_is_still_reclaimed` | 守卫：没有同行的沉默路人照旧在阈值后被 `idle` 回收——豁免只属“在途” |
| `test_the_idle_clock_is_held_by_an_unanswered_conversation` | 未答的问题、已听到还没回的话、供给方还在写的那一句都不算闲；沉默过阈值的路人本来就会回收（负控制） |
| `test_an_extra_walking_on_its_own_is_not_idle` | 自己也在一段 `move` 里不是闲；到站后 idle 照常计时（豁免有界） |
| `test_a_carried_extra_leaves_by_walking_to_its_own_target` | 被携带者要离开走既有显式路径：他自己 `move` 到别处，`_follows_escort` 不再带他，且没有任何 `extra_removed` 替他的决定 |

变异对照（每格一个 `/tmp/mut99*` 副本，改完只跑 `EscortIdleGates`）：

| 变异 | 读数 |
|---|---|
| 调用点退回旧式 `idle = now - last_active > threshold` | **1 红 / 4 绿**（红＝`…rides_out_the_idle_threshold`：`extra_removed 朱同学 idle @07:03`） |
| 删掉“没结的对话”那一条 | **1 红 / 4 绿**（红＝`…held_by_an_unanswered_conversation`） |
| 删掉“别人 `with` 里的同行者”那一条 | **1 红 / 4 绿**（红＝`…rides_out_the_idle_threshold`） |
| 删掉“自己也在一段 move 里”那一条 | **1 红 / 4 绿**（红＝`…walking_on_its_own_is_not_idle`） |

## 5. 回归读数（收尾实测，`cd 契约失效时请勿喂猫/v4`）

```text
python3 -m unittest discover -s harness/tests -p 'test_*.py'
  680 支（基线 675；本票 +5：EscortIdleGates）→ OK (skipped=1)，连跑 2 次均 OK
  两条已登记的间歇族本轮 0 次出现（`test_extra_turns_are_recorded_and_conversational`、
  `test_silent_abandonment_auto_continues_pending_action`），单跑历史读数见票 98 §7
python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
  226 支（基线 221，+5）→ OK
python3 scripts/seed_lint.py
  seed lint OK（exit 0；warning 8 条，与票 91/92/93/95/98 同数同族）
```

- 既有 extra 生命周期测试逐条核对过语义：`test_extra_idle_despawn_is_a_visible_interruption`
  （票 42）仍是“没同行的沉默路人按 idle 回收且是可感知中断”，与本票的豁免条件不重叠，原样绿。
- `test_engine.py` 的 extra 初始化/恢复测试与 `test_npc_layer.py` 的 `partner_gone` 断言均绿。

## 6. 旧检查点加载（下一窗口的续跑起点，显式验证）

```text
cp = runs/real-20261018T062031+0800-1910732-547128242.checkpoint.json
load_checkpoint(cp) → World.from_checkpoint(pack.build_world(), cp["world"])
  loaded world now: 2026-03-16T18:00:00+08:00 version: 4742 events: 4742 extras: ['胡大叔']
resume(cp, out=/tmp/…, endpoint="2026-03-16T18:20:00+08:00", call=<只 wait 的 stub provider>)
  18:20 stop_at_reached / events 4832 / turns 1712 / stub calls 44
  replay contiguous: True  world_versions_contiguous: True
```

- 该检查点里正有一名存活 extra（`胡大叔`）：`restore_checkpoint` 的 `_rehydrate_extra` 与 `run()` 重启
  extra 循环都走到了；新判据对恢复出来的行只读既有字段，不需要任何补写或迁移。
- 加载路径没有新增字段依赖，旧工件（`runs/archive-*`、`checkpoints/d1-am.json` 的读取测试）照常。

## 7. 仍然开着 / 移交

1. **同行豁免只覆盖 idle**：若 extra 是被**第三方**带着走、而它的 `partner` 留在原地，`alive` 为假，
   仍会以 `partner_gone` 在途中回收。窗口 5 的实例里伙伴就是携带者，所以本轮不扩大 `partner_gone`
   的语义（那会牵动“一次对话一个 MC”的产品裁定，`V4-CAST §1`）；若需要“换人陪行”，另开票。
2. **票 74 缺陷 A 未修**：`_horizon_bound()` 仍不把 `_extra_inflight` 并入时钟钉。本轮让 idle 不再吞
   在途回答（缺陷 B 的那一半），但“时钟可以越过在途回答”这条语义仍在，属于时钟钉问题而不是回收问题。
3. **回收仍是“销毁”而不是“告别”**：`extra_removed` 仍只带 `location`/`reason`（票 42 的可见中断语义），
   本票没有让 extra 在被回收前说一句离开的话——窗口 5 的诉求是“别在途中静默消失”，不是“每次都告别”。

## 8. 复算命令

```text
cd 契约失效时请勿喂猫/v4
python3 -m unittest harness.tests.test_historical_failures.EscortIdleGates
python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
python3 -m unittest discover -s harness/tests -p 'test_*.py'
python3 scripts/seed_lint.py
```

变异对照（每组一个副本，改完只跑对应点类）：

```text
rm -rf /tmp/mut99a && mkdir -p /tmp/mut99a && cp -r harness world scripts /tmp/mut99a/
# engine._handle_extras：idle 退回旧式时间差
cd /tmp/mut99a && python3 -m unittest harness.tests.test_historical_failures.EscortIdleGates
  → Ran 5 … FAILED (failures=1)

rm -rf /tmp/mut99b && mkdir -p /tmp/mut99b && cp -r harness world scripts /tmp/mut99b/
# engine._extra_is_idle：删掉“没结的对话”那一条
cd /tmp/mut99b && python3 -m unittest harness.tests.test_historical_failures.EscortIdleGates
  → Ran 5 … FAILED (failures=1)

rm -rf /tmp/mut99c && mkdir -p /tmp/mut99c && cp -r harness world scripts /tmp/mut99c/
# engine._extra_is_idle：删掉“别人 with 里的同行者”那一条
cd /tmp/mut99c && python3 -m unittest harness.tests.test_historical_failures.EscortIdleGates
  → Ran 5 … FAILED (failures=1)

rm -rf /tmp/mut99d && mkdir -p /tmp/mut99d && cp -r harness world scripts /tmp/mut99d/
# engine._extra_is_idle：删掉“自己也在一段 move 里”那一条
cd /tmp/mut99d && python3 -m unittest harness.tests.test_historical_failures.EscortIdleGates
  → Ran 5 … FAILED (failures=1)
```
