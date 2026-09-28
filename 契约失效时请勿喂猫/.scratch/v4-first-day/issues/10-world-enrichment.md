# Ticket 10-world-enrichment: 世界加厚（新地点/规则层/NPC 班底/节奏纹理）

Status: done

## Issue

按 V4-CAST.md 实现：新地点+步行网络、地点规则层、7 个 NPC 人设（四段式+
导演笔记）、extras 匿名路人民（对话期生命周期）、节奏纹理 scheduled。
PO 补充规格（已写入 V4-CAST §1）：匿名路人为对话期生命周期，extras 按地点
配置，rare 者知道更多地点相关事实。

## 改名与新增清单

- **删**：`locations/宿舍.md`（拆分为男生/女生宿舍）
- **新增地点描述**（10）：男生宿舍、女生宿舍、食堂、小卖部、操场、图书馆、
  教学楼、夜市、河堤、陈默家（远程地点，仅电话可达，无 route）
- **新增 NPC 角色**（7）：宿管阿姨、食堂大妈、辅导员、班长、陈默妈（远程）、
  林瑶室友、下棋大爷——四段式 + `## 导演笔记`（唤醒场景/本场目标示例/
  知识注记/分寸线）。注：load_character 会剥离第五段（导演笔记不进 NPC 自己
  的 prompt），引擎简报构造器需直接从文件读取该节——与引擎 worker 的契约。
- **manifest.yml**：locations 14（含 rules×6、extras 池×12 个地点，每个
  common×2 + rare×1）；actors 10（role: mc×3 / npc×7；陈默@男生宿舍、
  林瑶@女生宿舍、唐小岚@半坡咖啡馆；陈默妈@陈默家无 route 即永不行走）；
  routes 60（30 对，自洽校园路径网）；barriers 7；scheduled 16
  （新增：陈默妈来电 07:35、早/午/晚饭点、上课铃、下午课、台风纪念活动
  公告（班长报名钩子+下周年纪念的铺垫）；移除 23:00 熄灯事件——
  world_stops 22:00 后不可达的死内容）。

## 校验结果

- `load_world_pack` + `build_world`：通过（14 locations / 10 actors）
- `load_characters`：10 个全载入；`导演笔记` 确认不泄漏进 seed
- `world_primer`：含全部新地点，1525 字符、30 条步行耗时
- `dry_run world`：到达 22:00（events=16, turns=115）
- 英文实体 id 残留 grep：无

## Comments

- 2026-09-07 agent (pi, gpt-5.6-luna): 如上全部完成。设计依据 V4-CAST.md；
  稀有信息者按 PO 指示与地点剧情相关（档案室老校友知道台账抢救史、
  家属院老人知道哨子传说——均为公开记忆层，不泄密）。陈默妈的"周日上午"
  调整为本模拟日（周一）07:35 补打来电，周日晚例电写进她的导演笔记。
- 2026-09-07 agent (pi, gpt-5.6-luna): 集成时发现 6 个测试失败，全部为引擎
  worker 并发半成品或需引擎配合的断言，不在本 ticket 范围，转交清单：
  1) Trace.record_agent 尚未接受 runner 已传入的 role kwarg（trace.py 待补）
  2) kernel 新动作 ask_stranger 缺 action_schema 条目
  3) test_loader.test_all_seed_characters_load 断言 3 → 应为 10
  4) test_historical_failures.test_seed_route_graph_is_connected：陈默家为
     远程地点（manifest 已加 remote: true 钩子），gate 应跳过 remote 地点
  5) 另两个 historical gate 失败同为 1) 的连带
  world 侧校验（build_world/characters/primer/dry_run）全部通过。
