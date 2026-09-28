# Ticket 05: integration & first validation run

Issue: 把 01-04 的产出接起来——引擎测试、世界包校验、端到端冒烟、首验 run 启动。

Acceptance criteria:
- [x] v4 测试套件全绿（229 tests, OK, skipped=1 是 v3 锚点的 scenario 测试）
- [x] dry_run world 到达 22:00（events=11, turns=22）
- [x] mock_run world 到达 22:00（events=19, turns=26）
- [x] 关键面抽查：中文系统提示（inner 排第一、协议在末尾）、inner 解析+200 字截断、
      别名遥测命中计数（wait:seconds->duration_seconds）
- [x] 首验 run 启动（基线臂 = 当前 provider gpt-5.6-luna；A/B 其余臂后续再跑）

Status: done

## Comments

- 2026-09-04 agent (pi, gpt-5.6-luna): 集成验证如上，全部通过；首验 run 以
  nohup 启动，artifact 落在 v4/runs/，到达 world_stops 或 8h 墙钟后人工审阅
  （按根 AGENTS.md run-analysis protocol：读轨迹、报 lived behavior 与问题，
  不只报统计）。
