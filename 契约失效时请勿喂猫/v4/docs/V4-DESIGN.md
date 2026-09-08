# v4 Design: social immersion

> **SSOT 指针**：agent 接口（system prompt 逐字文本、工具清单、每回合消息
> 骨架、响应语义、KB 行模型与回放常数）的最新定稿在 `V4-AGENT-INTERFACE.md`
> （2026-09-07）。引擎时序/并发/冻结语义的 SSOT 在 `V4-ENGINE.md`
> （2026-09-08）。本文 §2/§3 中与上述文档冲突的细节（工具 JSON 形状、感知块、
> tick 大小、中断措辞）以其为准；§9-§10 草案已被其吸收。

Goal: fix the "emotionless company" outcome of the first 2-day run. The root
causes measured there: environment economics rewarded document grinding over
people; the seed scenario was purely bureaucratic; persona prompts trained
passivity ("choose the longest offered wait"); dialogue was expensive and
asynchronous; private emotional life never gained perceptual salience. This
doc is the design truth for the next version; nothing here is implemented yet.
Supersedes the former "ideal interaction design" list in ENGINE_CONTRACT.md.

## 0. Language: the story world is Chinese

The v4 seed pack (personas, locations, documents, world events, all narration
and world feedback) is written in Chinese. Rationale: the strongest novel
context for the candidate models (volc/ds/qwen/glm line) is Chinese; English
fiction pulls Western-novel priors that do not match the register we want,
and the first English run read as translationese. The protocol layer stays
ASCII: action kinds and argument names are English (tool-call convention);
all entity ids (actors, locations, documents, items) and display names are
Chinese (陈默, 半坡咖啡馆) — v4 seeds already ship Chinese ids. The scenario
is re-skinned to a natural Chinese campus setting (学生会, 社团, 食堂, 保卫处).
One language per world — no mixing Japanese or English prose into
the narration. Local-model A/B arm must then pick a Chinese-capable base
(e.g. Qwen-family), since many abliterated models are English-centric.

## 1. Model strategy (A/B before switching)

