# 114 — 轨迹工件改成紧凑形态进 git（撤销 113 的“按大小不记录”）

Status: fixed
Need-review: yes
Need-test-cases: landed（`harness/tests/test_pack.py` 七支）

## 0. 一句话

用户裁定：几十 MB 不算大，**按大小把记录排除掉是错的做法**。于是把它换成
“一条事实只有一个紧凑形态”：一行一条记录的 jsonl，`zstd -19` 压紧，**进 git**；
内容一条不少，只去掉逐字重复的那一份。实测整天轨迹 17 MB → 0.52 MB，检查点
23 MB → 0.85 MB（去掉内嵌的重复轨迹后 0.29 MB）。

## 1. 为什么原始 `.json` 会显得那么大

同一段事实被写了好几遍，再叠上 `indent=2`：

| 位置 | 内容 | D1 全天工件里的体积 |
| --- | --- | --- |
| `world_events` | 世界事件全量 | 1.27 MB |
| `agent_turns` | 每回合的 `perception` / `affordances`（都是从事件和世界状态推出来的快照） | 6.08 MB |
| `sessions` | 会话快照 | 0.34 MB |
| 检查点里的 `trace` | **与当天轨迹逐字相同** | 7.92 MB |
| 缩进空格 | `indent=2` | 约一倍 |

zstd 把这些重复吃掉之后就是 0.5 MB 量级——所以问题从来不是“太大”，是“存了两遍”。

## 2. 修法

- `harness/pack.py`：把一个工件摊成**一行一条记录**（meta / 一条世界事件 / 一条回合 /
  一个会话 / 一份知识 / 检查点的一个部件），用 `zstd -19` 写 `<name>.jsonl.zst`。
- **不裁剪**：角色看到的、说出的、引擎记下的每一条都在。唯一的例外是检查点里内嵌的
  `trace`——它与同一次运行的轨迹逐字相同，pack 时省掉、`unpack` 时从同名轨迹补回
  （pack 的 meta 里记着 `omitted: ["trace"]`，所以这件事是可查的，不是悄悄丢的）。
- `scripts/pack_trajectory.py`：`pack` / `check` / `unpack` 三个命令；`check` 判三种
  失败——原始文件没打包、紧凑工件比原文件旧（跑完忘了打包）、展开后与原文不一致。
- `.gitignore` 只按大小挡原始 `.json`（本地可读副本），紧凑工件照常入库；
  预跑门加 `pack_trajectory.py check`。
- `v4/runs/README.md` 写清“一件工件两个形态”与运行结束时的三步动作。

## 3. 撤销：`artifacts.tsv` / `scripts/artifacts.py`（113 §5 的临时做法）

上一张票把“几十 MB 不进 git”当成前提，于是造了“清单 + 复制到第二块盘 + 核对哈希”
这一套。用户裁定那个前提不成立之后，这套东西就是**同一件事实的第二个家**：
紧凑工件已经在 git 里，哈希与字节数由 git 本身保证，再留一份声明清单只会漂移。
所以删掉 `v4/artifacts.tsv`、`v4/scripts/artifacts.py`、`v4/scripts/test_artifacts.py`；
预跑门改成 `pack_trajectory.py check`。磁盘上 `/home/z/hf/vibe-artifacts/v4` 那份
321 MB 早期拷贝保留为**本地缓存**（不是事实的家，可随时删）。

## 4. 验收

- `python3 scripts/pack_trajectory.py pack` → 现存 55 件全部打包。
- `python3 scripts/pack_trajectory.py check` → `trajectory OK：55 件紧凑工件与原始文件逐件一致`。
- `unpack` 抽查 D1 全天工件：展开后与原始 `.json` 的内容哈希**逐字节一致**
  （20.2 MB 原始 ↔ 637 KB 紧凑；检查点 26.8 MB ↔ 338 KB）。
- `harness/tests/test_pack.py` 七支：整份 trajectory 往返一致、角色看到的字段一条不少、
  旧工件（没有 `knowledge` 一栏）不会被凭空补出空字典、检查点省掉重复 trace 并可从轨迹
  补回、打包齐全时 check 通过、未打包即失败、原文件更新后即“过期”。

## 5. 未做

- `real_run` 还没有在批次结束后自动打包：现在靠 `check` 的“过期”判定兜住。若以后
  批次很密、希望每批都有紧凑工件，再把 `packer.pack` 接进 `Trace.save` 的调用点
  （代价是每批一次 zstd -19，约 1 秒/20 MB）。
- 更狠的压缩（`xz -9` 略小 0.02 MB，`--long` 需要解压端也开窗口）没有必要：
  zstd 解压快、流式可读，够用。
