# v5/runs —— 轨迹工件的家（入 git）

一次运行在 `stories/<story>/runs/` 留下四件原始材料，各答一件事：

| 路 | 四件 | 回答什么 |
| --- | --- | --- |
| 脚本局 | `<v>.md` / `<v>.context.md` / `<v>.events.json` / `<v>.json` | 发生了什么、**他当时知道什么**、事件账、摘要 |
| 模型局 | `agent-*/transcript.md` / `context.md` / `events.jsonl` / `run.json` | 同上 |

它们是**证据**，不是缓存：报告与票据里的每条读数都指回这里。四件里少了逐回合的
`context.md`，这一局就回答不了"他知道什么才做了那件事"，也就不算证据。

## 一件工件有两个形态

| 形态 | 名字 | 进 git？ | 用途 |
| --- | --- | --- | --- |
| 原始 | `stories/<story>/runs/…`（四件） | 否（整目录挡在 `.gitignore`） | 本地读、`jq` 查、复核 |
| 规范 | `<story>-<路>.jsonl.zst` | **是** | 事实的家：一行一条记录 + `zstd -19` |

紧凑形态**不裁剪内容**：角色看到的、说出的、引擎记下的每一条都在，展开回来与原始四件
逐字节相同。实测五支故事 25 条路：3,172,688 字节原始 → 227,547 字节工件（13.9×）。
压缩来自同一段事实在视图、事件账、摘要里各写一遍以及 `indent` 的空格，不是删。

## 三个命令（在 `v5/` 目录下）

```text
python3 scripts/pack_trajectory.py pack     # 打包未打包 / 变过的路；幂等，内容没变不重写
python3 scripts/pack_trajectory.py check    # 核对（v5 门的一环）
python3 scripts/pack_trajectory.py unpack runs/<story>-<路>.jsonl.zst [<out_dir>]
```

`check` 判四种失败，各自点名是哪个故事哪条路：原始四件没有工件（未打包）、工件比原始
文件旧（跑完忘了打包）、展开后与原文不逐字节一致（打包写错了或被改过）、原始里没有
`context.md`（不是证据）。`unpack` 不给目录时按工件里记的路径回到 `stories/<story>/runs/`，
写完逐件自校验摘要。

## 一次运行结束时的动作

1. `python3 scripts/pack_trajectory.py pack` —— 把这一局压成一份工件。
2. `python3 scripts/pack_trajectory.py check` —— 绿了再写报告与票据里的读数。
3. 报告里引用的工件名就是它的文件名（`<story>-<路>.jsonl.zst`），不要另写别名。

原始四件可以清理：只要 `unpack` 与 `check` 对得上，事实就在 git 里。实现与反向控制：
`scripts/pack_trajectory.py`、`tests/test_m5_pack.py`（三条测试分别证明 `check` 抓得住
缺 `context.md`、包被改过、包过期）。