- Candidates: current gpt-5.6-luna (baseline) vs a volc/* flagship chat model
  vs a ds/* flagship chat model vs a local abliterated roleplay model via
  ~/llama.cpp (models under ~/hf, `hf` tool for downloads). Exact ids to be
  confirmed from the omniroute provider at run time.
- Metrics: social yield (conversations initiated, topic breadth, emotional
  events) and wasted-turn ratio (repeated no-content reads/waits). A livelier
  model can net out cheaper if it stops the read-loop pathology.
- Risk: small abliterated models lose instruction-following and long-horizon
  coherence; a 3000+ turn run dies from drift before it gets spicy. Treat as
  lower-bound exploration, not the default.
- Sampling: moderate-high temperature. Character turns run with reasoning
  OFF by default; depth must come from the model's chat register, not CoT
  tokens (see reasoning matrix below). If an arm tests reasoning low, it must
  also implement passback, and its latency is hidden by 8-actor wall-clock
  concurrency; the 1-minute tick keeps conversation pacing natural
  (engine semantics: V4-ENGINE.md).

### Reasoning passback matrix (per provider, for the A/B arms)

- gpt-5.6 (gh/*): /responses only. Reasoning items are encrypted and must be
  passed back in the next turn's input (`include: ["reasoning.encrypted_content"]`)
  or measured IQ drops hard. The current adapter does NONE of this — it is a
  bare /responses POST — so the gpt arm is only worth testing after the
  adapter keeps and replays encrypted reasoning items. Stateful store via
  previous_response_id is proxy-dependent; encrypted_content is the portable
  form.
- ds/* (DeepSeek official): returns `reasoning_content` as visible text, but
  the API contract strips it from multi-turn history — there is nothing to
  pass back. Chat and reasoner are separate models; the chat models are fast
  by design, which is exactly the register character turns want.
- volc/* (Doubao): thinking is a per-request switch; multi-turn history
  likewise carries only final content, not the thinking trace.
- Conclusion: stateful encrypted reasoning is an OpenAI /responses exclusive.
  Every non-gpt arm gets its depth from chat-register models, not passback.
  The hardcoded thinking:none in provider config becomes per-arm adapter
  configuration (endpoint shape + thinking switch + reasoning policy).

## 2. Immersive harness（已被 V4-AGENT-INTERFACE.md 取代的残留已清除）

本节原为沉浸式 harness 的早期草案（第二人称 GM 叙事、JSON-in-content 协议、
宽容解析、judge 回退、inner-in-JSON）。定稿见 `V4-AGENT-INTERFACE.md` §0-§2：
第三人称客观编年体、原生工具调用（name/arguments 严格解析）、think 工具、
别名遥测。此处仅存两条仍然有效的决议：

- 世界消息永不出现 "The world accepts your X" 式回执——结果以带时间戳的感知
  事件出现；拒绝保留即时纠正行。
- 参数名别名容忍 + 遥测：同义词命中即执行并计数；高频命中的参数名是坏命名，
  改名。（与 no-silent-aliasing 原则的调和：当场宽容，聚合上大声。）

## 3. Location-wide visibility and communication physics

- Everyone at a location perceives every public event there, related to them
  or not: two people talking is heard by the third. Private channels (text
  message, email, one side of a phone call) stay private.
- Privacy line: the fact that someone reads a document is visible; the
  document's content is not — unless they speak it aloud. Secrets can exist.
- Volume: `whisper` (only the addressed party hears; tagged perceptually as
  suspicious — a stranger whispering at you reads as fishy unless you are
  close to them) and `normal` (whole location). No loud tier for now.
- Interrupt semantics: only actors listed in `interrupt` and co-located get
  their pending action suspended with a continue-or-cancel choice; cancel
  marks the action failed/unfinished. No asleep state (AGENT-INTERFACE M1):
  waits are interruptible like any action; interrupts bind at execution
  position (V4-ENGINE §2.5).
- Message latency: one tick; tick = 1 minute (configurable; engine semantics:
  V4-ENGINE.md). Tick size is common knowledge
  so agents can budget time and words; speaking nonsense has a real cost.

## 4. Social economy

- Personas lead with desire and fear, not duty. Each character carries 1-2
  personal goals orthogonal to the audit plot and a secrets table (what I
  know / will never say / why). Delete "choose the longest offered wait";
  replace with "when idle, seek out people you care about".
- Relationship salience（per-pair warmth/trust 维度）与 joint actions（invite/
  join/accompany）：**未排期**——不在 v4 首版；若首验日显示社交深度不足再启用。
- Seeded co-presence events (storm blackout, crowded cafe on
  rainy hours) pull people into the same rooms.
- A gossip character is the information diffusion pump; draft at
  V4-GOSSIP-CHARACTER.md. Others are not helpful assistants: they trade,
  deflect, or refuse, and getting caught lying becomes news itself.

## 5. Carried-over interaction design (from the 2-day run review)

1. One world message per turn; accepted actions get no receipt — outcomes
   arrive, timestamped, in the next perception. Only rejections/failures keep
   an immediate corrective message.
2. Timestamped diary perception lines ("[14:32] park-minseo entered …").
3. Bounded, deduplicated private-state echo; compaction closes a context
   segment and the trace stores segments (system + compaction output + the
   turns lived under it), so views can show the true lived structure.
4. No silent context drops: oversized messages truncate with a visible marker
   and a trace warning.
5. Interruptible vs non-interruptible duration actions (see §3).
6. Minimal action interfaces: `move {target}` (duration computed from the
   map), `wait {duration}` free-form within sane bounds, `observe` as an
   explicit re-look tool. Instant actions emit one event (done + status);
   duration actions emit two (started, finished + status).
7. Change-driven observation: full observation on first arrival, on demand,
   and an automatic refresh every N rounds at the same place; in between, the
   actor tracks the place via pushed change events. Waits have no asleep
   filtering (AGENT-INTERFACE M1): public events at the location are delivered
   during `wait`; interrupts bind at execution position (V4-ENGINE §2.5).
   `wait`/`sleep` of other
   actors produce no observable events; one's own completion is reported to
   oneself only.

## 6. First validation run

One simulated day, tick = 1 minute, the gossip character plus at least two
existing characters, day-1 audit events only. Pass bar: each character has at
least two co-located conversations, the gossip character trades at least one
secret across an unrelated pair, and no character enters a no-content read
loop. If the day is achievable, tune content before touching clock
granularity or the realtime knob (V4-ENGINE §5).

## 7. 两层演员制与世界加厚

MC/NPC/匿名路人的分层、唤醒触发器、知识边界、导演简报、NPC 班底与世界加厚
清单已独立成文：`V4-CAST.md`（2026-09-04 定稿）。
