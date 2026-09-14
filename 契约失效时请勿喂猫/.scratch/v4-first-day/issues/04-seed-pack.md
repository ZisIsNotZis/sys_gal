# 04-seed-pack：全中文世界包（首验日）

## Issue

v4 首验日需要一个全中文世界包：3 个角色（唐小岚/陈默/林瑶）、5 个地点、
一日事件（07:00–22:00），文化换皮为中式校园，欲望先行的人设 + 秘密清单。

## Acceptance criteria

- [x] manifest.yml 沿用 schema_version:1，可被 v4 harness 的
      `load_world_pack('world')` 加载并 `build_world()` 成功
- [x] id 全 ASCII，中文文本内直接用中文名，无"陈默 (Chen Mo)"式并列
- [x] 三个角色：欲望/恐惧先行，各含"秘密清单"小节（知道/绝不说/为什么），
      无"等待"倾向措辞；唐小岚按设计稿落地并接上审计/草稿线
- [x] 文档内容（manifest content）为可读中文文本，保留核心设定：台账与
      导出件时间戳冲突、审计包两个未标注总额+手写更正、底层凭证缺失
- [x] scheduled 只排首日 10 个事件，含咖啡馆早高峰/下雨共处机会与审计期限
- [x] 中文内容无英文漏网（标题四段式结构名除外）

## Status: done

## Comments

- 2026-09-04 agent (v4 seed worker): 创建 manifest.yml（banshan-campus，
  5 locations/3 actors/5 documents/3 items/20 routes/5 barriers/10 scheduled）、
  characters/{tang-xiaolan,chen-mo,lin-yao}.md、locations/*.md ×5、
  documents/*.md ×5、items/{blank-paper,cracked-mug,red-whistle}.md。
  设计取舍：① 唐小岚账本里的"何倩/记者"改为场外人物（3 角色阵容），
  草稿保留为环境文档；② 台账/导出件的可读文本写入 manifest content，
  冲突具体化（21:40 vs 23:30 借泵、3 通 vs 2 通呼入、目击行缺失）；
  ③ system.facts 中文化，期限改为当日审计核对；④ idle_wait_seconds=900
  （15 分钟），一天约 60 个闲置粒度；⑤ 验证：world_loader 加载 +
  build_world 通过，ASCII 泄漏 grep 清零（四段式结构名除外）。


## Comments

- 2026-09-14 agent (pi, 当前会话模型): closed: superseded by 10-world-enrichment; the pack loads and dry_run reaches the seeded endpoint. No further action.
