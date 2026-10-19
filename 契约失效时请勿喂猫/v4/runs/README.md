# v4/runs —— 轨迹工件的家

一局 provider 运行留下两件东西：整份轨迹（`real-*.json`，含 `world_events` /
`agent_turns` / `sessions`）和批次检查点（`*.checkpoint.json`）。它们是**证据**，
不是缓存：`AGENTS.md` 要求每次运行后人工复盘完整轨迹，报告与票据里的每条读数都
指回这些文件。

## 为什么不进 git，又为什么不等于可以丢

一件轨迹十几到几十 MB，仓库根的 `.gitignore` 因此只按大小挡住 `runs/*.json` 与
`checkpoints/*.json`（同一目录里的小文本照常入库）。但被挡住之后它只是一个本地
文件——一次 `git clean -xdf`、一次误删、一次换机器就没了。

这件事已经发生过：D1 第三次全天验收（2026-10-18，`real-20261018T113143+0800-…`）
与 d1-pm 的检查点就是这样丢的，而 `reports/m1-day1-acceptance3.md`、票 112 至今
还在引用它们。**声明里写了却不存在，等于没有。**

## 两件工具

```text
python3 scripts/artifacts.py archive    # 把未归档的工件复制到第二处位置并登记
python3 scripts/artifacts.py check      # 逐条核对：在不在、字节数、sha256
python3 scripts/artifacts.py check --strict   # 还有未归档工件也算失败
```

- 声明是 `v4/artifacts.tsv`（路径 / 字节数 / sha256 / 第二处持久位置），由
  `archive` 追加，不要手改——改了就和文件对不上，`check` 会失败。
- 第二处持久位置默认 `/home/z/hf/vibe-artifacts/v4`（另一块盘），可用
  `$V4_ARTIFACT_ARCHIVE` 覆盖。
- `check` 是预跑门的一环：跑 provider 之前先过一遍，别在证据已经缺失的情况下
  又跑一局。

## 一次运行结束时的动作

1. `python3 scripts/artifacts.py archive` —— 新工件立刻落到第二处位置。
2. `python3 scripts/artifacts.py check` —— 绿了再写报告与票据里的读数。
3. 报告里引用的工件名就是 `artifacts.tsv` 里的那一行，不要另写别名。

本地 `runs/` 可以清理（它是工作副本），清理前先 `check`：只要第二处位置上的
哈希对得上，本地删掉不丢事实；对不上就先补齐。
