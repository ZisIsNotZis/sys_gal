# v4/runs —— 轨迹工件的家

一局 provider 运行留下两件东西：整份轨迹（`real-*.json`，含 `world_events` /
`agent_turns` / `sessions` / `knowledge`）和批次检查点（`*.checkpoint.json`）。
它们是**证据**，不是缓存：`AGENTS.md` 要求每次运行后人工复盘完整轨迹，报告与票据
里的每条读数都指回这些文件。

## 一件工件有两个形态

| 形态 | 名字 | 进 git？ | 用途 |
| --- | --- | --- | --- |
| 原始 | `real-x.json` | 否（只按大小挡） | 本地读、`jq` 查、引擎恢复 |
| 规范 | `real-x.jsonl.zst` | **是** | 事实的家：一行一条记录 + `zstd -19` |

原始 `.json` 看着大，其实是同一段事实写了好几遍：世界事件、每个回合的感知快照、
可行动作清单、检查点里内嵌的整份轨迹，再加 `indent=2` 的空格。实测 D1 全天工件
17 MB → 紧凑形态 **0.52 MB**；23 MB 的检查点 → **0.85 MB**，去掉与当天轨迹逐字
相同的 `trace` → **0.29 MB**。所以“文件太大所以不记录”是错的：记录全部，换紧凑
形态。

紧凑形态**不裁剪内容**：角色看到的、说出的、引擎记下的每一条都在；只去掉逐字重复
的那一份（检查点内嵌的 trace，展开时从同名轨迹补回）。

## 三个命令

```text
python3 scripts/pack_trajectory.py pack     # 打包新工件 / 原文件更新过的
python3 scripts/pack_trajectory.py check    # 核对（预跑门的一环）
python3 scripts/pack_trajectory.py unpack runs/real-x.jsonl.zst /tmp/real-x.json
```

`check` 判三种失败：原始文件没有紧凑工件（未打包）、紧凑工件比原文件旧（跑完忘了
打包）、展开后与原文不一致（打包写错了）。实现与夹具：`harness/pack.py`、
`harness/tests/test_pack.py`。

## 一次运行结束时的动作

1. `python3 scripts/pack_trajectory.py pack` —— 把这一局的两个工件打包。
2. `python3 scripts/pack_trajectory.py check` —— 绿了再写报告与票据里的读数。
3. 报告里引用的工件名就是 pack 文件的名字（`real-x.jsonl.zst`），不要另写别名。

原始 `.json` 可以清理（`/home/z/hf/vibe-artifacts/v4` 那份早期拷贝同理，只是本地
缓存）：只要 `check` 与 `unpack` 对得上，事实就在 git 里。
