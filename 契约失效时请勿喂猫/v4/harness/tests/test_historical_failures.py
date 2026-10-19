"""Historical failure patterns as pre-run regression gates.

Every failure observed in v1/v2/v3 runs is listed below with the test that
must stay green before a large provider-backed run is launched. Patterns that
already have dedicated tests are linked by name; the gap-filling gates live in
this module and are named for the failure they guard.

Coverage ledger
---------------
F1  provider 502 / transient retries escaping as agent_failure ... test_kernel provider tests, test_runner fail-fast tests
F2  generic "records no immediate physical change" feedback ...... test_no_accepted_action_reports_no_immediate_physical_change
F3  search/read had no objective result ......................... test_kernel (search/inspect), test_world_pack (read/copy)
F4  missing document primitives (read/copy/label/compare) ...... test_world_pack (copy/compare/label/provenance)
F5  rejection retry loop (Gao 校史档案室 move x3) ................. test_runner (repeated_rejection, alternatives),
                                                               test_rejected_loop_is_safe_and_instructive
F6  empty private state across long sessions ................... test_character_session (private updates, snapshot)
F7  privacy / cross-session leaks .............................. test_kernel (visibility), test_character_session (actor-local)
F8  System contract untested under a session ................... test_runner (system accept/query/reward/penalty/name)
F9  no run reached world_stops ................................. test_deterministic_seed_run_reaches_seeded_endpoint
I01 knock affordance / generic interact seam ................... test_kernel (generic interaction seam)
I02 closed-location dead-end / no opening path ................. test_seed_closed_locations_all_have_a_scheduled_opening_effect
I03 rejected-action lifecycle (replayed forever) .............. test_runner (rejection identity, delivered once)
I04 provider retry message duplication ......................... test_character_session (retry idempotent)
I05 message-boundary compaction ................................ test_character_session (bounding without slicing)
I06 compaction authority ....................................... test_character_session (authoritative order/restore)
I07 checkpoint resume .......................................... test_checkpoint (causal resume)
I08 streaming transport ........................................ deferred (needs-triage): intentionally NOT a gate
I09 romance seed pressure ...................................... seed data, not an engine gate
P1  wait-dominated deadlock .................................... test_deterministic_seed_run_reaches_seeded_endpoint
P2  repeated identical failed intentions ...................... test_rejected_loop_is_safe_and_instructive
P3  scheduled events with no consequence ...................... test_scheduled_effects_apply_objective_state_and_replay (kernel)
P4  accidental permanent location lock ........................ test_world_pack (no accidental shared-location locking)
P5  meetings never co-locate .................................. test_seed_route_graph_is_connected
P6  reading a file not at your location ....................... test_kernel (rejection lists what is present)
P7  send_message with a missing/wrong target key (new probe) ... test_send_message_without_target_is_helpful
P8  document action with wrong key (2-day run, 97 rejections) . test_document_action_with_wrong_key_is_helpful
P9  flashback returned nothing for seeded backstory ............ test_flashback_recalls_seeded_history_and_resolves_aliases
P10 uncovered concrete-presence claim in objective prose ....... test_uncovered_concrete_prop_claim_blocks_the_seed,
                                                               test_world_pack SceneObjectContractTests
T1a world clock races during a slow deliberation (7:35->7:40) ... test_deliberation_pins_the_world_clock
T1b no auto-wait after text (reply arrives to a departed actor) . test_text_auto_wait_and_npc_reply_followup
T1c NPC memory-only turn parks with the reply uncomposed ........ test_text_auto_wait_and_npc_reply_followup
T2  compaction leaves an orphaned tool message at the head ...... test_compaction_never_keeps_an_orphaned_tool_message
T3  compaction call sends role:tool to the Responses endpoint ... test_compaction_call_translates_tool_roles_for_responses
T4  authored pre-run history compiles + flashback replays it .... test_authored_history_compiles_and_flashback_replays_it
E1  extra turns die silently at trace-record time ............. test_extra_turns_are_recorded_and_conversational
E2  extra self-wake chatter loop (replies to own speech) ...... test_extra_turns_are_recorded_and_conversational
E3  extras permanently silent: content-only replies dropped ... test_extra_turns_are_recorded_and_conversational
E42 extra path leaks and fabricates (ticket 42, d1-am artifact) ... test_extra_envelope_is_never_broadcast_as_speech,
                                                               test_extra_tool_calls_reask_the_protocol_envelope,
                                                               test_extra_unparsable_envelope_is_silence_not_raw_json,
                                                               test_extra_prompt_states_self_name_and_assertion_bounds,
                                                               test_extra_idle_despawn_is_a_visible_interruption,
                                                               test_legacy_extra_call_envelope_is_never_broadcast
    events #1271/#1272 (12:42, 韩大叔=extra) broadcast the whole decision
    envelope — private `inner` plus protocol structure — as 韩大叔's spoken
    line (`heard=['唐小岚']`), because the extra path had its own ad-hoc
    parse; the rare 图书馆 extra 陈大爷 asserted an unmodeled 抄件 with a
    signature date and narrated 开柜/递件 as done (no open/give event in the
    log, affordances `[]`); it never knew its own name (`to:["韩大叔"]` →
    `unknown or ambiguous speak recipient`); and its 12:53 idle despawn left
    唐小岚 only "他走了" for an errand she had just handed over.
E50 extra checkpoint state incomplete (ticket 50) .............. test_extra_checkpoint_roundtrip_keeps_state_and_produces_a_turn,
                                                               test_old_format_extra_checkpoint_is_rebuilt_and_tolerated,
                                                               test_runner_sync_path_carries_the_prompt_and_tolerates_a_legacy_row
    checkpoint_state() persisted only fragment/knowledge_notes/partner/
    last_active/rarity/start, dropping system_prompt/context_cursor/
    pending_question/pending_heard_speech; _extra_turn then read
    info["system_prompt"] OUTSIDE its try, so any resume with a live extra on
    stage died with a KeyError and lost the pending question and replay
    cursor. The archived d1-am artifact carries a live extra (韩大叔), so the
    next half-day resume (d1-am -> d1-pm) would have hit it.
E71 py3.14 unpicklable itertools.count breaks deepcopy (ticket 71) ... test_world_deepcopy_survives_and_event_ids_stay_unique,
                                                               test_deepcopy_keeps_shown_seq_allocating
    machine Python moved to 3.14.8 (suite was green on 2026-10-13):
    copy.deepcopy(World/ActorKB) raised `TypeError: cannot pickle
    'itertools.count' object`, taking out every replay/checkpoint path
    (replay_world, launch trace, kb restore). Fix: kernel.Count replaces
    itertools.count (monotonic, picklable); the serialized
    next_sequence/next_event_id/shown_seq schema is unchanged and the
    archived checkpoints/d1-am.json loads as before.
E72a add_document placement is not delivery (ticket 72) ............ test_audit_slip_delivery_requires_a_scheduled_relay
    审计催办单 was placed at 学生会办公室 with no target while 陈默
    sat at 校史档案室 — d1-审计催办转达 counted 0 relays with lint green
    (report §5.3). A seed document an anchor depends on must carry a
    scheduled relay: target names the responsible actor, notice carries
    the slip and the duty.
E72b read passed, speech occasion missing (ticket 72) .............. test_speech_anchor_requires_a_scheduled_occasion
    林瑶 read the audit pack 12 times; pm speech needles counted 0 — no
    scene opened the substance to speech (report §6.3). An anchor that
    scores 说 must schedule an open co-presence occasion
    (audit_pack_review 16:20, broadcast at 学生会办公室).
E73 extra answer races the idle despawn (ticket 73) ............... test_extra_turns_are_recorded_and_conversational
    2026-10-16 live red (module solo + full discover): the stub answer
    sat queued on the shared daemon pool while world time outran it; the
    60s idle despawn then cancelled the extra mid-answer (probe:
    赵阿姨 extra_removed 'idle' 07:03, stub_calls=0) — 1 extra turn,
    "1 != 2". Fix is test-side: warm the pool before run and pin
    extra_idle_seconds above the scenario span. Product-side finding
    (clock pin ignores _extra_inflight on the normal advance path) is
    registered in ticket 73 for a separate engine ticket.
    2026-10-18 (ticket 104): the pool warm-up left the gate a coin flip
    under load — in a populated pack world the scheduler keeps stepping the
    clock on the rest of the cast's one-tick wait completions while the
    extra's provider call is in flight, so the same scenario measured
    arrival 07:01 or 07:02 and an answer 0, 60 or 120s late, and sometimes
    the run ended before the second answer landed ("1 != 2"). Fix is the
    fixture, not the engine: 陈默 stands alone in the world, its idle wait is
    a LEGAL one (wait 3600 exceeded this seed's 900s cap, so the rejection
    repair substituted a one-tick wait — one more event in the window), the
    follow-up ask is issued only after the reply was heard, and the stub
    answers only once 陈默 has parked (a barrier on world state). The
    deliberation window then owes no event at all, so the clock pin is the
    only thing that can hold the tick and the assertion is exact: answer
    tick == arrival tick (was ≤1 tick). Mutation-proven: removing
    `_extra_inflight` from `_quiescent()` or fast-forwarding two ticks under
    the deliberating extra both red the gate.
E75 take race: second same-item completion crashed the clock (ticket 75) .. test_take_race_second_completion_does_not_crash_the_clock
    2026-10-16 d1-pm live red (run real-20261016T192137, world 16:07):
    林瑶室发 and 李学姐 both queued take 可用纸笔 at 16:06 while the item
    was present, so both submits passed validation; the 16:07
    completions fired back to back — the first deleted item_locations,
    the second raised KeyError and killed the run. Completion-time
    guard: a take whose item is already gone stands as an event and
    mutates nothing (mirror of the despawned-extra defensive returns).
    Ticket 98 (E102) tightened the invariant: the second SUBMIT is now
    rejected ("X is taking it right now"), so the crash path is only
    reachable from a restored old checkpoint — the guard stays, and the
    gate feeds it a completion directly.
E76 公告栏死循环：登记为文书，read 已经够 (ticket 77) .. test_notice_board_needs_only_a_document_row,
                                                               test_world_pack
                                                               PrimitiveSufficiencyTests.test_a_notice_board_is_a_document_and_read_already_covers_it
    d1 全天工件 (real-20261016T210724 + pm 续跑): error turns #329/355/362/
    363/500/994 and ~10 more were `read 教学楼正门内侧公告栏` → "这里没有
    这样一件能读的文书"; five people spent 10:49–13:35 delegating the same
    unperformable errand, then asked two passers-by. Gap was seed-side: the
    board was named as an information channel in notices but never registered
    as an entity with a body. Encoding: a `documents:` row (+ Markdown
    description, `reading_seconds`, default auto_read) — `read` therefore
    offers it, produces `document_read`, and stay-read covers the rest. No
    look/examine verb was added.
E77 库存/陈设不可查验：物品描述已经在知觉里 (ticket 77) . test_fixture_stock_needs_only_an_item_description,
                                                               test_world_pack
                                                               PrimitiveSufficiencyTests.test_stock_and_fixtures_are_item_descriptions_in_perception
    唐小岚 hunted the kettle in her own café (16:26–16:51, 19:34–19:55) and
    asked customers ("我就在这家店当班，刚才没认出来"); 班长/陈默/吴阿姨 held a
    20-minute stalemate over 关东煮 stock (19:34–19:52); 食堂菜牌 13:22–13:38.
    Perception already delivers the objective description of every item here
    (`_visible_descriptions` + ticket 49's `observed` row), so a fixture or a
    stall's stock is an `items:` row whose prose states the quantity, and a
    menu/price list is a `documents:` row (E76). No look verb was added.
E78 12345 借电话死胡同：缺的是世界内出口 (ticket 77) ..... test_the_hotline_loop_needs_a_world_exit_not_a_verb,
                                                               test_world_pack
                                                               PrimitiveSufficiencyTests.test_the_night_dead_end_is_a_missing_route_not_a_missing_verb
    21:30–22:00: 下棋大爷 had nowhere legal to spend the night; 班长 and 陈默
    tried 12345, the engine had no call action, and the half hour became a
    "borrow a phone" loop (店员 and extras: 不归我管) while the clock reached
    22:00 undecided. Root cause is a seed gap — no reachable place that serves
    the need — so one route plus the place's own description turns the loop
    into an ordinary `move`. Residual, recorded not implemented: a literal
    call to a non-person endpoint is not expressible today; the minimal
    generalisation would widen `text`'s target class to registered non-person
    endpoints (kernel text branch + `_resolve_person`), never a `call` verb.
E77b 值班干事缺席：宿主是既有 actor + 可读的现场留痕 ..... test_world_pack
                                                               PrimitiveSufficiencyTests.test_a_duty_clerk_is_an_existing_actor_and_absence_leaves_a_record
    d1-pm: 16:20 面核 was a targetless broadcast, the scene had no host and
    nothing to perceive, and 林瑶 (away 16:13–16:55) could only say "I missed
    it". Encoding without a spawn primitive: the host is an ordinary `actors:`
    row (V4-CAST §1 NPC tier) woken by the existing scheduled `target` row,
    and the occasion leaves a document via the existing `add_document`
    effect, which a late arriver perceives and reads.
E79 scheduled notice asserts an acting person no actor can host (ticket 78)
                                                              SeedContractGateTests.test_g1_an_acting_role_noun_needs_a_real_actor,
                                                              test_g1_quoted_speech_and_absence_forms_are_not_agents,
                                                              test_the_gates_bite_on_the_shipped_pack
    d1-pm (manifest.yml:830, `audit_pack_review`): the 16:20 broadcast says
    "学生会办公室的值班干事按规程把学生会审计包当场摊开逐项核对" while no actor
    is that clerk — 林瑶 left at 16:13, passed the office at 16:24/16:34/16:45
    with nothing to perceive, and said at 16:56 "我错过了16:20的面核". Same
    family: 管理员 W 返岗/核对移交清单/签字 (admin_return, admin_handover,
    files_closed, admin_resolution, ledger_found), 老板娘 in coop_thread, 阿姨 in
    quest_washer, and the 1130 line of 值班簿 content where 值班干事 holds a
    shift. Fix: the four-gate lint (G1) requires an acting role noun in a
    scheduled notice to be a real `actors:` row (ticket 77b's encoding: host =
    existing NPC actor, no spawn primitive) or to be rewritten as a visible
    absence; registering it as a concept or declaring a location extra does not
    count, because a concept has no hands and an extra is a lazily invited
    stranger with no presence guarantee, inventory or trace.
E80 bare role noun neither registered nor declared generic (ticket 78)  SeedContractGateTests.test_g2_a_bare_role_noun_needs_registration_or_a_generic_declaration,
                                                              test_the_gates_bite_on_the_shipped_pack
    值班干事 (面核通知、值班簿/场地申请表正文、林瑶的 12:30 常驻行)、老板娘
    (小卖部与关东煮的正文、唐小岚的 15:00 带话行)、店员、值班学生、管理员、
    负责人、老师、编辑/记者、学生馆员、阿姨、大爷…— these nouns were readable
    but unnameable: the name contract only checks names that are registered, so a
    role noun nobody registered slipped through both ways. Fix: G2 requires each
    bare role noun in authored prose to be a registered name (marked [[ ]]) or to
    be declared generic in that row's `role_prose:`. The declaration lives on the
    owned row (scheduled/concept/kb/actors/items/documents/locations) so it never
    reaches the model as text.
E81 registered place or item with no reachable path (ticket 78) .. SeedContractGateTests.test_g3_every_location_needs_a_route_from_an_mc_start,
                                                              test_g3_a_prose_destination_must_be_a_location_not_a_place_concept,
                                                              test_g3_an_item_needs_a_path_or_a_completeness_declaration,
                                                              test_the_gates_bite_on_the_shipped_pack
    唐小岚 carried a standing task "交接班前去后街糕点铺帮老板娘带话" for
    12:21–19:54; 后街糕点铺 was registered only as a `kind: place` concept — no
    location, no route, and no actor could give directions, so `move` answered
    "不是一个你知道的地方" for six hours. Same family: 红色哨子 and 蓝色兔子雨伞
    sit at 老家属院, a `remote: true` location no one can walk to, with no
    acquisition path and no completeness declaration. Fix: G3 requires every
    location to be walk-reachable from each MC start (remote locations excepted
    by explicit declaration), every item/document to have a reachable place, a
    reachable carrier or a `completeness: expectation/belief/missing`, and every
    prose destination ("去/回 X") to be a registered location rather than a bare
    place concept.
E82 prose-announced interaction without an existing affordance class (ticket 78)
                                                              SeedContractGateTests.test_g4_a_read_mention_needs_a_document,
                                                              test_g4_an_examine_mention_needs_an_item,
                                                              test_g4_a_call_mention_needs_a_person_to_reach,
                                                              test_the_gates_bite_on_the_shipped_pack
    Three loops the d1-pm reviewers found (§2.4): 公告栏 read 10:49–13:35 by
    everyone who could be delegated ("这里没有这样一件能读的文书", 10+ error
    turns); 热水壶/关东煮库存/食堂菜牌 asked of strangers for minutes at a time
    (16:26–16:51, 19:34–19:52, 13:22–13:38); and 12345/借电话 21:30–22:00, a
    hotline the世界 cannot even express. Fix: G4 requires a prose-mentioned
    interaction to land on an existing target class — read wants a document
    (kernel `_available_readables`), a seen/taken thing wants an `items:` row
    (description through perception/observed), a contacted person wants an
    `actors:` row or a KB contact row — and reports the missing category with its
    remedy. 12345 is not in the seed today: the seed-side instance is "重大事项
    须电话报备" (校史档案室 rule + 档案室管理员 desc) which names no reachable
    person, and the hotline itself was invented by the model because the world
    had no line to answer.
E83 a fixed fixture could be picked up and carried off (ticket 80, 票 79 §8 ⑤)
                                                              SeedContractGateTests.test_a_fixed_fixture_cannot_be_taken_and_stays_put
    票 78 G4 按票 77 的编码把 货架/冰柜/柜台/关东煮/例汤/热水壶 登记成 `items:`，
    好让在场的人知觉到它们；但 `take` 对任何 item 都成立，于是模型可以把一台
    冰柜拿走、也可以就地递给别人（give 的就地分支）或扔掉（trash）——陈设离开
    原处之后，房间描写与库存描写就都不成立。修法是一处最小泛化而不是新原语：
    `items:` 增加可选布尔 `takeable`（缺省 true），false 表示固定陈设，take 结构化
    拒绝并给出 `fixed_reason`（缺省“这是固定陈设”），give/trash 走同一条判定；
    物品位置、检查点与 replay 一字未改——变的只是“拒绝”这一判定。
E84 extra 被回收时把身上的东西一起带走了 (ticket 83, 报 81 §5) ...
                                                              ExtraDespawnItemInvariantGates
    real-20261018T012247, 窗口 07:00→14:00: 12:52 extra 陈阿姨 在半坡咖啡馆
    `take 校报草稿` 成功，13:07 按 idle 回收——草稿随她离开世界，item_locations
    里没有它、没有一条说明它去了哪的事件，唐小岚 13:17 回到咖啡馆时只剩裂纹
    马克杯（那是她 !always 的目标物）。修法：`World.remove_extra` 在提交
    extra_removed 之前，把背包里的每件物品按既有 place 语义落回它最后所在地点，
    一件一条可见的 `item_dropped`；于是"任何物品在任何时刻要么在某人手里、要么
    在某个地点"在每个日志前缀上都成立，replay 重建同一结果（此前 replay 遇到
    extra 的 take 直接 KeyError：extra_arrived/extra_removed 从未被重放）。
E85 写记录的动作用了、却读起来不像能写记录 (ticket 83, 报 81 §1/§3 报告) ...
                                                              WriteRecordAffordanceGates
    林瑶 08:34 真的用 `leave_note` 写了 400 字事实记录（turn 93，note_left 落地），
    08:53 起却说"不把口头说明或留字条当成完成"，13:13 手里握着 `可用纸笔` 写下
    "纸笔在我手上，但没有可用工具把个人事实记录实际写入纸面"。诊断：动作本身
    在工具表与 affordances 里，且**不依赖任何持有物**（kernel 只看 text），
    缺的是说法——它只被描述成"给之后进入者留一张会烧掉的字条"。修法不改语义：
    工具说明与 affordance 提示都先把它说成"写记录/留字条"，并明说纸笔不是前提。
E86 一个没有调用的回合在 trace 里是空白行 (ticket 83, 报 81 §2) ...
                                                              TurnWithoutActionGates
    real-20261018T012247 的 12:51 林瑶（mc）回合：result=none、inner=None、零调用，
    世界只往前走一拍；同一 run 另有 5 个 NPC 空回合。审阅者只看到一条没有原因的
    空白行。修法不改模型行为：`_execute_chain` 对零调用的回合记一条 system_turn
    `empty_turn`，reason=`prose_only`（写了话但没提交意图）或 `no_output`（什么都
    没返回），带 actor/turn_id/role/private_chars。
E87 话语不是动作：七次"我马上给你打"零交付 (ticket 83, 报 81 §3) ...
                                                              TurnWithoutActionGates
                                                              (test_a_spoken_promise_is_recorded_as_speech_not_as_an_action,
                                                               test_a_turn_that_speaks_is_not_an_empty_turn)
    12:44–12:58 食堂大妈七次承诺打饭、零次 give/place；同一 run 11:48–11:59 她还
    用"长柄勺找不着"解释盛不了汤，而 item 描写里长柄勺就在桶边。裁定：引擎侧
    无需改——七次承诺都是真的 `speak` 调用，世界照实记了七句话、零交付（她要的
    `一份餐食` 就在食堂，`give` 一直在她的工具表里），缺的是 NPC 导演简报的约束
    （不得断言世界状态的改变、承诺交付要真的调用 give）。看守测试钉住这条区分：
    只有 speak 的回合没有 item_given、也**不**被记成空回合；真的 give 才产生
    item_given。
E88 承诺、断言与"写记录"三件事没有写进各自角色的提示 (ticket 85, 报 81 §3)
                                                              PromptDeliveryConsistencyGates
                                                              (test_an_npc_wake_briefing_binds_delivery_to_tools,
                                                               test_an_extra_prompt_binds_delivery_to_tools,
                                                               test_mc_tool_notes_say_words_are_not_delivery)
    E87 的裁定把缺口交给提示层，但提示层当时只有"不得叙述没做过的动作"这一句：
    NPC 唤醒收到的 `[director]` 块只有本场目标，一句
    "说话不改变世界/承诺要用 give 兑现/不得断言未见的世界变化"都没有；extra 的
    固定 prompt 同样没有"话不改变世界"与"不得否认世界状态"；MC 只有工具说明，
    而 `give`/`take` 的说明读起来像是纯物理描述（"递给在场的某人"），
    `leave_note` 也没有把"书面记录"这层说清。三类角色各自的提示因此都把
    "说"当成了"做"。修法只在提示层：`prompt.NPC_WAKE_RULES`（NPC 唤醒块固定
    开头）、`build_extra_system_prompt` 的"你能做的事"、`action_schema` 的工具说明
    各加相应一条，引擎语义、世界、种子一字未改。
E89 书面稿只能留给下一位进入者、读后即焚 (ticket 88, 报 86 §1) ..... PersistentNoteGates
    (test_a_persistent_note_can_be_read_twice_with_the_same_text,
     test_a_default_note_still_burns_after_its_first_reader,
     test_replay_rebuilds_the_same_persistent_note_id,
     test_a_checkpoint_keeps_the_note_and_never_reuses_its_id,
     test_an_old_checkpoint_without_notes_still_loads,
     test_the_archived_d1_am_checkpoint_still_loads)
    窗口 2（real-20261018T023423）12:11–15:02：21 次 `item_given` 全是纸笔在三人
    之间往返、0 次成稿；96 个回合（9.9%）在讨论"留条能不能算稿"（12:47/13:18/
    13:19/14:55）。根因不是缺动作而是语义：`leave_note` 的投递是"给之后第一位
    非作者、阅后即焚"，按定义交不到在场的收件人、也读不了第二遍。修法是一处
    泛化：`leave_note` 增加可选 `persist`（缺省 false，旧语义一字节不改）；persist
    时便条成为可寻址实体 `note-<作者>-<序号>`（留在原地点、进知觉的「字条」行与
    read 的可用目标、可重复读、可 trash），`note_left` 事件带 id 与 text 所以
    replay 重建同一 id；"交付"= 把它留在目标地点，不新增动作。检查点只增
    `persistent_notes` / `next_note_serial` 两个可缺省键（旧检查点照常加载）。
E90 零动作的 extra 回合没有记录 (ticket 88, 报 86 §2) .............. ExtraEmptyTurnGates
    (test_a_zero_action_extra_turn_is_recorded_with_its_reason,
     test_an_answering_extra_turn_is_not_an_empty_turn)
    窗口 2 的 system_turns 有 6 条 `empty_turn`（MC/NPC），但 trace 里 `result: none`
    的回合有 8 条：09:33 林大爷、14:13 陈师傅 零调用、inner 为空却没有任何记录。
    E86 的 `empty_turn` 只记在 `_execute_chain` 的 MC/NPC 链路径上，extra 走
    `_extra_turn` 就漏了。修法只加诊断：extra 真正被问了却没有返回任何调用时记一条
    `empty_turn`（role=extra、reason=no_output），世界不变、不惩罚角色。
E91 点名的路人被随机姓名替换 (ticket 88, 报 86 §3/§6) ............ ExtraPoolAliasGates
    (test_naming_a_pool_alias_spawns_that_entry_under_that_name,
     test_an_unnamed_ask_still_samples_the_pool)
    后街糕点铺的池条目是"后街糕点铺的老板娘"，但 `_spawn_extra` 用
    `generate_stranger_name()` 取名：13:14 生成李师傅、15:09 生成王学长，唐小岚
    两次到场都在问"李师傅或店里负责人现在在吗"，要找的"老板娘"从未出现（15:12
    只能靠"反正有人听见了"结案）。修法是一处泛化：池条目可声明 `aliases:`；
    `speak(to=["老板娘"])` 与 `to=["陌生人"]` 走同一条搭话通道（`stranger_asked`
    多一个 `alias`），引擎优先取该条目并让别名成为它的名字；未点名时仍随机取样，
    生命周期机制（idle despawn / E84 落物）不变。
E92 台账在对话里够不着它 (ticket 91, 报 90 §1) ................. LedgerDialogueGates
    (test_the_bound_character_gets_a_fact_table_answer_by_naming_the_ledger,
     test_a_question_outside_the_fact_table_gets_the_ledger_s_dont_know,
     test_a_used_up_ledger_stops_answering_instead_of_answering_again,
     test_the_query_limit_itself_closes_the_ledger,
     test_an_unbound_character_naming_the_ledger_is_not_answered_by_it,
     test_a_misnamed_attempt_gets_the_ledger_s_real_address_back)
    窗口 3（real-20261018T033115）09:02：陈默 `speak(to=["2013年台风台账"])`
    被内核判成"未知收件人"；`World.ACTIONS` 里没有 `ask`、`Ledger.affordances()`
    按工单 14 返回 `[]`、v4 工具面无 `system_query`，而文档 §5 写着"它是世界内
    对话者……所有交互走对话"。全段 `system_answer` 0 次、`system_reward_granted`
    0 次，案件的三个条款一次都没被答上。修法不新增动作：`speak` 的收件人解析
    扩展到已接受案件的 System 对话者（受约束角色点名种子 `system.name`），走既有
    fact table 应答，答案以既有 `system_answer` 私有事件只投递给它；答不了说
    不知道、超限/结案即闭口、未受约束的角色不被应声。裁定"钉住的文书"用既有的
    `takeable: false`（见 test_world_pack PlaceBoundDocumentTests）。
E93 连续空回合的后果没人告诉角色 (ticket 91, 报 90 §2) ........... ConsecutiveEmptyTurnGates
                                                               NoActionNoticeTextGates
    窗口 3 的 08:42–09:04：陈默九个回合只有正文、零工具调用（`intention: null`、
    `content_private` 81–142 字、provider 故障 0——不是引擎重试），每拍世界只多了
    一条 §4 的 60 秒发呆 `wait`，时钟每拍前进约两分钟；`empty_turn` 记了，但那一拍
    的后果从没回到他的输入里，于是他在正文里把台账三条款答了五遍。修法两处、都不
    改时钟：`empty_turn` 多一个连续计数 `streak`（进检查点、有调用即清零），零调用
    的回合把一条"那段想法没有改变世界"的反馈（带连续次数）追加到下一回合输入，
    一拍一条、不叠加、不代填动作。
E94 结案时机：首次命中就结案让 `limit` 不可达 (ticket 93, 票 91 §4-2 裁定) ... LedgerClosureGates
    (`test_two_hits_in_a_row_each_produce_an_answer_and_the_case_stays_open`,
     `test_after_the_limit_the_ledger_silences_without_closing_the_case`,
     `test_the_seeded_settlement_beat_closes_the_case`,
     `test_a_world_beat_that_is_not_the_settlement_keeps_the_case_open`,
     `test_the_real_seed_schedules_the_settlement_and_it_closes_the_case`)
    `Ledger.query` 一命中就把 `status` 置成 `completed` 并发 `system_reward_granted`，
    于是 `query_limit > 1` 的种子实际只答一次（第二问走 `closed` 而不是 `limit`），
    而 `V4-AGENT-INTERFACE` §5 写的是“查询次数硬上限”、`V4-STORY-MILESTONES` 把结算
    排到 d7/d12。用户裁定：**结案由种子排程的结算事件驱动**（既有 `system_reward_granted`
    私有路径），首次命中只给答案。修法：`query` 命中不再改 `status`、不再发报酬；
    `Ledger.settle` 在种子那条 `settle_on` 节拍（本种子 3/22 15:00 `ledger_settlement`）
    到达时结案并发报酬（幂等）；引擎在 `_after_advance` 只认这一条节拍名，其它世界
    事件不结案；`world_loader` 在加载时校验 `settle_on` 点得到一条真排程（点错即
    “永不结案”，所以大声失败）。`status` 终态从 `completed` 改为 `closed`，旧语义下
    依赖“命中即结算”的两支测试（`test_kernel`、`test_runner`）按新语义重写。
E95 台账事实表要逐字猜问句，拒绝零痕迹 (ticket 95, 报 94 §1) ... LedgerFactMatchingGates
    (`test_a_natural_question_hits_by_keywords`,
     `test_a_question_with_no_keyword_gets_dont_know_and_a_private_audit`,
     `test_a_tie_between_two_entries_gets_dont_know`,
     `test_every_dialogue_leaves_one_private_audit_with_the_answer_event_id`,
     `test_an_entry_without_keywords_still_answers_its_own_question`,
     `test_the_real_seed_answers_five_natural_questions_with_plain_text`)
    窗口 4：陈默 5 次点名台账全部 submitted，`system_answer` 仍 0——`facts.get(question.strip())`
    要求逐字命中三条原始问句，而他从没见过它们；拒绝在世界日志里 0 痕迹。修法：条目可声明
    `keywords`（缺省回落到条目问句）；问句归一化（NFKC + kb.normalize）后按命中关键词数打分，
    唯一最高分即答，并列/零分答“不知道”，**不调模型**；每次对话（含拒绝）提交一条只给提问者的
    `system_dialogue` 私有事件（`question/matched/outcome/answer_event_id?`），仍不产生公开 speech。
E96 没有“带某人一起走”的原语 (ticket 95, 报 94 §4) ........... EscortMoveGates
    (`test_two_people_arrive_together_with_one_synchronised_sequence`,
     `test_a_companion_locked_in_an_uninterruptable_action_rejects_the_move`,
     `test_replay_after_an_escort_keeps_everyone_in_the_same_place`,
     `test_a_companion_who_is_not_here_is_rejected`)
    窗口 4：305 族 219 条发言 / 17 个角色 / 6h51m，165 条“我不能实际扶/陪/带”。世界没有“扶着
    某人一起走”的动作，305 也不是地点，17 个角色的拒绝全都对。修法：`move` 可选
    `with=[同在此地的人]`——校验同处一地/未被不可打断动作锁住/自己不在走另一段，共同按发起者
    路线逐跳移动（每位被携带者自己的 leave/enter，同步时刻、连续 version），被携带者保留感知与
    自主（不替他行动，途中可脱离）；replay 靠 enter 重建。
E97 无 target 的 world_event 全场广播 (ticket 95, 报 94 §2) ... WorldEventScopeGates
    (`test_a_location_scopes_the_audience_instead_of_broadcasting`,
     `test_a_location_scoped_event_still_reaches_its_explicit_target`,
     `test_replay_preserves_the_scoped_audience`)
    窗口 4：16:00/16:20/16:45 三条排程事件无 target → `_visibility` 返回全场，连正文广播 12–14 人；
    陈默在档案室 16:02 就引用 16:05 才定向给他的原话。修法：payload 可选 `location`——有它时
    可见集 = 该地点在场者 +（若有）target；只有 target 时不变；都没有仍是既有全局广播。
    `world_loader` 校验 location 是已知地点。
E98 工具面没有“在文书上写” (ticket 95, 报 94 §3) ............. DocumentAnnotationGates
    (`test_signature_is_an_appended_annotation_that_others_can_read`,
     `test_a_second_writer_appends_without_overwriting`,
     `test_replay_rebuilds_the_annotations`,
     `test_writing_on_a_document_that_is_not_here_is_rejected`)
    窗口 4：`面核记录` 要求“谁到场核对谁填自己那一栏”，但工具面没有 annotate（`document_annotated`
    与 `annotations` 早已存在却无入口），班长只能另贴字条，0 人签。修法：`leave_note` 可选
    `on=<文书 id>`——文字作为一条批注追加进该文书（同地或手上、可读；与 persist 互斥），产生
    既有 `document_annotated`（同地点可见），正文仍只属于读过它的人（`_public` 对非作者剥掉），
    不覆盖他人条目；签字/批注的 verb-gap 教学改为指向 `leave_note on=`。
E99 手边物品不在 give 候选里 (ticket 95, 报 94 §C) ........... GiveAtHandAffordanceGates
    (`test_an_item_at_my_location_is_a_visible_give_candidate`)
    窗口 4：食堂大妈全天 give 0 次，11:00“窗口要有人守”只成为一句招呼，两份饭自取（午饭上台
    48 分钟后才被拿）。引擎早已支持就地取再递（ticket 63），缺的只是可见性。修法：`affordances()`
    的 give 候选 = 背包 ∪ 当前地点可拿物品（排除固定陈设）；拒绝回执的可行调用清单同样包含。
E100 可选参数的空字符串被当成“已提供” (ticket 98, 报 97 §E1) ... BlankNoteOnGates
    (`test_a_blank_on_writes_an_ordinary_persistent_note`,
     `test_a_whitespace_only_on_is_the_same_as_no_on`,
     `test_a_real_document_still_takes_the_annotation_path`)
    窗口 5（08:06–17:19，run real-20261018T062031）：全天 106 条拒绝（陈默 60、林瑶 23、
    林瑶室友 8……）都是 `leave_note {text, persist: true, on: ""}`——校验用
    `if on is not None` 判“同时声明”，空串于是把“留一份新文稿”自己判成冲突，而陈默
    从 11:25 起逢人就说“我三次尝试留书面说明都没有成功”。语义：`on` 只有非空字符串
    才进批注分支，空串/纯空白等于没提供（提交入口一次性剔除，payload/事件/replay 只看一种写法）。
E101 `move with: [""]` 被当成“有同行者” (ticket 98, 报 97 §E2) ... BlankCompanionGates
    (`test_an_empty_companion_entry_means_walking_alone`,
     `test_an_empty_with_list_means_walking_alone`,
     `test_a_real_companion_still_comes_along`,
     `test_a_placeholder_companion_name_teaches_walking_alone`)
    窗口 5：76 条“move 的 with 里有一个空名字”，相邻形态还有 `["_self"]`/`["陈默(you)"]`/
    `["唐小岚"]`（自己）——模型在找“一个人走”的表达法，而接口只有“不写 with”，拒绝回执
    实测 7 连未纠正（唐小岚 08:29–08:59），于是她 13:04 对外说出“移动需要明确同行者”。
    修法：空项/纯空白项先过滤、重复项去重，过滤后为空 = 独自走（`with` 整个键去掉）；
    schema 允许空数组；拒绝回执与工具说明明写“一个人走就只写 target”。
E102 同一件东西被两个人同时 take 都算成功 (ticket 98, 报 97 §E3) ... SingleInstanceTakeGates
    (`test_the_second_taker_is_rejected_while_the_first_is_still_taking`,
     `test_an_item_never_has_two_holders`,
     `test_a_late_take_names_where_the_item_actually_is`,
     `test_an_abandoned_take_releases_the_item`)
    窗口 5 17:57（run real-20261018T062031，事件 #4707–#4719）：陈默与辅导员各自
    `take 一份晚饭`，两条 `action_started`/`action_completed` 全部成立，只有先完成的那位
    背包里真的有它；辅导员 17:59 还对外说“谢谢，我们都拿了晚饭”。不变量：一件东西在任一
    时刻只有一个持有者或一个地点——`take`（以及 `give` 的就地递出，同一族：
    两个人各递一次同一份饭，两个收件人背包里都会有一份）从提交到完成独占这一件，
    第二次拿给出“正被 X 拿在手里”的结构化拒绝；拿完之后的 take 说出它现在在谁
    手上/在哪里。
E103 陌生人嘴里有还没送到的便条正文 (ticket 98, 报 97 §E4) ... ExtraScenePrivacyGates
    (`test_a_stranger_never_receives_a_note_that_is_not_his`,
     `test_a_public_prop_still_grounds_its_own_description`,
     `test_the_owner_still_sees_her_own_note`)
    窗口 5 15:04–15:06：唐小岚读过 `代话便条` 后向“陌生人”求同行，当场生成的 `张学长` 把
    便条原文当“老板娘留的话”说了出来，送达被提前兑付一次。诊断（该回合 perception 实录）：
    extra 没有拿到提问者的 KB/记忆，泄漏通道是场景事实块——`scene_perception` 把同地每件
    东西的 `entity_descriptions` 全文发给它，而这份便条的客观描述就是正文（种子已声明
    `known_to: [唐小岚]`）。修法：被 `known_to` 限定给别人的东西，extra 看得见它在场，
    但不拿到描述正文；公开物件（`校报草稿`）照旧给描述，“一份”这类数量断言仍有根据。
E104 同行途中的 extra 被当成“闲”回收 (ticket 99, 报 98 §5.3) ... EscortIdleGates
    (`test_a_carried_extra_rides_out_the_idle_threshold`,
     `test_a_silent_extra_with_no_walk_is_still_reclaimed`,
     `test_the_idle_clock_is_held_by_an_unanswered_conversation`,
     `test_a_carried_extra_leaves_by_walking_to_its_own_target`)
    窗口 5 15:15–15:33（run real-20261018T062031）：张学长 15:06 应下“愿意陪你去”，
    15:08 随唐小岚 `move 后街糕点铺 with 张学长` 出发，15:15 两人同到小卖部，15:19 它
    在下一跳（780s）途中得到 `extra_removed reason: idle`。成因：idle 判据只看
    `last_active`（上一次开口/动手的时刻），把“没人跟它说话”当成“它站在原地”——
    被携带的整段路上它没有动作事件，也不该有。修法：`AsyncEngine._extra_is_idle`
    把两种在场状态排除在 idle 之外：它正被一次 `move` 携带着赶路（自己也在这段路上，
    或它是别人 `with` 里的同行者），或它还有一笔没结的对话（未答的问题、已听到还没回
    的话、供给方还在写的那一句）。被携带者要离开仍走既有“途中可脱离”的路：他自己
    开始走另一段 move，`_follows_escort` 便不再带他；到了地方站定后 idle 照常计时。
E105 便条能写能读、递不出去 (ticket 101, 报 100 W6-E1) ...... NoteDeliveryGates
    (`test_a_written_sheet_is_a_note_that_can_be_handed_over_and_read`,
     `test_a_persistent_note_left_on_the_table_can_also_be_handed_over`,
     `test_a_rejected_note_handover_never_offers_an_unrelated_document`,
     `test_replay_rebuilds_the_handed_over_note_and_the_used_sheet`,
     `test_the_sheet_route_is_offered_and_a_non_paper_is_refused`)
    窗口 6 18:44–21:30（run real-20261018T073833）：陈默写了署名说明，18:48
    `give note-陈默-1` 给辅导员被拒（“你没有拿着…可行调用：give 2013年邻里撤离通知书”）；
    19:07 `leave_note on:"空白纸"` 被拒（`on` 只认 `document_defs`）。主角 D1 的核心目标
    （自己写好、签名、亲手交给辅导员）因此**结构上不可达**。修法：`give` 的目标物 =
    物品 ∪ 已存在的便条 id（便条本来就在世界上，递它就是递纸；持有关系沿用背包，
    事件仍是 `item_given`，replay 同 id 同手）；`leave_note on=<纸张>` 把那张纸写成
    一份带编号、可读、可递的文稿（纸被用掉），与 `on=<文书>` 的批注路径按目标类型分派；
    拒绝只说便条在谁手上/哪里，不再拿无关文书当替代。
E106 睡觉没有表达法，夜段 43% 回合是 wait 900 (ticket 101, 报 100 W6-E3) ... SleepWaitGates
    (`test_eight_hours_of_sleep_is_accepted_and_advances_the_clock`,
     `test_a_sleeping_actor_is_woken_before_its_hour_is_up`,
     `test_a_named_scheduled_event_wakes_a_sleeper_and_a_broadcast_does_not`,
     `test_replay_and_checkpoint_keep_the_sleep`)
    窗口 6 夜间 7 次 `wait 34200–48960`（≈9.5–13.6 小时，“睡到明早”）被 900 秒上限拒收，
    模型只能 15 分钟一觉熬到天亮，19:14–21:24 有 2h10m 结构空转。修法：`wait` 增加
    可选 `sleep: true`（不新增动作种类，§2 早已裁定 sleep 并入 wait），单次上限 12 小时，
    `sleeping` 字段起睡置真、完成/被叫醒/被打断清零；同地社交事件照旧经 `wake_waiter`
    打断，另加 `World.wake_sleeper`：`target` 点名他的排程事件也能叫醒，未点名的全场
    广播不叫醒。
E107 extra 的“没被问”回合仍然静默 (ticket 101, 报 100 W6-E4) ... ExtraNoRequestTurnGates
    (`test_a_wake_without_a_question_records_the_reason_instead_of_a_blank_line`)
    窗口 6 18:00 胡大叔 `result: none`、`calls: []`、`inner: null`、role extra，
    夜间 `system_turns` 与本段回合的交集为空。E90 只盖住“被问了但没输出”：这一拍是
    从检查点续跑时 restored extra 的第一拍（无待答问题、无新听到的话，`needs_response`
    为假 → 模型根本没被请求）。修法只加诊断：这一种也记 `empty_turn`（`reason:
    no_request`），于是“没被问”与“被问了没输出”在 trace 上可分辨；世界不变。
E108 引擎机制进入对白 (ticket 101, 报 100 W6-E2) ...... NoMechanismInSpeechGates
    (`test_the_mc_tool_surface_carries_the_rule`,
     `test_the_npc_and_extra_prompts_do_not_carry_it`)
    窗口 6 19:12 陈默对在场三人说“刚才的留字只生成了下一位进入者才看得到的字条”——
    机制上正确，因此才证明它是从 hint/回执推出来的引擎知识，而不是任何世界内的感知。
    修法：`action_schema.NO_MECHANISM_IN_SPEECH`（“不要向他人描述引擎机制…只说你做了什么、
    谁看见了什么”）只加在 MC 的工具说明（`leave_note`）上；NPC 与路人的提示一字未加
    （NPC 共用同一份工具表，但它们的提示另有自己的演技规则）。
E109 长睡一回合把整个夜吞掉：唤醒成了日志里的死信 (ticket 106, D1 报 103 D1-E1) ... WakeReachabilityGates
    (`test_a_private_wake_still_reaches_an_awake_actor_while_another_sleeps`,
     `test_a_named_scheduled_event_wakes_a_sleeper_on_the_chain_path`)
    D1 `real-20261018T085705`：18:35 林瑶 `wait 28800 sleep:true` 之后 18:40–22:00
    共 205 分钟零回合，六条夜间排程、三条 `private_wake`、四条 `reminder_due`
    全落在世界日志里，22:00 时醒着且空闲的人感知游标停在 18:36。成因不是唤醒
    路径，而是链内那次时钟推进：`_execute_chain` 的 `advance` 只夹 stop horizon
    与决策视界，`limit` 落到 stop_at，一次 `advance` 把整段夜间记进日志而不派
    回合，`_stop_check` 随即停表。修法：回合内推进再夹到 `World.next_event_time()`
    （时钟只由调度器走）；不新增世界状态、不强制叫醒任何人。`SleepWaitGates③`
    为何没拦住：它用旧 callable agent（`_submit` 路径），而真实回合走
    `_execute_chain` —— 本类用 `session_obj` stub 补上这一段。
E110 `private_wake` 对睡着的人是死信 (ticket 109 D1-2-E5) ... PrivateWakeDeliveryGates
    (`test_a_private_wake_wakes_a_sleeping_mc_and_lands_a_turn`,
     `test_a_private_wake_for_an_absent_target_records_the_reason`)
    D1 工件 real-20261018T100115：21:36 给林瑶、21:40 给陈默的两条 `private_wake`
    落在两人的 `wait sleep:true` 期间（林瑶 21:06→07:16、陈默 21:10→07:10），
    `World.advance` 只把这个 kind `_commit` 进日志（可见性 {本人}），唤醒只在
    引擎的 `_wake_waiters` 里为 `world_event` 走——两人的最后一个回合停在
    21:05 / 21:09，心跳成了一封没人读的死信。修法：`World.advance` 的
    `private_wake` 分支改走 `_fire_private_wake`——先提交 `private_wake`，再
    `wake_sleeper`（E106 同一条路径，留下可见的 `wait_woken`）；目标已不在世界
    里则记一条 `private_wake_failed {reason: actor_not_present}`，可见性不含任何
    活人。副作用：空闲心跳现在会打断长睡，`mc_idle_heartbeat` 是调节旋钮。
E111 `engine.turns` 与 `trace.agent_turns` 差 241 (ticket 109 §附) ... V4-ENGINE §7
    计数口径裁定（无独立门）
    (`test_extra_turns_are_recorded_and_conversational` 的两条计数断言)
    D1 工件 real-20261018T100115：`engine.turns=1479`、`trace.agent_turns=1720`，
    差 241 = 29 名 extra 的 `_extra_loop` 回合（上一轮 868 - 793 = 75 同理）。
    不是漏记也不是丢回合：`Engine._turns` 只数 persistent actor 的 `_take_turn`
    （mc+npc），`max_turns` 与停机诊断用它；`Trace.agent_turns` 记下每个 agent
    回合（含 extra 与 `result: none` 的诊断行），报告与轨迹复核用它。各自含义与
    用途写进 V4-ENGINE §7，断言钉在既有的 extra 门里（persistent 回合在轨迹里
    恰好一行；两数之差 = extra 回合数）。
I38 private inner channel unreachable — 0/1356 turns (3 runs) ... test_inner_channel_is_reachable_on_the_wire_and_native_path,
                                                               test_legacy_envelope_inner_still_works,
                                                               test_missing_inner_native_call_is_rejected_with_a_self_correcting_example,
                                                               test_reasoning_content_fills_a_missing_inner,
                                                               test_engine_records_turn_inner_and_a_failed_call_is_not_a_dead_turn
I39 item prose bodies unreadable; read rejections lied ......... test_turn_305_held_register_reads_and_remote_document_is_not_offered
    turn 305 (12:44, 陈默 in 食堂): inventory held 签到本, yet `read 签到本`
    was rejected "不在你手边" and the suggestion list offered 移交存根
    (archive, unheld). 24/72 error turns were this class in the d1-am run.
    test_world_pack: test_item_with_content_reads_once_like_a_document,
                     test_inventory_item_reads_and_every_offered_read_succeeds,
                     test_held_item_without_a_body_says_so_and_offers_real_actions,
                     test_known_to_does_not_grant_remote_read_or_description,
                     test_undeclared_item_body_fails_seed_lint_and_declaring_it_turns_green
    test_historical_failures (I39 item-body regression)
I43 chain path fed the repetition monitor None (ticket 43) ... test_chain_path_feeds_the_repetition_monitor,
                                                               test_chain_path_counts_waits_as_stagnation_with_a_next_action
    engine.py `_execute_chain` called `note_turn(actor_id, None, result)`;
    `RepetitionMonitor.note_turn` returns immediately on `intention is None`.
    The run's real (chain) path therefore counted nothing, and `wait` was also
    unconditionally exempt (`_EXCLUDED_ACTIONS`). On the d1-am artifact nine
    identical failing `read 签到本` and eighteen `wait 900` turns produced zero
    notices. Fix (user ruling 2026-09-30): hand the chain's `recorded`
    Intention to the monitor with a rejected/submitted outcome, count
    consecutive waits as stagnation (its own threshold/stride, reset by a
    non-wait action or a location change), and list the character's real
    remaining actions. `sleep`/`text` stay exempt.
I44 note left while the recipient is present goes nowhere .... test_leave_note_receipt_names_the_audience_and_offers_give,
                                                               test_run_end_reports_undelivered_notes
    d1-am artifact, turn 163 (09:51, 校史档案室, nearby_actors=['陈默']):
    林瑶 left 陈默 a 借条; note_left #645 was the run's only note event —
    陈默 left at 10:41 and no non-author ever entered the archive again, so
    the note stayed pending forever. The note_read mechanism already existed
    (kernel._consume_notes burns it for the next non-author entrant); the
    defect was feedback and observability — the receipt did not name the
    room of listeners or offer `give`, and an undelivered note left no trace
    at run end. Fix: the receipt states the audience, names present people
    and offers `give`; the run outcome (以及 real_run 打印) carries
    `unread_notes`. Semantics unchanged (pinned before and after the fix by
    test_world_pack: test_leave_note_waits_for_next_entry_and_hides_text_from_room,
    test_note_is_delivered_privately_to_only_the_next_enterer,
    test_note_author_reentry_preserves_own_note_for_a_later_reader):
    read-once-and-burn, the author never consumes their own, co-located people
    never get the content, the first non-author entrant gets the full text.
I45 NPC 休止：待答提问与到期提醒都叫不醒 ......................... test_npc_layer (NpcWakeContractTests:
    named-question nudge / own-reminder wake / reminder-reason / no-extra-wake /
    speaking-turn-settles-debt / owed-debt checkpoint round-trip)
    d1-am artifact (real-20260930T160727): 宿管阿姨 i=88→254 (08:39–11:51)
    went 3h12m with zero turns while 林瑶室友's two face-to-face questions
    (08:30/08:31) sat in her perception; 陈默妈 after i=197 (10:46) went 2h13m
    with zero turns even though her 12:00 reminder did fire (world event
    #1069, visible_to includes her). Root cause: `reminder_due` never set
    `_npc_pending` (an idle NPC's own due `!at=` row woke nothing — the
    kernel only force-interrupts a busy actor), and the named-speech wake had
    no "named but hasn't answered" persistence, so a non-speaking turn
    (read/wait) swallowed the question for good. Fix: a `reminder_due` for an
    NPC queues it with "你的安排到点了：<desc>"; a named speech or directed
    message opens a `_npc_owed` debt {at, from, nudged} that a speaking turn
    (speech/message_sent) settles, and that grants one extra wake after
    `owed_response_delay` (default 600s) while idle — never a per-turn wake,
    never spending cold-scene wake budget. The debt round-trips through the
    checkpoint and a legacy checkpoint without the key restores as no-debt.
I49 objective description was a one-shot snapshot ................ test_objective_observation (observed record/event,
    checkpoint round-trip, read fallback, stay-read, auto_read opt-out),
    test_historical_failures test_objective_description_survives_compaction
    issue 49 (user ruling 2026-09-30): the objective description existed but
    was delivered only on the arrival turn — never entered memory, and could
    not survive context compaction. A seen-but-bodyless prop made `read`
    either guess or answer "not in your hand". Fix: `ActorState.observed`
    records the objective text once, per entity, on first sight (emitting a
    private `observed` event); a `read` of a seen thing returns that text;
    and staying in view for `reading_seconds` auto-produces a `document_read`.
I58 unvisited locations' interiors reached every actor ......... test_location_contracts
    (test_unvisited_actors_are_not_told_the_archive_interior,
     test_location_identity_is_available_to_every_actor,
     test_arriving_at_the_archive_delivers_its_interior,
     test_expanded_location_rows_carry_the_brief_not_the_interior,
     test_one_paragraph_location_fails_seed_lint_and_splitting_turns_green)
    d1-am artifact (real-20261001T065553), two independent reviewers:
    宿管阿姨 (turn 292, 11:25) wrote "档案室2013年台风台账那页折痕翻得厉害"
    though she never left the 女生宿舍 值班台 all day; 食堂大妈 (turn 388,
    12:44) told 陈默 "铁皮柜按年份码着呢" though she never entered the
    archive. Root cause: `world_loader._expand_entity_rows` auto-expanded every
    location's FULL body into each actor's KB, and `world_primer` used the
    body's first line, so interior layout reached actors with no source. Fix
    (ticket 58): a location `.md` separates a public brief (first paragraph)
    from interior detail (later paragraphs); the KB and primer carry only the
    brief, the interior is delivered on arrival by the ticket-49 objective
    description, and seed_lint refuses a one-paragraph body with remediation
    text. Residual, deliberately NOT fixed in this lane: an unmarked placed
    document still expands its full description to every actor — the 折痕 clause
    itself came from `documents/2013年台风台账.md` (no `known_to` in the seed),
    which needs a product decision about document visibility, not a location fix.
I61 unmarked placed documents were world-public (ticket 61) ..... test_document_contracts
    d1-am artifact (real-20261001T065553), the half of I58 this ticket closes:
    宿管阿姨 (turn 292, 11:25) reasoned "档案室2013年台风台账那页折痕翻得厉害"
    without ever leaving the 女生宿舍 值班台 — the 折痕 clause came verbatim
    from `world/documents/2013年台风台账.md`. `_expand_entity_rows` treated a
    placed item/document with no `known_to` as the public visible layer and
    auto-expanded its FULL body into every actor's KB (宿管阿姨/食堂大妈/
    辅导员/班长 all carried the 台账 line and 陈默's 撤离通知书 line). Fix
    (ticket 61): an item/document is world-public only when the seed says so
    (`known_to`); an unmarked placed one expands to nobody, and whoever needs
    it receives its objective description through the ticket-49 observed /
    `[所见]` path (the archive arrival, or holding it). Locations are
    unchanged — their public brief stays world-level (ticket 58). A
    non-blocking seed lint flags a placed document whose body asserts a
    concrete state (折痕/缺页/涂改/缺角…) while `known_to` is empty, so the
    author confirms the state is not meant to be common knowledge.
I62 concepts' desc carried state/conclusions to a wide known_to (ticket 62) ... ConceptStateLeakGates
    (test_unmet_actors_do_not_carry_the_concept_conclusions,
     test_the_world_primer_carries_no_concept_state,
     test_reaching_the_ledger_yields_the_borrow_state,
     test_holding_the_notice_yields_the_unfinished_arrow,
     test_plot_owners_keep_the_concepts_they_need,
     test_wide_known_to_with_a_state_desc_warns_and_narrowing_silences_it,
     test_twin_concepts_do_not_leak_their_conclusions,
     test_narrowed_pump_knowers_keep_a_source,
     test_narrowing_keeps_the_names_its_gossip_needs)
    d1-am artifacts: 食堂大妈's #knowledge block (real-20260930T160727) carried
    the verbatim concept line "[器材室]: 借出两台抽水泵的地方，登记人签名潦草。
    2013 年那晚的借出时间在纸质台账和导出件上对不上。" although she never read
    the 台账/导出件; flood-route-note's "箭头没画完" reached all ten actors
    (known_to 全列), and old-neighbor-rep's desc named the signer outright.
    Root cause is the ticket-61 family: `known_to` means "knows the thing
    exists" (ticket 40), but the concept `desc` is delivered as a knowledge
    line, so "knows of it" read as "knows the state/conclusion". Fix: a concept
    desc states only what the thing is; state/conclusions (未画完 / 对不上 /
    签名人) come from a source through the ticket-49 observed path;
    flood-route-note narrows to the two actors the plot needs (陈默 holds the
    notice in his drawer, 林瑶 needs its evidence), and the notice stays
    unmarked — its body's names resolve for nobody, matching ticket 61's
    runtime default (the seed lint's structural scope for an unmarked
    item/document is now "nobody", not "everyone"). A non-blocking seed lint
    warns when a desc still carries a state/conclusion word while `known_to`
    lists ≥5 actors. Tie-out (same lane, ticket 62 收尾): the twin concepts
    with the identical mechanical defect were collected too — `pumps` sent
    "纸质台账记 22:05，导出件记 23:30" to [陈默, 林瑶, 下棋大爷, 食堂大妈], and
    `primary-school` asserted the 21:40 call conclusion to the same four. Their
    descs are now identity only and `pumps` narrows to [陈默, 林瑶, 下棋大爷]
    (present / must read); 食堂大妈 keeps her 器材室/小学 public-memory names so
    the gossip is not orphaned. Residual, deliberately NOT fixed in this lane:
    the characters' own memory rows, the `history.visible_to` channel, and the
    other conclusions still in a desc (flood-route-2013, access-project);
    `audit-case` is the intended puzzle and is untouched.
I59 update_memory key friction was the run's largest error class (ticket 59) ... test_scheduled_key_label_and_bare_weekday_are_accepted,
                                                               test_fused_always_label_is_accepted,
                                                               test_compound_key_error_names_the_closest_existing_row,
                                                               test_normal_always_and_contact_are_unchanged,
                                                               test_partial_update_memory_reports_each_row_and_keeps_the_valid_ones,
                                                               test_checker_splits_out_update_memory_failures
    d1-am artifact (real-20261001T065553): 24 of the 52 error turns were
    update_memory. Three real shapes: (1) the label/directive fused into one key
    — the time key (`!at=3/16(周一) 08:10 上午班`, `!at=3/16(一) 12:05`) was
    rejected "unparseable scheduled key", and the bare directive
    (`!always 无障碍改造`, `!always 值班表`, `!contact 辅导员`) answered
    "unknown directive key"; (2) a multi-key target whose keys live on DIFFERENT
    rows (`!contact 林瑶 桂姨`, `!always 签名人 老街坊代表`) answered "no row
    keyed" with only per-key nearest keys, no executable retry; (3) a batch row
    failing failed the whole call, so the valid rows that HAD been written read
    as lost. Fix: `!at=` keys accept a fused label (split into a second text
    key) and both `周X`/bare `X` weekday spellings (canonicalized to one handle);
    a known bare directive fused with its text (`!always ...` / `!contact ...`)
    is split back onto the directive plus one text key per token; a no-match
    error adds the open row with the largest key overlap named with its exact
    keys; and update_memory applies row by row, reporting each outcome (partial
    success is ok=True with the failed rows also recorded in
    `memory_rejections`). Safety is unchanged: keys still match verbatim, a
    `!contact` first text key must still be a registered actor, and the
    `!at`/`!always` schedule and reminder_due auto-close are untouched. The
    checker prints `update_memory 失败行数` separately.
I46 recipient checks judged the live world, not the decision snapshot . test_one_bad_recipient_does_not_void_the_rest_of_the_batch,
                                                               test_a_name_seen_in_the_perception_is_always_resolvable,
                                                               test_every_recipient_offered_in_a_rejection_can_be_reached,
                                                               test_a_departed_addressee_is_undelivered_never_heard,
                                                               test_whisper_to_a_departed_addressee_reaches_nobody,
                                                               test_one_costly_action_per_turn_is_protocol_text,
                                                               test_a_busy_chain_result_names_the_rule_and_the_retry_turn
    d1-am artifact (real-20260930T160727): 班长 turn 212 (11:09) was
    rejected `speak recipient must be here; absent: 陈默` although the SAME
    turn's affordances listed `{"kind":"speak","to":["下棋大爷","陈默","陌生人"]}`;
    turn 215 (11:14) was rejected `unknown name '下棋大爷'` although that
    turn's perception said `nearby_actors=['下棋大爷']`; 辅导员 turn 233
    (11:30) lost a whole line addressed to 班长+下棋大爷+陈默 because 下棋大爷
    had walked off mid-deliberation, and the name list the rejection printed
    offered 唐小岚/宿管阿姨, who were not in the room at all. 陈默/辅导员 also
    burned 4-6 turns on `not executed: current … completes at …`.
    Root cause: affordances/perception are the DECISION-time snapshot while
    submit re-resolved names and co-presence against the already-advanced
    world, all-or-nothing for the whole recipient list. Fix: `World.submit`
    takes the turn's perception snapshot (`seen_here`), a multi-addressee
    `speak` is planned per target (reachable ones keep the words, a departed
    or unresolvable one is recorded as `undelivered` on the committed action
    and reported in the tool result), a rejection's candidate list is
    per-action and executable (contacts+here for `text`, here for `give`),
    and the protocol text states one costly action per turn with the busy
    tool result naming the retry turn. A rejection's candidate list is
    per-action and executable: people who are here for `speak`/`give`,
    contacts plus people here for `text`.
I48 unperformed actions narrated as verified fact (ticket 48) .. test_alias_group_keeps_one_intended_recipient,
                                                               test_unknown_recipient_answer_preserves_the_intent,
                                                               test_verb_gap_teaching_names_the_real_action,
                                                               test_protocol_forbids_narrating_unperformed_actions,
                                                               test_verb_gap_block_matches_the_doc_verbatim,
                                                               test_checker_flags_a_read_claim_without_a_read,
                                                               test_checker_flags_unregistered_named_objects
    d1-am artifact (real-20260930T160727), four independent reviewers:
    a tool call that never succeeded is narrated as a completed, verified
    fact. 宿管阿姨 (i=254/263) said "没见着‘林瑶’俩字" yet all five `read
    晚归登记本` calls were rejected (0 document_read all run); 林瑶 (i=217->229)
    said "柜开了，抄件在我眼前：三通、23:30、目击那行在" while `read/take
    蓝皮夹抄件` were both rejected (the details came from extra 陈大爷's
    mouth); 陈默妈 (i=188/193) said "妈这边拨那号码也不通，空号音" though the
    world has no dial action and she never called, and 陈默 recorded "我和妈
    都拨过"; 辅导员/班长 promised to "在值班簿上补签字", an action the world
    does not model. The world had no "you did not do this" constraint. Fix
    (this lane deliberately adds no NLP gate): (1) the verb gaps are stated
    explicitly — a verb the world lacks maps onto the real action (`text`
    for a distant person, `update_memory` for one's own promise) or an
    explicit unavailable-feedback line names how to be effective; (2) a
    recipient addressed by the actor's own KB nickname/number that does not
    match literally resolves to the one person it denotes, or the rejection
    preserves the recipient intent (never redirects the private body, never
    silently renames); (3) the protocol text says only acts recorded by tool
    calls count; (4) the checker gains two review-only readings (read claimed
    with no document_read; unregistered named object asserted).
H1/H4 empty checkpoint written at launch ...................... test_launch_checkpoint_is_a_valid_loadable_trace
H2  duplicate run artifacts ................................... test_runner (unique run ids)
H3  failed/truncated artifact mislabeled as clean .............. test_trace_completion_gate_rejects_truncated_run (runner)
K1  mystery answer delivered before any read (ticket 47) ...... test_puzzle_answer_leak_fails_seed_lint
    d1-am artifact (real-20260930T160727): 辅导员's first screen `# knowledge`
    carried the audit-case concept desc verbatim ("汇总表两个总额没标用途，
    手写更正没署名，底层凭证不在包里", known_to=[…,辅导员,…]); she wrote the
    conclusion into memory at i=238 without reading the 学生会审计包, so her T6
    "亲眼看看包里是什么" was a formality. Root cause: a puzzle entry's desc is
    handed to its known_to actors as knowledge, and the seed wrote the ANSWER
    there. Fix: the puzzle desc states only the question/visible anomaly; a
    `puzzle: {reveal, answer}` declaration binds the answer clauses to the
    carrier document content, and seed lint turns red if an answer clause
    appears in the desc/memory (leak) or is missing from the reveal (unreachable).
K2  suppression guard unreachable by plot words (ticket 47) ... test_guard_row_unreachable_by_plot_phrase_fails_seed_lint,
                                                               test_hits_cannot_reach_old_street_rep_from_the_plot_sentence
    d1-am artifact: 陈默妈's guardrail row ("具体姓名我记不清了——不该猜的就不
    猜") was keyed only [老街坊代表]; 陈默's SMS asked about "落款签字的街坊代表"
    ("2013年台风撤离…"), so kb.hits never surfaced it and she invented
    "张建国＋1395731xxxx（他儿子）", spreading it to 陈默. Root cause: 陈默妈 is
    remote, so she holds no concept row; the guardrail is a private kb row, and
    hits() only matches row keys, forward or reverse, against the whole query
    text — a long plot sentence containing "街坊代表" cannot reach the longer
    key "老街坊代表". Fix: guard rows carry `triggers` (the plot phrases they
    must answer to) and a key that is a substring of one; seed lint turns red
    when no key is reachable.
K47c persona promises an unregistered prop (ticket 47) ......... test_unregistered_persona_prop_fails_seed_lint
    班长's card promised "志愿报名表、体测表、活动签到表" (and the run reached
    for 考勤表/二班考勤表); none were registered, so he failed three take/hand
    actions (i=230/256/268). Fix: character cards and concept memories may only
    name props from the controlled prop vocabulary that resolve to a registered
    item/concept; seed lint turns red otherwise.
K47d inline manifest content name unchecked (ticket 47) ........ test_unresolved_inline_content_name_fails_seed_lint
    seed_lint scanned only the .md prose files; `content:` scalars on the four
    registers (小满/纪风) were a legal vacuum (registered aliases by luck). Fix:
    name-like tokens in items/documents inline content/desc must resolve to a
    registered entity/concept.
K47e homonym collision is warned, not blocked (ticket 47) ....... test_name_collision_warning_names_the_confusable_pair
    失踪学生「小陈」 shared 陈默's common address "小陈"; 林瑶 conflated them at
    12:42 and the 大爷 had to disambiguate at 12:51 (world #1273/#1277/#1320).
    Fix: registered names that nest or share a surname form emit an advisory
    (non-blocking) collision line for human judgement.
I53 stall gate measured cumulative freeze; one hung decision pinned the clock
                                                             test_hung_decision_is_released_and_the_run_reaches_the_endpoint,
                                                             test_stall_never_trips_on_a_slow_but_progressing_run,
                                                             test_true_stall_is_reported_with_the_inflight_actor_and_duration,
                                                             test_residual_hung_wait_is_bounded_and_the_actor_acts_again,
                                                             test_abandoned_hung_call_is_isolated_from_the_live_session
    real-20261001T015004 froze on the sim clock at 11:32 (turn 248, then no
    turn for 15 wall minutes) with `stall_budget_exceeded` and no
    `decision_timeout` in the turns: 辅导员's live session ends on a 11:32
    `user` world message with no assistant reply (the call simply never
    returned; the same actor had already exhausted the provider retry budget
    at 11:13 and 11:16). Mechanism: `_scheduler_loop` froze on
    `min(_inflight.values())` with no bound — a single decision that never
    returns and holds the oldest wake keeps `min()` constant, so the clock
    never moves; meanwhile `_stall_seconds` was CUMULATIVE freeze wall time
    (`+=`, never reset) and `decision_timeout = worst_case_seconds()*8+5`
    (~4325s/72min) sat ABOVE the stall budget it was supposed to precede, so
    the run died before any timeout could fire. Fix: stall = consecutive wall
    time since the last world advance or completed turn (default 300s,
    `V4_STALL_SECONDS`), so a healthy slow run never trips; the freeze branch
    releases a horizon whose oldest decision exceeded `freeze_tolerance`
    (default min(decision_timeout, 120s), `V4_FREEZE_TOLERANCE_SECONDS`);
    `decision_timeout` is bounded to provider worst case + small margin; the
    `await hung` residual wait is bounded (`V4_HUNG_TIMEOUT_SECONDS`) and
    detaches the actor's session so the character acts again; and every stop
    writes "who was in flight, since when, waited how long, last-progress
    moment, stall definition, threshold hit" to the trace + flushed log.
I54 one provider request had no wall-clock bound (ticket 54) .... test_provider_budget (ProviderWallClockBudgetTests:
                                                               test_trickling_response_is_cut_off_within_the_budget,
                                                               test_normal_response_is_unchanged,
                                                               test_transient_502_retries_the_same_number_of_times,
                                                               test_slow_but_completing_response_succeeds)
    The 11:32 freeze of real-20261001T015004 has a provider-side root: in
    `provider._run_request` the `timeout` passed to `urlopen` is SOCKET-level
    (one connect/recv of silence), NOT an upper bound for the request, and the
    retry-budget check only ran at the TOP of each attempt. `response.read()`
    therefore had no bound at all: an upstream that trickle-feeds or holds the
    connection open keeps it blocked forever. That is exactly the shape of the
    辅导员 leg — its live session ends on a 11:32 `user` message with no
    assistant reply, hours after it had already produced `provider retry
    deadline exhausted after 4 attempts` at 11:13 and 11:16 — so the only
    thing that could stop it was the engine-side fallback of ticket 53 (a
    second layer that wastes a whole turn). Fix: one wall-clock budget per
    call (`_call_budget_seconds()` = `max_duration`, or the retry policy's
    structural worst case when unset); every attempt's socket timeout is
    `min(self.timeout, 剩余预算)`, the body is read one recv-chunk at a time
    (`read1`) with the deadline re-checked between chunks, and exceeding it
    closes the connection and raises the usual retryable metadata
    (`retry_exhausted=True`, `attempts=N`) with a message that names the
    elapsed budget so "upstream slow" is distinguishable from "upstream
    hung". `worst_case_seconds()` is unchanged in value (budget + one final
    socket timeout) and stays a true bound.
E55 checkpoint KeyError while the extra answers (ticket 55) . test_checkpoint_during_extra_answer_does_not_raise_and_resumes,
                                                               test_executing_engine_task_crash_ends_the_process_without_a_zombie
    real-20261001T055020 died at sim 09:14–09:19: `runs/real-
    20261001T055020….error.log` shows `checkpoint_state` line 2153 raising
    `KeyError: 'pending_question'`, which killed the scheduler task and froze
    the world (the extra was mid-answer at 09:14–09:19; the checkpoint
    landed at 06:16 wall). `_extra_loop` consumed the pending
    question with `pop` before its turn, so the answering window had no such
    key by design, while `checkpoint_state` read the extra fields with direct
    subscripts; E50's round-trip test checked in right after generation and
    never entered that window (green test, red production). The process then
    stayed RUNNING because the provider call sat in `asyncio.to_thread`'s
    non-daemon worker thread, which `concurrent.futures` joins at interpreter
    exit. Fix: serialize the four live fields with the same `.get(...)`
    defaults `_rehydrate_extra` uses (round-trip identity), clear the pending
    question instead of deleting it so "all runtime fields always exist" is
    an invariant, and park provider calls on daemon threads (`_run_blocking`)
    so a dead engine task ends the process with its non-zero status instead of
    leaving a zombie.
T56 private reasoning in the assistant正文 was broadcast (ticket 56) . test_private_reasoning_is_flagged_with_a_marker,
                                                               test_genuine_speech_is_never_flagged,
                                                               test_private_line_is_never_broadcast,
                                                               test_body_lands_in_the_private_turn_record,
                                                               test_self_correction_note_states_the_rule,
                                                               test_protocol_marker_scope_excludes_concealment,
                                                               test_protocol_text_in_speak_is_never_broadcast,
                                                               test_protocol_text_in_text_is_never_sent,
                                                               test_genuine_speak_text_still_goes_out,
                                                               test_genuine_text_message_still_goes_out,
                                                               test_concealment_in_speak_text_is_not_withheld
    real-20261001T065553, five independent reviewers: the `inner` FIELD was
    clean (ticket 38) but the model wrote private reasoning into the assistant
    PLAIN TEXT, which T1 broadcasts as `speak`. 陈默 i=402 ("回答要挑着说…
    我一个字不碰") heard=[班长,食堂大妈]; 林瑶 i=139 ("这层先记在自己本子里，
    不急着对陈默说") heard=[陈默]; 林瑶 i=319 ("记忆调用格式错了——指令词得
    单独占一格") heard=[辅导员,陈默]; 下棋大爷's 11 self-talks reached
    食堂大妈. The 辅导员 session is the control: empty content, inner in the
    field, no leak. Fix: (1) §1 states plainly that the body is only spoken
    words and plans/judgements/asides/protocol talk go in the call's `inner`;
    (2) a high-precision harness guard withholds such a line from `speak` —
    recording it in that actor's private turn, counting it, and showing the
    actor one self-correction — while genuine lines, including
    "（把热美式推过吧台）给，趁烫。" and "我先走了。", still broadcast.
    Extension (this lane, per the acceptance review): the protocol/tool
    meta-reasoning markers alone also apply to the `text` argument of
    `speak`/`text` — such a line is a formatting error, never a line or a
    message, so it is withheld (not spoken, not sent) with the same private
    record, self-correction and count; the concealment/plan markers stay
    plain-content-only (a person may say "我不能让他们知道" aloud). A lone
    "格式" never triggers — only the 格式错 pairing does.
T64 plain正文 was the speech channel: 169/265 speeches were narrated (ticket 64)
                                                               test_real_broadcast_bodies_are_never_speech,
                                                               test_body_is_recorded_privately_with_the_suspect_flag,
                                                               test_plan_body_without_address_gets_no_self_correction,
                                                               test_body_is_private_even_alongside_a_speak_call,
                                                               test_speak_call_still_speaks,
                                                               test_text_call_still_sends,
                                                               test_coarse_self_narration_screen_reads_but_never_blocks,
                                                               test_transitional_note_states_the_rule,
                                                               test_prompt_states_body_is_private_and_stays_verbatim,
                                                               test_checker_reports_unspoken_body_and_coarse_screen
    d1-am artifact (real-20261001T121425+0800-223688-090345540): 265 speech
    events, 96 from explicit speak/text calls and 169 from plain content via
    the old T1 ruling. The 169 were largely narration/plans that nobody should
    have heard — 陈默 07:59 "…登记本被拿走的事她可能知道。当面问，比发短信快。"
    (heard=['林瑶']), 陈默 08:06 "我必须先认账…", and 辅导员 12:09's private
    judgement, which 唐小岚 12:11 then acted on (cross-actor pollution). Ticket
    56's narrow guard missed all of them (it matched protocol words + explicit
    concealment pledges, not ordinary planning). Fix: flip the default — plain
    content is the actor's PRIVATE thought (recorded as `content_private`,
    never broadcast); only `speak`/`text` calls speak. A turn whose only speech
    attempt is a body that reads like addressed speech (quoted dialogue or a
    second-person address) gets ONE transitional self-correction. Ticket 56's
    protocol guard stays as the `text`-argument second line; a coarse
    self-narration screen on delivered speak/text lines is read-only telemetry
    (never gates, never blocks) so a future run can show whether the model
    starts dictating plans into `speak`.
E57 extras could only speak, so they narrated physical acts as done  (ticket 57)
                                                               test_the_kernel_already_offers_move_to_an_extra,
                                                               test_a_declared_departure_is_a_real_visible_move,
                                                               test_the_recorded_turn_carries_real_affordances_and_perception,
                                                               test_scene_briefing_grounds_a_stated_quantity,
                                                               test_a_rejected_action_is_reported_back_for_one_correction,
                                                               test_scene_perception_grants_no_more_than_co_location
    real-20261001T065553, three independent reviewers: `_extra_turn`
    hardcoded `affordances=[]` / `perception={events:[],inbox:[],
    nearby_actors:[]}` and iterated the reply with `if call_name !=
    "speak": continue`, while the extra tool surface was SPEAK_TOOLS. So
    孙学长 announced the window seat four times (location always 半坡咖啡馆,
    no move/leave event), 陈大叔 said "我先回去看书了啊" and was recycled by
    `extra_removed reason=idle`, and 何大叔 called one 校报草稿 "一摞". The
    kernel was never the cause — `affordances(extra)` already returned
    `move`; the harness discarded it. Fix: EXTRA_TOOLS (speak + move/take/
    place/give, no memory tools), the extra turn executes every offered verb
    through the kernel (world timing completes a move as leave/enter), a
    rejected verb is handed back for one self-correcting reply, the trace
    records the real scene perception + affordances, and the scene block
    carries the entity descriptions so a quantity is grounded (一份, not
    一摞). Moving away keeps the existing partner_gone/idle recycle path,
    whose event is visible to the room.
K60 location prose promised props the world could not produce (ticket 60)
                                                              test_shipped_seed_declares_the_scanner_and_cabinet_unusable,
                                                              test_an_asserted_interior_prop_without_a_registration_fails_seed_lint,
                                                              test_registering_a_promised_interior_prop_turns_the_same_prose_green,
                                                              test_unregistered_interior_props_still_offer_a_real_next_call,
                                                              test_the_registered_pen_and_paper_stay_in_the_student_union_office
    d1-am artifact (real-20261001T065553): 陈默 read 扫描仪 / 扫描仪日志 four
    times inside 43 minutes in 校史档案室, 林瑶室友 read 校史专用柜 /
    专用柜登记本 in 图书馆, and 辅导员 tried `take 桌上的白纸和笔` / `take
    纸笔` in the archive. All three names lived only in the room's prose
    (world/locations/校史档案室.md, world/locations/图书馆.md) plus the archive
    extra's knowledge note "扫描仪用法"; no entity backed them, so the world
    answered "这里没有这件东西" and the room read as broken. Ticket 47's lint
    covered character cards (K47c) and inline manifest content (K47d), never a
    location body. Fix: (1) seed_lint scans the interior detail (the
    paragraphs after the ticket-58 public brief) for a controlled prop
    vocabulary (the ticket-47 props plus 扫描仪/专用柜) and requires each hit to
    resolve to a registered entity/concept or to sit in a sentence that says
    it cannot be used here (不在本房间/坏了/管理员收着); (2) the seed states the
    truth — the scanner is out for repair ("平时扫描仪的待机灯常绿，这几天机器
    送修了"), the library cabinet is locked with its key at the 借阅处's
    student 馆员, and the archive has no spare pen and paper while naming where
    the registered 可用纸笔 lives — so 可用纸笔 stays in 学生会办公室 only
    ("不要两边都放"); (3) the archive extra's knowledge note no longer
    advertises 扫描仪用法. Residual, deliberately NOT fixed in this lane: a
    `read` of an invented name in a room with nothing readable (图书馆) has no
    executable alternative to offer; the room's own arrival detail names the
    lock and its key-holder instead.
I63 same-kind failures and the serve/verb gap (ticket 63) ..... test_same_kind_rejections_with_different_args_stagnate,
                                                               test_same_kind_rejections_only_fire_on_the_stride,
                                                               test_alternating_kinds_never_accumulate,
                                                               test_a_successful_same_kind_action_clears_the_rejection_run,
                                                               test_successful_other_actions_do_not_clear_a_rejected_run,
                                                               test_normal_multi_target_text_and_speak_never_trip,
                                                               test_rejected_kind_state_round_trips,
                                                               test_same_kind_rejections_reach_the_chain_path_notice,
                                                               test_a_present_item_can_be_served_with_give,
                                                               test_give_never_invents_an_absent_item,
                                                               test_notice_board_read_rejection_offers_a_real_next_step
    d1-am artifact (real-20261001T121425+0800-223688-090345540): four examples.
    (1) 下棋大爷/食堂大妈/宿管阿姨 each re-asked for 尼龙绳 in a different
    wording (尼龙绳 / 一卷尼龙绳 / 捆货用的绳子 / 值班室的粗尼龙绳) and every
    attempt was refused; the repetition aware monitor keyed on the EXACT
    (kind, args), so a changed parameter was a brand-new action and none of the
    six refused `take`s produced any notice. (2) 食堂大妈 asked to remove food
    four times (一碗豆浆、一个菜包、一个豆沙包 / 荤菜、素菜、米饭、一碗汤 / …)
    because she was serving her window counter and the world only had `take`
    (pick up) and `give` (hand over what you hold), with no path for a thing
    that is already at hand. (3) 班长 read 教学楼正门内侧公告栏 and 陈默 read
    公告栏底下的过期通知 — a location-level notice board is not a registered
    document, and the 教学楼 rejection listed nothing readable at all, so it
    offered no executable next step. Fix: (1) a refused-action run is counted
    by kind, not by exact args — three refusals of the same kind fire one
    stagnation notice that names what is really here, what is really readable
    and the other actions still available; only refused actions count, a
    successful same-kind action clears the run, and `text`/`sleep` stay exempt
    so normal multi-target messaging never trips it; (2) `give` hands over an
    item that is physically at the actor's own location (an atomic pick-up and
    hand-over), never an item that is neither held nor here; (3) a refused
    `read` of an unregistered, unreadable thing falls back to the real actions
    available here (take what is present / speak to someone here / move to a
    reachable open place) so the answer always has an executable step.
I65 the canteen/shop modeled no item, so serving was narrated (ticket 65)
                                                               test_the_canteen_can_hand_a_meal_to_someone_present,
                                                               test_the_shop_backs_its_brief_with_takeable_goods,
                                                               test_rope_is_declared_unavailable_where_it_was_reached_for,
                                                               test_a_real_handover_the_same_day_suppresses_the_reading,
                                                               test_ordinary_completeness_and_conditional_phrases_do_not_fire,
                                                               test_report_carries_the_handover_reading
    real-20261001T121425+0800-223688-090345540: 食堂大妈 failed seven
    take/give attempts for food and rope (`take 一碗豆浆、一个菜包、一个豆沙包`,
    `take 荤菜、素菜、米饭、一碗汤`), then said "豆浆包子趁烫，端好" with zero
    events behind it — the whole log holds no `item_given`. 小卖部 likewise
    promised 零食/饮料/关东煮 in its brief, and rope (下棋大爷's stone-table coil,
    宿管阿姨's corner toolbox) was a category the world never modeled, so the
    model promised it and dead-ended on every take. Fix: the canteen has a real
    take/give-able 一份餐食 and the shop a minimal stock, both placed so a service
    hand-over is an `item_given` event (ticket 63's at-hand `give` has a real
    object); the two rooms where rope was reached for state in their interior
    detail (ticket 60 wording) that there is no rope there; and the checker adds
    a review-only count of a same-day hand-over assertion with no corresponding
    `item_given` ("端好" as narration). The metric reads only, never blocks.
I66 contact/route dead ends: 李阿姨 unreachable, contacts asymmetric, 305宿舍 missing
                                                               test_unreachable_names_get_a_story_executable_alternative,
                                                               test_a_one_way_address_book_is_flagged_and_hinted,
                                                               test_a_room_number_is_reachable_or_explained
    real-20261001T121425+0800-223688-090345540: 陈默妈 left three routes to
    李阿姨 all dead — `knock 李阿姨家` and `text 李阿姨` (unknown name) and
    `move 老家属院` ("没有可用的路", no alternative, no reason), so her
    storyline goal "给李阿姨带话" could never complete and nothing corrected
    her. 宿管阿姨 messaged 下棋大爷 fine, but her reply came back `unknown name
    '下棋大爷'` because the address book is one-way (下棋大爷's contacts hold
    her; hers hold only 林瑶/陈默) — the borrowed-rope thread dead-ended. 林瑶
    室友 `move 305宿舍` → "不是一个你知道的地方" for her own room. Fix: the seed
    declares each unreachable name's reason + executable alternative
    (`unreachable_targets`) and the kernel appends it to the text/move/knock
    rejection; a received-but-unrecorded sender is surfaced to the recipient
    (with the `update_memory` call to close the gap) and seed lint lists one-way
    address books; 305宿舍's rejection names the building it lives in.
I67 wall clock starved by the in-flight freeze wait (ticket 67)
                                                               test_wall_deadline_fires_while_the_inflight_wait_never_releases,
                                                               test_max_turns_is_not_starved_by_the_same_inner_wait
    real-20261001T163024+0800-629102-384711601: the wall-clock/stall/max_turns/
    stop_at checks ran once per OUTER scheduler pass, while an in-flight
    decision kept the loop inside `while ... min(active)==target` until the
    ticket-53 release bound (`freeze_tolerance`). A never-resolving oldest
    wake therefore delayed the 2h safety stop (that run ended 12s late; the
    starvation window is the whole release bound). Fix: `_stop_check` runs
    inside the inner wait loop too, `_freeze_poll`/`_await_activity` cap their
    timeout by the remaining wall budget, and the stop diagnostic reports
    `max_wall_seconds`/`wall_overrun_seconds`.
I68 `private_state.memories` is a legacy v3 slot, not the v4 memory store
                                                               test_written_memory_row_is_visible_in_the_trace_notebook,
                                                               test_turn_annotates_the_real_store_next_to_the_legacy_field,
                                                               test_saved_artifact_carries_the_knowledge_section,
                                                               test_health_report_reads_kb_rows_apart_from_the_legacy_field
    real-20261001T163024+0800-629102-384711601: multiple reviewers read the
    always-empty `private_state.memories` as "update_memory 报成功但静默丢写"
    (a false P1). v4 memory lives in the engine KB (`runner.kb[actor].rows`, 38
    rows for 唐小岚) and `update_memory` returned `submitted` with
    `memory_rejections: []`. Fix: the trace carries the real notebook as a
    `knowledge` section and every v4 turn's private_state names the store
    (`memory_store: engine-kb`, `knowledge_rows: N`) right beside the legacy
    empty list; docs state where memory lives; the checker adds a review-only
    KB-rows vs legacy-memories reading.
"""

import json
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.agent_state import PrivateState
from harness.engine import TICK_SECONDS, AsyncEngine, _call_pool
from harness.kernel import ActionRejected, ActorState, Intention, LocationState, World
from harness.runner import AgentFn, Runner
from harness.seed import load_story_pack
from harness.system import DIALOGUE_REPLIES, Ledger
from harness.trace import Trace, verify_event_log
from harness.replay import replay_world

# The v4 project root (harness/tests/ -> harness/ -> v4), for subprocess gates.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _FlashbackProbe:
    """Binds AsyncEngine._flashback_query to a bare world (the method touches
    only self.world.history_log and self._flashback_pool)."""

    def __init__(self, world, kb=None):
        self.world = world
        self._flashback_pool = {}
        self._kb = kb or {}

    flashback_for = AsyncEngine._flashback_query


def engine_of(world):
    return _FlashbackProbe(world)


def _lean_wait_agents(world) -> "dict[str, AgentFn]":
    """Deterministic agents that accept the System once, then wait."""
    def agent(state, perception, affordances):
        offered = {str(option.get("kind")) for option in affordances}
        if state.actor_id == "陈默" and "system_accept" in offered:
            return Intention(state.actor_id, "system_accept",
                             {"case": "ambiguous-obligations"}, perception["world_version"])
        return Intention(state.actor_id, "wait", {"duration_seconds": 3600},
                         perception["world_version"])
    return {actor: agent for actor in world.actors}


class HistoricalFailureGates(unittest.TestCase):
    """Regression gates for failures documented in v1/v2/v3 audits and issues."""

    def test_deterministic_seed_run_reaches_seeded_endpoint(self):
        """F9/P1/P3: the seed schedule drains to world_stops with real effects."""
        pack = load_story_pack()
        world = pack.build_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        ledger = Ledger(pack.system.get("facts", {}), pack.system)
        endpoint = max(str(e["time"]) for e in pack.manifest["scheduled"]
                       if e["event"] == "world_stops")   # 多日弧线：最后一个日界
        trace = Trace("v3-test", "historical-gate-endpoint")
        # v3 Runner 没有 world_stops 早停：排干到终点即证明
        # （verify_complete 校验终点时刻与 stop 事件存在）。
        reason = Runner(world, _lean_wait_agents(world), states, trace, ledger).run(
            stop_at=datetime.fromisoformat(endpoint), max_turns=100_000)
        # 排干原因随 tick 对齐在 queue_drained / stop_at_reached 间摆动，
        # 两者同为"排程排干到日界"的证明。
        self.assertIn(reason, {"queue_drained", "stop_at_reached"})
        self.assertEqual(world.now.isoformat(), endpoint)
        trace.verify_complete(world, endpoint=endpoint, stop_event="world_stops")
        trace.verify_no_agent_errors()
        self.assertEqual(world.now.isoformat(), endpoint)

    def test_async_engine_seed_run_reaches_seeded_endpoint(self):
        """F9/P1 on the production driver (V4-ENGINE §8): the async DES
        engine drains the same seed to the same endpoint."""
        pack = load_story_pack()
        world = pack.build_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        ledger = Ledger(pack.system.get("facts", {}), pack.system)
        endpoint = max(str(e["time"]) for e in pack.manifest["scheduled"]
                       if e["event"] == "world_stops")   # 多日弧线：最后一个日界
        trace = Trace("v4-test", "historical-gate-endpoint-async")
        engine = AsyncEngine(world, _lean_wait_agents(world), states, trace, ledger)
        reason = engine.run(stop_at=datetime.fromisoformat(endpoint)
                            + timedelta(seconds=TICK_SECONDS + 1), max_turns=100_000)
        self.assertEqual(reason, "world_stops")
        self.assertEqual(world.now.isoformat(), endpoint)
        trace.verify_complete(world, endpoint=endpoint, stop_event="world_stops")
        trace.verify_no_agent_errors()
        self.assertEqual(world.now.isoformat(), endpoint)

    def test_no_accepted_action_reports_no_immediate_physical_change(self):
        """F2: accepted actions always carry a concrete consequence sentence."""
        world = load_story_pack().build_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        feedback = []
        steps = {actor: 0 for actor in world.actors}

        def agent(state, perception, affordances):
            if state.actor_id == "陈默":
                step = steps[state.actor_id]
                steps[state.actor_id] += 1
                if step == 0:
                    return Intention("陈默", "wait", {"duration_seconds": 60},
                                     perception["world_version"])
                if step == 1:
                    return Intention("陈默", "leave_note",
                                     {"text": "签名墨迹深浅不一，2013年撤离通知的签名要再查。"},
                                     perception["world_version"])
                if step == 2:
                    return Intention("陈默", "place", {"item": "2013年邻里撤离通知书"},
                                     perception["world_version"])
                if step == 3:
                    return Intention("陈默", "text",
                                     {"target": "林瑶", "text": "The form is filed."},
                                     perception["world_version"])
                if step == 4:
                    return Intention("陈默", "read", {"item": "2013年邻里撤离通知书"},
                                     perception["world_version"])
                if step == 5:
                    # ticket 10 拆分宿舍：男生宿舍与校史档案室不相邻，改去中庭。
                    return Intention("陈默", "move", {"target": "中庭"},
                                     perception["world_version"])
            return None

        def recorder(state, perception, affordances):
            return agent(state, perception, affordances)

        def record_world_result(message):
            feedback.append(message)

        setattr(recorder, "record_world_result", record_world_result)
        agents: dict[str, AgentFn] = {actor: (recorder if actor == "陈默" else agent)
                                      for actor in world.actors}
        trace = Trace("v4-test", "historical-gate-feedback")
        Runner(world, agents, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T20:00:00+08:00"), max_turns=1000)
        # v4 (V4-DESIGN §2): accepted actions have no receipts; every
        # outcome is narrated in the next perception with a timestamp.
        from harness.prompt import render_world_message
        rendered = " ".join(render_world_message(t["perception"], [])
                            for t in trace.agent_turns if t["actor"] == "陈默")
        self.assertTrue(all("no immediate physical change" not in m for m in feedback))
        self.assertIn("7:01", rendered)      # wait outcome shows as time advanced
        self.assertIn("陈默 留下一张字条（内容仅对下一位进入者可见，阅后即焚）",
                      rendered)  # room-message note template (F3, ruling 2026-09-22)
        self.assertIn("放下", rendered)           # drop consequence
        self.assertIn("短信已送达 林瑶（手机）", rendered)  # message delivery (sender receipt)
        self.assertIn("读了 2013年邻里撤离通知书", rendered)  # document read
        self.assertIn("进入 中庭", rendered)      # move arrival（中庭，与男生宿舍直连）

    def test_rejected_loop_is_safe_and_instructive(self):
        """F5/P2: a stubborn agent keeps rejecting with actionable reasons,
        never produces an engine error, and never freezes the world."""
        world = load_story_pack().build_world()
        states = {actor: PrivateState(actor) for actor in world.actors}

        def stubborn(state, perception, affordances):
            if state.actor_id == "陈默":
                # v4 slice: "nowhere" does not exist; the reason must keep
                # tracking state (reachable set) instead of repeating stale text.
                return Intention("陈默", "move", {"target": "nowhere"},
                                 perception["world_version"])
            return None

        trace = Trace("v3-test", "historical-gate-rejected-loop")
        Runner(world, {actor: stubborn for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-21T10:00:00+08:00"), max_turns=2000)
        turns = [turn for turn in trace.agent_turns if turn["actor"] == "陈默"]
        self.assertTrue(turns)
        self.assertTrue(all(turn["result"] == "rejected" for turn in turns))
        self.assertTrue(all(turn["error"] for turn in turns))
        self.assertFalse(any(event.kind == "action_started" for event in world.event_log))
        # Rejection feedback tracks state instead of repeating one stale reason:
        # while the basement is closed the reason says so; after it opens on
        # March 18 the reason becomes a path explanation. This is the regression
        # for the v2/v3 pattern of re-attempting one illegal move unchanged.
        reasons = [turn["error"] for turn in turns]
        # The reason names the target and the reachable set (state-tracking,
        # not a stale template).
        self.assertTrue(any("nowhere" in reason for reason in reasons))
        # v4 kernel 对未知地点的措辞：点名 + 从当前地点可达的集合。
        self.assertTrue(any("不是一个你知道的地方" in reason for reason in reasons))
        self.assertTrue(any("从男生宿舍可以到" in reason for reason in reasons))
        # The world still advanced through the schedule; one stuck actor is not a deadlock.
        self.assertGreaterEqual(world.now.isoformat(), "2026-03-16T12:00:00+08:00")

    def test_flashback_recalls_seeded_history_and_resolves_aliases(self):
        """P9: the documented v4 day-run failure — 陈默 flips through the
        whistle's memories and gets "（没有与你经历相关的可回放历史。）" even
        though 红色哨子/老街坊 are seeded. flashback must read the actor's own
        KB (pre-run memory), resolve aliases, and stay scoped to that actor."""
        pack = load_story_pack()
        world = pack.build_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        engine = AsyncEngine(world, _lean_wait_agents(world), states,
                             Trace("v4-test", "historical-gate-flashback"),
                             kb_seeds=pack.kb)
        engine._init_kb(world.now)
        whistle = engine._flashback_query("陈默", "红色哨子")
        self.assertTrue(whistle, "flashback on the seeded whistle returned nothing")
        self.assertTrue(any("红色哨子" in line for line in whistle))
        # An alias must reach the same registered concept/memory.
        self.assertTrue(engine._flashback_query("陈默", "老街坊"))
        # 林瑶 never lived through 陈默's private memories.
        self.assertFalse(engine._flashback_query("林瑶", "听见的哭声"))
        # A name nobody knows stays empty rather than inventing history.
        self.assertEqual(engine._flashback_query("陈默", "不存在的东西"), [])

    def test_seed_closed_locations_all_have_a_scheduled_opening_effect(self):
        """I02/P4: no seed location may be a permanent dead-end."""
        pack = load_story_pack()
        closed = [row["id"] for row in pack.locations if not row.get("open", True)]
        # I02/P4 的不变量：封闭地点不得是永久死路。v4 首验日没有封闭地点，
        # 不变量退化为空集成立；种子包将来加封闭地点时必须配 scheduled opening。
        opened = {str(effect["id"]) for row in pack.scheduled
                  for effect in row.get("effects", []) if effect.get("op") == "open_location"}
        self.assertEqual(opened, set(closed),
                         "every closed location must have a scheduled opening effect")

    def test_audit_slip_delivery_requires_a_scheduled_relay(self):
        """E72a / ticket 72 (report §5.3): add_document placement is not
        delivery. 审计催办单 landed at 学生会办公室 (audit_deadline, no
        target) while 陈默's registered post was 校史档案室 and nothing
        scheduled him there — the d1-审计催办转达 anchor counted 0 relays
        with lint green. Invariant: a seed document an anchor depends on
        must have a later scheduled relay whose target names the
        responsible actor and whose notice carries both the slip and the
        duty (转告辅导员). Deleting the 16:05 audit_relay_task, or its
        target, must go red here."""
        pack = load_story_pack()
        placed_at = None
        for row in pack.scheduled:
            if row.get("time") is None:
                continue
            if any(effect.get("op") == "add_document"
                   and effect.get("id") == "审计催办单"
                   for effect in row.get("effects", [])):
                placed_at = datetime.fromisoformat(str(row["time"]))
        self.assertIsNotNone(placed_at, "审计催办单 must be placed by the seed")
        relays = []
        for row in pack.scheduled:
            if row.get("time") is None:
                continue
            when = datetime.fromisoformat(str(row["time"]))
            if when <= placed_at:
                continue
            targets = row.get("target")
            targets = [targets] if isinstance(targets, str) else list(targets or [])
            notice = str(row.get("notice", ""))
            if ("陈默" in targets and "审计催办单" in notice
                    and "辅导员" in notice):
                relays.append(row)
        self.assertTrue(
            relays,
            "审计催办单 has no scheduled relay to 陈默 "
            "(target + notice with slip and duty) — placement alone is not delivery")

    def test_speech_anchor_requires_a_scheduled_occasion(self):
        """E72b / ticket 72 (report §6.3): a passing read path is not a
        speech occasion. 林瑶 read the audit pack 12 times while the pm
        gate's speech needles counted 0 — no D1 scene ever opened the
        substance to a speakable, co-present exchange. Shape for seed
        authors: an anchor scoring 说 must schedule an occasion; here
        audit_pack_review (16:20, open broadcast at 学生会办公室, any
        bystander may pick it up). Deleting that occasion — or narrowing
        it with a target so 林瑶 can no longer hear it — must go red."""
        pack = load_story_pack()
        window = (datetime.fromisoformat("2026-03-16T13:00:00+08:00"),
                  datetime.fromisoformat("2026-03-16T22:00:00+08:00"))
        occasions = []
        for row in pack.scheduled:
            if row.get("time") is None:
                continue
            when = datetime.fromisoformat(str(row["time"]))
            if window[0] <= when <= window[1] and "审计包" in str(row.get("notice", "")):
                occasions.append(row)
        self.assertTrue(occasions,
                        "audit substance has no pm speech occasion in the seed")
        self.assertTrue(all(not row.get("target") for row in occasions),
                        "the audit occasion must stay open (no target narrowing)")

    def test_take_race_second_completion_does_not_crash_the_clock(self):
        """E75 / ticket 75 (2026-10-16 d1-pm run real-20261016T192137 live
        red) + E102 / ticket 98 (window 5 17:57, run real-20261018T062031).

        Original red: two actors legitimately queued ``take 可用纸笔`` in the
        same tick — both standing at 学生会办公室 while the item was present,
        so both submits passed validation; the first completion deleted the
        item and the second raised KeyError, killing the run at 16:07. The
        guard then was "a completion whose item is already gone stands as an
        event and mutates nothing".

        Ticket 98 收紧了这个不变量：**第二次提交不再被接受**（`take` 从提交到
        完成独占这一件，第二次拿会被告知它在谁手里）——回执说成功、世界没变
        正是窗口 5 辅导员“我们都拿了晚饭”的成因。完成期的防御分支保留不动，
        因为它仍是恢复旧检查点（那里可能真的排着两条 take）时的唯一防线；
        这里直接喂给它第二次完成，钉住“不崩钟、也不改世界”。
        """
        start = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
        w = World(start=start,
                  actors=[ActorState("a", "room"), ActorState("b", "room")],
                  locations=[LocationState("room")])
        w.item_locations["纸笔"] = "room"
        w.submit(Intention("a", "take", {"item": "纸笔"}, w.version))
        with self.assertRaises(ActionRejected):
            w.submit(Intention("b", "take", {"item": "纸笔"}, w.version))
        w.advance()
        self.assertIn("纸笔", w.actors["a"].inventory)
        self.assertNotIn("纸笔", w.actors["b"].inventory,
                         "the second taker finds the spot empty")
        self.assertNotIn("纸笔", w.item_locations)
        w._complete("b", {"action": "take", "item": "纸笔"})   # 旧检查点的排队完成
        self.assertNotIn("纸笔", w.actors["b"].inventory,
                         "第二次完成只作为事件成立，世界不变的防御仍成立")
        completes = [e for e in w.event_log
                     if e.kind == "action_completed"
                     and str((e.payload or {}).get("action")) == "take"]
        self.assertEqual(len(completes), 1, "只有一次 take 真的发生")

    def test_uncovered_concrete_prop_claim_blocks_the_seed(self):
        """Issue 35 / P10: an objective "X 在 Y" claim whose prop is not a
        placed entity is a pre-run block, not a runtime surprise. The regression
        deletes the 签到本 placement while keeping the shift notice that asserts
        it; seed lint must go red with the prop named."""
        import importlib.util
        import shutil
        spec = importlib.util.spec_from_file_location(
            "seed_lint_gate", Path(__file__).parents[2] / "scripts" / "seed_lint.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = Path(__file__).parents[2] / "world"
        self.assertEqual(module.lint(source), [], "the shipped seed must be covered")
        with TemporaryDirectory() as directory:
            root = Path(directory) / "world"
            shutil.copytree(source, root)
            manifest = root / "manifest.yml"
            broken = manifest.read_text(encoding="utf-8").replace(
                "- id: 签到本\n  location: 校史档案室\n",
                "- id: 签到本\n  location:\n", 1)
            manifest.write_text(broken, encoding="utf-8")
            findings = module.lint(root)
            self.assertTrue(findings, "an unplaced 签到本 must fail the seed gate")
            self.assertIn("签到本", findings[0])

    def test_seed_route_graph_is_connected(self):
        """P5: any two characters can reach a common place; co-location is feasible."""
        pack = load_story_pack()
        # remote 地点（陈默家）是电话钩子，不参与步行连通性。
        nodes = {row["id"] for row in pack.locations if not row.get("remote", False)}
        graph = {node: set() for node in nodes}
        for row in pack.routes:
            if row["from"] in graph and row["to"] in graph:
                graph[row["from"]].add(row["to"])
                graph[row["to"]].add(row["from"])
        seen = set()
        stack = [next(iter(graph))]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(graph[node] - seen)
        self.assertEqual(len(seen), len(graph),
                         "route graph must be connected so characters can meet")

    def test_memorial_notices_prompt_attendance_without_pretending_it_happened(self):
        """3/22 director notices must not pre-play named actors' choices.

        Scheduled targets are delivery scopes, not presence conditions. Keep
        the beats as invitations/program notes and preserve the actual walk
        from 中庭 to 河堤 instead of narrating that it already happened.
        """
        pack = load_story_pack()
        by_event = {str(row["event"]): row for row in pack.manifest["scheduled"]
                    if str(row.get("time", "")).startswith("2026-03-22")}
        event_ids = ("memorial_morning", "old_neighbors_arrive",
                     "whistle_recognition", "memorial_ceremony", "evening_walk")
        self.assertTrue(all(event in by_event for event in event_ids))

        obsolete_claims = {
            "memorial_morning": ("拿着流程表逐项核对",
                                 "把档案室里批过的展品一件件搬下来"),
            "old_neighbors_arrive": ("站了很久，指着其中一张说",),
            "whistle_recognition": ("下棋大爷认出了", "三花流浪猫叼来的"),
            "memorial_ceremony": ("林瑶主持", "陈默念当年的撤离时间线"),
            "evening_walk": ("林瑶和陈默沿着河堤慢慢走",),
        }
        for event, fragments in obsolete_claims.items():
            for fragment in fragments:
                with self.subTest(event=event, fragment=fragment):
                    self.assertNotIn(fragment, by_event[event]["notice"])

        ceremony = by_event["memorial_ceremony"]
        self.assertEqual(ceremony["target"], ["林瑶", "陈默", "唐小岚"])
        self.assertIn("待执行安排", ceremony["notice"])
        self.assertIn("未在中庭时收到这条", ceremony["notice"])
        self.assertIn("不代表你已到场", ceremony["notice"])
        self.assertIn("通知书原件", ceremony["notice"])
        self.assertNotIn("代签通知书", ceremony["notice"])

        river_notice = by_event["evening_walk"]["notice"]
        self.assertIn("中庭", river_notice)
        self.assertIn("河堤", river_notice)
        self.assertIn("实际会合", river_notice)
        routes = {(row["from"], row["to"]): row["duration_seconds"]
                  for row in pack.routes}
        self.assertEqual(routes[("中庭", "河堤")], 900)
        self.assertIn("约15分钟", river_notice)

    def test_text_without_target_is_helpful(self):
        """P7: a send_message missing its target (or using a wrong key like
        ``to``) must reject with a schema-derived reason that names the
        required ``target`` key, never the opaque 'unknown actor: None' seen
        in the first tuned probe."""
        from harness.kernel import ActionRejected, ActorState, Intention, LocationState, World
        world = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                      actors=[ActorState("a", "room", known_contacts={"b"}),
                              ActorState("b", "far")],
                      locations=[LocationState("room"), LocationState("far")])
        with self.assertRaises(ActionRejected) as ctx:
            world.submit(Intention("a", "text",
                                   {"text": "hello"}, world.version))
        self.assertIn("target", str(ctx.exception))
        with self.assertRaises(ActionRejected) as ctx:
            world.submit(Intention("a", "text",
                                   {"to": "b", "text": "hello"}, world.version))
        self.assertIn("target", str(ctx.exception))
        self.assertIn("to", str(ctx.exception))
        with self.assertRaises(ActionRejected) as ctx:
            world.submit(Intention("a", "give", {"item": "x"}, world.version))
        self.assertIn("target", str(ctx.exception))

    def test_document_action_with_wrong_key_is_helpful(self):
        """P8: read/copy/annotate submitted with the wrong argument key
        (e.g. ``item`` instead of ``document``) must reject with a
        schema-derived reason naming the required ``document`` key, never the
        opaque 'None is not available' seen across the 2-day run."""
        from harness.kernel import ActionRejected, ActorState, Intention, LocationState, World
        world = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                      actors=[ActorState("a", "room")],
                      locations=[LocationState("room")],
                      document_defs={"ledger": {"title": "Ledger", "content": "x",
                                                "reading_seconds": 2}},
                      item_locations={"ledger": "room"})
        for kind in ("read", "leave_note"):
            args = {"doc": "ledger"} if kind == "read" else {"doc": "ledger", "text": "x"}
            with self.assertRaises(ActionRejected) as ctx:
                world.submit(Intention("a", kind, args, world.version))
            self.assertIn("'doc'", str(ctx.exception), kind)
            if kind == "read":
                self.assertIn("'item'", str(ctx.exception), kind)

    def test_turn_305_held_register_reads_and_remote_document_is_not_offered(self):
        """I39/I40: at turn 305 陈默 held 签到本 in 食堂, yet `read 签到本`
        was rejected "不在你手边" while the suggestion list offered 移交存根
        (archive, not held). A held readable item must read; a readable
        document the actor is not holding must never be suggested."""
        from harness.kernel import ActionRejected
        world = load_story_pack().build_world()
        chen = world.actors["陈默"]
        chen.location = "食堂"
        world.item_locations.pop("签到本", None)
        chen.inventory.add("签到本")
        world.submit(Intention("陈默", "read", {"item": "签到本"}, world.version))
        world.advance()
        self.assertEqual([e.payload["document"] for e in world.event_log
                          if e.kind == "document_read"], ["签到本"])
        offered = {row["item"] for row in world.affordances("陈默")
                   if row["kind"] == "read"}
        self.assertNotIn("移交存根", offered)
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("陈默", "read", {"item": "移交存根"},
                                   world.version))
        self.assertNotIn("不在你手边", str(caught.exception))
        self.assertNotIn("移交存根",
                         caught.exception.context.get("readable_now", []))

    def test_objective_description_survives_compaction(self):
        """I49: the objective description used to be a one-shot snapshot — it
        never entered memory and a compacted actor lost it. It must now be
        recorded once as a memory row + an `observed` event, survive a
        checkpoint, answer a `read` of a bodyless prop, and count as read
        from a stay long enough."""
        from harness.kernel import (ActionRejected, ActorState, Intention,
                                    LocationState, World)
        world = World(
            start=datetime.fromisoformat("2026-03-16T07:00:00+08:00"),
            actors=[ActorState("a", "lab")],
            locations=[LocationState("lab")],
            item_locations={"old_whistle": "lab", "ledger": "lab"},
            document_defs={"ledger": {"title": "台账", "content": "正文甲。",
                                       "reading_seconds": 120}},
            entity_descriptions={"lab": "# 实验室\n\n一排铁皮柜。",
                                 "old_whistle": "# 旧哨子\n\n一只小小的红色哨子。",
                                 "ledger": "# 台账\n\n一本登记簿。"},
        )
        world.poll("a")
        observed = world.actors["a"].observed
        self.assertIn("一只小小的红色哨子", observed["old_whistle"]["objective"])
        self.assertTrue(any(e.kind == "observed" and e.payload["entity"] == "old_whistle"
                            for e in world.event_log))
        restored = World.from_checkpoint(
            World(start=datetime.fromisoformat("2026-03-16T07:00:00+08:00"),
                  actors=[ActorState("a", "lab")], locations=[LocationState("lab")],
                  entity_descriptions={"lab": "x", "old_whistle": "y", "ledger": "z"}),
            world.checkpoint_state())
        self.assertEqual(restored.actors["a"].observed, observed)
        with self.assertRaises(ActionRejected) as caught:
            restored.submit(Intention("a", "read", {"item": "old_whistle"},
                                      restored.version))
        self.assertIn(observed["old_whistle"]["objective"], str(caught.exception))
        restored.advance(until=world.now + timedelta(seconds=120))
        restored.poll("a")
        self.assertTrue(any(e.kind == "document_read" and e.payload.get("auto")
                            for e in restored.event_log))

    def test_launch_checkpoint_is_a_valid_loadable_trace(self):
        """H1/H4: a checkpoint written at launch is structurally valid and round-trips."""
        pack = load_story_pack()
        world = pack.build_world()
        trace = Trace("v3-test", "historical-gate-launch-checkpoint")
        snapshot = trace.snapshot(world)
        self.assertEqual(snapshot["format"], "v3-trajectory-1")
        self.assertEqual(snapshot["run_id"], "historical-gate-launch-checkpoint")
        verify_event_log(snapshot["world_events"])  # empty log must still verify
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            trace.save(world, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["format"], "v3-trajectory-1")
            self.assertEqual(data["run_id"], "historical-gate-launch-checkpoint")
            verify_event_log(data["world_events"])
            # The empty-prefix trajectory replays cleanly against the pack.
            replayed = replay_world(pack.build_world(), data["world_events"])
            self.assertEqual(replayed.now.isoformat(), world.now.isoformat())


    def test_extra_turns_are_recorded_and_conversational(self):
        """E1/E2/E3 + ticket-22 timing: a speak(to=["陌生人"]) must spawn a
        passer-by when the utterance lands (completion tick, never at
        submit), whose reply reaches the world AND the trace, then park
        instead of chattering.

        E1 — engine _extra_turn passed a plain dict to Trace.record_agent,
        which reads intention.actor/.kind → AttributeError AFTER the speech
        was submitted but BEFORE the record; _extra_loop caught only
        CancelledError, so the task died silently and gather() swallowed the
        exception. Every run since the async engine landed had zero extra
        turns and zero extra speech.
        E2 — the extra's own speech is visible to itself; without draining
        its perception cursor, has_wakeup() stayed True forever and the
        extra answered every scheduler pass.
        E3 — extras answer in prose (no tool call); extra_tool_calls dropped
        content-only replies, so live-run extras never spoke at all (T1
        文本即说话 must apply to extras too).

        Ticket 104 — determinism. The tick assertions below were a coin flip
        under load (full discover: 07:02 arrivals, answers two ticks late, 0/1
        extra turns; timelines in ticket 104). The cause is the fixture, not
        the engine: the engine bounds world progress by in-flight decisions,
        so while an extra's provider call is in flight any queued event lets
        the scheduler step the clock — and a populated world keeps feeding it
        those events (each MC/NPC keeps completing one-tick waits and waking on
        ambient speech). Three fixture rules remove that coupling:
        1. one character on stage — the pack's other actors move the clock on
           their own;
        2. the idle wait is legal and longer than the scenario — this seed caps
           a wait at longest_wait_seconds, and `wait 3600` is rejected with the
           engine's rejection repair substituting a one-tick wait, i.e. one
           more event inside the window;
        3. the follow-up ask is issued only after the answer was heard, and the
           stub answers only once 陈默 has parked (a barrier on world state,
           not a sleep) — so the extra's deliberation window owes no event at
           all, which is exactly the state the ticket-22 pin must freeze.
        The gate then measures the engine's contract instead of the thread
        pool's mood: a late answer or a clock running under a deliberating
        extra shows up as world ticks, and those ticks are now fixed."""
        pack = load_story_pack()
        world = pack.build_world()
        # Ticket 104 rule 1: one character on stage. Co-present MCs/NPCs
        # re-decide on every ambient wake and each of their one-tick wait
        # completions is a queued event the scheduler may spend while the extra
        # is thinking; the ticks the answer lands on would then depend on
        # thread scheduling instead of on the engine.
        for other in [name for name in world.actors if name != "陈默"]:
            del world.actors[other]
        # Ticket 104 rule 2: a LEGAL idle wait (this seed caps a wait at
        # longest_wait_seconds) that also outlives the 07:00-07:06 scenario.
        idle_seconds = int(world.longest_wait_seconds)
        self.assertGreater(idle_seconds, 6 * TICK_SECONDS)
        answer_line = "我知道那笔记录的事。"

        class ProseExtra:
            """The stranger's provider: a `speak` tool call for the opening
            question, then prose (T1 文本即说话) for the follow-up.

            Ticket 104 rule 3: the first answer is released only after 陈默 has
            parked in its idle wait — a barrier on world state, so the answer's
            tick is decided by the clock rather than by which thread got the
            GIL first."""

            def __init__(self):
                self.calls = 0
                self.mc_parked = False

            def _await_mc_parked(self, timeout: float = 15.0) -> bool:
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    action = (world.actors["陈默"].current_action or {}).get(
                        "payload", {}).get("action")
                    if action == "wait":
                        return True
                    time.sleep(0.001)
                return False

            def chat_with_tools(self, messages, tools):
                self.calls += 1
                if self.calls == 1:
                    self.mc_parked = self._await_mc_parked()
                    return {"role": "assistant", "content": "", "tool_calls": [
                        {"id": "c1", "type": "function",
                         "function": {"name": "speak",
                                      "arguments": json.dumps(
                                          {"text": answer_line},
                                          ensure_ascii=False)}}]}
                # Later turns: inline decision JSON instead of a tool call —
                # the shape that used to leak verbatim into the world speech.
                return {"role": "assistant",
                        "content": json.dumps({"inner": "想想再答",
                                               "name": "speak",
                                               "arguments": {"text": "后续回答"}},
                                              ensure_ascii=False),
                        "tool_calls": []}

        trace = Trace("v4-test", "historical-gate-extra-turns")
        asked = set()

        def heard_answer(perception) -> bool:
            return any(str(event.get("payload", {}).get("text", "")) == answer_line
                       for event in perception.get("events", ()))

        def agent(state, perception, affordances):
            # Ticket 22: ask is merged into speak — to=["陌生人"] asks the
            # room's passers-by; auto-wait is engine-side, so this test's
            # intentions carry it implicitly.
            if not asked:
                asked.add("ask")
                return Intention(state.actor_id, "speak",
                                 {"text": "请问台账的事？", "volume": "normal",
                                  "to": ["陌生人"]},
                                 perception["world_version"])
            # One follow-up to the same stranger (routed to the existing
            # partner extra), asked only once the reply has been heard: asking
            # straight away would queue its completion inside the extra's
            # deliberation window and hand the scheduler a tick to spend.
            if "follow-up" not in asked and heard_answer(perception):
                asked.add("follow-up")
                return Intention(state.actor_id, "speak",
                                 {"text": "那签字的人是谁？", "volume": "normal",
                                  "to": ["陌生人"]},
                                 perception["world_version"])
            return Intention(state.actor_id, "wait",
                             {"duration_seconds": idle_seconds},
                             perception["world_version"])

        agents = {actor: agent for actor in world.actors}
        states = {actor: PrivateState(actor) for actor in world.actors}
        stub = ProseExtra()
        # E73 (2026-10-16 live red, module solo and full discover): the
        # extra's provider call rides the shared daemon pool, and a cold or
        # GIL-starved pool let the scheduler outrun the first answer; the
        # 60s idle despawn then cancelled the queued call mid-flight (probe:
        # 赵阿姨 extra_removed 'idle' at 07:03, stub_calls=0, 0 extra turns).
        # Warm the pool up front and pin the idle window above the scenario so
        # an in-flight answer can neither be cancelled nor counted idle.
        _call_pool().submit(lambda: None).result(timeout=5)
        engine = AsyncEngine(world, agents, states, trace, None,
                             extra_call=stub, decision_timeout=10,
                             max_wall_seconds=60, extra_idle_seconds=3600)
        stop = datetime.fromisoformat("2026-03-16T07:06:00+08:00")
        reason = engine.run(stop_at=stop, max_turns=300)
        arrived = [e for e in world.event_log if e.kind == "extra_arrived"]
        # The barrier's premise, stated instead of its symptom: a world that
        # moved while the stranger was still deliberating leaves no answer tick
        # to read — that is the ticket-22 failure itself (the clock ran under a
        # deliberating extra), so name the evidence rather than the follow-on.
        self.assertTrue(stub.mc_parked,
                        "陈默 never parked in its idle wait: the world moved on "
                        f"while the stranger deliberated (world now "
                        f"{world.now.strftime('%H:%M')}, arrivals "
                        f"{[e.time.strftime('%H:%M') for e in arrived]}, "
                        f"provider calls {stub.calls})")
        self.assertEqual(reason, "stop_at_reached")

        # E1: the extra's turns are recorded with role="extra" — exactly one
        # extra spawned, two turns (initial + follow-up ask routed to it).
        extra_turns = [t for t in trace.agent_turns if t.get("role") == "extra"]
        self.assertEqual(len(extra_turns), 2)
        self.assertTrue(all(t["result"] == "submitted" for t in extra_turns))
        self.assertEqual(len({t["actor"] for t in extra_turns}), 1)

        # E111（票 109 §附）：engine.turns 与 trace.agent_turns 是两个度量，
        # 不是丢回合——`Engine._turns`（停机诊断的 engine.turns、max_turns 的
        # 计数）只数 persistent actor 的 `_take_turn`，轨迹却记下每个 agent
        # 回合（含 extra 的 `_extra_loop` 与 `result: none` 的诊断行）。所以
        # persistent 回合在轨迹里恰好一行，两数之差恒等于 extra 回合数
        # （D1 2026-03-16：1720 - 1479 = 241 = 29 名 extra 的回合）。
        persistent_turns = [turn for turn in trace.agent_turns
                            if turn.get("role") != "extra"]
        diagnosis = next(row["result"] for row in trace.system_turns
                         if row["request"].get("kind") == "engine_stop_diagnostic")
        self.assertEqual(diagnosis["turns"], len(persistent_turns),
                         "停机诊断的 engine.turns 就是 persistent 回合计，每个在轨迹里恰好一行（E111）")
        self.assertEqual(len(trace.agent_turns) - diagnosis["turns"], len(extra_turns),
                         "两套计数之差就是 extra 回合数（E111）")

        # Ticket 22 timing: the passer-by spawns when the utterance LANDS
        # (the speak's completion tick, one minute after the ask), and its
        # answer lands on that same tick — the clock is pinned under the
        # deliberating extra. The arrival tick is fixed by the scenario (ask at
        # 07:00, completion 07:01) and the deliberation window owes no other
        # event (ticket 104), so both are exact: a minute of slip is a clock
        # that ran away under the extra, not a slow provider.
        self.assertEqual(len(arrived), 1)
        self.assertEqual(arrived[0].time.strftime("%H:%M"), "07:01")
        first_answer = next(e for e in world.event_log if e.kind == "speech"
                            and answer_line in str(e.payload.get("text", "")))
        self.assertEqual(first_answer.time, arrived[0].time)

        # The replies became real speech events; the follow-up answer must be
        # the parsed speak text, NOT the raw decision JSON.
        speech = [str(e.payload.get("text", "")) for e in world.event_log
                  if e.kind == "speech"]
        self.assertTrue(any("那笔记录" in t for t in speech))
        self.assertTrue(any(t == "后续回答" for t in speech))
        self.assertFalse(any(t.startswith("{") for t in speech))

        # E2: no chatter — exactly two provider calls (initial + follow-up).
        self.assertEqual(stub.calls, 2)

        # No actor task crashed.
        crashes = [r for r in trace.system_turns
                   if r["request"].get("kind") == "actor_task_crash"]
        self.assertEqual(crashes, [])


    def test_extra_envelope_is_never_broadcast_as_speech(self):
        """E42 (ticket 42-1): an extra reply carrying the protocol envelope
        must be re-asked, and the private `inner` must never reach a speech
        payload.

        The d1-am artifact broadcast `{"inner":"唐小岚把草稿的事交代给我了…",
        "name":"speak","arguments":{"text":"好嘞…"}}` verbatim as 韩大叔's
        line (events #1271/#1272, `heard=['唐小岚']`). The model had stuffed
        the envelope into `arguments.text`; the extra path had no envelope
        check, so the raw bytes went out as speech."""
        envelope = ('{"inner":"唐小岚把草稿的事交代给我了，三点前守好吧台就行",'
                    '"name":"speak","arguments":{"text":"好嘞，那份草稿我不收不动。"}}')

        class EnvelopeThenSpeech:
            def __init__(self):
                self.calls = 0

            def chat_with_tools(self, messages, tools):
                self.calls += 1
                if self.calls == 1:
                    return {"role": "assistant", "content": "", "tool_calls": [
                        {"id": "c1", "type": "function",
                         "function": {"name": "speak", "arguments": json.dumps(
                             {"inner": "先应下来", "text": envelope},
                             ensure_ascii=False)}}]}
                return {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "c2", "type": "function",
                     "function": {"name": "speak", "arguments": json.dumps(
                         {"inner": "先应下草稿的事",
                          "text": "好嘞，那份草稿我不收不动，三点方老师来了我就请她到吧台这儿拿。"},
                         ensure_ascii=False)}}]}

        pack = load_story_pack()
        world = pack.build_world()
        trace = Trace("v4-test", "historical-gate-extra-envelope")
        asked = False

        def agent(state, perception, affordances):
            nonlocal asked
            if state.actor_id == "唐小岚" and not asked:
                asked = True
                return Intention("唐小岚", "speak",
                                 {"text": "草稿先放你这儿，三点方老师来取。",
                                  "volume": "normal", "to": ["陌生人"]},
                                 perception["world_version"])
            return Intention(state.actor_id, "wait", {"duration_seconds": 3600},
                             perception["world_version"])

        states = {a: PrivateState(a) for a in world.actors}
        agents = {a: agent for a in world.actors if world.actors[a].role != "extra"}
        stub = EnvelopeThenSpeech()
        engine = AsyncEngine(world, agents, states, trace, None, extra_call=stub,
                             decision_timeout=10, max_wall_seconds=60,
                             extra_idle_seconds=60)
        engine.run(stop_at=datetime.fromisoformat("2026-03-16T07:06:00+08:00"),
                   max_turns=300)

        extra_lines = [str(e.payload.get("text", "")) for e in world.event_log
                       if e.kind == "speech" and e.actor not in {"唐小岚"}]
        self.assertTrue(extra_lines, "路人仍然必须开口")
        for line in extra_lines:
            self.assertNotIn("inner", line)
            self.assertNotIn('"arguments"', line)
            self.assertFalse(line.strip().startswith("{"), line)
        self.assertTrue(any("那份草稿我不收不动" in line for line in extra_lines))
        # 心声是私有的：它不得出现在任何 speech payload 的正文里
        self.assertFalse(any("三点前守好吧台" in text
                             for text in [str(e.payload.get("text", ""))
                                          for e in world.event_log
                                          if e.kind == "speech"]))
        self.assertFalse(any("先应下草稿的事" in text
                             for text in [str(e.payload.get("text", ""))
                                          for e in world.event_log
                                          if e.kind == "speech"]))
        # 但摘出的心声进入 trace（私有），供 inner 填充率统计
        extra_turns = [t for t in trace.agent_turns if t.get("role") == "extra"]
        self.assertEqual([t.get("inner") for t in extra_turns if str(t.get("inner") or "").strip()],
                         ["先应下草稿的事"])

    def test_legacy_extra_call_envelope_is_never_broadcast(self):
        """E42 (ticket 42-1, legacy callable path): the engine's own submit
        boundary refuses a protocol-shaped line even when the reply came from
        an older callable extra provider."""
        import asyncio

        envelope = ('{"inner":"唐小岚把草稿的事交代给我了，三点前守好吧台就行",'
                    '"name":"speak","arguments":{"text":"好嘞，那份草稿我不收不动。"}}')
        raw = json.dumps({"inner": "先应下来", "name": "speak",
                          "arguments": {"text": envelope}}, ensure_ascii=False)

        pack = load_story_pack()
        world = pack.build_world()
        trace = Trace("v4-test", "historical-gate-extra-legacy-envelope")
        states = {a: PrivateState(a) for a in world.actors}

        def flat(state, perception, affordances):
            return Intention(state.actor_id, "wait", {"duration_seconds": 3600},
                             perception["world_version"])

        engine = AsyncEngine(world, {a: flat for a in states}, states, trace, None,
                             extra_call=lambda messages: raw, decision_timeout=5,
                             max_wall_seconds=30)
        engine._scheduler_wake = asyncio.Event()
        partner = "唐小岚"
        location = world.actors[partner].location
        world.add_extra("韩大叔", location)
        engine._extras["韩大叔"] = {
            "fragment": "兼职店员", "knowledge_notes": "", "partner": partner,
            "start": len(world.event_log), "last_active": world.now,
            "rarity": "common", "pending_question": "草稿先放你这儿。",
            "context_cursor": len(world.event_log),
            "system_prompt": "（测试用静态前缀）"}
        asyncio.run(engine._extra_turn("韩大叔", "草稿先放你这儿。"))

        speeches = [str(e.payload.get("text", "")) for e in world.event_log
                    if e.kind == "speech"]
        self.assertEqual(speeches, [],
                         "原始信封绝不能作为台词进入世界事件")
        extra_turns = [t for t in trace.agent_turns if t.get("role") == "extra"]
        self.assertEqual([t["result"] for t in extra_turns], ["rejected"])

    def test_extra_tool_calls_reask_the_protocol_envelope(self):
        """E42 (ticket 42-1): the envelope is a formatting error with a
        self-correcting re-ask, not content. A clean inline envelope is
        parsed by the shared envelope parser (inner lifted out); a broken one
        is silence rather than raw JSON spoken aloud."""
        from harness.npc_agent import (build_extra_briefing,
                                       build_extra_system_prompt, extra_tool_calls)

        envelope = ('{"inner":"先把话应下来","name":"speak",'
                    '"arguments":{"text":"好嘞，那份草稿我不收不动。"}}')
        system = build_extra_system_prompt("兼职店员", "", "半坡咖啡馆")

        class RetryThenClean:
            def __init__(self):
                self.calls = 0
                self.messages: list[dict[str, Any]] = []

            def chat_with_tools(self, messages, tools):
                self.calls += 1
                self.messages = list(messages)
                if self.calls == 1:
                    return {"role": "assistant", "content": "", "tool_calls": [
                        {"id": "c1", "type": "function",
                         "function": {"name": "speak", "arguments": json.dumps(
                             {"inner": "先应下来", "text": envelope},
                             ensure_ascii=False)}}]}
                return {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "c2", "type": "function",
                     "function": {"name": "speak", "arguments": json.dumps(
                         {"inner": "换一句话", "text": "好嘞，草稿放这儿我守着。"},
                         ensure_ascii=False)}}]}

        provider = RetryThenClean()
        calls = extra_tool_calls(provider, system,
                                build_extra_briefing(transcript=["唐小岚（对你说）：草稿先放你这儿。"]))
        self.assertEqual(provider.calls, 2, "协议信封必须触发重说")
        # 重说带上模型自己那段被拒的输出与可自纠提示
        self.assertIn("inner", provider.messages[-1]["content"])
        self.assertIn("arguments", provider.messages[-2]["content"])
        self.assertEqual([c["name"] for c in calls], ["speak"])
        spoken = str(calls[0]["arguments"].get("text"))
        self.assertEqual(spoken, "好嘞，草稿放这儿我守着。")
        self.assertNotIn("inner", calls[0]["arguments"])
        self.assertEqual(calls[0]["inner"], "换一句话")

        class InlineEnvelope:
            def chat_with_tools(self, messages, tools):
                return {"role": "assistant", "content": envelope, "tool_calls": []}

        calls = extra_tool_calls(InlineEnvelope(), system, "")
        self.assertEqual(len(calls), 1)
        self.assertEqual(str(calls[0]["arguments"]["text"]), "好嘞，那份草稿我不收不动。")
        self.assertEqual(calls[0]["inner"], "先把话应下来")
        self.assertNotIn("inner", calls[0]["arguments"])

    def test_extra_unparsable_envelope_is_silence_not_raw_json(self):
        """E42 (ticket 42-1): a reply that stays envelope-shaped through
        every re-ask ends in silence — never in raw protocol JSON spoken
        aloud."""
        from harness.npc_agent import extra_tool_calls, build_extra_system_prompt

        class GarbageEnvelope:
            def __init__(self):
                self.calls = 0

            def chat_with_tools(self, messages, tools):
                self.calls += 1
                return {"role": "assistant",
                        "content": '{"inner":"想事儿","arguments":{"text":',
                        "tool_calls": []}

        provider = GarbageEnvelope()
        calls = extra_tool_calls(provider, build_extra_system_prompt("路人", "", "图书馆"),
                                 "【你实际听见的近处交谈】\n唐小岚：你在吗？")
        self.assertEqual(calls, [], "无法解析的信封只能沉默，绝不能当台词送出")
        self.assertGreaterEqual(provider.calls, 2, "失败必须带可自纠提示重说")

    def test_extra_prompt_states_self_name_and_assertion_bounds(self):
        """E42 (tickets 42-2/3/4) + E57: the extra prompt never said who it
        was, so 韩大叔 called itself by third person and mailed its own name
        into `to` (`unknown or ambiguous speak recipient`); with no capability
        or assertion bounds it invented a 抄件 signature date (unregistered
        entity) and narrated 开柜/递件 as done. Ticket 57 keeps the bounds
        while granting the real verbs: the prompt must offer `move` for an
        actual departure and still forbid narrating an unperformed act."""
        from harness.npc_agent import build_extra_system_prompt

        prompt = build_extra_system_prompt("兼职店员", "三点前守好吧台", "半坡咖啡馆",
                                           name="韩大叔")
        self.assertIn("韩大叔", prompt, "extra 提示词必须带上自己的名字")
        self.assertIn("第三人称", prompt, "必须禁止第三人称自称")
        self.assertIn("to", prompt)  # to 只能是在场他人
        self.assertIn("在场", prompt)
        self.assertIn("move", prompt, "要走就必须真的 move 走过去")
        self.assertIn("已经发生", prompt, "没做过的动作不得叙述成已发生")
        self.assertIn("传闻", prompt)
        self.assertIn("具体细节", prompt)
        self.assertIn("签名", prompt)  # 反例清单：签名/日期这类细节
        self.assertIn("一份", prompt, "数量要照实说，不许放大")
        self.assertIn("知识", prompt)
        self.assertIn("JSON", prompt)

    def test_extra_idle_despawn_is_a_visible_interruption(self):
        """E42 (ticket 42-5): 12:27 唐小岚 handed the stranger the errand
        "三点方老师来取草稿"; 12:53 `extra_removed 韩大叔 reason=idle` left her
        with only "他走了" — the commitment vanished with no perceptible
        break, and nothing in the world may rewrite his words into assent."""
        from harness.prompt import _event_sentence

        class Quiet:
            def chat_with_tools(self, messages, tools):
                return {"role": "assistant",
                        "content": "草稿放这儿吧，我看着。", "tool_calls": []}

        pack = load_story_pack()
        world = pack.build_world()
        trace = Trace("v4-test", "historical-gate-extra-despawn")
        asked = False

        def agent(state, perception, affordances):
            nonlocal asked
            if state.actor_id == "唐小岚" and not asked:
                asked = True
                return Intention("唐小岚", "speak",
                                 {"text": "三点方老师来取草稿，先放你这儿。",
                                  "volume": "normal", "to": ["陌生人"]},
                                 perception["world_version"])
            return Intention(state.actor_id, "wait", {"duration_seconds": 3600},
                             perception["world_version"])

        states = {a: PrivateState(a) for a in world.actors}
        agents = {a: agent for a in world.actors if world.actors[a].role != "extra"}
        engine = AsyncEngine(world, agents, states, trace, None, extra_call=Quiet(),
                             decision_timeout=10, max_wall_seconds=60,
                             extra_idle_seconds=60)
        engine.run(stop_at=datetime.fromisoformat("2026-03-16T07:12:00+08:00"),
                   max_turns=300)

        removed = [e for e in world.event_log if e.kind == "extra_removed"]
        self.assertEqual(len(removed), 1, "路人应因静默被回收")
        event = removed[0]
        self.assertEqual(event.payload.get("reason"), "idle")
        # 交付权：托付的发起者与路人同处一地，必须看见这次中断
        self.assertIn("唐小岚", event.visible_to)
        self.assertEqual(world.actors["唐小岚"].location, event.payload.get("location"))
        line = _event_sentence({"kind": event.kind, "actor": event.actor,
                                "payload": dict(event.payload)})
        self.assertIn(event.actor, line)
        self.assertIn("中断", line, "回收必须是可感知的中断，而不只是'走了'")
        self.assertNotIn("答应", line)
        self.assertNotIn("答应", json.dumps(dict(event.payload), ensure_ascii=False))

    def test_deliberation_pins_the_world_clock(self):
        """T1a (ticket 23): while an actor's decision is in flight, the world
        clock may advance at most to that actor's wake + 1 tick. The live
        run showed instant-decision actors ratcheting the clock one tick per
        chain (their internal world.advance ignored the horizon) — a 7:35
        perception committing its action at 7:40."""
        from harness.engine import TICK_SECONDS

        class SlowFirst:
            session_obj = True

            def __call__(self, world_message, state):
                if not hasattr(self, "slept"):
                    self.slept = True
                    time.sleep(1.5)   # provider wall latency, in flight
                return {"text": "", "calls": [
                    {"name": "wait", "arguments": {"duration_seconds": 3600}}]}

            def deliver_tool_results(self, results):
                pass

            def consume_compaction(self):
                return False

        class Instant:
            session_obj = True

            def __call__(self, world_message, state):
                return {"text": "", "calls": [
                    {"name": "wait", "arguments": {"duration_seconds": 60}}]}

            def deliver_tool_results(self, results):
                pass

            def consume_compaction(self):
                return False

        pack = load_story_pack()
        world = pack.build_world()
        trace = Trace("v4-test", "historical-gate-clock-pin")
        agents = {}
        for a in world.actors:
            if world.actors[a].role != "extra":
                agents[a] = SlowFirst() if a == "陈默" else Instant()
        states = {a: PrivateState(a) for a in agents}
        engine = AsyncEngine(world, agents, states, trace, None,
                             extra_call=None, decision_timeout=30,
                             max_wall_seconds=60)
        engine.run(stop_at=datetime.fromisoformat("2026-03-16T07:06:00+08:00"),
                   max_turns=400)
        # While 陈默's 1.5 s deliberation was in flight (wake 07:00), no
        # event may carry a timestamp later than 07:01. Events after his
        # chain (normal cycling once he resolved) are legitimate — so the
        # window closes at his first own committed event.
        his_first = min((e.world_version for e in world.event_log
                         if e.actor == "陈默"), default=None)
        self.assertIsNotNone(his_first)
        during = [e for e in world.event_log
                  if e.world_version < his_first
                  and e.time > datetime.fromisoformat("2026-03-16T07:01:00+08:00")]
        self.assertEqual(during, [])

    def test_text_auto_wait_and_npc_reply_followup(self):
        """T1b/T1c (ticket 23): after a text the sender auto-waits (a reply
        wakes it early); an NPC woken by a delivered message that spent its
        turn on flashback gets exactly one follow-up turn to compose the
        reply — the live run showed mom recall and then park forever."""
        class TextThenMom:
            """陈默 texts mom; 陈默妈 flashes back then (follow-up) texts back."""
            session_obj = True

            def __init__(self, actor):
                self.actor = actor
                self.turns = 0

            def __call__(self, world_message, state):
                self.turns += 1
                if self.actor == "陈默":
                    if self.turns == 1:
                        return {"text": "", "calls": [
                            {"name": "text",
                             "arguments": {"target": "陈默妈",
                                           "text": "妈，老街坊代表是谁？"}}]}
                    return {"text": "", "calls": [
                        {"name": "wait", "arguments": {"duration_seconds": 3600}}]}
                if self.actor == "陈默妈":
                    # turn 1 = flashback only (the parked shape); the
                    # engine's follow-up turn lets her text the answer back.
                    if self.turns == 1:
                        return {"text": "", "calls": [
                            {"name": "flashback",
                             "arguments": {"entity": "2013年台风"}}]}
                    return {"text": "", "calls": [
                        {"name": "text",
                         "arguments": {"target": "陈默",
                                       "text": "代表是你李爷爷，他还住老院。"}}]}
                return {"text": "", "calls": [
                    {"name": "wait", "arguments": {"duration_seconds": 3600}}]}

            def deliver_tool_results(self, results):
                pass

            def consume_compaction(self):
                return False

        pack = load_story_pack()
        world = pack.build_world()
        trace = Trace("v4-test", "historical-gate-text-reply")
        agents = {}
        for a in world.actors:
            if world.actors[a].role != "extra":
                agents[a] = TextThenMom(a)
        states = {a: PrivateState(a) for a in agents}
        engine = AsyncEngine(world, agents, states, trace, None,
                             extra_call=None, decision_timeout=10,
                             max_wall_seconds=60)
        engine.run(stop_at=datetime.fromisoformat("2026-03-16T07:10:00+08:00"),
                   max_turns=400)
        # Mom's reply reached 陈默's phone.
        delivered = [e for e in world.event_log if e.kind == "message_delivered"
                     and e.actor == "陈默妈"]
        self.assertTrue(delivered, "mom never texted back")
        self.assertTrue(any("李爷爷" in str(e.payload.get("text", ""))
                            for e in delivered))


    def test_compaction_never_keeps_an_orphaned_tool_message(self):
        """T2 (ticket 23, full-day run): compaction kept the last N messages
        verbatim — if the window opened on a role:tool entry (its assistant
        trigger folded into the memory), every later request carried an
        orphaned tool message and the strict gateway rejected them all day
        (930 dead turns from 10:13 to 22:00)."""
        from harness.natural_agent import V4Session

        class CountingProvider:
            def __init__(self):
                self.calls = 0

            def __call__(self, messages):
                self.calls += 1
                return "第一人称记忆正文。"

            def chat_with_tools(self, messages, tools):
                self.calls += 1
                return {"role": "assistant", "content": "", "tool_calls": []}

        provider = CountingProvider()
        session = V4Session("陈默", provider, compaction_threshold=300,
                            recent_messages=4)
        session.messages.append({"role": "user", "content": "x" * 100})
        for i in range(10):
            session.messages.append({"role": "assistant", "content": "",
                                     "tool_calls": [{"id": f"c{i}", "type": "function",
                                                     "function": {"name": "wait",
                                                                  "arguments": "{}"}}]})
            session.messages.append({"role": "tool", "tool_call_id": f"c{i}",
                                     "content": "ok"})
        session._maybe_compact()
        # No role:tool may sit at the head of the kept tail (right after the
        # system prompt and the memory summary).
        body = session.messages[1:]
        self.assertFalse(body and body[0].get("role") == "tool",
                         "compaction kept an orphaned tool message at the head")


    def test_compaction_call_translates_tool_roles_for_responses(self):
        """T3 (ticket 23): the compaction memory call rides the plain-text
        Responses path, which accepts only assistant/system/developer/user
        roles. A history containing role:tool entries made every compaction
        request 400 ("Invalid value: 'tool'") — and since compaction
        re-triggers each turn, the actor stayed dead all day."""
        import urllib.request
        from harness.provider import OpenAICompatible

        captured = {}

        class FakeHTTP:
            def __init__(self, provider):
                self.provider = provider

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps({"output": [{"type": "message", "content": [
                    {"type": "output_text", "text": "记忆正文。"}]}]}).encode()

        def fake_urlopen(request, timeout=None):
            captured["body"] = json.loads(request.data)
            captured["headers"] = dict(request.headers)
            return FakeHTTP(None)

        provider = OpenAICompatible(base_url="http://probe/v1", model="probe",
                                    api_key="k", timeout=5, retries=0)
        old_urlopen = provider.__class__.__module__  # placeholder, unused
        import harness.provider as provider_mod
        saved = provider_mod.urlopen
        provider_mod.urlopen = fake_urlopen
        try:
            out = provider([{"role": "system", "content": "S"},
                            {"role": "user", "content": "历史"},
                            {"role": "assistant", "content": "", "tool_calls": [
                                {"id": "c1", "type": "function",
                                 "function": {"name": "read", "arguments": "{}"}}]},
                            {"role": "tool", "tool_call_id": "c1",
                             "content": "工具的正文"}])
        finally:
            provider_mod.urlopen = saved
        self.assertIn("记忆正文", out)
        input_items = captured["body"]["input"]
        self.assertTrue(all(item.get("role") != "tool" for item in input_items))
        self.assertIn("[工具结果]", input_items[-1]["content"])
        self.assertIn("工具的正文", input_items[-1]["content"])


    def test_authored_history_compiles_and_flashback_replays_it(self):
        """T4 (ticket 25): the manifest `history:` section compiles into the
        world's history log as REAL past events (negative id space, real
        2013 timestamps), flashback replays them for exactly the actors who
        lived through them, and a checkpoint round-trip preserves the log.

        Before this, the typhoon night existed only as concept-memory prose —
        flashback had nothing real to replay, so the past was narration, not
        history. History (the log) and memory (per-agent KB latest-state)
        are two different things; this gate keeps both honest."""
        pack = load_story_pack()
        world = pack.build_world()
        # 11 authored typhoon-night events, negative ids, real 2013 stamps.
        self.assertEqual(len(world.history_log), 11)
        self.assertTrue(all(e.id < 0 for e in world.history_log))
        self.assertEqual(world.history_log[0].time.year, 2013)
        # Runtime log untouched: no event at compile, cursors park after the
        # history segment (history is never re-delivered as new).
        self.assertEqual(len(world.event_log), 0)

        # Visibility follows who lived through it: 老赵头's shouting was
        # 下棋大爷's private witness; 林瑶 was not there.
        zhao = [e for e in world.history_log if "老赵头" in str(e.payload)]
        self.assertEqual(len(zhao), 1)
        self.assertIn("下棋大爷", zhao[0].visible_to)
        self.assertNotIn("林瑶", zhao[0].visible_to)

        # Flashback replays the authored history for the witness…
        lines = engine_of(world).flashback_for("下棋大爷", "老赵头")
        self.assertTrue(any("2013-03-16 21:58" in line and "老赵头" in line
                            for line in lines), lines)
        # …and says nothing about it to someone it never reached.
        self.assertEqual(engine_of(world).flashback_for("林瑶", "老赵头"), [])

        # Checkpoint round-trip preserves the history log verbatim.
        state = world.checkpoint_state()
        self.assertEqual(len(state["history_log"]), 11)
        restored = World.from_checkpoint(pack.build_world(), state)
        self.assertEqual([e.time for e in restored.history_log],
                         [e.time for e in world.history_log])
        self.assertEqual([e.id for e in restored.history_log],
                         [e.id for e in world.history_log])

    def test_flashback_surfaces_prerun_history_in_engine(self):
        """T4 live-path: a real AsyncEngine whose actor flashbacks the seeded
        lead (老赵头) gets the authored 2013 history lines — the same query
        the live run serves."""
        pack = load_story_pack()
        world = pack.build_world()
        trace = Trace("v4-test", "prerun-flashback")
        agents = {a: (lambda *a_, **k_: {"text": "", "calls": [
            {"name": "wait", "arguments": {"duration_seconds": 3600}}]})
            for a in world.actors if world.actors[a].role != "extra"}
        states = {a: PrivateState(a) for a in agents}
        engine = AsyncEngine(world, agents, states, trace, None,
                             decision_timeout=10, max_wall_seconds=30)
        probe = _FlashbackProbe(engine.world)
        lines = probe.flashback_for("下棋大爷", "老赵头")
        self.assertTrue(any("2013-03-16 21:58" in line for line in lines), lines)
        self.assertEqual(probe.flashback_for("林瑶", "老赵头"), [])

    def test_inner_channel_is_reachable_on_the_wire_and_native_path(self):
        """I38 (ticket 38): three live runs never filled inner (0/1356 turns) —
        the wire schema had no slot for it and the native tool-call decoder
        never lifted it, so every private deliberation was broadcast as
        speech. Keep the whole channel: (a) the wire schema declares a
        required non-empty inner while SCHEMAS (the kernel's action shape)
        stays contaminated-free; (b) a native call carrying inner yields a
        non-empty Intention.inner and inner-free, schema-valid action args."""
        from harness.action_schema import (SCHEMAS, SPEAK_TOOLS, TOOLS,
                                           WIRE_PARAMETERS, validate_action_args)
        from harness.adapter import parse_decision

        # (a) Wire contract. inner is first in required; the action shape is
        # untouched so validate_action_args still judges action arguments only.
        for kind, action in SCHEMAS.items():
            wire = WIRE_PARAMETERS[kind]
            self.assertEqual(wire["required"][0], "inner", kind)
            self.assertEqual(wire["properties"]["inner"],
                             {"type": "string", "minLength": 1}, kind)
            self.assertNotIn("inner", action["properties"], kind)
            for key, prop in action["properties"].items():
                self.assertEqual(wire["properties"][key], prop, kind)
            for key in action.get("required", ()):
                self.assertIn(key, wire["required"], kind)
        self.assertEqual({t["function"]["name"]: t["function"]["parameters"]
                          for t in TOOLS}, WIRE_PARAMETERS)
        self.assertIn("inner",
                      SPEAK_TOOLS[0]["function"]["parameters"]["required"])

        # (b) Native call -> parser lift. inner never reaches the action args.
        intention = parse_decision("陈默", {
            "name": "speak",
            "arguments": {"inner": "先问清楚再说。", "text": "阿姨，登记本在哪？",
                          "volume": "normal", "to": ["宿管阿姨"]}}, 7)[0]
        self.assertIsNotNone(intention)
        self.assertEqual(intention.inner, "先问清楚再说。")
        self.assertNotIn("inner", intention.args)
        self.assertIsNone(validate_action_args("speak", intention.args))

        # The production decoder (V4Session) lifts identically and keeps the
        # turn's monologue for the trace.
        from harness.natural_agent import V4Session

        class _Provider:
            def chat_with_tools(self, messages, tools):
                return {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "c1", "type": "function",
                     "function": {"name": "wait", "arguments": json.dumps(
                         {"inner": "先等一分钟。", "duration_seconds": 60})}}]}

            def __call__(self, messages):
                return "记忆。"

        decision = V4Session("a", _Provider(), system_prompt="S").decide("7:00")
        self.assertEqual(decision["calls"][0]["arguments"], {"duration_seconds": 60})
        self.assertEqual(decision["inner"], "先等一分钟。")

        # Several calls in one turn: the turn's inner is their non-empty
        # monologues joined in call order (deterministic).
        class _Two:
            def chat_with_tools(self, messages, tools):
                return {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "c1", "type": "function", "function": {
                        "name": "wait", "arguments": json.dumps(
                            {"inner": "第一句。", "duration_seconds": 60})}},
                    {"id": "c2", "type": "function", "function": {
                        "name": "recall", "arguments": json.dumps(
                            {"inner": "第二句。", "keys": ["草稿"]})}}]}

            def __call__(self, messages):
                return "记忆。"

        two = V4Session("a", _Two(), system_prompt="S").decide("7:00")
        self.assertEqual(two["inner"], "第一句。\n第二句。")
        self.assertEqual(two["calls"][1]["arguments"], {"keys": ["草稿"]})

    def test_legacy_envelope_inner_still_works(self):
        """I38/38c: the top-level envelope inner (the pre-native path) keeps
        working alongside the in-arguments slot."""
        from harness.adapter import parse_decision

        intention = parse_decision(
            "陈默",
            '{"inner":"老信封也能用。","name":"wait","arguments":{"duration_seconds":60}}',
            3)[0]
        self.assertIsNotNone(intention)
        self.assertEqual(intention.inner, "老信封也能用。")
        self.assertNotIn("inner", intention.args)

    def test_missing_inner_native_call_is_rejected_with_a_self_correcting_example(self):
        """I38: a native call without a non-empty inner is rejected per call
        (not a dead turn), and the rejection teaches — it states the rule and
        shows a corrected call."""
        from harness.natural_agent import V4Session

        class _Provider:
            def chat_with_tools(self, messages, tools):
                return {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "c1", "type": "function",
                     "function": {"name": "wait",
                                  "arguments": json.dumps({"duration_seconds": 60})}}]}

            def __call__(self, messages):
                return "记忆。"

        decision = V4Session("a", _Provider(), system_prompt="S").decide("7:00")
        call = decision["calls"][0]
        self.assertIn("parse_error", call)
        message = call["parse_error"]
        self.assertIn("inner", message)
        self.assertIn("谁也听不见", message)
        self.assertIn('"name": "wait"', message)
        self.assertIn('"inner"', message)
        self.assertIsNone(decision["inner"])

        class _Empty:
            def chat_with_tools(self, messages, tools):
                return {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "c1", "type": "function",
                     "function": {"name": "wait", "arguments": json.dumps(
                         {"inner": "   ", "duration_seconds": 60})}}]}

            def __call__(self, messages):
                return "记忆。"

        empty = V4Session("a", _Empty(), system_prompt="S").decide("7:00")
        self.assertIn("parse_error", empty["calls"][0])
        self.assertIsNone(empty["inner"])

    def test_reasoning_content_fills_a_missing_inner(self):
        """I38/38e: an open-source chat model returns its reasoning outside the
        call; when that call omits inner, the reasoning IS the monologue and
        the provider extraction layer adopts it as inner."""
        import io
        from unittest import mock

        from harness.natural_agent import V4Session
        from harness.provider import OpenAICompatible

        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        payload = {"choices": [{"message": {
            "content": "", "reasoning_content": "我先在心里盘算一下。",
            "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": "wait",
                                         "arguments": json.dumps(
                                             {"duration_seconds": 60})}}]}}]}
        provider = OpenAICompatible(base_url="http://gw/v1", model="m", timeout=1,
                                    retries=0, max_concurrency=1, retry_backoff=0.0)
        session = V4Session("a", provider, system_prompt="S")
        with mock.patch("harness.provider.urlopen",
                        lambda request, timeout=None:
                        _Resp(json.dumps(payload).encode())):
            decision = session.decide("7:00 @room")
        self.assertNotIn("inner", decision["calls"][0]["arguments"])
        self.assertNotIn("parse_error", decision["calls"][0])
        self.assertEqual(decision["inner"], "我先在心里盘算一下。")

    def test_engine_records_turn_inner_and_a_failed_call_is_not_a_dead_turn(self):
        """I38/38f: the engine writes the turn's inner into the private trace
        field the health report reads, and a call-level parse_error (missing
        inner) is a normal per-call failure — the turn is not an agent error."""
        from harness.engine import AsyncEngine
        from harness.kernel import ActorState, LocationState, World

        class _Agent:
            session_obj = object()

            def __init__(self):
                self.delivered = []

            def __call__(self, world_message, state):
                return {"text": "", "inner": "我在原地等一会儿。",
                        "calls": [{"name": "wait",
                                   "arguments": {"duration_seconds": 60},
                                   "tool_call_id": "c1",
                                   "parse_error": "every call must carry a non-empty "
                                                  "inner: 谁也听不见"}]}

            def deliver_tool_results(self, results):
                self.delivered.extend(results)

            def consume_compaction(self):
                return False

            def session_snapshot(self):
                return None

        world = World(start=datetime.fromisoformat("2026-03-16T07:00:00+08:00"),
                      actors=[ActorState("a", "room")],
                      locations=[LocationState("room")])
        trace = Trace("v4-test", "inner-trace")
        agent = _Agent()
        engine = AsyncEngine(world, {"a": agent}, {"a": PrivateState("a")}, trace, None,
                             decision_timeout=10, max_wall_seconds=30)
        engine.run(stop_at=datetime.fromisoformat("2026-03-16T07:03:00+08:00"),
                   max_turns=20)
        turn = next(t for t in trace.agent_turns if t["actor"] == "a"
                    and t.get("inner"))
        self.assertEqual(turn["inner"], "我在原地等一会儿。")
        self.assertNotIn(turn["result"],
                         {"agent_error", "decision_timeout", "engine_error"})
        self.assertIn("inner", turn["error"] or "")
        self.assertTrue(any("inner" in str(r.get("text")) for r in agent.delivered))


def _extra_call(name: str, args: dict) -> dict:
    """A provider reply carrying one native tool call."""
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": f"c-{name}", "type": "function",
         "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}


class _ExtraScript:
    """A scripted extra provider: records each call's (messages, tools) and
    answers with ``reply(n)`` for the n-th call."""

    def __init__(self, reply):
        from copy import deepcopy
        self._deepcopy = deepcopy
        self.reply = reply
        self.calls: list[tuple[list[dict], list[dict]]] = []

    def chat_with_tools(self, messages, tools):
        self.calls.append((self._deepcopy(messages), self._deepcopy(tools)))
        return self.reply(len(self.calls))


class Ticket57ExtraActionGates(unittest.TestCase):
    """E57 (ticket 57, real-20261001T065553): an extra could only speak, so
    the run's three strangers narrated physical acts as done — 孙学长
    declared the window seat four times (location never changed, no
    move/leave event), 陈大叔 said "我先回去看书了啊" with no departure, and
    何大叔 called one 校报草稿 "一摞". `_extra_turn` hardcoded
    `affordances=[]` and `perception={events:[],inbox:[],nearby_actors:[]}`,
    iterated `intention_calls` with `if call_name != "speak": continue`, and
    the extras' tool surface was SPEAK_TOOLS. The kernel's `affordances()`
    was never the cause — it already returned `move` for role=extra (verified
    below); the harness threw it away. Fix: extras get EXTRA_TOOLS (speak +
    move/take/place/give, no memory tools), the turn executes every offered
    verb through the kernel, a rejected verb is reported back for one
    correction, and the recorded turn carries the real scene perception and
    affordances. The scene block grounds a stated quantity (一份, not 一摞)."""

    START = datetime.fromisoformat("2026-03-16T09:00:00+08:00")

    def _run(self, reply, *, stop_minutes: int = 30):
        pack = load_story_pack()
        world = pack.build_world()
        trace = Trace("v4-test", "ticket57-extra-action")
        asked = False

        def agent(state, perception, affordances):
            nonlocal asked
            if state.actor_id == "唐小岚" and not asked:
                asked = True
                return Intention("唐小岚", "speak",
                                 {"text": "同学，你就是新来的兼职吧？",
                                  "volume": "normal", "to": ["陌生人"]},
                                 perception["world_version"])
            return Intention(state.actor_id, "wait", {"duration_seconds": 3600},
                             perception["world_version"])

        provider = _ExtraScript(reply)
        states = {a: PrivateState(a) for a in world.actors}
        agents = {a: agent for a in world.actors if world.actors[a].role != "extra"}
        engine = AsyncEngine(world, agents, states, trace, None, extra_call=provider,
                             decision_timeout=10, max_wall_seconds=60,
                             extra_idle_seconds=3600)
        engine.run(stop_at=self.START + timedelta(minutes=stop_minutes), max_turns=300)
        return world, trace, provider

    def _extra_name(self, trace) -> str:
        return next(t["actor"] for t in trace.agent_turns if t.get("role") == "extra")

    def test_the_kernel_already_offers_move_to_an_extra(self):
        """The empty affordances were a harness loss, not a role filter: the
        kernel's affordances() returns move/speak for role=extra on its own."""
        world = load_story_pack().build_world()
        world.add_extra("路人甲", "半坡咖啡馆")
        kinds = {a["kind"] for a in world.affordances("路人甲")}
        self.assertIn("move", kinds)
        self.assertIn("speak", kinds)
        self.assertIn("图书馆", {a.get("target") for a in world.affordances("路人甲")
                                 if a["kind"] == "move"})

    def test_a_declared_departure_is_a_real_visible_move(self):
        """孙学长 declared 4 times he was going to the window seat and never
        moved. A move reply must commit a leave (heard by the room) and an
        enter, change the location, and despawn via partner_gone."""
        def reply(n):
            return _extra_call("move", {"inner": "不掺和了，我先走一步", "target": "图书馆"})

        world, trace, provider = self._run(reply)
        name = self._extra_name(trace)
        leaves = [e for e in world.event_log if e.kind == "leave" and e.actor == name]
        self.assertTrue(leaves, "宣布离开必须落地为真实的 leave 事件")
        self.assertIn("唐小岚", leaves[0].visible_to,
                      "同场的发起者必须看得见这次离开")
        entered = [e for e in world.event_log if e.kind == "enter" and e.actor == name]
        self.assertTrue(entered, "离开必须落地为真实的 enter 事件")
        self.assertEqual(entered[-1].payload.get("location"), "图书馆")
        self.assertNotIn(name, world.actors, "离开后按 partner_gone 回收")
        removed = [e for e in world.event_log if e.kind == "extra_removed" and e.actor == name]
        self.assertEqual(removed[-1].payload.get("reason"), "partner_gone")
        self.assertTrue(any(t["result"] == "submitted" for t in trace.agent_turns
                            if t["actor"] == name))

    def test_the_recorded_turn_carries_real_affordances_and_perception(self):
        """(b)(e): the extra turn's trace no longer holds an empty stub — it
        records the kernel's move affordance and the co-located partner."""
        world, trace, provider = self._run(
            lambda n: _extra_call("speak", {"inner": "搭句话", "text": "哎，是我，怎么了？"}))
        turn = next(t for t in trace.agent_turns if t.get("role") == "extra")
        self.assertIn("move", {a.get("kind") for a in turn["affordances"]})
        self.assertIn("speak", {a.get("kind") for a in turn["affordances"]})
        self.assertIn("唐小岚", turn["perception"]["nearby_actors"])
        self.assertIn("校报草稿", turn["perception"]["nearby_items"])

    def test_scene_briefing_grounds_a_stated_quantity(self):
        """(d): 何大叔 turned one 校报草稿 into 一摞. The extra's own scene
        now states the prop and its real description, so 一份 is grounded and
        the model need not guess — and the tool surface is the non-memory
        action set."""
        world, trace, provider = self._run(
            lambda n: _extra_call("speak", {"inner": "应一声", "text": "哦，那不打扰你了。"}))
        user_tail = provider.calls[0][0][-1]["content"]
        self.assertIn("校报草稿", user_tail)
        self.assertIn("一份", user_tail)
        self.assertIn("照实", user_tail)
        names = [t["function"]["name"] for t in provider.calls[0][1]]
        self.assertEqual(names, ["speak", "move", "take", "place", "give"])
        for memory_tool in ("update_memory", "recall", "flashback", "wait", "text"):
            self.assertNotIn(memory_tool, names)

    def test_a_rejected_action_is_reported_back_for_one_correction(self):
        """A move the world cannot execute (月球) must not be narrated as
        done: the rejection is handed back to the extra, which answers once
        more in bounds, and no leave/enter is ever fabricated."""
        def reply(n):
            if n == 1:
                return _extra_call("move", {"inner": "走了", "target": "月球"})
            return _extra_call("speak", {"inner": "那天我去不了",
                                          "text": "月球我可去不了，我就在这儿等你回来。"})

        world, trace, provider = self._run(reply, stop_minutes=10)
        name = self._extra_name(trace)
        self.assertGreaterEqual(len(provider.calls), 2, "被拒的动作必须回给 extra 重说")
        correction = provider.calls[1][0][-1]["content"]
        self.assertIn("没能执行", correction)
        self.assertIn("月球", correction)
        self.assertFalse([e for e in world.event_log if e.kind == "leave" and e.actor == name],
                         "没发生的离开绝不能变成事实")
        speeches = [str(e.payload.get("text", "")) for e in world.event_log
                    if e.kind == "speech" and e.actor == name]
        self.assertTrue(any("去不了" in s for s in speeches), speeches)

    def test_scene_perception_grants_no_more_than_co_location(self):
        """The read-only scene view must use the same `visible_to` authority
        as a main actor's poll — co-location and delivery only, never the
        private knowledge channel."""
        world = load_story_pack().build_world()
        location = "半坡咖啡馆"
        world.add_extra("路人甲", location)
        perception = world.scene_perception("路人甲")
        expected = sorted(a for a in world.actors
                          if a != "路人甲" and world.actors[a].location == location)
        self.assertEqual(perception["nearby_actors"], expected)
        visible_ids = {e.id for e in world.event_log if "路人甲" in e.visible_to}
        self.assertEqual({e["id"] for e in perception["events"]}, visible_ids)
        self.assertNotIn("knowledge", perception)


class RepetitionMonitorGates(unittest.TestCase):
    """I43 (ticket 43, user ruling 2026-09-30): the chain execution path fed
    the repetition monitor `None` — `engine.py _execute_chain` called
    `note_turn(actor_id, None, result)` and `RepetitionMonitor.note_turn`
    drops the turn on its first line (`intention is None`). Every run's real
    path is the chain path, so on the d1-am artifact not one identical action
    was ever counted: nine identical failing `read 签到本` and eighteen
    `wait 900` turns produced zero "same action" notices. These gates pin the
    chain -> monitor wire and the wait-stagnation notice that must follow it."""

    START = datetime.fromisoformat("2026-03-16T07:00:00+08:00")

    def _run(self, world, agent, *, stop_minutes, **kw):
        trace = Trace("v4-test", "chain-repetition")
        engine = AsyncEngine(world, {"a": agent}, {"a": PrivateState("a")},
                             trace, None, decision_timeout=10,
                             max_wall_seconds=30, mc_idle_heartbeat=60, **kw)
        engine.run(stop_at=self.START + timedelta(minutes=stop_minutes),
                   max_turns=60)
        return [turn["perception"].get("situational_notice") or ""
                for turn in trace.agent_turns if turn["actor"] == "a"]

    def test_chain_path_feeds_the_repetition_monitor(self):
        """(a) An identical failing world action repeated on the chain path
        must reach the monitor and fire the \"same action\" notice."""
        from harness.kernel import ActorState, LocationState

        class _FailingChain:
            session_obj = object()

            def __init__(self):
                self.delivered = []

            def __call__(self, world_message, state):
                return {"text": "", "calls": [
                    {"name": "move", "arguments": {"target": "nowhere"},
                     "tool_call_id": "c1"}]}

            def deliver_tool_results(self, results):
                self.delivered.extend(results)

            def consume_compaction(self):
                return False

            def session_snapshot(self):
                return None

        world = World(start=self.START, actors=[ActorState("a", "room")],
                      locations=[LocationState("room")])
        agent = _FailingChain()
        notices = self._run(world, agent, stop_minutes=20)
        self.assertTrue(any("same action" in notice for notice in notices),
                        f"the chain path never reached the monitor: {notices}")
        # The fixture's action really did fail; otherwise the gate proves nothing.
        self.assertTrue(any("nowhere" in str(r.get("text"))
                            for r in agent.delivered))

    def test_chain_path_counts_waits_as_stagnation_with_a_next_action(self):
        """(b) Consecutive waits on the chain path become stagnation, and the
        notice lists a concrete action still available here."""
        from harness.kernel import ActorState, LocationState

        class _WaitingChain:
            session_obj = object()

            def __call__(self, world_message, state):
                return {"text": "", "calls": [
                    {"name": "wait", "arguments": {"duration_seconds": 60},
                     "tool_call_id": "c1"}]}

            def deliver_tool_results(self, results):
                pass

            def consume_compaction(self):
                return False

            def session_snapshot(self):
                return None

        world = World(start=self.START, actors=[ActorState("a", "room")],
                      locations=[LocationState("room"), LocationState("far")],
                      routes={("room", "far"): 120})
        notices = self._run(world, _WaitingChain(), stop_minutes=20)
        stagnation = [notice for notice in notices if "waiting in place" in notice]
        self.assertTrue(stagnation, f"waits were not counted as stagnation: {notices}")
        self.assertTrue(any("move to far" in notice for notice in stagnation),
                        f"stagnation notice listed no executable action: {stagnation}")


class SameKindFailureGates(unittest.TestCase):
    """Ticket 63 (d1-am artifact real-20261001T121425+0800-223688-090345540).

    Four examples: (1) the same failed action re-worded (尼龙绳 / 一卷尼龙绳 /
    捆货用的绳子 / 值班室的粗尼龙绳) never counted as repetition because the
    monitor keyed on exact (kind, args); (2) 食堂大妈 tried to take food she
    was serving at her own window — the world only had take/give; (3) 班长 read
    教学楼正门内侧公告栏, a location-level notice board that is not a registered
    document, and the 教学楼 rejection listed nothing readable, so it offered no
    executable next step. These gates pin the same-kind refusal run, the serve
    path, and the always-executable read rejection."""

    START = datetime.fromisoformat("2026-03-16T07:00:00+08:00")

    def _chain_run(self, world, agent, *, stop_minutes):
        trace = Trace("v4-test", "ticket63-same-kind")
        engine = AsyncEngine(world, {"a": agent}, {"a": PrivateState("a")},
                             trace, None, decision_timeout=10,
                             max_wall_seconds=30, mc_idle_heartbeat=60)
        engine.run(stop_at=self.START + timedelta(minutes=stop_minutes),
                   max_turns=60)
        return [turn for turn in trace.agent_turns if turn["actor"] == "a"]

    def test_same_kind_rejections_reach_the_chain_path_notice(self):
        """(a) Three refused `take`s with different wording must fire one
        stagnation notice listing what is really here."""
        from harness.kernel import ActorState, LocationState

        class _DifferentlyWordedTakes:
            session_obj = object()

            def __init__(self):
                self.delivered = []
                self._index = 0

            def __call__(self, world_message, state):
                word = ("尼龙绳", "一卷尼龙绳", "捆货用的绳子", "值班室的粗尼龙绳")[
                    self._index % 4]
                self._index += 1
                return {"text": "", "calls": [
                    {"name": "take", "arguments": {"item": word},
                     "tool_call_id": "c1"}]}

            def deliver_tool_results(self, results):
                self.delivered.extend(results)

            def consume_compaction(self):
                return False

            def session_snapshot(self):
                return None

        world = World(start=self.START, actors=[ActorState("a", "room")],
                      locations=[LocationState("room")])
        world.item_locations["晚归登记本"] = "room"
        turns = self._chain_run(world, _DifferentlyWordedTakes(), stop_minutes=30)
        # The fixture's attempts really did fail; otherwise the gate proves nothing.
        self.assertTrue(any("这里没有「尼龙绳」" in str(turn.get("error") or "")
                            for turn in turns),
                        "the fixture take never failed")
        notices = [turn["perception"].get("situational_notice") or ""
                   for turn in turns]
        fired = [notice for notice in notices if "refused in a row" in notice]
        self.assertTrue(fired, f"同类被拒没有触发停滞提示: {notices}")
        self.assertTrue(any("晚归登记本" in notice for notice in fired),
                        f"提示没有列出此处确实有的东西: {fired}")

    def test_a_present_item_can_be_served_with_give(self):
        """(c) The 上菜/递物 gap: an item already at the actor's own location
        (the window counter) can be handed to someone here without a separate
        `take` — but only because it is physically present."""
        from harness.kernel import ActorState, LocationState
        world = World(start=self.START,
                      actors=[ActorState("dama", "窗口"),
                              ActorState("guest", "窗口")],
                      locations=[LocationState("窗口")])
        world.item_locations["一碗豆浆"] = "窗口"
        world.submit(Intention("dama", "give",
                               {"target": "guest", "item": "一碗豆浆"},
                               world.version))
        world.advance()
        self.assertIn("一碗豆浆", world.actors["guest"].inventory)
        self.assertNotIn("一碗豆浆", world.item_locations)
        transfer = next(event for event in world.event_log
                        if event.kind == "item_given")
        self.assertEqual(transfer.payload,
                         {"item": "一碗豆浆", "from": "dama", "to": "guest"})

    def test_give_never_invents_an_absent_item(self):
        """The boundary of the serve path: `give` still refuses an item that
        is neither held nor physically here — it never invents one."""
        from harness.kernel import ActorState, LocationState
        world = World(start=self.START,
                      actors=[ActorState("dama", "窗口"),
                              ActorState("guest", "窗口")],
                      locations=[LocationState("窗口")])
        for invented in ("一台抽水泵", "荤菜、素菜、米饭、一碗汤"):
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("dama", "give",
                                       {"target": "guest", "item": invented},
                                       world.version))
            self.assertIn(invented, str(caught.exception))
            self.assertIn("没有拿着", str(caught.exception))
            self.assertFalse(any(event.kind == "item_given"
                                 for event in world.event_log))

    def test_notice_board_read_rejection_offers_a_real_next_step(self):
        """(d) A location-level notice board is not a registered document. The
        rejection must still hand back an executable step (where to go / who to
        ask / what is really readable), never a dead end."""
        world = load_story_pack().build_world()
        ban = world.actors["班长"]
        ban.location = "教学楼"
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("班长", "read",
                                   {"item": "教学楼正门内侧公告栏"},
                                   world.version))
        message = str(caught.exception)
        self.assertIn("教学楼正门内侧公告栏", message)
        alternatives = list(caught.exception.alternatives)
        self.assertTrue(alternatives,
                        f"公告栏类 read 拒绝没有给出可执行下一步: {message}")
        for alternative in alternatives:
            verb, _, rest = str(alternative).partition(" ")
            if verb == "move":
                target = rest.removeprefix("to ").removesuffix(" (open)")
                self.assertIn(target, world.locations)
                self.assertTrue(world.locations[target].open)
            elif verb == "take":
                self.assertEqual(world.item_locations.get(rest), "教学楼")
            elif verb == "read":
                self.assertIn(rest, world._available_readables(ban))
            elif verb == "speak":
                self.assertIn(rest.removeprefix("to "), world._present_others(ban))
            else:
                self.fail(f"unrecognised alternative '{alternative}'")


class _ExtraCheckpointFixtures(unittest.TestCase):
    """Shared fixtures for the extra checkpoint gates (E50/E55)."""

    QUESTION = "台账的事你听说了吗？"
    ANSWER = "账簿的事我听人说过，三点前得交回去。"

    def _extra_world(self):
        from harness.kernel import ActorState, LocationState
        return World(start=datetime.fromisoformat("2026-03-16T07:00:00+08:00"),
                     actors=[ActorState("a", "room")],
                     locations=[LocationState("room", extras=(
                         {"fragment": "兼职店员", "rarity": "common",
                          "knowledge_notes": "三点前要把账簿交回去"},))])

    def _speaking_extra(self):
        answer = self.ANSWER

        class _SpokenExtra:
            def __init__(self):
                self.calls = 0

            def chat_with_tools(self, messages, tools):
                self.calls += 1
                return {"role": "assistant", "content": "", "tool_calls": [
                    {"id": f"c{self.calls}", "type": "function",
                     "function": {"name": "speak", "arguments": json.dumps(
                         {"inner": "这本账我确实听过一嘴", "text": answer},
                         ensure_ascii=False)}}]}

        return _SpokenExtra()

    def _engine(self, world, extra_call):
        import asyncio

        def agent(state, perception, affordances):
            return Intention("a", "wait", {"duration_seconds": 3600},
                             perception["world_version"])

        engine = AsyncEngine(world, {"a": agent}, {"a": PrivateState("a")},
                             Trace("v4-test", "extra-checkpoint"), None,
                             extra_call=extra_call, decision_timeout=5,
                             max_wall_seconds=30)
        # Spawn/answer seams read these; run() rebuilds them for a resumed run.
        engine._scheduler_wake = asyncio.Event()
        engine._wake_events = {}
        return engine


class ExtraCheckpointGates(_ExtraCheckpointFixtures):
    """E50 (ticket 50): a live extra's full mutable state must survive a
    checkpoint round-trip. A half-day resume (d1-am -> d1-pm) starts a new
    engine from a checkpoint that already has an extra on stage; if the
    checkpoint dropped system_prompt the extra's loop died with a KeyError,
    and dropping context_cursor/pending_question lost the reply window and
    the unanswered question."""

    def _spawn_and_snapshot(self, engine, question):
        """Spawn the extra through the real generation seam, then snapshot its
        state inside the loop so the task can never consume the question."""
        import asyncio
        captured: dict = {}

        async def scenario():
            engine._spawn_extra("a", question, asyncio.get_running_loop())
            captured["name"] = next(iter(engine._extras))
            captured["live"] = dict(engine._extras[captured["name"]])
            captured["runner"] = engine.checkpoint_state()
            captured["world"] = engine.world.checkpoint_state()
            tasks = list(engine._extra_tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        asyncio.run(scenario())
        return captured

    def test_extra_checkpoint_roundtrip_keeps_state_and_produces_a_turn(self):
        """E50(a/b): spawn -> checkpoint -> restore into a new engine -> the
        extra still answers (no KeyError), with its cursor and pending
        question intact."""
        base = self._extra_world()
        world = self._extra_world()
        engine = self._engine(world, self._speaking_extra())
        captured = self._spawn_and_snapshot(engine, self.QUESTION)
        name, live = captured["name"], captured["live"]

        restored_world = World.from_checkpoint(base, captured["world"])
        resumed = self._engine(restored_world, self._speaking_extra())
        resumed.restore_checkpoint(captured["runner"])
        restored = resumed._extras[name]

        # (b) pending question + transcript cursor + fixed prefix survive.
        self.assertEqual(restored["pending_question"], self.QUESTION)
        self.assertEqual(restored["context_cursor"], live["context_cursor"])
        self.assertEqual(restored["pending_heard_speech"], live["pending_heard_speech"])
        self.assertEqual(restored["system_prompt"], live["system_prompt"])
        self.assertEqual(restored["fragment"], live["fragment"])
        self.assertEqual(restored["start"], live["start"])

        # (a) the resumed run still produces the extra's turn (no KeyError).
        resumed.run(stop_at=datetime.fromisoformat("2026-03-16T07:03:00+08:00"),
                    max_turns=30)
        lines = [str(e.payload.get("text", "")) for e in restored_world.event_log
                 if e.kind == "speech" and e.actor == name]
        self.assertIn(self.ANSWER, lines)
        crashes = [r for r in resumed.trace.system_turns
                   if r["request"].get("kind") == "actor_task_crash"]
        self.assertEqual(crashes, [])

    def test_old_format_extra_checkpoint_is_rebuilt_and_tolerated(self):
        """E50(c): a pre-ticket-50 row (only the six legacy keys) must be
        rebuilt with safe defaults, not raise, and its turn must still run."""
        import asyncio
        from harness.npc_agent import build_extra_system_prompt

        world = self._extra_world()
        world.add_extra("韩大叔", "room")
        start = len(world.event_log)
        engine = self._engine(world, self._speaking_extra())
        legacy = {"transient_failures": {"a": 0},
                  "extras": {"韩大叔": {
                      "fragment": "兼职店员",
                      "knowledge_notes": "三点前要把账簿交回去",
                      "partner": "a", "last_active": world.now.isoformat(),
                      "rarity": "common", "start": start}}}
        engine.restore_checkpoint(legacy)   # 旧格式缺 system_prompt 等键

        info = engine._extras["韩大叔"]
        self.assertEqual(info["system_prompt"],
                         build_extra_system_prompt("兼职店员", "三点前要把账簿交回去",
                                                   "room", name="韩大叔"))
        self.assertEqual(info["context_cursor"], start)
        self.assertEqual(info["pending_question"], "")
        self.assertFalse(info["pending_heard_speech"])

        # The tolerance lives in _extra_turn too: a direct turn must not raise.
        asyncio.run(engine._extra_turn("韩大叔", self.QUESTION))
        lines = [str(e.payload.get("text", "")) for e in world.event_log
                 if e.kind == "speech" and e.actor == "韩大叔"]
        self.assertIn(self.ANSWER, lines)

    def test_runner_sync_path_carries_the_prompt_and_tolerates_a_legacy_row(self):
        """E50 (sync Runner): the legacy path had the same gap — its
        checkpoint dropped system_prompt and its _extra_turn read the key
        outside its try. Persist it, and rebuild on an old-format row."""
        from harness.npc_agent import build_extra_system_prompt
        from harness.runner import Runner

        def wait_agent(state, perception, affordances):
            return Intention(state.actor_id, "wait", {"duration_seconds": 3600},
                             perception["world_version"])

        def build():
            world = self._extra_world()
            world.add_extra("韩大叔", "room")
            agents = {a: wait_agent for a in world.actors}
            states = {a: PrivateState(a) for a in world.actors}
            return world, agents, states

        world, agents, states = build()
        prompt = build_extra_system_prompt("兼职店员", "三点前要把账簿交回去", "room")
        runner = Runner(world, agents, states, Trace("v4-test", "runner-extra-cp"), None)
        runner._extras["韩大叔"] = {
            "fragment": "兼职店员", "knowledge_notes": "三点前要把账簿交回去",
            "partner": "a", "last_active": world.now, "rarity": "common",
            "start": 0, "system_prompt": prompt}
        self.assertEqual(runner.checkpoint_state()["extras"]["韩大叔"]["system_prompt"],
                         prompt)

        # Resume from a pre-ticket-50 Runner row (no system_prompt key).
        world2, agents2, states2 = build()
        answer = self.ANSWER
        resumed = Runner(world2, agents2, states2, Trace("v4-test", "runner-extra-cp2"),
                         None,
                         extra_call=lambda messages: json.dumps(
                             {"name": "speak", "arguments": {"text": answer}},
                             ensure_ascii=False))
        resumed.restore_checkpoint({
            "transient_failures": {a: 0 for a in world2.actors},
            "extras": {"韩大叔": {
                "fragment": "兼职店员", "knowledge_notes": "三点前要把账簿交回去",
                "partner": "a", "last_active": world2.now.isoformat(),
                "rarity": "common", "start": 0}}})
        resumed._extra_turn("韩大叔", self.QUESTION)   # must not raise
        lines = [str(e.payload.get("text", "")) for e in world2.event_log
                 if e.kind == "speech" and e.actor == "韩大叔"]
        self.assertIn(self.ANSWER, lines)


# Ticket 55: the process-under-test for E55(c). It reproduces the production
# shape — a worker thread parked in a provider call while an engine task
# raises — without a real provider. Run with the project root as cwd so
# `harness` imports.
_ENGINE_CRASH_CHILD = '''\
import time
from datetime import datetime, timedelta
from harness.agent_state import PrivateState
from harness.engine import AsyncEngine
from harness.kernel import ActorState, Intention, LocationState, World
from harness.trace import Trace

START = datetime.fromisoformat("2026-03-16T07:00:00+08:00")


def blocking_agent(state, perception, affordances):
    time.sleep(3600)          # a provider call that never returns in-run
    return Intention("a", "wait", {"duration_seconds": 60},
                     perception["world_version"])


def crashy_checkpoint():
    raise RuntimeError("checkpoint boom (ticket-55 zombie regression)")


world = World(start=START, actors=[ActorState("a", "room")],
              locations=[LocationState("room")])
engine = AsyncEngine(world, {"a": blocking_agent}, {"a": PrivateState("a")},
                     Trace("v4-test", "zombie-child"), None,
                     decision_timeout=60, max_wall_seconds=30,
                     stall_threshold_seconds=1.0, freeze_tolerance_seconds=0.2,
                     hung_tolerance_seconds=0.2, checkpoint=crashy_checkpoint)
engine.run(stop_at=START + timedelta(minutes=1))
'''


class CheckpointDuringExtraAnswerGates(_ExtraCheckpointFixtures):
    """E55 (ticket 55): a checkpoint that lands while the extra is answering
    must still serialize, and a dying engine task must end the process.

    real-20261001T055020 stopped at sim 09:14–09:19 when the scheduler task
    raised ``KeyError: 'pending_question'`` in ``checkpoint_state``:
    ``_extra_loop`` consumed the question with ``pop`` before the turn, so
    "the extra is answering" was a window in which pending_question/
    pending_heard_speech did not exist — while ``checkpoint_state`` read them
    with direct subscripts. The scheduler died, the world froze, and the
    process still showed RUNNING because a provider call parked in
    ``asyncio.to_thread``'s non-daemon worker made the interpreter wait at
    exit. E50's round-trip test checked in right after generation and so
    never entered the answering window."""

    def test_checkpoint_during_extra_answer_does_not_raise_and_resumes(self):
        """E55(a): checkpoint inside the answering window (question already
        consumed) must not raise, the consumed fields must serialize as their
        restore defaults, and the restored extra must still answer."""
        import asyncio
        import threading

        entered, release = threading.Event(), threading.Event()
        answer = self.ANSWER

        class _BlockingExtra:
            def __init__(self):
                self.calls = 0

            def chat_with_tools(self, messages, tools):
                self.calls += 1
                entered.set()
                assert release.wait(10), "test never released the extra"
                return {"role": "assistant", "content": "", "tool_calls": [
                    {"id": f"c{self.calls}", "type": "function",
                     "function": {"name": "speak", "arguments": json.dumps(
                         {"inner": "这本账我确实听过", "text": answer},
                         ensure_ascii=False)}}]}

        base = self._extra_world()
        world = self._extra_world()
        engine = self._engine(world, _BlockingExtra())
        captured: dict = {}

        async def scenario():
            engine._spawn_extra("a", self.QUESTION, asyncio.get_running_loop())
            name = next(iter(engine._extras))
            task = engine._extra_tasks[name]
            while not entered.is_set():          # the loop consumed the question
                await asyncio.sleep(0.01)
            # Ticket 55 transient: the answer is in flight.
            captured["name"] = name
            captured["runner"] = engine.checkpoint_state()
            captured["world"] = engine.world.checkpoint_state()
            release.set()
            for _ in range(500):                 # let the turn land, then stop
                if any(e.kind == "speech" and e.actor == name
                       for e in world.event_log):
                    break
                await asyncio.sleep(0.01)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        asyncio.run(scenario())
        name = captured["name"]

        row = captured["runner"]["extras"][name]
        self.assertEqual(row["pending_question"], "")
        self.assertFalse(row["pending_heard_speech"])

        restored_world = World.from_checkpoint(base, captured["world"])
        resumed = self._engine(restored_world, self._speaking_extra())
        resumed.restore_checkpoint(captured["runner"])
        self.assertEqual(resumed._extras[name]["pending_question"], "")

        # The restored extra still answers a fresh directed line (not wedged).
        restored_world.submit(Intention("a", "speak",
                                        {"text": "那本账簿你什么时候交回去？",
                                         "to": [name]}, restored_world.version))
        asyncio.run(resumed._extra_turn(name, ""))
        lines = [str(e.payload.get("text", "")) for e in restored_world.event_log
                 if e.kind == "speech" and e.actor == name]
        self.assertIn(answer, lines)

    def test_executing_engine_task_crash_ends_the_process_without_a_zombie(self):
        """E55(c): a deliberately-raising engine task must end the process
        with a non-zero status promptly, even with a provider call parked in
        a worker thread. Pre-fix this hung until the test timeout and showed
        RUNNING (non-daemon to_thread kept the interpreter alive)."""
        import subprocess
        import sys

        started = time.monotonic()
        try:
            proc = subprocess.run([sys.executable, "-c", _ENGINE_CRASH_CHILD],
                                  cwd=str(_PROJECT_ROOT), capture_output=True,
                                  text=True, timeout=20)
        except subprocess.TimeoutExpired:
            self.fail("engine task crash left a zombie: the process never exited")
        elapsed = time.monotonic() - started

        self.assertNotEqual(proc.returncode, 0,
                            f"crash exited cleanly:\n{proc.stderr[-2000:]}")
        self.assertIn("checkpoint boom", proc.stderr)
        self.assertLess(elapsed, 15,
                        f"crash took {elapsed:.1f}s to end the process")


class NoteDeliveryGates(unittest.TestCase):
    """I44 (ticket 44, user ruling 2026-09-30): a note is delivered only to
    the next non-author entrant, and the author's receipt must say so.

    In the d1-am artifact 林瑶 left 陈默 a 借条 while he stood in the same room
    (turn 163, 09:51, nearby_actors=['陈默']); note_left #645 was the run's only
    note event — 陈默 left at 10:41 and no non-author ever entered the archive
    again, so the note stayed pending forever while the author got no signal.
    The mechanism (kernel._consume_notes -> note_read) already existed; the
    defect was the receipt and the invisibility of an undelivered note. The
    delivery/privacy/author-reentry semantics are pinned by test_world_pack:
    test_leave_note_waits_for_next_entry_and_hides_text_from_room,
    test_note_is_delivered_privately_to_only_the_next_enterer,
    test_note_author_reentry_preserves_own_note_for_a_later_reader."""

    START = datetime.fromisoformat("2026-03-16T09:51:00+08:00")
    NOTE = "借条：借出台风台账一份、移交存根一件，经手人：陈默（值班）。"

    def _room(self):
        from harness.kernel import ActorState, LocationState, World
        return World(start=self.START,
                     actors=[ActorState("林瑶", "校史档案室"),
                             ActorState("陈默", "校史档案室"),
                             ActorState("外人", "中庭")],
                     locations=[LocationState("校史档案室"), LocationState("中庭")],
                     routes={("校史档案室", "中庭"): 60,
                             ("中庭", "校史档案室"): 60})

    def test_leave_note_receipt_names_the_audience_and_offers_give(self):
        """(a) With 陈默 present, the receipt states the audience, names the
        people in the room, and offers the `give` path — without leaking the
        note body to the author or to the co-located actor."""
        from harness.engine import AsyncEngine

        class _Agent:
            session_obj = object()

            def __init__(self):
                self.delivered = []

            def deliver_tool_results(self, results):
                self.delivered.extend(results)

            def consume_compaction(self):
                return False

            def session_snapshot(self):
                return None

        world = self._room()
        agent = _Agent()
        engine = AsyncEngine(world, {a: agent for a in world.actors},
                             {a: PrivateState(a) for a in world.actors},
                             Trace("v4-test", "ticket44-receipt"), None,
                             decision_timeout=10, max_wall_seconds=30)
        engine._scheduler_wake = threading.Event()
        engine._stop_horizon = None
        engine._execute_chain("林瑶", [{"name": "leave_note",
                                        "arguments": {"text": self.NOTE},
                                        "tool_call_id": "note-1"}],
                              {"time": world.now.isoformat(), "events": []},
                              world.affordances("林瑶"), world.version)

        result = agent.delivered[0]
        self.assertTrue(result["ok"])
        receipt = str(result["text"])
        # (1) Audience: people present do not see the content; the first later
        #     non-author entrant reads the full text privately and burns it;
        #     the author's own return does not consume it.
        self.assertIn("在场", receipt)
        self.assertIn("非作者", receipt)
        self.assertIn("焚", receipt)
        self.assertIn("返场", receipt)
        # (2) The present person is named and `give` is offered as the path.
        self.assertIn("陈默", receipt)
        self.assertIn("give", receipt)
        # The receipt never carries the note body.
        self.assertNotIn(self.NOTE, receipt)
        # The co-located actor perceives only that a note was left.
        packet = world.poll("陈默")
        self.assertNotIn(self.NOTE, str(packet["events"]))
        self.assertFalse(any(e["kind"] == "note_read" for e in packet["events"]))

    def test_run_end_reports_undelivered_notes(self):
        """(d) A note still pending at the run endpoint is observable: the
        outcome carries the unread notes; once a non-author enters and burns
        it, the next run-end report is empty."""
        world = self._room()
        world.submit(Intention("林瑶", "leave_note", {"text": self.NOTE},
                               world.version))
        world.advance()
        trace = Trace("v4-test", "ticket44-unread")
        trace.finish(reason="stop_at_reached", world=world)
        pending = trace.outcome["unread_notes"]
        self.assertEqual([(n["author"], n["location"], n["text"]) for n in pending],
                         [("林瑶", "校史档案室", self.NOTE)])
        self.assertEqual(pending[0]["left_at"], world.now.isoformat())

        world.submit(Intention("外人", "move", {"target": "校史档案室"},
                               world.version))
        world.advance()
        trace.finish(reason="stop_at_reached", world=world)
        self.assertEqual(trace.outcome["unread_notes"], [])


class _ChainAgent:
    """Minimal v4 agent stub: it collects the chain's tool results."""

    session_obj = object()

    def __init__(self):
        self.delivered: list[dict] = []

    def deliver_tool_results(self, results):
        self.delivered.extend(results)

    def consume_compaction(self):
        return False

    def session_snapshot(self):
        return None


def _chain_engine(world):
    """An engine bound to one stub agent per actor, ready for
    `_execute_chain` — the same seam the ticket-44 gates use."""
    agents = {actor_id: _ChainAgent() for actor_id in world.actors}
    engine = AsyncEngine(world, agents,
                         {actor_id: PrivateState(actor_id) for actor_id in world.actors},
                         Trace("v4-test", "ticket46-chain"), None,
                         decision_timeout=10, max_wall_seconds=30)
    engine._scheduler_wake = threading.Event()
    engine._stop_horizon = None
    return engine, agents


class RecipientSnapshotGates(unittest.TestCase):
    """I46 (ticket 46, d1-am artifact real-20260930T160727).

    班长's 11:09 line to 陈默 was rejected `absent: 陈默` in the same turn whose
    affordances offered 陈默; its 11:14 line was rejected `unknown name
    '下棋大爷'` while that turn's perception listed 下棋大爷; 辅导员's 11:30 line
    to three people was dropped whole when one of them had walked off. The
    judgement must be the one the decision saw, and one bad addressee must
    never void the rest of the sentence."""

    START = datetime.fromisoformat("2026-09-30T11:09:00+08:00")

    def _scene(self, **places):
        """The d1-am scene: a 教学楼 corridor and 辅导员办公室 next door.
        Defaults put 班长/陈默/下棋大爷 in the corridor and 辅导员 in the
        office; keyword overrides restage them."""
        home = {"班长": "教学楼", "陈默": "教学楼", "下棋大爷": "教学楼",
                "辅导员": "辅导员办公室"}
        home.update(places)
        return World(start=self.START,
                     actors=[ActorState(name, place) for name, place in home.items()],
                     locations=[LocationState("教学楼"), LocationState("辅导员办公室")],
                     routes={("教学楼", "辅导员办公室"): 60,
                             ("辅导员办公室", "教学楼"): 60})

    def _walk_away(self, world, who, to="辅导员办公室"):
        """`who` leaves during the deliberation (the artifact's 11:09->11:17
        drift): the next turn's perception is already stale."""
        world.submit(Intention(who, "move", {"target": to}, world.version))
        world.advance()

    def test_one_bad_recipient_does_not_void_the_rest_of_the_batch(self):
        """(a)+(d) turn 233 (11:30): one line, three addressees, one of them
        gone — the words must reach whoever is still here and only the
        departed addressee may be reported as unreachable."""
        world = self._scene(辅导员="教学楼")
        self._walk_away(world, "陈默")
        engine, agents = _chain_engine(world)
        text = "纪风，表拿来我看看。老先生慢走。陈默，两点到四点。"
        engine._execute_chain("辅导员", [{
            "name": "speak",
            "arguments": {"text": text, "volume": "normal",
                          "to": ["班长", "下棋大爷", "陈默"],
                          "wait_response": False},
            "tool_call_id": "speak-1"}],
            {"time": world.now.isoformat(),
             "nearby_actors": ["班长", "下棋大爷", "陈默"], "events": []},
            world.affordances("辅导员"), world.version)

        result = agents["辅导员"].delivered[0]
        self.assertTrue(result["ok"], "一个离开的收件人不得作废整句话")
        self.assertIn("陈默", result["text"])
        self.assertIn("没送到", result["text"])
        speech = next(event for event in world.event_log if event.kind == "speech")
        self.assertEqual(speech.payload["text"], text, "整句话不得消失")
        self.assertEqual(speech.payload["to"], ["班长", "下棋大爷"])
        self.assertEqual(speech.payload["heard"], sorted(["班长", "下棋大爷"]))
        self.assertNotIn("陈默", speech.visible_to,
                         "离开的人不得因快照而被投递，也不得听见")

    def test_a_name_seen_in_the_perception_is_always_resolvable(self):
        """(b) turn 215 (11:14): `nearby_actors=['下棋大爷']` yet the submit
        answered `unknown name '下棋大爷'`. A name the decision saw must
        resolve; if that person has meanwhile left, the result says so."""
        world = self._scene()
        self._walk_away(world, "下棋大爷")
        engine, agents = _chain_engine(world)
        engine._execute_chain("班长", [{
            "name": "speak",
            "arguments": {"text": "大爷，您慢走。", "volume": "normal",
                          "to": ["下棋大爷"], "wait_response": False},
            "tool_call_id": "speak-1"}],
            {"time": world.now.isoformat(), "nearby_actors": ["下棋大爷"],
             "events": []}, world.affordances("班长"), world.version)

        result = agents["班长"].delivered[0]
        self.assertTrue(result["ok"])
        self.assertNotIn("unknown name", result["text"])
        self.assertIn("下棋大爷", result["text"])
        self.assertIn("没送到", result["text"])
        self.assertIn("离开", result["text"],
                      "名字解析成功但人已不在：结果是‘已离开’而不是‘不认识’")

    def test_every_recipient_offered_in_a_rejection_can_be_reached(self):
        """(c) the ticket-39 contract for recipients: the names a rejection
        prints come from the same judgement and each one succeeds on retry
        (the 11:30 rejection offered 唐小岚/宿管阿姨, who were not there)."""
        world = self._scene()
        world.actors["班长"].known_contacts = {"辅导员"}

        # give hands an object over: only people actually here are offered.
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("班长", "give",
                                   {"target": "辅导员", "item": "班里的表"},
                                   world.version))
        candidates = list(caught.exception.context["recipient_candidates"])
        self.assertEqual(candidates, ["下棋大爷", "陈默"])
        for name in candidates:
            world.actors["班长"].inventory.add("班里的表")
            world.submit(Intention("班长", "give",
                                   {"target": name, "item": "班里的表"},
                                   world.version))
            world.advance()

        # text reaches a contact wherever they are, and anyone here.
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("班长", "text",
                                   {"target": "杜撰的人", "text": "喂"},
                                   world.version))
        text_candidates = list(caught.exception.context["recipient_candidates"])
        self.assertIn("辅导员", text_candidates)
        self.assertIn("陈默", text_candidates)
        for name in text_candidates:
            world.submit(Intention("班长", "text", {"target": name, "text": "喂"},
                                   world.version))
            world.advance()

        # speak: whoever the judgement can address — anyone listed can be
        # submitted without a rejection (a departed one is a delivery note).
        engine, agents = _chain_engine(world)
        engine._execute_chain("班长", [{
            "name": "speak",
            "arguments": {"text": "喂", "volume": {"wrong": "type"},
                          "to": ["陈默"]},
            "tool_call_id": "speak-bad"}],
            {"time": world.now.isoformat(), "nearby_actors": ["陈默", "下棋大爷"],
             "events": []}, world.affordances("班长"), world.version)
        bad = agents["班长"].delivered[0]
        self.assertFalse(bad["ok"])
        listed = str(bad["text"]).split("Names in your personal knowledge or here: ")[1]
        names = [entry.strip() for entry in listed.split(".")[0].split(",") if entry.strip()]
        self.assertTrue(names)
        world.advance()   # the chain's no-world-action turn idles one tick
        for name in names:
            world.submit(Intention("班长", "speak",
                                   {"text": "喂", "volume": "normal",
                                    "to": [name], "wait_response": False},
                                   world.version))
            world.advance()

        # text: a shape failure offers contacts and people here — a name the
        # snapshot merely saw is not textable, so it is not offered.
        engine._execute_chain("班长", [{
            "name": "text",
            "arguments": {"text": "喂", "to": "辅导员"},
            "tool_call_id": "text-bad"}],
            {"time": world.now.isoformat(), "nearby_actors": ["陈默", "下棋大爷"],
             "events": []}, world.affordances("班长"), world.version)
        bad = agents["班长"].delivered[-1]
        self.assertFalse(bad["ok"])
        listed = str(bad["text"]).split("Names in your personal knowledge or here: ")[1]
        text_names = [entry.strip() for entry in listed.split(".")[0].split(",") if entry.strip()]
        self.assertEqual(text_names, sorted(["辅导员", "下棋大爷", "陈默"]))
        world.advance()
        for name in text_names:
            world.submit(Intention("班长", "text", {"target": name, "text": "喂"},
                                   world.version))
            world.advance()

    def test_one_costly_action_per_turn_is_protocol_text(self):
        """(4) the repeated `not executed: current … completes at …` (陈默
        145/147, 辅导员 T8/T9/T14/T16) came from a second costly action in one
        turn. The protocol text must state the rule, and the runtime copy must
        stay byte-identical to the documented §1 block."""
        from harness.natural_agent import SYSTEM_PROMPT_V4

        doc = (Path(__file__).parents[2] / "docs" / "V4-AGENT-INTERFACE.md").read_text(
            encoding="utf-8")
        self.assertIn(SYSTEM_PROMPT_V4, doc,
                      "§1 的 system prompt 必须与运行时逐字一致")
        self.assertIn("一个回合只应有一个耗时动作", SYSTEM_PROMPT_V4)

    def test_a_busy_chain_result_names_the_rule_and_the_retry_turn(self):
        """(4) the busy tool result must be self-correcting: it states the
        one-costly-action rule, the real completion time and the exact call
        to resubmit — without relaxing the busy gate or any duration."""
        world = self._scene()
        engine, agents = _chain_engine(world)
        # 辅导员 is still deciding, so this turn's world may only reach one
        # tick ahead (the freeze rule): the second costly action cannot start.
        engine._inflight["辅导员"] = world.now
        calls = [{"name": "wait", "arguments": {"duration_seconds": 180},
                  "tool_call_id": "wait-1"},
                 {"name": "speak", "arguments": {
                     "text": "我到了。", "volume": "normal", "to": ["辅导员"],
                     "wait_response": False}, "tool_call_id": "speak-2"}]
        engine._execute_chain("班长", calls,
                              {"time": world.now.isoformat(), "events": []},
                              world.affordances("班长"), world.version)

        results = agents["班长"].delivered
        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[1]["ok"])
        self.assertIn("一个回合只应有一个耗时动作", results[1]["text"])
        self.assertIn("not executed", results[1]["text"])
        self.assertIn('"name": "speak"', results[1]["text"])
        self.assertIn(world.actors["班长"].busy_until.isoformat(), results[1]["text"])


class SeedKnowledgeContractGates(unittest.TestCase):
    """Ticket 47: the seed may not leak a mystery answer, strand a guardrail,
    or promise a prop the world cannot produce. Each rule is proven red on a
    deliberately broken copy of the shipped seed and green on the real one."""

    @staticmethod
    def _module():
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "seed_lint_ticket47",
            Path(__file__).parents[2] / "scripts" / "seed_lint.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _source():
        return Path(__file__).parents[2] / "world"

    @staticmethod
    def _copy(directory):
        import shutil
        root = Path(directory) / "world"
        shutil.copytree(SeedKnowledgeContractGates._source(), root)
        return root

    @staticmethod
    def _edit_manifest(root, mutate):
        import yaml
        path = root / "manifest.yml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")

    def test_puzzle_answer_leak_fails_seed_lint(self):
        """K1: writing the audit answer back into the puzzle desc must go red."""
        module = self._module()
        self.assertEqual(module.lint(self._source()), [],
                         "the shipped seed separates the mystery from its answer")
        with TemporaryDirectory() as directory:
            root = self._copy(directory)

            def leak(data):
                for row in data["concepts"]:
                    if row["id"] == "audit-case":
                        row["desc"] = ("[[学生会办公室]]的一份在办审计：汇总表上有两个"
                                       "总额没有标注用途，手写更正没有署名。核对期限是今天 16:00。")

            self._edit_manifest(root, leak)
            findings = module.lint(root)
            self.assertTrue(any("谜底泄漏" in f for f in findings), findings)

    def test_guard_row_unreachable_by_plot_phrase_fails_seed_lint(self):
        """K2: a guard row whose only key misses the plot phrase must go red."""
        module = self._module()
        self.assertEqual(module.lint(self._source()), [])
        with TemporaryDirectory() as directory:
            root = self._copy(directory)

            def strand(data):
                for row in data["kb"]["陈默妈"]:
                    if "老街坊代表" in row.get("keys", []):
                        row["keys"] = ["老街坊代表"]

            self._edit_manifest(root, strand)
            findings = module.lint(root)
            self.assertTrue(any("检索不到" in f for f in findings), findings)

    def test_hits_cannot_reach_old_street_rep_from_the_plot_sentence(self):
        """K2 root cause, pinned at the matcher: hits() only compares row keys
        against the whole query, so a longer key hides inside a shorter plot
        word and vice versa only for a short query."""
        from harness.kb import hits
        sms = "妈，问个旧事：2013年台风撤离那张许可证，落款签字的街坊代表是谁？"
        self.assertFalse(hits(["老街坊代表"], [sms]))
        self.assertTrue(hits(["街坊代表"], [sms]))
        self.assertTrue(hits(["2013年台风"], [sms]))

    def test_unregistered_persona_prop_fails_seed_lint(self):
        """K47c: a named prop a character card promises must resolve."""
        module = self._module()
        self.assertEqual(module.lint(self._source()), [])
        with TemporaryDirectory() as directory:
            root = self._copy(directory)
            card = root / "characters" / "班长.md"
            card.write_text(card.read_text(encoding="utf-8")
                            + "\n他手里永远压着一张二班的考勤表。\n",
                            encoding="utf-8")
            findings = module.lint(root)
            self.assertTrue(any("考勤表" in f for f in findings), findings)

    def test_unresolved_inline_content_name_fails_seed_lint(self):
        """K47d: a name-like token inside inline content must resolve."""
        module = self._module()
        self.assertEqual(module.lint(self._source()), [])
        with TemporaryDirectory() as directory:
            root = self._copy(directory)

            def break_name(data):
                for row in data["items"]:
                    if row["id"] == "值班簿":
                        row["content"] = row["content"].replace("值班干事", "王阿姨")

            self._edit_manifest(root, break_name)
            findings = module.lint(root)
            self.assertTrue(any("王阿姨" in f for f in findings), findings)

    def test_counselor_knows_the_question_not_the_answer(self):
        """K1 at the world level: 辅导员's first-screen KB holds the deadline
        question but not the conclusion, which only reading the package gives."""
        from harness.world_loader import load_world_pack
        pack = load_world_pack(self._source())
        delivered = "\n".join(str(row["desc"]) for row in pack.kb["辅导员"])
        self.assertIn("核对期限", delivered)
        for clause in ("汇总表上有两个总额没有标注用途",
                       "旁边一处手写更正没有署名",
                       "底层的报销凭证不在这包里"):
            self.assertNotIn(clause, delivered)
        world = pack.build_world()
        self.assertIn("底层的报销凭证不在这包里",
                      world.document_defs["学生会审计包"]["content"])

    def test_name_collision_warning_names_the_confusable_pair(self):
        """K47e: the 小陈/陈默 clash is warned, and warnings never block."""
        module = self._module()
        joined = "\n".join(module.collision_warnings(self._source()))
        self.assertIn("小陈", joined)
        self.assertIn("陈默", joined)
        self.assertEqual(module.lint(self._source()), [],
                         "a homonym warning must not gate the seed")


def _seed_lint_module():
    """Load scripts/seed_lint.py as a module (same importlib pattern the
    ticket-47 seed-contract gates use)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "seed_lint_ticket60", Path(__file__).parents[2] / "scripts" / "seed_lint.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _world_root() -> Path:
    return Path(__file__).parents[2] / "world"


def _copy_world(directory) -> Path:
    import shutil
    root = Path(directory) / "world"
    shutil.copytree(_world_root(), root)
    return root


def _rewrite(root: Path, relative: str, mutate) -> None:
    path = root / relative
    path.write_text(mutate(path.read_text(encoding="utf-8")), encoding="utf-8")


def _edit_manifest(root: Path, mutate) -> None:
    import yaml
    path = root / "manifest.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


class SeedLocationPropGates(unittest.TestCase):
    """Ticket 60 (d1-am artifact real-20261001T065553): three props lived only
    in a room's prose. 陈默 read 扫描仪 / 扫描仪日志 four times inside 43
    minutes in 校史档案室, 林瑶室友 read 校史专用柜 / 专用柜登记本 in 图书馆,
    and 辅导员 tried `take 桌上的白纸和笔` / `take 纸笔` in the archive. No
    entity backed any of them, so the world answered "这里没有这件东西" and the
    room read as broken. Ticket 47's lint covered character cards (K47c) and
    inline manifest content (K47d), never a location body.

    The gates prove the red/green pair for both legal dispositions: assert a
    prop as usable without registering it -> red; register it -> green; write
    the truth into the sentence (the shipped fix) -> green.
    """

    ARCHIVE = "locations/校史档案室.md"
    LIBRARY = "locations/图书馆.md"
    # The shipped wording keeps the archived scanner in the room's detail and
    # declares it out for repair (ticket 58's own tests locate the archive
    # interior by the first clause, so that clause stays verbatim).
    ARCHIVE_SHIPPED = "平时扫描仪的待机灯常绿，这几天机器送修了"
    ARCHIVE_ASSERTS_USABLE = "扫描仪的待机灯常绿"
    LIBRARY_SHIPPED = ("校史相关材料锁在一楼角落的一只专用柜里，"
                       "柜门钥匙在借阅处的学生馆员手上，学生自己打不开——")
    LIBRARY_ASSERTS_USABLE = "校史相关材料在一楼角落的专用柜，查阅要登记——"

    def test_shipped_seed_declares_the_scanner_and_cabinet_unusable(self):
        """Both traps are fixed by wording, not by a fake registration: the
        seed stays green and says why the prop cannot be used here."""
        lint = _seed_lint_module()
        self.assertEqual(lint.lint(_world_root()), [])
        archive = (_world_root() / self.ARCHIVE).read_text(encoding="utf-8")
        library = (_world_root() / self.LIBRARY).read_text(encoding="utf-8")
        self.assertIn(self.ARCHIVE_SHIPPED, archive)
        self.assertIn("没有备用的纸笔", archive)
        self.assertIn(self.LIBRARY_SHIPPED, library)
        self.assertIn("打不开", library)

    def test_an_asserted_interior_prop_without_a_registration_fails_seed_lint(self):
        """K60 red -> green (ticket 60 §3): the room asserting a working scanner
        and a reachable library cabinet is a pre-run block; the shipped "cannot
        be used" wording is the legal fix with no entity registered."""
        lint = _seed_lint_module()
        with TemporaryDirectory() as directory:
            root = _copy_world(directory)
            _rewrite(root, self.ARCHIVE, lambda text: text.replace(
                self.ARCHIVE_SHIPPED, self.ARCHIVE_ASSERTS_USABLE))
            _rewrite(root, self.LIBRARY, lambda text: text.replace(
                self.LIBRARY_SHIPPED, self.LIBRARY_ASSERTS_USABLE))
            findings = lint.lint(root)
            self.assertTrue(any("扫描仪" in f for f in findings), findings)
            self.assertTrue(any("专用柜" in f for f in findings), findings)
            self.assertTrue(any("不可操作表述" in f for f in findings), findings)
            # 改写为不可操作 -> 绿（无需注册）
            _rewrite(root, self.ARCHIVE,
                     lambda text: text.replace(self.ARCHIVE_ASSERTS_USABLE,
                                               self.ARCHIVE_SHIPPED))
            _rewrite(root, self.LIBRARY,
                     lambda text: text.replace(self.LIBRARY_ASSERTS_USABLE,
                                               self.LIBRARY_SHIPPED))
            self.assertEqual(lint.lint(root), [])

    def test_registering_a_promised_interior_prop_turns_the_same_prose_green(self):
        """The other legal disposition (ticket 60 §2): keep the room asserting a
        working scanner, register it as a placed, non-readable item and mark the
        name in the prose — the same sentence now passes."""
        lint = _seed_lint_module()
        with TemporaryDirectory() as directory:
            root = _copy_world(directory)
            _rewrite(root, self.ARCHIVE,
                     lambda text: text.replace(self.ARCHIVE_SHIPPED,
                                               "[[扫描仪]]的待机灯常绿"))
            (root / "items" / "扫描仪.md").write_text(
                "# 扫描仪\n\n档案室那台平板机器，把纸质件扫成图像；机身上没有可读的正文。\n",
                encoding="utf-8")
            known_to = ["陈默", "林瑶", "唐小岚", "宿管阿姨", "食堂大妈",
                        "辅导员", "班长", "林瑶室友", "下棋大爷"]

            def register(data):
                data["items"].append({
                    "id": "扫描仪", "location": "校史档案室", "known_to": known_to,
                    "readable": False,
                    "readable_reason": "一台平板扫描仪，机身上没有可读的正文。",
                })

            _edit_manifest(root, register)
            self.assertEqual(lint.lint(root), [])

    def test_unregistered_interior_props_still_offer_a_real_next_call(self):
        """Ticket 60 negative case: the actor's attempt must get the truth plus
        an executable alternative, never a dead end. The archive keeps readable
        material (so its offered calls really run), and the room detail the
        actor already received names where the pen and paper actually are."""
        from harness.kernel import Intention
        world = load_story_pack().build_world()

        counselor = world.actors["辅导员"]
        counselor.location = "校史档案室"
        detail = world.poll("辅导员")["descriptions"]["校史档案室"]
        self.assertIn("送修", detail)
        self.assertIn("纸笔", detail)
        self.assertIn("学生会办公室", detail)
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("辅导员", "take", {"item": "纸笔"},
                                   world.version))
        message = str(caught.exception)
        self.assertIn("这里没有「纸笔」可拿", message)
        self.assertIn("签到本", message)          # what really is here
        self.assertTrue(caught.exception.alternatives)
        first = str(caught.exception.alternatives[0])
        self.assertTrue(first.startswith("take "))
        taken = first[len("take "):]
        world.submit(Intention("辅导员", "take", {"item": taken},
                               world.version))
        world.advance()
        self.assertIn(taken, counselor.inventory)

        reader = world.actors["陈默"]
        reader.location = "校史档案室"
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("陈默", "read", {"item": "扫描仪"},
                                   world.version))
        readable_now = caught.exception.context.get("readable_now") or []
        self.assertTrue(readable_now, str(caught.exception))
        self.assertTrue(caught.exception.alternatives)
        target = str(readable_now[0])
        world.submit(Intention("陈默", "read", {"item": target}, world.version))
        world.advance()
        self.assertIn(target, [event.payload.get("document")
                               for event in world.event_log
                               if event.kind == "document_read"])

        roommate = world.actors["林瑶室友"]
        roommate.location = "图书馆"
        library_detail = world.poll("林瑶室友")["descriptions"]["图书馆"]
        self.assertIn("钥匙", library_detail)
        self.assertIn("打不开", library_detail)
        for invented in ("校史专用柜", "专用柜登记本"):
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("林瑶室友", "read", {"item": invented},
                                       world.version))
            self.assertIn(f"这里没有「{invented}」", str(caught.exception))

    def test_the_registered_pen_and_paper_stay_in_the_student_union_office(self):
        """"不要两边都放": the archive states it has no spare paper, and the one
        registered 可用纸笔 stays where the 08:20 notice and the 场地申请表
        flow need it."""
        from harness.world_loader import load_world_pack
        pack = load_world_pack(_world_root())
        rows = {str(row["id"]): row for row in pack.items}
        self.assertEqual(rows["可用纸笔"]["location"], "学生会办公室")
        world = pack.build_world()
        self.assertEqual(world.item_locations.get("可用纸笔"), "学生会办公室")
        self.assertNotIn("纸笔", world.item_locations)   # no second copy anywhere
        archive = (_world_root() / self.ARCHIVE).read_text(encoding="utf-8")
        self.assertEqual(archive.count("纸笔"), 1)


class Ticket65CanteenServeGates(unittest.TestCase):
    """Ticket 65 (real-20261001T121425+0800-223688-090345540).

    食堂大妈 failed seven take/give attempts for food and rope (`take 一碗豆浆、
    一个菜包、一个豆沙包`, `take 荤菜、素菜、米饭、一碗汤`), then said "豆浆
    包子趁烫，端好" with nothing behind it. The canteen (and the shop) modeled
    no item at all, so the serving counter had nothing to hand over. The same
    run's rope thread is the other half: 下棋大爷 claimed a coil of nylon rope
    on his stone table and 宿管阿姨 "found" one in the corner toolbox — a
    category left deliberately unmodeled, so the room's own detail must say it
    is not available instead of the world promising it and dead-ending.

    The seed backs the two counter-locations with a minimal real item and
    states the rope's unavailability where it was reached for."""

    CANTEEN_ITEM = "一份餐食"
    ZHONGTING = "locations/中庭.md"
    DORM = "locations/女生宿舍.md"

    def test_the_canteen_can_hand_a_meal_to_someone_present(self):
        """(a) Today-red: the counter has a give-able meal, so the server's
        hand-over is an `item_given` event, never narration."""
        world = load_story_pack().build_world()
        world.actors["陈默"].location = "食堂"
        world.submit(Intention("食堂大妈", "give",
                               {"target": "陈默", "item": self.CANTEEN_ITEM},
                               world.version))
        world.advance()
        given = [e for e in world.event_log if e.kind == "item_given"]
        self.assertEqual([e.payload["item"] for e in given], [self.CANTEEN_ITEM])
        self.assertIn(self.CANTEEN_ITEM, world.actors["陈默"].inventory)

    def test_the_shop_backs_its_brief_with_takeable_goods(self):
        """The shop's brief names 零食/饮料/关东煮; the seed backs it with a
        minimal take-able stock instead of leaving the promise unmodeled."""
        from harness.world_loader import load_world_pack
        pack = load_world_pack(_world_root())
        rows = {str(row["id"]): row for row in pack.items}
        at_shop = [item for item, row in rows.items()
                   if row.get("location") == "小卖部"]
        self.assertTrue(at_shop, "小卖部正文承诺了货品，却没有一件可拿的物品")
        world = pack.build_world()
        for item in at_shop:
            self.assertEqual(world.item_locations.get(item), "小卖部")

    def test_rope_is_declared_unavailable_where_it_was_reached_for(self):
        """(b) The rope is deliberately not an item; the two rooms where it was
        reached for say so in their own interior detail (ticket 60 wording), so
        the model reads "there is none here" instead of being promised one and
        dead-ending. A take of it still answers truthfully about what is here."""
        zhongting = (_world_root() / self.ZHONGTING).read_text(encoding="utf-8")
        dorm = (_world_root() / self.DORM).read_text(encoding="utf-8")
        self.assertIn("没有绳子", zhongting)
        self.assertIn("没有绳子", dorm)
        world = load_story_pack().build_world()
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("下棋大爷", "take", {"item": "尼龙绳"},
                                   world.version))
        self.assertIn("这里没有「尼龙绳」可拿", str(caught.exception))


def _seed_lint_module():
    """Load scripts/seed_lint.py as a module (same importlib pattern the
    other seed-lint gates use)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "seed_lint_ticket66", Path(__file__).parents[2] / "scripts" / "seed_lint.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Ticket66DeadEndGates(unittest.TestCase):
    """I66 (ticket 66, real-20261001T121425+0800-223688-090345540).

    陈默妈's 李阿姨 goal dead-ended on all three routes (`knock 李阿姨家`,
    `text 李阿姨` as unknown name, `move 老家属院` as "没有可用的路" with no
    alternative and no reason), so "给李阿姨带话" could never complete and
    nothing corrected her. 宿管阿姨 could message 下棋大爷 but her reply came
    back `unknown name '下棋大爷'` — the address book is one-way, so the
    borrowed-rope thread died. 林瑶室友 `move 305宿舍` got "不是一个你知道的
    地方" for her own room.

    The reachability contract: a named target a role treats as a place or
    contact must be reachable, contactable, or explicitly unavailable with an
    executable alternative."""

    def test_unreachable_names_get_a_story_executable_alternative(self):
        """(a) 李阿姨/李阿姨家/老家属院 are neither reachable nor contactable;
        each rejection must name the world fact and hand back an executable
        next step, never leaving all three routes dead."""
        world = load_story_pack().build_world()
        cases = [
            ("text", {"target": "李阿姨", "text": "李姐，帮你带句话"},
             ("邻居", "托人")),
            ("knock", {"target": "李阿姨家"},
             ("门牌", "那边的人", "走不过去")),
            ("move", {"target": "老家属院"},
             ("电话", "走不过去", "那边的人")),
        ]
        for kind, args, needles in cases:
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("陈默妈", kind, dict(args), world.version))
            message = str(caught.exception)
            self.assertIn(args["target"], message)
            self.assertTrue(
                any(needle in message for needle in needles),
                f"{kind} {args['target']} gave no executable alternative: {message}")

    def test_a_one_way_address_book_is_flagged_and_hinted(self):
        """(b) 下棋大爷 can message 宿管阿姨; she cannot reply because her
        address book lacks him. The gap is visible before a run (lint) and at
        run time (received-but-unrecorded sender), with the executable way to
        close it — never a silent drop."""
        from harness.prompt import render_world_message
        lint = _seed_lint_module()
        warnings = lint.contact_symmetry_warnings(_world_root())
        self.assertTrue(any("宿管阿姨" in w and "下棋大爷" in w for w in warnings),
                        warnings)

        world = load_story_pack().build_world()
        world.submit(Intention("下棋大爷", "text",
                               {"target": "宿管阿姨", "text": "阿姨，借根粗尼龙绳。"},
                               world.version))
        world.advance()
        perception = world.poll("宿管阿姨")
        self.assertIn("下棋大爷", perception.get("unrecorded_senders", []))
        rendered = render_world_message(perception)
        self.assertIn("下棋大爷", rendered)
        self.assertIn("update_memory", rendered)
        self.assertIn("!contact", rendered)

    def test_a_room_number_is_reachable_or_explained(self):
        """(c) 林瑶室友's `move 305宿舍` said only "不是一个你知道的地方". The
        rejection must name the building the room lives in and say why it is
        not a separate place, instead of a bare unknown-place rejection."""
        world = load_story_pack().build_world()
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("林瑶室友", "move", {"target": "305宿舍"},
                                   world.version))
        message = str(caught.exception)
        self.assertIn("305", message)
        self.assertIn("女生宿舍", message)
        self.assertTrue(any(needle in message for needle in ("房间", "寝室", "不单独建模")),
                        message)


def _checker_module():
    """Load scripts/check_milestones.py as a module for the ticket-48
    scene-health metrics (same importlib pattern the seed-lint gates use)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_milestones_ticket48",
        Path(__file__).parents[2] / "scripts" / "check_milestones.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _speech_artifact(speech, reads=()):
    """A minimal day-1 artifact: (h, m, actor, text) speech events plus
    (h, m, actor, document) document_read events, enough for the two metrics."""
    events = []
    for index, (hour, minute, actor, text) in enumerate(speech, start=1):
        events.append({
            "id": index,
            "time": f"2026-03-16T{hour:02d}:{minute:02d}:00+08:00",
            "kind": "speech", "actor": actor,
            "payload": {"text": text, "heard": []}, "visible_to": [actor],
            "world_version": index})
    for offset, (hour, minute, actor, document) in enumerate(reads, start=len(events) + 1):
        events.append({
            "id": offset,
            "time": f"2026-03-16T{hour:02d}:{minute:02d}:00+08:00",
            "kind": "document_read", "actor": actor,
            "payload": {"document": document, "title": document},
            "visible_to": [actor], "world_version": offset})
    return {"world_events": events}


class Ticket48NarratedFactGates(unittest.TestCase):
    """Ticket 48 (d1-am artifact real-20260930T160727).

    Four independent reviewers each reported the same shape: a tool call
    that never succeeded is narrated as a completed, verified fact. These
    gates pin the three fixes: verb-gap teaching, identity-preserving
    recipient resolution, and the protocol sentence that only tool-called
    acts are real. The lane adds no NLP gate."""

    START = datetime.fromisoformat("2026-03-16T09:00:00+08:00")

    def _phone_scene(self):
        """陈默 at 教学楼, his mother remote — the scene whose d1-am 11:51
        text used an invented name/number (1395731xxxx（张建国儿子）)."""
        world = World(start=self.START,
                      actors=[ActorState("陈默", "教学楼"),
                              ActorState("陈默妈", "老家县城")],
                      locations=[LocationState("教学楼"), LocationState("老家县城")],
                      routes={("教学楼", "老家县城"): 600,
                              ("老家县城", "教学楼"): 600})
        world.actors["陈默"].known_contacts = {"陈默妈"}
        return world

    def test_alias_group_keeps_one_intended_recipient(self):
        """(2) A contact addressed by two of the actor's own KB nicknames for
        the SAME person (a number plus a description) is one intended
        recipient, not an ambiguity that voids the message. The private body
        must reach that person unchanged."""
        world = self._phone_scene()
        # what engine._sync_contacts mirrors from the actor's !contact row
        world.actors["陈默"].contact_aliases = {
            "1395731xxxx": "陈默妈", "张建国儿子": "陈默妈"}
        spoken = "妈，那个号再核一下。"
        world.submit(Intention("陈默", "text",
                               {"target": "1395731xxxx（张建国儿子）", "text": spoken},
                               world.version))
        world.advance()
        sent = [e for e in world.event_log if e.kind == "message_sent"]
        self.assertEqual([e.payload["target"] for e in sent], ["陈默妈"],
                         "两个都指向同一个人的称呼不是歧义")
        delivered = [e for e in world.event_log if e.kind == "message_delivered"]
        self.assertTrue(delivered)
        self.assertEqual(delivered[0].payload["text"], spoken,
                         "私密正文必须原样送达真正的收件人")

    def test_unknown_recipient_answer_preserves_the_intent(self):
        """(2) A number/description that denotes nobody the actor can reach
        must not silently rewrite the recipient, must not re-send the private
        body elsewhere, and must offer an executable, intent-preserving path
        (record the lead, find out who it is) instead of only 'unknown'."""
        world = self._phone_scene()
        engine, agents = _chain_engine(world)
        body = "妈，您再帮我看一眼那号码。"
        engine._execute_chain("陈默", [{
            "name": "text",
            "arguments": {"target": "1395731xxxx（张建国儿子）",
                          "text": body, "wait_response": False},
            "tool_call_id": "text-1"}],
            {"time": world.now.isoformat(), "nearby_actors": [], "events": []},
            world.affordances("陈默"), world.version)
        result = agents["陈默"].delivered[0]
        self.assertFalse(result["ok"])
        text = str(result["text"])
        self.assertIn("1395731xxxx", text, "必须点名你真正写下的称呼/号码")
        self.assertIn("update_memory", text, "要给出可执行的记线索路径")
        self.assertIn("不会", text, "必须说明原话不会被改发")
        self.assertNotIn(body, text, "私密正文不得被复用成发给别人的调用")
        self.assertNotIn('"name": "text"', text,
                         "不得生成携带原正文的改发调用")

    def test_verb_gap_teaching_names_the_real_action(self):
        """(1) A verb the world does not model gets explicit unavailable
        feedback that names the real action: 打电话 -> text; 签字/批注 ->
        leave_note on=<文书>（票 95 E98 起签字只是写进既有文书的一栏）;
        开柜/取件 -> take."""
        world = self._phone_scene()
        engine, agents = _chain_engine(world)
        cases = [("call", {"target": "陈默妈", "text": "喂"}, '"name": "text"'),
                 ("phone", {"number": "1395731xxxx"}, '"name": "text"'),
                 ("sign", {"item": "移交存根"}, "leave_note"),
                 ("annotate", {"item": "2013年台风台账"}, "leave_note"),
                 ("verify", {"item": "移交存根"}, "read"),
                 ("open", {"item": "晚归登记本"}, "take")]
        for verb, args, needle in cases:
            engine._execute_chain("陈默", [{
                "name": verb, "arguments": dict(args),
                "tool_call_id": f"{verb}-1"}],
                {"time": world.now.isoformat(), "nearby_actors": [], "events": []},
                world.affordances("陈默"), world.version)
            world.advance()
            result = agents["陈默"].delivered[-1]
            self.assertFalse(result["ok"], verb)
            self.assertIn(needle, str(result["text"]),
                          f"{verb} 的反馈要指向真正做得到的动作")
            self.assertIn("没有", str(result["text"]), verb)

    def test_protocol_forbids_narrating_unperformed_actions(self):
        """(3) The §1 protocol sentence: only tool-called acts count; do not
        assert an unperformed act as done or an unread document as verified.
        The runtime prompt and the doc block stay byte-identical."""
        from harness.natural_agent import SYSTEM_PROMPT_V4
        doc = (Path(__file__).parents[2] / "docs" / "V4-AGENT-INTERFACE.md").read_text(
            encoding="utf-8")
        self.assertIn("只有你真的做过的事才能说成做过", SYSTEM_PROMPT_V4)
        self.assertIn("没读过的内容", SYSTEM_PROMPT_V4)
        self.assertIn(SYSTEM_PROMPT_V4, doc,
                      "§1 的 system prompt 必须与运行时逐字一致")

    def test_verb_gap_block_matches_the_doc_verbatim(self):
        """(1)(5) The verb-gap inventory documented in the interface spec
        must be rendered from the runtime constant, so docs and behaviour
        cannot drift apart."""
        from harness.engine import VERB_GAP_TEACHING, render_verb_gap_block
        doc = (Path(__file__).parents[2] / "docs" / "V4-AGENT-INTERFACE.md").read_text(
            encoding="utf-8")
        for verb in ("call", "phone", "dial", "sign", "annotate", "seal",
                     "verify", "check", "open", "unlock"):
            self.assertIn(verb, VERB_GAP_TEACHING,
                          f"§2.2 的动作缺口清单必须覆盖 {verb}")
        self.assertIn(render_verb_gap_block(), doc,
                      "§2.2 的缺口清单必须与运行时常量逐字一致")

    def test_checker_flags_a_read_claim_without_a_read(self):
        """(4) metric A: a first-person read claim naming an object the actor
        has no document_read for that day is counted (review only)."""
        module = _checker_module()
        claimed = _speech_artifact(
            [(12, 17, "宿管阿姨",
              "你阿姨这本子翻了十二年——没见着\"林瑶\"俩字")])["world_events"]
        hits = module.read_claims_without_a_read(claimed, 1)
        self.assertTrue(hits, "宿管阿姨 5 次 read 全被拒，却叙述成问过本子")
        self.assertEqual(hits[0]["actor"], "宿管阿姨")

        read_it = _speech_artifact(
            [(12, 17, "宿管阿姨", "我读过晚归登记本，上面没有她的名字。")],
            reads=[(11, 0, "宿管阿姨", "晚归登记本")])["world_events"]
        self.assertEqual(
            module.read_claims_without_a_read(read_it, 1), [],
            "真的读过时不得误报")

    def test_checker_flags_unregistered_named_objects(self):
        """(4) metric B: a named-object-shaped token outside the registry is
        counted with a sample; a registered item is not."""
        module = _checker_module()
        registry = {"晚归登记本", "借阅登记本"}
        fabricated = _speech_artifact(
            [(10, 56, "陈大爷",
              "好，柜开了——蓝皮夹就这一册，你接稳了。")])["world_events"]
        hits = module.unregistered_object_claims(fabricated, 1, registry=registry)
        self.assertTrue(hits, "extra 叙述了没有注册的蓝皮夹")
        self.assertEqual(hits[0]["object"], "蓝皮夹")
        self.assertEqual(hits[0]["actor"], "陈大爷")

        registered = _speech_artifact(
            [(11, 51, "宿管阿姨",
              "晚归登记本我翻了，昨晚没人登记回来。")])["world_events"]
        self.assertEqual(
            module.unregistered_object_claims(registered, 1, registry=registry), [],
            "注册过的具名物件（晚归登记本）不得误报")


_STALL_START = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def _stall_world():
    return World(start=_STALL_START,
                 actors=[ActorState("a", "room"), ActorState("b", "room")],
                 locations=[LocationState("room"), LocationState("far")],
                 routes={("room", "far"): 120})


class _BlockingAgent:
    """A decision that never returns until the test releases its gate; the
    first call blocks forever, later calls resolve (ticket 53)."""

    def __init__(self, gate):
        self.gate = gate
        self.calls = 0

    def __call__(self, state, perception, affordances):
        self.calls += 1
        if self.calls == 1:
            self.gate.wait(timeout=1)
        return Intention(state.actor_id, "wait",
                         {"duration_seconds": 60}, perception["world_version"])


class _LeisurelyAgent:
    """Healthy but slow: every turn costs a little wall time and still makes
    a real world step (ticket 53 — a slow thinker is not a stall). With
    ``speak=True`` it keeps talking, which re-marks a co-located hung actor as
    "ready" through ambient events (the quiescence trap the release rule must
    not fall into)."""

    def __init__(self, delay, speak=False):
        self.delay = delay
        self.speak = speak
        self.calls = 0

    def __call__(self, state, perception, affordances):
        self.calls += 1
        time.sleep(self.delay)
        if self.speak:
            return Intention(state.actor_id, "speak",
                             {"text": "我还在，别急。"}, perception["world_version"])
        return Intention(state.actor_id, "wait",
                         {"duration_seconds": 60}, perception["world_version"])


class _V4SessionStub:
    """Minimal v4-session shape: `decide` appends the world message like
    V4Session.decide does, so an abandoned hang leaves a dangling user turn."""

    def __init__(self, messages=None):
        self.messages = list(messages or [{"role": "system", "content": "s"}])

    def snapshot(self):
        return {"format": "v4-character-session-1", "actor": "a",
                "messages": [dict(m) for m in self.messages],
                "compacted_memories": []}


class _V4HungAgent:
    """v4-shaped agent whose first decision hangs after appending its user
    turn; later decisions resolve (ticket 53 residual-wait isolation)."""

    session_obj = True

    def __init__(self, gate):
        self.gate = gate
        self.sess = _V4SessionStub()
        self.calls = 0
        self.first_message = ""

    def __call__(self, world_message, state):
        self.calls += 1
        if self.calls == 1:
            self.first_message = world_message
            self.sess.messages.append({"role": "user", "content": world_message})
            self.gate.wait(timeout=1)
            return {"text": "", "calls": [], "inner": None}
        return {"text": "", "calls": [{"name": "wait",
                                        "arguments": {"duration_seconds": 60}}]}

    def session_snapshot(self):
        return self.sess.snapshot()

    def restore_session(self, snapshot):
        self.sess = _V4SessionStub(snapshot["messages"])

    def deliver_tool_results(self, results):
        pass

    def consume_compaction(self):
        return False


def _stop_diagnostic(trace):
    for turn in trace.system_turns:
        if turn.get("request", {}).get("kind") == "engine_stop_diagnostic":
            return turn["result"]
    return None


class StallAndHungDecisionGates(unittest.TestCase):
    """Ticket 53 (real-20261001T015004, frozen at 11:32 on turn 248).

    The `stall_budget_ratio` gate measured *cumulative* freeze wall time, so a
    healthy-but-slow run drifting toward the budget eventually tripped it; and
    the scheduler's freeze branch waited on `min(_inflight.values())` with no
    bound, so one decision that never returned pinned the whole clock until a
    72-minute `decision_timeout` (never reached) or the stall gate fired. The
    four gates below pin the fixed semantics: consecutive no-progress, a
    bounded horizon release, a bounded residual wait, and a diagnostic that
    survives into the trace."""

    def _engine(self, world, agents, **kw):
        states = {actor: PrivateState(actor) for actor in world.actors}
        trace = Trace("v4-test", "historical-gate-ticket-53")
        engine = AsyncEngine(world, agents, states, trace, None, **kw)
        return engine, trace

    def test_hung_decision_is_released_and_the_run_reaches_the_endpoint(self):
        """(a) One decision that never returns must not pin the clock: the
        scheduler releases its horizon, the other actor keeps stepping, and
        the run still reaches the requested endpoint."""
        gate = threading.Event()
        world = _stall_world()
        agents = {"a": _BlockingAgent(gate), "b": _LeisurelyAgent(0.01, speak=True)}
        engine, trace = self._engine(world, agents, decision_timeout=30.0,
                                     freeze_tolerance_seconds=0.1,
                                     stall_threshold_seconds=30.0,
                                     max_wall_seconds=30.0)
        try:
            reason = engine.run(stop_at=_STALL_START + timedelta(seconds=600),
                                max_turns=200)
        finally:
            gate.set()
        self.assertEqual(reason, "stop_at_reached",
                         "一个挂死的决策把整轮时钟钉死了")
        self.assertGreaterEqual(agents["b"].calls, 5,
                                "另一个角色没有继续推进")
        self.assertTrue(any(e.kind == "speech" for e in world.event_log),
                        "同场角色没有再开口（共处事件本会把挂死角色重新标成 ready）")
        released = [t for t in trace.system_turns
                    if t["request"].get("kind") == "inflight_released"]
        self.assertTrue(released, "失联决策从未被放行")
        self.assertEqual(released[0]["result"]["actor"], "a")

    def test_stall_never_trips_on_a_slow_but_progressing_run(self):
        """(b) A healthy run whose every turn waits a little (and keeps
        stepping) must never trip the no-progress stall gate."""
        world = _stall_world()
        agents = {"a": _LeisurelyAgent(0.02), "b": _LeisurelyAgent(0.02)}
        engine, trace = self._engine(world, agents, decision_timeout=30.0,
                                     freeze_tolerance_seconds=1000.0,
                                     stall_threshold_seconds=0.5,
                                     max_wall_seconds=30.0)
        reason = engine.run(stop_at=_STALL_START + timedelta(seconds=600),
                            max_turns=200)
        self.assertEqual(reason, "stop_at_reached")
        self.assertTrue(all(t["result"]["reason"] != "stall_no_progress"
                            for t in trace.system_turns
                            if t["request"].get("kind") == "engine_stop_diagnostic"),
                        "健康慢跑被误判为停摆")
        self.assertGreaterEqual(agents["a"].calls, 5)

    def test_true_stall_is_reported_with_the_inflight_actor_and_duration(self):
        """(c) Genuine no-progress is still caught after the threshold, and
        the end record names who was in flight and for how long."""
        gate = threading.Event()
        world = _stall_world()
        agents = {"a": _BlockingAgent(gate), "b": _LeisurelyAgent(0.0)}
        engine, trace = self._engine(world, agents, decision_timeout=30.0,
                                     freeze_tolerance_seconds=1000.0,
                                     stall_threshold_seconds=0.2,
                                     max_wall_seconds=30.0)
        try:
            reason = engine.run(stop_at=_STALL_START + timedelta(seconds=600),
                                max_turns=200)
        finally:
            gate.set()
        self.assertEqual(reason, "stall_no_progress")
        diagnostic = _stop_diagnostic(trace)
        self.assertIsNotNone(diagnostic, "结束诊断没有写进 trace")
        self.assertIn("a", [row["actor"] for row in diagnostic["inflight"]],
                      "诊断没有写明在飞的决策")
        row = next(r for r in diagnostic["inflight"] if r["actor"] == "a")
        self.assertGreaterEqual(row["waited_seconds"], 0.2)
        self.assertEqual(diagnostic["stall_threshold_seconds"], 0.2)
        self.assertIn("progress", diagnostic["stall_definition"])
        self.assertGreaterEqual(diagnostic["seconds_since_progress"], 0.2)

    def test_residual_hung_wait_is_bounded_and_the_actor_acts_again(self):
        """(d) After a decision times out, the residual wait for the still-
        running call is bounded; once it is exceeded the actor is detached and
        takes its next turn instead of retiring for good."""
        gate = threading.Event()
        world = _stall_world()
        blocked = _BlockingAgent(gate)
        agents = {"a": blocked, "b": _LeisurelyAgent(0.01)}
        engine, trace = self._engine(world, agents, decision_timeout=0.05,
                                     hung_tolerance_seconds=0.05,
                                     freeze_tolerance_seconds=1000.0,
                                     stall_threshold_seconds=10.0,
                                     max_wall_seconds=30.0)
        try:
            reason = engine.run(stop_at=_STALL_START + timedelta(seconds=300),
                                max_turns=200)
        finally:
            gate.set()
        self.assertEqual(reason, "stop_at_reached")
        self.assertGreaterEqual(blocked.calls, 2,
                                "残留等待超界后该角色再没行动过")
        abandoned = [t for t in trace.system_turns
                     if t["request"].get("kind") == "hung_decision_abandoned"]
        self.assertTrue(abandoned, "残留等待没有上限，从未放弃")
        self.assertEqual(abandoned[0]["result"]["actor"], "a")

    def test_abandoned_hung_call_is_isolated_from_the_live_session(self):
        """(d) The abandoned call keeps writing to the session object it was
        born with; the actor must resume on the pre-decision snapshot so two
        writers never share one transcript."""
        gate = threading.Event()
        world = _stall_world()
        hung = _V4HungAgent(gate)
        agents = {"a": hung, "b": _LeisurelyAgent(0.01)}
        engine, trace = self._engine(world, agents, decision_timeout=0.05,
                                     hung_tolerance_seconds=0.05,
                                     freeze_tolerance_seconds=1000.0,
                                     stall_threshold_seconds=10.0,
                                     max_wall_seconds=30.0)
        try:
            reason = engine.run(stop_at=_STALL_START + timedelta(seconds=300),
                                max_turns=200)
        finally:
            gate.set()
        self.assertEqual(reason, "stop_at_reached")
        self.assertGreaterEqual(hung.calls, 2)
        abandoned = [t for t in trace.system_turns
                     if t["request"].get("kind") == "hung_decision_abandoned"]
        self.assertTrue(abandoned)
        self.assertTrue(abandoned[0]["result"]["session_restored"])
        live = hung.session_snapshot()["messages"]
        self.assertFalse(
            any(m.get("role") == "user" and hung.first_message
                and hung.first_message in str(m.get("content")) for m in live),
            "被放弃的挂死调用污染了续用会话")


# Ticket 56 red fixtures: the exact private-reasoning lines T1 broadcast as
# speech in real-20261001T065553 (each carried a real `heard` set: #1810
# 陈默 heard=[班长,食堂大妈]; #619 林瑶 heard=[陈默]; #1569 林瑶 heard=[辅导员,
# 陈默]). The last two cover the required vocabulary absent from that artifact.
_T56_PRIVATE_LINES = [
    "大妈当面问我在档案室见着什么了，班长又正好站在旁边——回答要挑着说："
    "台账的下落可以讲，3/14和值班表的事是辅导员收走的线，我一个字不碰；"
    "但小周小陈的全名这个行政上的事，可以当面问班长要。",
    "纸看完了：落款是当年老街坊代表的手写签名——**这个名字我见过**。"
    "小时候家属院的某张纸上，监护人栏旁边就落着这么一个大人。"
    "这层先记在自己本子里，不急着对陈默说。现在把纸交回给他，开扫。",
    "记忆调用格式错了——指令词得单独占一格。重来，三行分开修正：",
    "这事不能让班长知道，我先记在自己本子里。",
    "inner 里该写心里话，不该写进正文。",
]

# Ticket 56 green fixtures: genuine spoken lines from the SAME run (verbatim
# from world_events #829 / #95 / #440 / #207) plus the ticket's named control
# "我先走了". None of these may ever be withheld.
_T56_SPOKEN_LINES = [
    "（把热美式推过吧台）给，趁烫。你说\"吧台交给我\"——口气倒熟得很，"
    "老实交代，你以前是不是在这儿端过杯子？我接手的时候可没人跟我说店里还有位"
    "\"编外学长\"。",
    "早上好啊，同学！这么早，赶早八？",
    "老嫂子，早啊！给我来俩包子一碗豆浆——要热的，我这把老骨头喝不得凉的。",
    "陈默，你问的两件，我一件一件说实在话。头一件，那本台账2013年那页折痕重"
    "——谁翻的，我还真不知道；我在门房待了三十年，档案室里的名堂不归我管。",
    "记住，八点一刻在档案室门口见。",
    "我先走了。",
]


class _OneLineProvider:
    """A v4 provider whose every reply is one plain-text line (no tools)."""

    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    def chat_with_tools(self, messages, tools):
        self.calls += 1
        return {"role": "assistant", "content": self.content, "tool_calls": []}


class Ticket56PrivateContentGates(unittest.TestCase):
    """Ticket 56 (real-20261001T065553, five independent reviewers), retained
    after ticket 64 flipped the default.

    Ticket 56 found private reasoning written into the assistant's plain text
    being broadcast by the old T1 ruling. Ticket 64 removed that channel
    (the body is the actor's private thought; only `speak`/`text` speak), so
    these gates now pin the still-load-bearing parts: the high-precision
    predicate, and that a plain body is never broadcast. The speak/text-
    argument guard is pinned in Ticket56ProtocolArgumentGates."""

    START = datetime.fromisoformat("2026-03-16T09:00:00+08:00")

    def _engine(self, line: str):
        from harness.character_loader import CharacterSeed
        from harness.natural_agent import make_persistent_agent_v4
        world = World(start=self.START,
                      actors=[ActorState("陈默", "档案室"), ActorState("班长", "档案室")],
                      locations=[LocationState("档案室")], routes={})
        provider = _OneLineProvider(line)
        seed = CharacterSeed(actor_id="陈默", identity="", private_seed="")

        def quiet(state, perception, affordances):
            return Intention(state.actor_id, "wait",
                             {"duration_seconds": 60}, perception["world_version"])

        agents = {"陈默": make_persistent_agent_v4(seed, provider), "班长": quiet}
        states = {actor: PrivateState(actor) for actor in world.actors}
        trace = Trace("v4-test", "ticket56-private-content")
        engine = AsyncEngine(world, agents, states, trace, None,
                             decision_timeout=5, max_wall_seconds=30)
        engine.run(stop_at=self.START + timedelta(minutes=2), max_turns=40)
        return world, trace, agents["陈默"]

    def _speeches(self, world):
        return [str(e.payload.get("text", "")) for e in world.event_log
                if e.kind == "speech"]

    def test_private_reasoning_is_flagged_with_a_marker(self):
        """Every real leak (and the required vocabulary) carries a marker."""
        from harness.npc_agent import looks_like_private_reasoning
        for line in _T56_PRIVATE_LINES:
            self.assertIsNotNone(looks_like_private_reasoning(line),
                                 f"私密正文漏判：{line[:40]}")

    def test_genuine_speech_is_never_flagged(self):
        """Real spoken lines from the same run, incl. an action aside and
        "我先走了", are never private reasoning."""
        from harness.npc_agent import looks_like_private_reasoning
        for line in _T56_SPOKEN_LINES:
            self.assertIsNone(looks_like_private_reasoning(line),
                              f"真台词被误伤：{line[:40]}")
        # The "不急着…说" combination requires a preposition/addressee, so
        # ordinary "这事不急着说" stays spoken.
        self.assertIsNone(looks_like_private_reasoning("这事不急着说，回头再讲。"))

    def test_private_line_is_never_broadcast(self):
        """A plain body never becomes a `speak` event."""
        world, _trace, _agent = self._engine(_T56_PRIVATE_LINES[0])
        self.assertEqual(self._speeches(world), [],
                         "私密正文不得广播为 speech")

    def test_body_lands_in_the_private_turn_record(self):
        """The plain body is kept on that actor's private turn (never
        broadcast), so the trace can still explain what the actor was thinking."""
        world, trace, _agent = self._engine(_T56_PRIVATE_LINES[1])
        recorded = [t for t in trace.agent_turns
                    if t["actor"] == "陈默" and t.get("content_private")]
        self.assertTrue(recorded, "正文没有记入角色私密记录")
        self.assertIn("不急着对陈默说", str(recorded[0].get("content_private")))
        self.assertEqual(self._speeches(world), [])

    def test_self_correction_note_states_the_rule(self):
        from harness.natural_agent import PRIVATE_CONTENT_NOTE
        self.assertIn("不是你说出口的话", PRIVATE_CONTENT_NOTE)
        self.assertIn("格式错误", PRIVATE_CONTENT_NOTE)
        self.assertIn("inner", PRIVATE_CONTENT_NOTE)


# Ticket 64 red fixtures: the exact plain-content bodies that T1 broadcast in
# real-20261001T121425 (every matching world_events speech payload had no `to`,
# so it came from the body, not a speak call). After the flip none may become a
# speech event. The first four are the ticket's narration/plan examples; 5 and 6
# are the cross-actor-pollution examples (陈默 heard=['林瑶']).
_T64_PRIVATE_BODY_LINES = [
    "台账的话还在耳边：它要我说出它是什么、责任人是谁、期限。先把手里这张泛黄的通知书从头到尾看一遍"
    "——之前只扫过眼，签名和那条没画完的洪水路线旁注都还没细读。",
    "先别急着开口——台账要的是\"答上三件事里的门道\"，答错没有第二次。我把和这本台账有关的往事都翻出来，"
    "看自己到底记得多少。",
    "到岗第一件事是签到，但台账在三问——先把台账本子本身翻开细读，2013年那页有反复翻动的折痕，"
    "答案多半藏在里面。",
    "七点过了，店里还没人。我把磨豆机豆仓补满，把裂纹马克杯收进吧台底下那格，别让客人碰着割手"
    "——然后擦好台面，等着开门后头一批客人进来。",
    "林瑶进来了。她常在这儿值班——3月14日下午那班签到本上只写了\"值班学生\"没写名字，而且登记本被拿走的事"
    "她可能知道。当面问，比发短信快。",
    "林瑶反过来问我三个问题——其中抽屉那个，我必须先认账：今早我压根没开过左手抽屉，\"登记本不在\""
    "只是我上次值班留下的印象。先把实话说了，再去核实。",
]

# Ticket 64 green fixtures: real speak/text call texts from the same run that
# the coarse self-narration screen hits (they are genuine spoken planning, and
# the screen is read-only — the point is they still go out).
_T64_COARSE_SCREEN_LINES = [
    ("陈默妈", "行，下周末回，妈不催你。就是昨晚电话没人接，我这后半宿都没睡踏实——你值班再困，早饭也得吃。"
              "你说的档案室那摊事，是学校派你的还是你自己揽的？别什么都往自己肩上扛。相亲的事我去跟李阿姨说，"
              "你安心念书。家里都好，别惦记我，我吃得比你强。到家前一晚给妈发个信，我好上街买菜。"),
    ("辅导员", "林瑶那头还没动静，你先按四样把说明初稿拟着，别干等。我出去一趟：唐小岚捡的那份草稿就在半坡"
              "咖啡馆，她那个号我手机里没有，短信回不了——我干脆走一趟当面看稿，来回二十分钟，误不了你交包。"
              "林瑶回信儿了先记着，我回来你一并告诉我。说明初稿拟完，念一遍给自己听，四样缺哪样补哪样。"),
    ("班长", "辅导员，补一句陈默托我捎的：3/15 上午您要是排过人去档案室叫陈默帮忙、或者托谁带过话，麻烦把时间"
             "和人名写下来给我——他 08:03 签到后被人叫走，之后一截记忆整段空白，叫走他的那位就是最后一个见过"
             "借阅登记本的人，两下能对上就省大事。您指的路我收到了，现在就翻抽屉、文件柜和公告栏底下压的过期"
             "通知，翻着 3/4 的签收底或排班公告当场喊您。对了，唐小岚 14:15 那趟是直接来学生会办公室给林瑶过目"
             "十分钟，不去咖啡馆——您在店里要还是看不成稿子，就别干等，直接回来碰头。"),
]


class _V4FixedProvider:
    """A v4 provider returning one fixed assistant message every turn."""

    def __init__(self, content: str = "", calls: list[tuple[str, dict]] | None = None):
        self.content = content
        self.calls = list(calls or [])

    def chat_with_tools(self, messages, tools):
        tool_calls = []
        for index, (name, args) in enumerate(self.calls):
            tool_calls.append({"id": f"c{index}", "type": "function",
                               "function": {"name": name,
                                            "arguments": json.dumps(args, ensure_ascii=False)}})
        return {"role": "assistant", "content": self.content, "tool_calls": tool_calls}


def _t64_engine(content: str = "", calls: list[tuple[str, dict]] | None = None):
    """A v4 engine whose 陈默 always answers with `content` plus `calls`."""
    from harness.character_loader import CharacterSeed
    from harness.natural_agent import make_persistent_agent_v4
    start = datetime.fromisoformat("2026-03-16T09:00:00+08:00")
    world = World(start=start,
                  actors=[ActorState("陈默", "档案室"), ActorState("班长", "档案室")],
                  locations=[LocationState("档案室")], routes={})
    provider = _V4FixedProvider(content, calls)
    seed = CharacterSeed(actor_id="陈默", identity="", private_seed="")

    def quiet(state, perception, affordances):
        return Intention(state.actor_id, "wait",
                         {"duration_seconds": 60}, perception["world_version"])

    agents = {"陈默": make_persistent_agent_v4(seed, provider), "班长": quiet}
    states = {actor: PrivateState(actor) for actor in world.actors}
    trace = Trace("v4-test", "ticket64-content-private")
    engine = AsyncEngine(world, agents, states, trace, None,
                         decision_timeout=5, max_wall_seconds=30)
    engine.run(stop_at=start + timedelta(minutes=2), max_turns=40)
    return world, trace, agents["陈默"]


def _t64_turn(trace, actor="陈默"):
    return next(t for t in trace.agent_turns if t["actor"] == actor)


class Ticket64ContentIsPrivateGates(unittest.TestCase):
    """Ticket 64 (real-20261001T121425+0800-223688-090345540).

    265 speech events: 96 from explicit speak/text calls, 169 from plain
    content that the old T1 ruling broadcast — mostly narration and plans
    (陈默 07:59 heard=['林瑶']; 辅导员's private judgement reached 唐小岚).
    The default is flipped: the body is the actor's private thought, and
    speech is only what a speak/text call says."""

    def test_real_broadcast_bodies_are_never_speech(self):
        """(a) Today-red: every real narration body that used to become a
        speech event now produces none."""
        for line in _T64_PRIVATE_BODY_LINES:
            world, _trace, _agent = _t64_engine(content=line)
            self.assertEqual(
                [e for e in world.event_log if e.kind == "speech"], [],
                f"正文仍被广播：{line[:30]}")

    def test_body_is_recorded_privately_with_the_suspect_flag(self):
        """The body is kept on the private turn; a body that reads like
        addressed speech (2nd person) is flagged and earns one self-correction."""
        line = "哎，姑娘，你这正要上楼吧？"
        world, trace, agent = _t64_engine(content=line)
        turn = _t64_turn(trace)
        self.assertEqual(turn["content_private"], line)
        self.assertTrue(turn["content_suspect_dialogue"])
        self.assertEqual([e for e in world.event_log if e.kind == "speech"], [])
        from harness.natural_agent import UNSPOKEN_CONTENT_NOTE
        messages = agent.session_snapshot()["messages"]
        self.assertTrue(any(m.get("role") == "user" and m.get("content") == UNSPOKEN_CONTENT_NOTE
                            for m in messages),
                        "疑似对白正文没有收到过渡自纠")

    def test_plan_body_without_address_gets_no_self_correction(self):
        """High-precision pin: a plan/narration body with no quoted dialogue
        and no second-person address stays silent — no note, no noise."""
        line = _T64_PRIVATE_BODY_LINES[3]
        world, trace, agent = _t64_engine(content=line)
        turn = _t64_turn(trace)
        self.assertEqual(turn["content_private"], line)
        self.assertFalse(turn["content_suspect_dialogue"])
        from harness.natural_agent import UNSPOKEN_CONTENT_NOTE
        messages = agent.session_snapshot()["messages"]
        self.assertFalse(any(m.get("role") == "user" and m.get("content") == UNSPOKEN_CONTENT_NOTE
                             for m in messages),
                         "普通旁白不该触发自纠（避免噪音）")

    def test_body_is_private_even_alongside_a_speak_call(self):
        """A turn that also used speak does not get the content correction
        (it did speak); its body is still private."""
        spoken = "档案室这边我来盯着，你先去忙。"
        world, trace, agent = _t64_engine(
            content="心里盘算着怎么开口。",
            calls=[("speak", {"to": ["班长"], "text": spoken, "volume": "normal",
                               "inner": "跟他交代一下"})])
        turn = _t64_turn(trace)
        self.assertEqual(turn["content_private"], "心里盘算着怎么开口。")
        self.assertEqual([e.payload["text"] for e in world.event_log
                          if e.kind == "speech"], [spoken])
        from harness.natural_agent import UNSPOKEN_CONTENT_NOTE
        messages = agent.session_snapshot()["messages"]
        self.assertFalse(any(m.get("role") == "user" and m.get("content") == UNSPOKEN_CONTENT_NOTE
                             for m in messages))

    def test_speak_call_still_speaks(self):
        """(b) The speak tool is the channel that still works."""
        spoken = "大爷，您慢走。"
        world, _trace, _agent = _t64_engine(
            calls=[("speak", {"to": ["班长"], "text": spoken, "volume": "normal",
                               "inner": "打招呼"})])
        speeches = [str(e.payload["text"]) for e in world.event_log if e.kind == "speech"]
        self.assertEqual(speeches, [spoken])

    def test_text_call_still_sends(self):
        """(b) A text call still delivers a private message."""
        body = "妈，早。昨晚值班睡得沉，电话没接住。"
        world, _trace, _agent = _t64_engine(
            calls=[("text", {"target": "班长", "text": body, "inner": "回一条"})])
        sent = [e for e in world.event_log if e.kind == "message_sent"]
        self.assertEqual([e.payload["target"] for e in sent], ["班长"])
        delivered = next(e for e in world.event_log if e.kind == "message_delivered")
        self.assertEqual(delivered.payload["text"], body)

    def test_coarse_self_narration_screen_reads_but_never_blocks(self):
        """Ticket 64 metric: the coarse self-narration screen hits real spoken
        planning (read-only telemetry), and those lines still go out. The
        retained speak/text protocol guard must never flag them (zero false
        positives on real lines from the same run)."""
        from harness.npc_agent import (looks_like_protocol_reasoning,
                                       looks_like_self_narration)
        for actor, line in _T64_COARSE_SCREEN_LINES:
            self.assertIsNotNone(looks_like_self_narration(line), actor)
            self.assertIsNone(looks_like_protocol_reasoning(line), actor)
        actor, line = _T64_COARSE_SCREEN_LINES[1]
        world, _trace, _agent = _t64_engine(
            calls=[("speak", {"to": ["班长"], "text": line, "volume": "normal",
                               "inner": "交代出门的事"})])
        self.assertIn(line, [str(e.payload["text"]) for e in world.event_log
                             if e.kind == "speech"],
                      "粗筛命中不得拦截真台词")

    def test_transitional_note_states_the_rule(self):
        from harness.natural_agent import UNSPOKEN_CONTENT_NOTE
        self.assertIn("这段没有说出口", UNSPOKEN_CONTENT_NOTE)
        self.assertIn("speak", UNSPOKEN_CONTENT_NOTE)
        self.assertIn("text", UNSPOKEN_CONTENT_NOTE)

    def test_prompt_states_body_is_private_and_stays_verbatim(self):
        """(2) §1 says the body is the actor's private thought, has no listener,
        and speech goes through speak/text; runtime prompt == doc §1, and §4
        agrees, so the contract cannot drift."""
        from harness.natural_agent import SYSTEM_PROMPT_V4
        doc = (Path(__file__).parents[2] / "docs" / "V4-AGENT-INTERFACE.md").read_text(
            encoding="utf-8")
        self.assertIn("是你心里的想法", SYSTEM_PROMPT_V4)
        self.assertIn("要说话就用 speak 工具", SYSTEM_PROMPT_V4)
        self.assertIn("私聊用 text", SYSTEM_PROMPT_V4)
        self.assertIn(SYSTEM_PROMPT_V4, doc,
                      "§1 的 system prompt 必须与运行时逐字一致")
        section4 = doc.split("## 4.", 1)[1].split("## 5.", 1)[0]
        self.assertIn("不渲染为任何 speech 事件", section4,
                      "§4 必须写明正文不广播")

    def test_checker_reports_unspoken_body_and_coarse_screen(self):
        """(5) The system-health block counts (i) bodies never spoken — with
        the suspected-dialogue subset — and (ii) the read-only coarse screen,
        apart from (iii) the retained speak/text protocol guard. Review only."""
        module = _checker_module()
        leaked = _speech_artifact(
            [(9, 5, "辅导员", "林瑶那头还没动静，你先按四样把说明初稿拟着，别干等。")])["world_events"]
        data = {
            "agent_turns": [
                {"actor": "陈默", "role": "mc",
                 "content_private": "她可能知道。当面问，比发短信快。",
                 "content_suspect_dialogue": False,
                 "perception": {"time": "2026-03-16T09:00:00+08:00"}},
                {"actor": "班长", "role": "mc",
                 "content_private": "哎，姑娘，你这正要上楼吧？",
                 "content_suspect_dialogue": True,
                 "perception": {"time": "2026-03-16T09:01:00+08:00"}},
                {"actor": "宿管阿姨", "role": "npc", "withheld_private": True,
                 "withheld_text": "inner 该在字段里",
                 "perception": {"time": "2026-03-16T09:02:00+08:00"}},
            ],
            "world_events": leaked,
            "sessions": {},
        }
        report = module.health_report(data, 1)
        self.assertEqual(report["正文未说出口（含疑似对白）"],
                         "2（疑似对白 1；仍被广播的私密正文 0）")
        self.assertEqual(report["speak/text 协议正文被拦下"], 1)
        self.assertIn("1（", report["speak/text 疑似自我旁白（只读）"])
        self.assertIn("别干等", report["speak/text 疑似自我旁白（只读）"])


# Ticket 56 extension red fixtures: protocol/tool meta-reasoning placed in a
# speak/text `text` argument. It cannot be a real line or message. The second
# is the same line the content path already withholds.
_T56_PROTOCOL_ARG_LINES = [
    "记忆调用格式错了——指令词得单独占一格。",
    "inner 里该写心里话，不该写进正文。",
]
# Green: genuine lines that must still go out through the same tool args. The
# format one pins that a lone "格式" never triggers (only the 格式错 pairing).
_T56_GENUINE_ARG_LINES = [
    "（把热美式推过吧台）给，趁烫。",
    "这张表的格式我看看，回头给你回话。",
    "我先走了。",
]


class _NoteRecordingSession:
    """Records the ticket-56 self-corrections the engine sends the actor."""

    def __init__(self):
        self.notes = 0

    def note_private_content(self):
        self.notes += 1


class _ProtocolArgChainAgent(_ChainAgent):
    """`_ChainAgent` whose session object records self-corrections."""

    def __init__(self):
        super().__init__()
        self.session_obj = _NoteRecordingSession()


def _protocol_arg_engine(world):
    """A chain engine on the ticket-56 extension seam (session-aware)."""
    agents = {actor_id: _ProtocolArgChainAgent() for actor_id in world.actors}
    engine = AsyncEngine(world, agents,
                         {actor_id: PrivateState(actor_id) for actor_id in world.actors},
                         Trace("v4-test", "ticket56-protocol-arg"), None,
                         decision_timeout=10, max_wall_seconds=30)
    engine._scheduler_wake = threading.Event()
    engine._stop_horizon = None
    return engine, agents


class Ticket56ProtocolArgumentGates(unittest.TestCase):
    """Ticket 56 extension: protocol/tool meta-reasoning is a formatting
    error even inside a speak/text `text` argument. Withhold it (never
    broadcast / never send), record it privately, self-correct and count.
    Concealment/plan markers stay plain-content-only."""

    START = datetime.fromisoformat("2026-03-16T09:00:00+08:00")

    def _scene(self):
        return World(start=self.START,
                     actors=[ActorState("陈默", "档案室"), ActorState("班长", "档案室")],
                     locations=[LocationState("档案室")], routes={})

    def _perception(self, world, who="陈默"):
        return {"time": world.now.isoformat(),
                "nearby_actors": [a for a in ("陈默", "班长") if a != who],
                "events": []}

    def test_protocol_marker_scope_excludes_concealment(self):
        from harness.npc_agent import (looks_like_private_reasoning,
                                       looks_like_protocol_reasoning)
        for line in _T56_PROTOCOL_ARG_LINES:
            self.assertIsNotNone(looks_like_protocol_reasoning(line), line)
        # Concealment is class (b) only: the speak/text-arg guard must not
        # apply it (a person may say it aloud).
        self.assertIsNone(looks_like_protocol_reasoning("这事我不能让他们知道。"))
        self.assertIsNotNone(looks_like_private_reasoning("这事我不能让他们知道。"))
        for line in _T56_GENUINE_ARG_LINES:
            self.assertIsNone(looks_like_protocol_reasoning(line), line)

    def test_protocol_text_in_speak_is_never_broadcast(self):
        for line in _T56_PROTOCOL_ARG_LINES:
            world = self._scene()
            engine, agents = _protocol_arg_engine(world)
            engine._execute_chain("陈默", [{
                "name": "speak",
                "arguments": {"text": line, "volume": "normal", "to": ["班长"]},
                "tool_call_id": "s1"}], self._perception(world),
                world.affordances("陈默"), world.version)
            self.assertFalse(any(e.kind == "speech" for e in world.event_log),
                             f"协议文本被当作台词广播：{line}")
            result = agents["陈默"].delivered[0]
            self.assertFalse(result["ok"])
            self.assertIn("不是你说出口的话", result["text"])
            turn = engine.trace.agent_turns[-1]
            self.assertTrue(turn["withheld_private"], line)
            self.assertIn(line, str(turn["withheld_text"]))
            self.assertEqual(agents["陈默"].session_obj.notes, 1,
                             "speak 参数路径缺少自纠提示")

    def test_protocol_text_in_text_is_never_sent(self):
        for line in _T56_PROTOCOL_ARG_LINES:
            world = self._scene()
            engine, agents = _protocol_arg_engine(world)
            engine._execute_chain("陈默", [{
                "name": "text",
                "arguments": {"target": "班长", "text": line},
                "tool_call_id": "t1"}], self._perception(world),
                world.affordances("陈默"), world.version)
            kinds = [e.kind for e in world.event_log]
            self.assertNotIn("message_sent", kinds, f"协议文本被当作短信发出：{line}")
            self.assertNotIn("message_delivered", kinds)
            result = agents["陈默"].delivered[0]
            self.assertFalse(result["ok"])
            turn = engine.trace.agent_turns[-1]
            self.assertTrue(turn["withheld_private"], line)
            self.assertEqual(agents["陈默"].session_obj.notes, 1)

    def test_genuine_speak_text_still_goes_out(self):
        for line in ("（把热美式推过吧台）给，趁烫。",
                     "这张表的格式我看看，回头给你回话。", "我先走了。"):
            world = self._scene()
            engine, agents = _protocol_arg_engine(world)
            engine._execute_chain("陈默", [{
                "name": "speak",
                "arguments": {"text": line, "volume": "normal", "to": ["班长"]},
                "tool_call_id": "s1"}], self._perception(world),
                world.affordances("陈默"), world.version)
            speech = next(e for e in world.event_log if e.kind == "speech")
            self.assertEqual(speech.payload["text"], line)
            self.assertTrue(agents["陈默"].delivered[0]["ok"], line)
            self.assertFalse(any(t.get("withheld_private")
                                 for t in engine.trace.agent_turns))

    def test_genuine_text_message_still_goes_out(self):
        line = "班长，这张表的格式我看看，回头给你回话。"
        world = self._scene()
        engine, agents = _protocol_arg_engine(world)
        engine._execute_chain("陈默", [{
            "name": "text",
            "arguments": {"target": "班长", "text": line},
            "tool_call_id": "t1"}], self._perception(world),
            world.affordances("陈默"), world.version)
        sent = next(e for e in world.event_log if e.kind == "message_sent")
        self.assertEqual(sent.payload["target"], "班长")
        delivered = next(e for e in world.event_log if e.kind == "message_delivered")
        self.assertEqual(delivered.payload["text"], line)
        self.assertTrue(agents["陈默"].delivered[0]["ok"])

    def test_concealment_in_speak_text_is_not_withheld(self):
        """Scoping pin: the concealment/plan markers stay plain-content-only,
        so a real line like "这事我不能让他们知道" still goes out."""
        line = "班长，这事我不能让他们知道，你帮我把口风咬紧。"
        world = self._scene()
        engine, agents = _protocol_arg_engine(world)
        engine._execute_chain("陈默", [{
            "name": "speak",
            "arguments": {"text": line, "volume": "normal", "to": ["班长"]},
            "tool_call_id": "s1"}], self._perception(world),
            world.affordances("陈默"), world.version)
        speech = next(e for e in world.event_log if e.kind == "speech")
        self.assertEqual(speech.payload["text"], line)
        self.assertTrue(agents["陈默"].delivered[0]["ok"])
        self.assertFalse(any(t.get("withheld_private") for t in engine.trace.agent_turns))


class DocumentWorldPublicGuardTests(unittest.TestCase):
    """I61: the 折痕 clause of `documents/2013年台风台账.md` must not sit in an
    actor's KB unless the seed put that actor in `known_to` or the actor has
    really seen/read the thing (ticket 49)."""

    LEDGER_STATE = "2013 年那一页有反复翻动的折痕"

    def test_unmarked_document_state_is_not_world_public(self):
        pack = load_story_pack()
        for actor in ("宿管阿姨", "食堂大妈", "辅导员", "班长"):
            delivered = "\n".join(str(row["desc"]) for row in pack.kb[actor])
            self.assertNotIn(self.LEDGER_STATE, delivered,
                             f"{actor} never reached the archive (I61)")

    def test_seeing_the_ledger_registers_it_as_an_objective_memory(self):
        world = load_story_pack().build_world()
        world.actors["宿管阿姨"].location = "校史档案室"
        packet = world.poll("宿管阿姨")
        self.assertIn(self.LEDGER_STATE, packet["descriptions"]["2013年台风台账"])
        self.assertIn(self.LEDGER_STATE,
                      world.actors["宿管阿姨"].observed["2013年台风台账"]["objective"])


class ConceptStateLeakGates(unittest.TestCase):
    """I62 (ticket 62, d1-am artifacts): a concept's `desc` is the identity
    shared with its `known_to` actors, never a state or a conclusion.

    食堂大妈's #knowledge block (real-20260930T160727) carried "[器材室]: 借出两台
    抽水泵的地方，登记人签名潦草。2013 年那晚的借出时间在纸质台账和导出件上对
    不上。" though she never read either document; flood-route-note's "箭头没画完"
    reached all ten actors; old-neighbor-rep's desc named the signer outright.
    `known_to` means "knows it exists" (ticket 40); the detail must come from a
    source (ticket 49). These gates pin the leak, the source, and the plot need.
    """

    # Verbatim clauses of the three descs before the fix. None is identity.
    LEAKED = (
        "箭头没画完",                        # flood-route-note: unfinished arrow
        "登记人签名潦草",                    # equipment-room: the register's state
        "借出时间在纸质台账和导出件上对不上",  # equipment-room: the discrepancy
        "落款上签名的那个人",                # old-neighbor-rep: who signed
        "审计要的责任人指向他",              # old-neighbor-rep: the conclusion
    )
    # d1-am actors who never reached the notice or either 2013 document.
    UNMET = ("宿管阿姨", "辅导员", "班长", "陈默妈", "林瑶室友", "唐小岚",
             "食堂大妈")

    def test_unmet_actors_do_not_carry_the_concept_conclusions(self):
        # (a) red before the fix: every actor's KB held flood-route-note's
        # "箭头没画完", and 食堂大妈 carried equipment-room's "对不上" clause.
        pack = load_story_pack()
        for actor in self.UNMET:
            delivered = "\n".join(str(row["desc"]) for row in pack.kb[actor])
            for phrase in self.LEAKED:
                self.assertNotIn(phrase, delivered,
                                 f"{actor} never reached the source (I62)")

    def test_the_world_primer_carries_no_concept_state(self):
        from harness.world_loader import world_primer
        primer = world_primer(load_story_pack())
        for phrase in self.LEAKED:
            self.assertNotIn(phrase, primer)

    def test_reaching_the_ledger_yields_the_borrow_state(self):
        # (b) the state survives as a real source: reading the two 2013
        # documents yields the signature state and the two timestamps.
        world = load_story_pack().build_world()
        world.actors["宿管阿姨"].location = "校史档案室"
        for document, expect in (("2013年台风台账", ("经手人签名潦草", "22:05")),
                                 ("2013年外借记录导出件", ("23:30", "对不上"))):
            world.submit(Intention("宿管阿姨", "read", {"item": document},
                                   world.version))
            world.advance()
            world.advance()
            read = next(e for e in world.event_log if e.kind == "document_read"
                        and e.payload.get("document") == document)
            for clause in expect:
                self.assertIn(clause, read.payload["content"])

    def test_holding_the_notice_yields_the_unfinished_arrow(self):
        # (b) 陈默 holds the notice, so the ticket-49 observation gives him the
        # objective line with the unfinished arrow — identity-only desc loses
        # nothing a source cannot return.
        world = load_story_pack().build_world()
        packet = world.poll("陈默")
        self.assertIn("没写完的箭头", packet["descriptions"]["2013年邻里撤离通知书"])
        self.assertIn(
            "没写完的箭头",
            world.actors["陈默"].observed["2013年邻里撤离通知书"]["objective"])

    def test_plot_owners_keep_the_concepts_they_need(self):
        # (c) narrowing must not cut a legitimately-knowing actor: 陈默/林瑶 are
        # the two actors the plot needs, and 食堂大妈's own card asserts the
        # public 器材室 rumor.
        pack = load_story_pack()
        keys = {actor: {key for row in rows for key in row["keys"]}
                for actor, rows in pack.kb.items()}
        for actor in ("陈默", "林瑶"):
            for concept in ("洪水路线旁注", "老街坊代表", "器材室"):
                self.assertIn(concept, keys[actor])
        self.assertIn("器材室", keys["食堂大妈"],
                      "her card states the public 器材室 rumor")
        for actor in ("宿管阿姨", "辅导员", "班长", "陈默妈", "林瑶室友"):
            self.assertNotIn("洪水路线旁注", keys[actor])

    def test_wide_known_to_with_a_state_desc_warns_and_narrowing_silences_it(self):
        # (3) the non-blocking lint: a state/conclusion word in a desc handed
        # to ≥5 actors is visible; narrowing `known_to` silences it.
        lint = _seed_lint_module()
        self.assertEqual(lint.concept_state_warnings(_world_root()), [],
                         "the shipped descs carry identity only")
        with TemporaryDirectory() as directory:
            root = _copy_world(directory)

            def widen(data):
                row = next(c for c in data["concepts"] if c["id"] == "flood-route-note")
                row["desc"] = "撤离通知书页边一条铅笔画的窄窄洪水路线，箭头没画完。"
                row["known_to"] = ["陈默", "林瑶", "唐小岚", "宿管阿姨", "食堂大妈",
                                   "辅导员", "班长", "陈默妈", "林瑶室友", "下棋大爷"]

            _edit_manifest(root, widen)
            warnings = lint.concept_state_warnings(root)
            self.assertTrue(any("flood-route-note" in w and "没画完" in w
                                for w in warnings), warnings)

            def narrow(data):
                row = next(c for c in data["concepts"] if c["id"] == "flood-route-note")
                row["known_to"] = ["陈默", "林瑶"]

            _edit_manifest(root, narrow)
            self.assertEqual(lint.concept_state_warnings(root), [],
                             "a narrow known_to is not a shared conclusion")

    # Twin concepts (ticket 62 收尾): same mechanical defect as equipment-room.
    # The pumps desc handed the archive-internal timestamps to 食堂大妈; the
    # primary-school desc asserted the 21:40 call conclusion, both to actors who
    # were neither present nor had read anything.
    TWIN_LEAKED = (
        "纸质台账记 22:05，导出件记 23:30",  # pumps: the discrepancy conclusion
        "第一通电话就是从那儿打出来的",        # primary-school: the call conclusion
    )

    def test_twin_concepts_do_not_leak_their_conclusions(self):
        # Red before the fix: 食堂大妈's KB carried both clauses (pumps,
        # primary-school) though she was not at the scene and read nothing.
        pack = load_story_pack()
        for actor in self.UNMET:
            delivered = "\n".join(str(row["desc"]) for row in pack.kb[actor])
            for phrase in self.TWIN_LEAKED:
                self.assertNotIn(phrase, delivered,
                                 f"{actor} never reached the source (I62)")
        from harness.world_loader import world_primer
        primer = world_primer(pack)
        for phrase in self.TWIN_LEAKED:
            self.assertNotIn(phrase, primer)

    def test_narrowed_pump_knowers_keep_a_source(self):
        # Red before the fix: 食堂大妈 held a 两台抽水泵 row. Only those who
        # were present (下棋大爷) or must read the record (陈默/林瑶) keep it;
        # the conclusion is still obtainable from the two documents.
        pack = load_story_pack()
        keys = {actor: {key for row in rows for key in row["keys"]}
                for actor, rows in pack.kb.items()}
        for actor in ("陈默", "林瑶", "下棋大爷"):
            self.assertIn("两台抽水泵", keys[actor])
        self.assertNotIn("两台抽水泵", keys["食堂大妈"],
                         "she was not present and never read the files")
        world = pack.build_world()
        world.actors["宿管阿姨"].location = "校史档案室"
        for document, clause in (("2013年台风台账", "22:05"),
                                 ("2013年外借记录导出件", "23:30")):
            world.submit(Intention("宿管阿姨", "read", {"item": document},
                                   world.version))
            world.advance()
            world.advance()
            read = next(e for e in world.event_log if e.kind == "document_read"
                        and e.payload.get("document") == document)
            self.assertIn(clause, read.payload["content"])

    def test_narrowing_keeps_the_names_its_gossip_needs(self):
        # The chain is intact: 食堂大妈 loses the archive-internal pumps row
        # but keeps her public-memory names, so the 器材室/小学 gossip is not
        # orphaned; audit-case stays the puzzle it was (谜面语义不变).
        pack = load_story_pack()
        keys = {actor: {key for row in rows for key in row["keys"]}
                for actor, rows in pack.kb.items()}
        self.assertIn("器材室", keys["食堂大妈"])
        self.assertIn("小学", keys["食堂大妈"])
        audit = next(c for c in pack.manifest["concepts"] if c["id"] == "audit-case")
        self.assertIn("对得上对不上", audit["desc"])
        self.assertEqual(audit["puzzle"]["reveal"], "学生会审计包")
        delivered = "\n".join(str(row["desc"]) for row in pack.kb["辅导员"])
        for clause in audit["puzzle"]["answer"]:
            self.assertNotIn(clause, delivered,
                             "the audit answer stays in the readable pack only")


class Ticket59UpdateMemoryGates(unittest.TestCase):
    """I59 (ticket 59, d1-am artifact real-20261001T065553).

    update_memory was the run's largest error class (24 of 52 error turns).
    These gates pin the three real shapes and the split-out health metric:
    (1) a label fused into the ``!at=`` time key (and the bare-weekday
    spelling) must be accepted; (2) a multi-key target whose keys live on
    different rows must name the closest row to retry with; (3) a batch keeps
    its valid rows and reports each outcome."""

    START = datetime.fromisoformat("2026-03-16T07:00:00+08:00")

    def _kb(self, rows=None):
        from harness.kb import ActorKB
        return ActorKB("宿管阿姨", rows or [{"keys": ["宿管阿姨"], "desc": "我"}],
                       self.START)

    def test_scheduled_key_label_and_bare_weekday_are_accepted(self):
        kb = self._kb()
        errs, telemetry, _ = kb.apply_ops(
            [{"keys": ["!at=3/16(周一) 08:10 上午班", "档案室"], "op": "open",
              "desc": "上班"},
             {"keys": ["!at=3/16(一) 12:05", "林瑶", "中午回来"], "op": "open",
              "desc": "回来没"}], self.START)
        self.assertEqual(errs, [], "a fused label / bare weekday must not cost a turn")
        self.assertEqual(telemetry["applied"], 2)
        keys = {k for r in kb.snapshot()["rows"] for k in r["keys"]}
        self.assertIn("!at=3/16(周一) 08:10", keys)
        self.assertIn("上午班", keys, "the fused label becomes its own mention key")
        self.assertIn("!at=3/16(周一) 12:05", keys)
        self.assertNotIn("!at=3/16(一) 12:05", keys,
                         "both weekday spellings canonicalize to one handle")

    def test_fused_always_label_is_accepted(self):
        kb = self._kb()
        errs, telemetry, _ = kb.apply_ops(
            [{"keys": ["!always 无障碍改造"], "op": "open", "desc": "盯着无障碍改造"}],
            self.START)
        self.assertEqual(errs, [], "a fused !always label must not cost a turn")
        self.assertEqual(telemetry["applied"], 1)
        row = next(r for r in kb.snapshot()["rows"] if "无障碍改造" in r["keys"])
        self.assertEqual(set(row["keys"]), {"!always", "无障碍改造"})

    def test_normal_always_and_contact_are_unchanged(self):
        kb = self._kb([{"keys": ["宿管阿姨"], "desc": "我"},
                       {"keys": ["!always", "要紧的事"], "desc": "记住"}])
        row = next(r for r in kb.snapshot()["rows"] if "要紧的事" in r["keys"])
        self.assertEqual(set(row["keys"]), {"!always", "要紧的事"},
                         "the canonical spelling keeps its exact key set")

    def test_compound_key_error_names_the_closest_existing_row(self):
        kb = self._kb([{"keys": ["宿管阿姨"], "desc": "我"},
                       {"keys": ["!contact", "林瑶"], "desc": "认识林瑶"}])
        errs, telemetry, _ = kb.apply_ops(
            [{"keys": ["!contact", "林瑶", "桂姨"], "op": "edit", "desc": "x"}],
            self.START)
        self.assertEqual(telemetry["applied"], 0)
        self.assertEqual(len(errs), 1)
        self.assertIn("no row keyed", errs[0])
        self.assertIn("键重合最多的现有行是「!contact 林瑶」", errs[0],
                      "the retry must be one step")

    def test_partial_update_memory_reports_each_row_and_keeps_the_valid_ones(self):
        world = World(start=self.START,
                      actors=[ActorState("陈默", "校史档案室")],
                      locations=[LocationState("校史档案室")], routes={})
        engine, agents = _chain_engine(world)
        from harness.kb import ActorKB
        engine._kb["陈默"] = ActorKB("陈默", [{"keys": ["陈默"], "desc": "我"}],
                                     world.now)
        engine._execute_chain(
            "陈默",
            [{"name": "update_memory",
              "arguments": {"inner": "记一笔", "rows": [
                  {"keys": ["新线索A"], "op": "open", "desc": "A"},
                  {"keys": ["没有的行"], "op": "edit", "desc": "B"}]},
              "tool_call_id": "mem-1"}],
            {"time": world.now.isoformat(), "nearby_actors": [], "events": []},
            world.affordances("陈默"), world.version)
        result = agents["陈默"].delivered[-1]
        self.assertTrue(result["ok"], "a partial write is not a lost batch")
        self.assertIn("部分成功", result["text"])
        self.assertIn("新线索A", result["text"])
        self.assertIn("没有的行", result["text"])
        keys = {k for r in engine._kb["陈默"].snapshot()["rows"] for k in r["keys"]}
        self.assertIn("新线索A", keys, "the valid row must land")
        turn = engine.trace.agent_turns[-1]
        self.assertTrue(turn["memory_rejections"],
                        "the failed rows stay countable apart from the turn error")
        self.assertIsNone(turn["error"], "a partial write is not a failed turn")

    def test_checker_splits_out_update_memory_failures(self):
        module = _checker_module()
        turns = [
            {"perception": {"time": "2026-03-16T07:04:00+08:00"},
             "memory_rejections": ["keys=[a] op=edit: no row keyed 'a'"]},
            {"perception": {"time": "2026-03-16T07:05:00+08:00"},
             "memory_rejections": []},
        ]
        report = module.health_report(
            {"agent_turns": turns, "sessions": {}, "world_events": []}, 1)
        self.assertEqual(report["update_memory 失败行数"], 1)


class _NeverReturningAgent:
    """A decision that never returns until the test opens its gate.

    Ticket 67's failing shape: the actor's wake stays the oldest in `_inflight`
    forever, so `min()` never moves and nothing drives the scheduler out of its
    inner freeze-wait loop on its own."""

    def __init__(self, gate):
        self.gate = gate
        self.calls = 0

    def __call__(self, state, perception, affordances):
        self.calls += 1
        self.gate.wait()
        return Intention(state.actor_id, "wait",
                         {"duration_seconds": 60}, perception["world_version"])


def _freeze_branch_world():
    """A world whose queued event lies beyond the freeze bound.

    `next_event > horizon_bound` is what routes the scheduler into the inner
    freeze-wait branch; without a future event the outer pass keeps rotating.
    Two co-located actors both block, so the bound's `min()` is stable."""
    world = _stall_world()
    world.schedule_reminder("a", _STALL_START + timedelta(seconds=600),
                            "rid-67", "稍后的提醒", "later")
    return world


class Ticket67WallDeadlineGates(unittest.TestCase):
    """Ticket 67 (real-20261001T163024): the wall-clock backstop was starved.

    The wall/stall/max_turns/stop_at checks ran once per OUTER scheduler pass;
    while `_inflight` held a stable oldest wake the code sat in the inner
    freeze-wait loop until the ticket-53 release bound, so a never-resolving
    decision pushed the stop past its budget. `_stop_check` now runs inside the
    inner loop and every wait caps itself by the remaining wall budget."""

    def _engine(self, world, agents, **kw):
        states = {actor: PrivateState(actor) for actor in world.actors}
        trace = Trace("v4-test", "historical-gate-ticket-67")
        return AsyncEngine(world, agents, states, trace, None, **kw), trace

    def test_wall_deadline_fires_while_the_inflight_wait_never_releases(self):
        gate = threading.Event()
        world = _freeze_branch_world()
        agents = {"a": _NeverReturningAgent(gate), "b": _NeverReturningAgent(gate)}
        engine, trace = self._engine(world, agents, decision_timeout=30.0,
                                     freeze_tolerance_seconds=2.0,
                                     stall_threshold_seconds=60.0,
                                     max_wall_seconds=0.5)
        started = time.monotonic()
        try:
            reason = engine.run(stop_at=_STALL_START + timedelta(seconds=1200),
                                max_turns=2000)
        finally:
            gate.set()
        elapsed = time.monotonic() - started
        self.assertEqual(reason, "wall_clock_deadline_reached")
        self.assertLess(elapsed, 1.5,
                        "墙钟到点后被'等在飞决策'的内层循环饿死（修复前 ≥2s）")
        diagnostic = _stop_diagnostic(trace)
        self.assertIsNotNone(diagnostic, "结束诊断没有写进 trace")
        self.assertEqual(diagnostic["max_wall_seconds"], 0.5)
        self.assertLessEqual(diagnostic["wall_overrun_seconds"], 0.5,
                             "因墙钟停止时必须报出实际超出时长")
        self.assertIn("a", [row["actor"] for row in diagnostic["inflight"]])

    def test_max_turns_is_not_starved_by_the_same_inner_wait(self):
        # Guard, not a pre-fix red: in this construction the turn budget is
        # already reached by the time the outer pass runs, so `max_turns` is
        # caught either way. The point is the shared `_stop_check` also covers
        # it inside the freeze wait (same fix as the wall deadline above).
        gate = threading.Event()
        world = _freeze_branch_world()
        agents = {"a": _NeverReturningAgent(gate), "b": _NeverReturningAgent(gate)}
        engine, trace = self._engine(world, agents, decision_timeout=30.0,
                                     freeze_tolerance_seconds=2.0,
                                     stall_threshold_seconds=60.0)
        started = time.monotonic()
        try:
            reason = engine.run(stop_at=_STALL_START + timedelta(seconds=1200),
                                max_turns=1)
        finally:
            gate.set()
        self.assertEqual(reason, "max_turns_reached")
        self.assertLess(time.monotonic() - started, 1.5,
                        "max_turns 同样被内层等待饿死")


class Ticket68MemoryStoreGates(unittest.TestCase):
    """Ticket 68 (real-20261001T163024): the trace's `private_state.memories`
    is the legacy v3 slot and stays empty by design; v4 memory lives in the
    engine KB (38 rows for 唐小岚 in that run). A reviewer read the empty field
    as a silently dropped `update_memory` write and filed a false P1. The trace
    now carries the real notebook (`knowledge`) and each v4 turn names the store
    (`memory_store` / `knowledge_rows`) so the saved artifact is
    self-consistent and a write is verifiable inside the trace."""

    def _engine_with_notebook(self):
        world = World(start=_STALL_START,
                      actors=[ActorState("陈默", "校史档案室")],
                      locations=[LocationState("校史档案室")], routes={})
        engine, agents = _chain_engine(world)
        from harness.kb import ActorKB
        engine._kb["陈默"] = ActorKB("陈默", [{"keys": ["陈默"], "desc": "我"}],
                                     world.now)
        return engine, agents, world

    def _write(self, engine, world):
        engine._execute_chain(
            "陈默",
            [{"name": "update_memory",
              "arguments": {"inner": "记一笔", "rows": [
                  {"keys": ["!always", "校报草稿"], "op": "open",
                   "desc": "把草稿原件收好。"}]},
              "tool_call_id": "mem-68"}],
            {"time": world.now.isoformat(), "nearby_actors": [], "events": []},
            world.affordances("陈默"), world.version)

    def test_written_memory_row_is_visible_in_the_trace_notebook(self):
        engine, agents, world = self._engine_with_notebook()
        self._write(engine, world)
        self.assertTrue(agents["陈默"].delivered[-1]["ok"], "写入未成功")
        rows = engine.trace.knowledge["陈默"]["rows"]
        self.assertIn("校报草稿", {k for r in rows for k in r["keys"]},
                      "update_memory 写入的行必须能在轨迹里查到")

    def test_turn_annotates_the_real_store_next_to_the_legacy_field(self):
        engine, agents, world = self._engine_with_notebook()
        self._write(engine, world)
        ps = engine.trace.agent_turns[-1]["private_state"]
        self.assertEqual(ps["memories"], [], "遗留字段按设计为空")
        self.assertEqual(ps["memory_store"], "engine-kb",
                         "复盘可见字段必须指明记忆真身所在")
        self.assertEqual(ps["knowledge_rows"], 2)

    def test_saved_artifact_carries_the_knowledge_section(self):
        engine, agents, world = self._engine_with_notebook()
        self._write(engine, world)
        snap = engine.trace.snapshot(world)
        self.assertIn("knowledge", snap, "轨迹快照必须带 KB 段")
        self.assertIn("校报草稿",
                      {k for r in snap["knowledge"]["陈默"]["rows"] for k in r["keys"]})

    def test_health_report_reads_kb_rows_apart_from_the_legacy_field(self):
        module = _checker_module()
        report = module.health_report(
            {"agent_turns": [
                {"perception": {"time": "2026-03-16T07:04:00+08:00"},
                 "private_state": {"memories": [], "memory_store": "engine-kb",
                                   "knowledge_rows": 38}}],
             "sessions": {}, "world_events": [],
             "knowledge": {"唐小岚": {"rows": [{"keys": ["唐小岚"]}] * 38}}}, 1)
        reading = report["记忆存放（engine KB / 遗留 memories）"]
        self.assertIn("engine-kb", reading)
        self.assertIn("唐小岚:38", reading)
        self.assertIn("遗留", reading)
        legacy = module.health_report(
            {"agent_turns": [
                {"perception": {"time": "2026-03-16T07:04:00+08:00"},
                 "private_state": {"memories": []}}],
             "sessions": {}, "world_events": []}, 1)
        self.assertIn("旧工件", legacy["记忆存放（engine KB / 遗留 memories）"],
                      "旧工件必须显式说明而非猜")




class PrimitiveSufficiencyAuditTests(unittest.TestCase):
    """Ticket 77 — E76/E77/E78：三个死循环族，零引擎改动。

    方法：取**真实世界包**构建世界，只补审计建议的那一条种子声明（测试内叠加，
    不入种子），证明死循环的出口已经可执行。若将来有人删掉"读=文书"、"知觉=物品
    描述"或路由 affordance，这三条会红；若有人提议加 look/call/spawn 原语，请先
    说明这里为什么不成立。
    """

    def test_notice_board_needs_only_a_document_row(self):
        """E76 / ticket 77 — 公告栏死循环（d1 10:49–13:35 主循环，16:12–16:58 复染）。

        活体证据 `real-20261016T210724….json` 与 pm 续跑：错误轮 #329/355/362/
        363/500/994 等十余次都是 `read 教学楼正门内侧公告栏` → "这里没有这样一件
        能读的文书"；五个人互相委派了同一件无法执行的差事两小时，还去问了两位
        路人 extra。审计结论：引擎不缺"看"的原语，缺的是把公告栏登记成文书。
        补一条 `documents:` 声明（带 reading_seconds，可停留即读）后，同一个 `read`
        立刻覆盖它：affordances 出现 read，读后产生 document_read，旁观者只看见
        "他在读"、看不到正文。
        """
        world = load_story_pack().build_world()
        board = "教学楼公告栏"
        world.actors["陈默"].location = "教学楼"
        world.document_defs[board] = {
            "title": board, "reading_seconds": 30, "auto_read": True,
            "content": "玻璃罩下压着三张纸：《台风纪念活动通知》招志愿者整理老照片；"
                       "一张课程表；一张过期的停电通知。"}
        world.item_locations[board] = "教学楼"
        self.assertIn({"kind": "read", "item": board}, world.affordances("陈默"),
                      "read is the verb the loop already had — the board was unregistered")
        world.submit(Intention("陈默", "read", {"item": board}, world.version))
        world.advance()
        read = [e for e in world.event_log if e.kind == "document_read"]
        self.assertEqual(len(read), 1)
        self.assertIn("老照片", read[0].payload["content"])
        self.assertEqual(read[0].visible_to, frozenset({"陈默"}),
                         "the room sees the act, the text stays with the reader")

    def test_fixture_stock_needs_only_an_item_description(self):
        """E77 / ticket 77 — 库存/陈设不可查验（热水壶 16:26–16:51 与 19:34–19:55、
        关东煮库存 19:34–19:52、食堂菜牌 13:22–13:38）。

        活体证据：唐小岚在自己当班的咖啡馆里找不到热水壶，只能向客人打听，16:40
        自嘲"我就在这家店当班，刚才没认出来"；班长/陈默/吴阿姨为"关东煮还剩什么"
        僵持近二十分钟（report §1.4/§2.4）。审计结论：引擎的知觉已经把**在场物品
        的客观描述**投给在场者（`_visible_descriptions` + ticket 49 的 observed
        记忆行），所以摊位库存和陈设只需要一条 `items:` 声明（正文写清数量），
        不需要 examine 原语；需要"读"的（菜牌、价目表）按 E76 登记成文书。
        """
        world = load_story_pack().build_world()
        pot = "关东煮锅"
        world.actors["唐小岚"].location = "半坡咖啡馆"
        world.entity_descriptions[pot] = ("# 关东煮锅\n\n格子锅里还剩六串：萝卜两份、"
                                          "豆腐四份，汤正开着。")
        world.item_locations[pot] = "半坡咖啡馆"
        perceived = world.poll("唐小岚")
        self.assertIn(pot, perceived["descriptions"], "在场即见，问人之前世界已经给了答案")
        self.assertIn("萝卜两份", perceived["descriptions"][pot])
        self.assertIn("萝卜两份",
                      world.actors["唐小岚"].observed[pot]["objective"],
                      "首次看见即落成记忆行（ticket 49），不依赖当回合")
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("唐小岚", "read", {"item": pot}, world.version))
        self.assertIn("实物", caught.exception.message,
                      "it is a prop, not a document — and the refusal says so")
        self.assertTrue(caught.exception.alternatives,
                        "a prop still leaves an executable next step")

    def test_the_hotline_loop_needs_a_world_exit_not_a_verb(self):
        """E78 / ticket 77 — 12345 借电话死胡同（21:30–22:00）。

        活体证据：下棋大爷找不到能合法过夜的地方；班长与陈默想拨 12345，但引擎
        没有打电话的动作，最后半小时成了"借电话"循环（向店员、向 extra 借，全是
        "不归我管"），世界钟在任务未决时走到 22:00（report §1.5/§2.4）。审计结论：
        死胡同的根因是种子里缺一个**世界内出口**（可达的地点 + 说明它用途的地方
        正文/通知），不是缺 call 原语；`text` 对非人地址的拒绝已经给出可执行替代。
        残留（记录、不实现）：字面意义上"打给非人端点"今天确实不可表达，最小泛化
        是把 `text` 的目标类从 actor 扩到已注册非人端点，而不是新增 call 动作。
        """
        from harness.kernel import LocationState
        world = load_story_pack().build_world()
        world.actors["下棋大爷"].location = "半坡咖啡馆"
        night = "通宵值班室"
        self.assertIs(world._route_path("半坡咖啡馆", night), None,
                      "the shipped map has no such place yet — that is the gap")
        world.locations[night] = LocationState(night)
        world.routes[("半坡咖啡馆", night)] = 300
        world.routes[(night, "半坡咖啡馆")] = 300
        world.entity_descriptions[night] = ("# 通宵值班室\n\n门一直开着，"
                                            "值班台后能登记夜里无处可去的人。")
        self.assertIn({"kind": "move", "target": night},
                      world.affordances("下棋大爷"),
                      "one seeded exit turns the loop into an ordinary walk")
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("下棋大爷", "text", {"target": "12345",
                                                        "text": "夜里哪儿能待？"},
                                   world.version))
        self.assertIn("12345", caught.exception.message)
        self.assertIn("recipient_candidates", caught.exception.context,
                      "even the unsupported address is refused with real people named")


if __name__ == "__main__":
    unittest.main()


# --- Ticket 78: 种子契约四门（G1–G4）的最小世界包夹具 ------------------------
#
# 四门都读一个完整的 world pack，所以夹具必须是一个能被 load_world_pack 接受的
# 最小世界：一个地点、一个演员、一条 kb 身份行、每个实体一份 .md。测试只增删
# 声明，不改引擎——门红了就说明声明缺了，绿了就说明声明在了。

_GATE_CLOCK = {"start": "2026-03-16T07:00:00+08:00",
               "stop": "2026-03-16T09:00:00+08:00"}


def _gate_world(directory, *, locations=None, actors=None, items=None,
                documents=None, routes=None, scheduled=None, concepts=None,
                bodies=None) -> Path:
    """最小世界包：默认一个屋子、一个演员甲、空的一切。"""
    import yaml
    root = Path(directory) / "world"
    locations = locations if locations is not None else [{"id": "屋子"}]
    actors = actors if actors is not None else [{"id": "甲", "location": "屋子"}]
    items = items or []
    documents = documents or []
    bodies = bodies or {}
    manifest = {
        "schema_version": 1,
        "clock": dict(_GATE_CLOCK),
        "locations": locations,
        "actors": actors,
        "items": items,
        "documents": documents,
        "routes": routes or [],
        "barriers": [],
        "scheduled": scheduled or [],
        "kb": {str(row["id"]): [{"keys": [str(row["id"])], "desc": f"我，{row['id']}。"}]
               for row in actors},
    }
    if concepts:
        manifest["concepts"] = concepts
    for category in ("locations", "characters", "items", "documents"):
        (root / category).mkdir(parents=True, exist_ok=True)
    for row in locations:
        place = str(row["id"])
        body = bodies.get(place, f"# {place}\n\n一间屋子。\n")
        (root / "locations" / f"{place}.md").write_text(body, encoding="utf-8")
    for row in actors:
        (root / "characters" / f"{row['id']}.md").write_text(
            f"# {row['id']}\n\n一个在这里的人。\n", encoding="utf-8")
    for row in documents:
        entity = str(row["id"])
        body = bodies.get(entity, f"# {entity}\n\n一张纸。\n")
        (root / "documents" / f"{entity}.md").write_text(body, encoding="utf-8")
    for row in items:
        entity = str(row["id"])
        body = bodies.get(entity, f"# {entity}\n\n一件东西。\n")
        (root / "items" / f"{entity}.md").write_text(body, encoding="utf-8")
    (root / "manifest.yml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    return root


def _gate_module():
    """按本文件既有习惯以 importlib 载入 scripts/seed_lint.py。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "seed_lint_ticket78", Path(__file__).parents[2] / "scripts" / "seed_lint.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gate_findings(lint, name, root):
    """跑四门里的一门：pack 从这里载入，root 用来给违规定位到行。"""
    from harness.world_loader import load_world_pack
    pack = load_world_pack(root)
    gate = getattr(lint, name)
    if name == "reachability_findings":
        return gate(pack, root)
    return gate(pack, root)


class SeedContractGateTests(unittest.TestCase):
    """Ticket 78: 四道种子契约门。每一门在最小夹具上先红后绿：

    红 = 声明缺了，门指出行与修法；绿 = 按修法补上声明，同一段正文通过。
    四门只认既有概念类别（actors / locations / items / documents / concepts /
    kb 联系人），不引入新原语——与票 77 的“原语充分性”一致：
    公告栏是 documents 行、关东煮锅是 items 行、值班干事是 actors 行。
    """

    def test_g1_an_acting_role_noun_needs_a_real_actor(self):
        """G1 红：排程广播里“值班干事把话说明白了”没有任何演员能兑现。

        d1-pm 的 16:20 面核就是这一族：通知里有一个摊开审计包的人，世界里没有
        这个人，晚到的人也无从感知“面核正在进行”。"""
        lint = _gate_module()
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, scheduled=[{
                "event": "refusal",
                "time": "2026-03-16T07:30:00+08:00",
                "notice": "值班干事把话说明白了：本周的申请一律不受理。"}])
            findings = lint.schedule_agent_findings(lint.load_world_pack(root), root)
            self.assertEqual(len(findings), 1, findings)
            self.assertIn("值班干事", findings[0])
            self.assertIn("actors:", findings[0], "修法必须指到既有类别")
            self.assertIn("缺席", findings[0], "第二条修法是可观测缺席写法")
        # 绿①：把主语换成既有演员。
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, scheduled=[{
                "event": "refusal",
                "time": "2026-03-16T07:30:00+08:00",
                "notice": "[[甲]]把话说明白了：本周的申请一律不受理。"}])
            self.assertEqual(lint.schedule_agent_findings(lint.load_world_pack(root), root), [])
        # 绿②：改成可观测缺席写法，不声称有人在场执行。
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, scheduled=[{
                "event": "refusal",
                "time": "2026-03-16T07:30:00+08:00",
                "notice": "值班干事今天不在，受理窗口关着，没有收件渠道。"}])
            self.assertEqual(lint.schedule_agent_findings(lint.load_world_pack(root), root), [])

    def test_g1_quoted_speech_and_absence_forms_are_not_agents(self):
        """G1 的两处歧义边界：引号里是某个角色说的话（转述），缺席写法说的是
        这个人不在——两者都不是“世界要让人来做这件事”。"""
        lint = _gate_module()
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, scheduled=[{
                "event": "gossip",
                "time": "2026-03-16T07:30:00+08:00",
                "notice": "[[甲]]转述隔壁的话：'李阿姨给儿子相了个姑娘。'"}])
            self.assertEqual(lint.schedule_agent_findings(lint.load_world_pack(root), root), [])

    def test_g2_a_bare_role_noun_needs_registration_or_a_generic_declaration(self):
        """G2 红：正文里的“值班干事”既没注册，也没声明是泛称。

        d1-pm 里同一个词出现在面核通知、值班簿、场地申请表与唐小岚的常驻行：
        谁读到它都没有可解析的东西，谁写它都不需要解释这个人是谁。"""
        lint = _gate_module()
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, scheduled=[{
                "event": "refusal",
                "time": "2026-03-16T07:30:00+08:00",
                "notice": "值班干事把话说明白了：本周的申请一律不受理。"}])
            findings = lint.role_prose_findings(lint.load_world_pack(root), root)
            self.assertEqual(len(findings), 1, findings)
            self.assertIn("值班干事", findings[0])
            self.assertIn("role_prose", findings[0], "第二条修法是显式泛称声明")
        # 绿①：声明这一行的角色词是泛称集合。
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, scheduled=[{
                "event": "refusal",
                "time": "2026-03-16T07:30:00+08:00",
                "role_prose": ["值班干事"],
                "notice": "值班干事把话说明白了：本周的申请一律不受理。"}])
            self.assertEqual(lint.role_prose_findings(lint.load_world_pack(root), root), [])
        # 绿②：注册成泛称概念（kind: generic 不给任何人发知识行）。
        with TemporaryDirectory() as directory:
            root = _gate_world(
                directory,
                scheduled=[{"event": "refusal",
                            "time": "2026-03-16T07:30:00+08:00",
                            "notice": "[[值班干事]]把话说明白了：申请一律不受理。"}],
                concepts=[{"id": "duty-clerk", "name": "值班干事", "kind": "generic"}])
            self.assertEqual(lint.role_prose_findings(lint.load_world_pack(root), root), [])

    def test_g3_every_location_needs_a_route_from_an_mc_start(self):
        """G3 红：注册了一个没有任何路由的地点——角色 move 过去只会被拒绝，
        常驻任务因此永远完不成（后街糕点铺的 6 小时带话死任务）。"""
        lint = _gate_module()
        places = [{"id": "屋子"}, {"id": "铺子"}]
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, locations=places)
            findings = lint.reachability_findings(lint.load_world_pack(root), root)
            self.assertTrue(any("铺子" in finding for finding in findings), findings)
            self.assertIn("routes:", findings[0], "修法必须指到既有声明")
        # 绿：双向加一条路由。
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, locations=places, routes=[
                {"from": "屋子", "to": "铺子", "duration_seconds": 300},
                {"from": "铺子", "to": "屋子", "duration_seconds": 300}])
            self.assertEqual(lint.reachability_findings(lint.load_world_pack(root), root), [])
        # 绿：远程地点（只通电话/消息）是种子显式声明的走不到。
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, locations=[
                {"id": "屋子"}, {"id": "老家", "remote": True, "primer": False}])
            self.assertEqual(lint.reachability_findings(lint.load_world_pack(root), root), [])

    def test_g3_a_prose_destination_must_be_a_location_not_a_place_concept(self):
        """G3 第二臂：种子派角色去一个只有 kind: place 概念的地方。"""
        lint = _gate_module()
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, concepts=[{
                "id": "back-street", "name": "后街铺子", "kind": "place",
                "known_to": ["甲"], "desc": "校门后街的小铺子。"}],
                scheduled=[{"event": "errand",
                            "time": "2026-03-16T07:30:00+08:00",
                            "target": "甲",
                            "notice": "交接班前去[[后街铺子]]帮老板娘带话。"}])
            findings = lint.reachability_findings(lint.load_world_pack(root), root)
            self.assertTrue(any("后街铺子" in finding for finding in findings), findings)
        # 绿：同一个地方注册成地点 + 双向路由。
        with TemporaryDirectory() as directory:
            root = _gate_world(
                directory,
                locations=[{"id": "屋子"}, {"id": "后街铺子"}],
                routes=[{"from": "屋子", "to": "后街铺子", "duration_seconds": 300},
                        {"from": "后街铺子", "to": "屋子", "duration_seconds": 300}],
                scheduled=[{"event": "errand",
                            "time": "2026-03-16T07:30:00+08:00",
                            "target": "甲",
                            "notice": "交接班前去[[后街铺子]]帮老板娘带话。"}])
            self.assertEqual(lint.reachability_findings(lint.load_world_pack(root), root), [])

    def test_g3_an_item_needs_a_path_or_a_completeness_declaration(self):
        """G3 红：一件东西放在走不到的地方（红色哨子在远程的老家属院）。

        绿①：放进一个可达角色的背包。绿②：作者声明它此刻不在手上。"""
        lint = _gate_module()
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, locations=[
                {"id": "屋子"}, {"id": "老家", "remote": True, "primer": False}],
                items=[{"id": "哨子", "location": "老家", "readable": False,
                        "readable_reason": "一只哨子。"}])
            findings = lint.reachability_findings(lint.load_world_pack(root), root)
            self.assertTrue(any("哨子" in finding for finding in findings), findings)
            self.assertIn("completeness", findings[0])
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, items=[
                {"id": "哨子", "location": None, "readable": False,
                 "readable_reason": "一只哨子。"}],
                actors=[{"id": "甲", "location": "屋子", "inventory": ["哨子"]}])
            self.assertEqual(lint.reachability_findings(lint.load_world_pack(root), root), [])
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, items=[
                {"id": "哨子", "location": None, "completeness": "missing",
                 "readable": False, "readable_reason": "一只哨子。"}])
            self.assertEqual(lint.reachability_findings(lint.load_world_pack(root), root), [])

    def test_g4_a_read_mention_needs_a_document(self):
        """G4 红：房间正文提到公告栏，但 read 的目标只能是文书。

        d1-pm 10:49–13:35 的全团“谁去看公告栏”循环就是这一族：没有任何人能
        read 一块板，走进楼也没有“查看张贴”的动作。"""
        lint = _gate_module()
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, bodies={
                "屋子": "# 屋子\n\n一间屋子。\n\n门边的公告栏贴着过期通知。\n"})
            findings = lint.interaction_findings(lint.load_world_pack(root), root)
            self.assertEqual(len(findings), 1, findings)
            self.assertIn("公告栏", findings[0])
            self.assertIn("documents:", findings[0], "修法必须指到既有类别")
        # 绿：把公告栏注册成一份可读文书，正文就是张贴的内容；地点行同时按
        # ticket 35 声明它可以被读（actionable_refs），两条契约正好接上。
        with TemporaryDirectory() as directory:
            root = _gate_world(
                directory,
                locations=[{"id": "屋子", "actionable_refs": [
                    {"action": "read", "target": "公告栏", "at": "屋子"}]}],
                documents=[{"id": "公告栏", "title": "公告栏", "location": "屋子",
                            "known_to": ["甲"], "reading_seconds": 10,
                            "content": "本周的申请一律不受理。"}],
                bodies={"屋子": "# 屋子\n\n一间屋子。\n\n门边的公告栏贴着过期通知。\n",
                        "公告栏": "# 公告栏\n\n门边钉着的一块板。\n"})
            self.assertEqual(lint.interaction_findings(lint.load_world_pack(root), root), [])

    def test_g4_an_examine_mention_needs_an_item(self):
        """G4 红：正文提到热水壶（要被看见/拿取），但它不是 items 行。

        票 77 已裁定这条编码：房间陈设是 items 行，描述走知觉与 observed。"""
        lint = _gate_module()
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, bodies={
                "屋子": "# 屋子\n\n一间屋子。\n\n桌上有一只热水壶，壶身有一道旧划痕。\n"})
            findings = lint.interaction_findings(lint.load_world_pack(root), root)
            self.assertTrue(any("热水壶" in finding for finding in findings), findings)
            self.assertIn("items:", findings[0])
        with TemporaryDirectory() as directory:
            root = _gate_world(
                directory,
                items=[{"id": "热水壶", "location": "屋子", "known_to": ["甲"],
                        "readable": False, "readable_reason": "一只水壶。"}],
                bodies={"屋子": "# 屋子\n\n一间屋子。\n\n桌上有一只热水壶，壶身有一道旧划痕。\n"})
            self.assertEqual(lint.interaction_findings(lint.load_world_pack(root), root), [])

    def test_g4_a_call_mention_needs_a_person_to_reach(self):
        """G4 红：一条规则要求“电话报备”，而世界里没有可联系的对方
        （档案室管理員只是概念；d1-pm 里全团连 12345 都无法表达）。"""
        lint = _gate_module()
        with TemporaryDirectory() as directory:
            root = _gate_world(directory, locations=[
                {"id": "屋子", "rules": ["管理员不在时重大事项须电话报备"]}])
            findings = lint.interaction_findings(lint.load_world_pack(root), root)
            self.assertTrue(any("电话" in finding for finding in findings), findings)
            self.assertIn("actors:", findings[0])
        # 绿：要求打电话的对象是一个真实角色（同时它也是本行正文提到的对象）。
        with TemporaryDirectory() as directory:
            root = _gate_world(
                directory,
                actors=[{"id": "甲", "location": "屋子"}, {"id": "乙", "location": "屋子"}],
                locations=[{"id": "屋子", "rules": ["重大事项须打电话找[[乙]]报备"]}])
            self.assertEqual(lint.interaction_findings(lint.load_world_pack(root), root), [])

    def test_the_gates_bite_on_the_shipped_pack(self):
        """四门在**真实种子**的结构上也咬得住（夹具之外的第二重证据）。

        每门往一份真实种子副本里注入一类缺陷，再看它自己那一门是否报出：排程
        里一个没人能演的角色（G1/G2）、一个被摘掉全部路由的地点（G3）、房间
        正文里一件没注册的静物（G4）。这样即使夹具写错，门与真实种子的接线也检过。
        """
        lint = _gate_module()
        import shutil
        import yaml
        with TemporaryDirectory() as directory:
            root = Path(directory) / "world"
            shutil.copytree(Path(__file__).parents[2] / "world", root)
            manifest_path = root / "manifest.yml"
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            data["scheduled"].insert(0, {
                "event": "gate_probe",
                "time": "2026-03-16T07:10:00+08:00",
                "notice": "巡夜保安把侧门锁上了，钥匙交回了值班室。"})
            data["routes"] = [row for row in data["routes"]
                              if "河堤" not in (row["from"], row["to"])]
            manifest_path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8")
            canteen = root / "locations" / "食堂.md"
            canteen.write_text(canteen.read_text(encoding="utf-8").rstrip("\n")
                               + "\n\n窗口上方挂着一块菜牌，写着今天的四个菜。\n",
                               encoding="utf-8")
            pack = lint.load_world_pack(root)
            # 门报的是词表里的角色词（“保安”），不是整句主语。
            self.assertTrue(any("保安" in finding and "gate_probe" in finding
                                for finding in lint.schedule_agent_findings(pack, root)))
            self.assertTrue(any("保安" in finding and "gate_probe" in finding
                                for finding in lint.role_prose_findings(pack, root)))
            reach = lint.reachability_findings(pack, root)
            self.assertTrue(any("location 河堤" in finding for finding in reach), reach)
            self.assertTrue(any("菜牌" in finding
                                for finding in lint.interaction_findings(pack, root)))

    def test_a_fixed_fixture_cannot_be_taken_and_stays_put(self):
        """E83 / ticket 80（票 79 §8-5）：新登记的五件陈设是固定陈设，拿不走。

        票 78 G4 按票 77 的编码把它们写成 `items:`（在场者靠知觉拿到描写），
        而 `take` 对任何 item 都成立——模型可以把一台冰柜拿走。泛化只有一处：
        `items:` 的可选 `takeable: false` 让 take 结构化拒绝，理由取
        `fixed_reason`（缺省“这是固定陈设”）；give 的就地分支与 trash 走同一条判定，
        因为两者同样能把它从原处抹去。红：把种子里的 `takeable: false` 删掉，
        下面第一段拿冰柜就不再被拒。"""
        pack = load_story_pack()
        world = pack.build_world()
        world.actors["唐小岚"].location = "小卖部"
        world.actors["陈默"].location = "小卖部"
        offered = [option for option in world.affordances("唐小岚")
                   if option.get("kind") == "take"]
        self.assertNotIn({"kind": "take", "item": "冰柜"}, offered,
                         "固定陈设不进 take 候选")
        self.assertIn({"kind": "take", "item": "一瓶饮料"}, offered,
                      "同一地点的货仍然可以拿")
        for kind, args in (("take", {"item": "冰柜"}),
                           ("give", {"item": "冰柜", "target": "陈默"}),
                           ("trash", {"item": "冰柜"})):
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("唐小岚", kind, dict(args), world.version))
            self.assertEqual(caught.exception.context.get("reason"), "fixed_fixture", kind)
            self.assertIn("拿不走", caught.exception.message, kind)
            self.assertIn("抱走", caught.exception.message, kind)  # 种子写的理由原样转达
            self.assertEqual(world.item_locations.get("冰柜"), "小卖部", kind)
        world.submit(Intention("唐小岚", "take", {"item": "一瓶饮料"}, world.version))
        world.advance()
        self.assertIn("一瓶饮料", world.actors["唐小岚"].inventory)
        # 种子没写理由时用缺省文案；写了就照抄，不改写。
        bare = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                     actors=[ActorState("a", "room")], locations=[LocationState("room")],
                     item_locations={"冰柜": "room"},
                     fixed_items={"冰柜": "", "冰柜二号": "通电中，搬不动。"})
        bare.item_locations["冰柜二号"] = "room"
        for item, wording in (("冰柜", "这是固定陈设"), ("冰柜二号", "通电中，搬不动。")):
            with self.assertRaises(ActionRejected) as caught:
                bare.submit(Intention("a", "take", {"item": item}, bare.version))
            self.assertIn(wording, caught.exception.message)
        # 装载器校验字段类型：`takeable` 写错不是静默降级成“可携带”。
        import shutil
        from harness.world_loader import load_world_pack
        with TemporaryDirectory() as directory:
            root = Path(directory) / "world"
            shutil.copytree(Path(__file__).parents[2] / "world", root)
            manifest = root / "manifest.yml"
            broken = manifest.read_text(encoding="utf-8").replace(
                "- id: 冰柜\n  location: 小卖部\n  takeable: false\n",
                "- id: 冰柜\n  location: 小卖部\n  takeable: 'no'\n", 1)
            self.assertNotEqual(broken, manifest.read_text(encoding="utf-8"))
            manifest.write_text(broken, encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                load_world_pack(root)
            self.assertIn("takeable must be true or false", str(caught.exception))

    def test_the_four_gates_run_as_one_command_on_a_clean_pack(self):
        """四门合成一条通道：一个干净的世界包零违规，CLI 因此只有一条判据。"""
        lint = _gate_module()
        with TemporaryDirectory() as directory:
            root = _gate_world(directory)
            self.assertEqual(lint.contract_gate_findings(root), [])


# --- 票据 83：M1 第一窗口（07:00→14:00）的引擎侧修复 ------------------------
# 三处引擎行为（物品在 extra 生命周期下不消失、写记录动作的可用性文案、
# 无调用的回合在 trace 里可诊断）各自先红后绿；第四条（NPC 只叙述不施动）的
# 裁定见票据 83 与 docs/V4-ENGINE.md §7.4：话语从不被当作动作，缺陷在提示层。

class ExtraDespawnItemInvariantGates(unittest.TestCase):
    """E84（报 81 §5，票 74 缺陷 B 的邻居）：extra 带走的主线道具必须留在世上。

    2026-10-18 窗口 run（real-20261018T012247）12:52 陈阿姨在半坡咖啡馆
    `take 校报草稿` 成功，13:07 她按 idle 被回收——草稿随她一起离开世界：
    `item_locations` 里没有它、没有一条事件说明它去了哪里，唐小岚 13:17 回到
    咖啡馆时 nearby_items 只剩裂纹马克杯（她的 !always 目标物无声消失）。
    引擎侧的不变式因此是：**任何物品在任何时刻都有一个确定的位置**——extra
    被回收前，它手里的每件东西都要按既有 `place` 语义落到它最后所在地点，
    并留下一条可 replay 的事件。
    """

    START = datetime.fromisoformat("2026-03-16T12:50:00+08:00")

    def _scene(self):
        world = load_story_pack().build_world()
        world.actors["唐小岚"].location = "半坡咖啡馆"
        world.add_extra("陈阿姨", "半坡咖啡馆")
        world.submit(Intention("陈阿姨", "take", {"item": "校报草稿"}, world.version))
        world.advance(until=world.now + timedelta(minutes=2))
        return world

    def test_despawn_leaves_carried_items_at_the_last_location(self):
        world = self._scene()
        self.assertIn("校报草稿", world.actors["陈阿姨"].inventory)
        self.assertNotIn("校报草稿", world.item_locations)
        world.remove_extra("陈阿姨", reason="idle")
        self.assertEqual(world.item_locations.get("校报草稿"), "半坡咖啡馆",
                         "回收 extra 不能把物品一起带走")
        drops = [e for e in world.event_log if e.kind == "item_dropped"]
        self.assertEqual([e.payload.get("item") for e in drops], ["校报草稿"])
        self.assertEqual(drops[0].payload.get("location"), "半坡咖啡馆")
        self.assertIn("唐小岚", drops[0].visible_to, "同在地点的人必须看得见它落在原处")
        self.assertIn({"kind": "take", "item": "校报草稿"}, world.affordances("唐小岚"),
                      "落在原处的道具必须重新可拿")
        from harness.prompt import _event_sentence
        line = _event_sentence(
            {"kind": "item_dropped", "actor": "陈阿姨",
             "payload": drops[0].payload}, location="半坡咖啡馆")
        self.assertIn("校报草稿", line or "")
        self.assertIn("留在了半坡咖啡馆", line or "",
                      "同地的人在消息里读得到「它落在了原处」")

    def test_replay_rebuilds_the_same_item_location(self):
        world = self._scene()
        world.remove_extra("陈阿姨", reason="idle")
        replayed = replay_world(load_story_pack().build_world(), world.replayable_log())
        self.assertEqual(replayed.item_locations.get("校报草稿"), "半坡咖啡馆")
        self.assertNotIn("陈阿姨", replayed.actors)
        self.assertEqual(
            [e["kind"] for e in replayed.replayable_log()],
            [e["kind"] for e in world.replayable_log()])

    def test_every_prefix_keeps_the_item_somewhere(self):
        """不变式的形状：日志的每个前缀之后，草稿要么在某人手里，要么在某个地点。"""
        world = self._scene()
        world.remove_extra("陈阿姨", reason="idle")
        initial = load_story_pack().build_world()
        log = world.replayable_log()
        for cut in range(1, len(log) + 1):
            state = replay_world(initial, log[:cut])
            holders = [actor for actor, value in state.actors.items()
                       if "校报草稿" in value.inventory]
            self.assertTrue(holders or state.item_locations.get("校报草稿"),
                            f"第 {cut} 条事件之后「校报草稿」既不在任何地点也不在任何人手里")


class WriteRecordAffordanceGates(unittest.TestCase):
    """E85（报 81 报告 08:53/13:13）：写记录的动作存在，却读起来不像能写记录。

    林瑶 08:34 真的用 `leave_note` 写下了 400 字事实记录（turn 93，
    `note_left` 落地），可 08:53 起她说"记录应分别写好再交，不把口头说明或
    留字条当成完成"，13:13 拿着 `可用纸笔` 的 `inner` 是"纸笔在我手上，但没有
    可用工具把个人事实记录实际写入纸面"。诊断：`leave_note` **不依赖任何持有物**
    （`World.affordances` 无条件给出，工具表无条件声明，kernel 只看 `text`），
    但它的说明只把它写成"给之后进入的人留一张字条、阅后即焚"，于是一个要把
    记录写在纸上的角色认定"这不是记录"。修法不改语义、不造机制：让工具说明与
    affordance 提示把它说成"写记录/留字条"，并明说这件事不需要先拿到纸笔。
    """

    def _offered(self, world, actor):
        return [option for option in world.affordances(actor)
                if option.get("kind") == "leave_note"]

    def test_leave_note_is_described_as_writing_a_record_with_or_without_paper(self):
        from harness.action_schema import TOOLS
        tool = next(t["function"] for t in TOOLS if t["function"]["name"] == "leave_note")
        description = tool["description"]
        self.assertIn("写记录", description, "工具说明必须把 leave_note 说成能写记录")
        self.assertIn("字条", description)
        pack = load_story_pack()
        for held, label in ((False, "空手"), (True, "拿着纸笔")):
            world = pack.build_world()
            if held:
                world.actors["林瑶"].inventory.add("可用纸笔")
            offered = self._offered(world, "林瑶")
            self.assertEqual(len(offered), 1, f"{label}：写记录的动作必须在可用清单里")
            self.assertIn("写记录", str(offered[0].get("hint", "")), label)
            world.submit(Intention("林瑶", "leave_note",
                                   {"text": "3/16 记录：亲见、转述与未知分开写。"},
                                   world.version))
            world.advance()
            self.assertEqual(world.locations["女生宿舍"].notes[-1]["author"], "林瑶", label)

    def test_a_note_is_not_gated_on_holding_writing_material(self):
        """两种持有状态下都能写：纸笔不是前提，拒绝文案里也不出现"先取纸笔"。"""
        pack = load_story_pack()
        for held in (False, True):
            world = pack.build_world()
            if held:
                world.actors["陈默"].inventory.add("可用纸笔")
            world.submit(Intention("陈默", "leave_note", {"text": "记录：仅写亲历。"},
                                   world.version))
            events = world.advance()
            self.assertTrue(any(e.kind == "note_left" for e in events), held)
            with self.assertRaises(ActionRejected) as caught:
                world.submit(Intention("陈默", "leave_note", {"text": "  "}, world.version))
            self.assertNotIn("纸笔", caught.exception.message)


class TurnWithoutActionGates(unittest.TestCase):
    """E86（报 81 §2）：一个没有调用的回合必须在 trace 里说清为什么什么都没发生。

    2026-10-18 窗口 run 的 12:51 林瑶（mc）回合：`result=none`、`inner=None`、
    零调用，世界只往前走一拍——审阅者只看到一条空白行。引擎不改模型行为，
    只把"这一回合没有产生动作"记成一条带 reason 的 system_turn：
    `prose_only`（写了话但没提交意图）或 `no_output`（什么都没返回）。

    E87（报 81 §3）：话语从不被当成动作。食堂大妈 12:44–12:58 七次"我马上给你
    打"都是真的 `speak` 调用（事件 #…），没有一次 `give`/`place`——引擎照实记
    了七句话、零交付，所以那是提示层（NPC 导演简报）的问题，不是引擎把承诺当
    动作。本类同时钉住这条区分：一个只有 speak 的回合不会产生 `empty_turn`。
    """

    def _engine(self, world, replies):
        """A v4 engine whose agents return the scripted reply per actor turn."""
        trace = Trace("v4-test", "ticket83-empty-turn")
        queue = {actor: list(rows) for actor, rows in replies.items()}

        class _SessionAgent:
            """v4 agent: returns (text, calls) per call, records what it sent."""

            def __init__(self, actor):
                self.actor = actor
                self.session_obj = object()

            def __call__(self, text, state):
                rows = queue.get(self.actor) or [{"text": "", "calls": []}]
                row = rows.pop(0) if len(rows) > 1 else rows[0]
                return {"text": row.get("text", ""), "calls": row.get("calls", []),
                        "inner": None}

        agents = {actor: _SessionAgent(actor) for actor in world.actors}
        states = {actor: PrivateState(actor) for actor in world.actors}
        engine = AsyncEngine(world, agents, states, trace, None,
                             decision_timeout=10, max_wall_seconds=60)
        return engine, trace

    def _run(self, replies, minutes=6, locate=None):
        world = load_story_pack().build_world()
        for actor, place in (locate or {}).items():
            world.actors[actor].location = place
        engine, trace = self._engine(world, replies)
        engine.run(stop_at=world.now + timedelta(minutes=minutes), max_turns=40)
        return world, trace

    @staticmethod
    def _empty_turns(trace, actor):
        return [t for t in trace.system_turns
                if t["request"].get("kind") == "empty_turn"
                and t["result"].get("actor") == actor]

    def test_a_turn_with_text_and_no_call_is_recorded_as_prose_only(self):
        world, trace = self._run({"陈默": [{"text": "我再想想，还没决定要做什么。"}]})
        rows = self._empty_turns(trace, "陈默")
        self.assertTrue(rows, "有输出但没有调用的回合必须留下可审计记录")
        self.assertEqual(rows[0]["result"]["reason"], "prose_only")
        self.assertEqual(rows[0]["result"]["role"], "mc")
        self.assertGreater(rows[0]["result"]["private_chars"], 0)

    def test_a_turn_with_nothing_at_all_is_recorded_as_no_output(self):
        world, trace = self._run({"林瑶": [{"text": "", "calls": []}]})
        rows = self._empty_turns(trace, "林瑶")
        self.assertTrue(rows, "既无调用又无输出的回合必须留下可审计记录")
        self.assertEqual(rows[0]["result"]["reason"], "no_output")
        self.assertEqual(rows[0]["result"]["private_chars"], 0)

    def test_a_spoken_promise_is_recorded_as_speech_not_as_an_action(self):
        """E87：七次"我马上给你打"是七句话、零次交付——引擎照实记账。

        反夹具：食堂大妈同一回合只说 `speak`，世界里没有 `item_given`/`place`，
        轨迹里也没有 `empty_turn`（她提交了意图）；正夹具：她真的 `give`
        一份餐食给在场的唐小岚时，`item_given` 才出现。
        """
        world = load_story_pack().build_world()
        world.actors["唐小岚"].location = "食堂"
        world.submit(Intention("食堂大妈", "speak",
                               {"text": "行，一荤一素配米饭，我马上给你打。",
                                "volume": "normal", "to": ["唐小岚"]}, world.version))
        world.advance()
        self.assertTrue([e for e in world.event_log if e.kind == "speech"])
        self.assertFalse([e for e in world.event_log if e.kind == "item_given"],
                         "说话不产生交付")
        self.assertIn("一份餐食", world.item_locations, "她确实有可交付的东西")
        world.submit(Intention("食堂大妈", "give",
                               {"item": "一份餐食", "target": "唐小岚"}, world.version))
        world.advance()
        self.assertEqual([e.payload.get("item") for e in world.event_log
                          if e.kind == "item_given"], ["一份餐食"])
        self.assertIn("一份餐食", world.actors["唐小岚"].inventory)

    def test_a_turn_that_speaks_is_not_an_empty_turn(self):
        """E87 的负向守卫：提交了 speak 的回合不是空回合。

        E86 的诊断只该覆盖"没有提交任何意图"的回合；一个只说了话的回合是
        `submitted`（话进了世界），不能被记成空回合——否则"话语"与"空转"就
        又混在一起了。
        """
        ask = {"name": "speak",
               "arguments": {"text": "大妈，我要一份一荤一素配米饭。",
                             "volume": "normal", "to": ["食堂大妈"]}}
        promise = {"name": "speak",
                   "arguments": {"text": "行，一荤一素配米饭，我马上给你打。",
                                 "volume": "normal", "to": ["唐小岚"]}}
        world, trace = self._run({
            "唐小岚": [{"text": "", "calls": [ask]}],
            "食堂大妈": [{"text": "", "calls": [promise]}]},
            locate={"唐小岚": "食堂", "陈默": "男生宿舍"})
        promises = [e for e in world.event_log
                    if e.kind == "speech" and e.actor == "食堂大妈"]
        self.assertTrue(promises, "承诺必须作为一句话落地")
        self.assertFalse([e for e in world.event_log if e.kind == "item_given"],
                         "说话不产生交付")
        self.assertFalse(self._empty_turns(trace, "食堂大妈"),
                         "提交了 speak 的回合不是空回合")
        turn = next(t for t in trace.agent_turns if t["actor"] == "食堂大妈")
        self.assertEqual(turn["result"], "submitted")


class PromptDeliveryConsistencyGates(unittest.TestCase):
    """E88（票 85）：话语不改变世界、不得断言未见的世界变化、写记录不必先有纸笔。

    票 83 把"NPC 只叙述不施动"判给提示层，但提示层当时只说了一半：NPC 唤醒的
    `[director]` 块里只有本场目标，没有"承诺要用 give 兑现"；extra 的固定 prompt
    只有"不得叙述没做过的动作"，没有"话不改变世界／不得否认世界状态"；MC 只有
    工具说明，而 `give`/`take` 读起来是纯物理描述、`leave_note` 也没说清"书面记录"
    这一层。三支测试分别钉住三类角色各自组装出来的提示文本（读文本，不读函数），
    并断言这些约束没有跑到不属于它的角色类型里。
    """

    def _run_capturing(self, replies, *, minutes=6, locate=None):
        """Run a v4 engine and keep every world message each actor was handed."""
        world = load_story_pack().build_world()
        for actor, place in (locate or {}).items():
            world.actors[actor].location = place
        sent: dict[str, list[str]] = {actor: [] for actor in world.actors}
        queue = {actor: list(rows) for actor, rows in replies.items()}

        class _RecordingAgent:
            """v4 agent: records the assembled prompt, then answers from script."""

            def __init__(self, actor):
                self.actor = actor
                self.session_obj = object()

            def __call__(self, text, state):
                sent[self.actor].append(text)
                rows = queue.get(self.actor) or [{"text": "", "calls": []}]
                row = rows.pop(0) if len(rows) > 1 else rows[0]
                return {"text": row.get("text", ""), "calls": row.get("calls", []),
                        "inner": None}

        agents = {actor: _RecordingAgent(actor) for actor in world.actors}
        states = {actor: PrivateState(actor) for actor in world.actors}
        trace = Trace("v4-test", "ticket85-prompt-delivery")
        engine = AsyncEngine(world, agents, states, trace, None,
                             decision_timeout=10, max_wall_seconds=60)
        engine.run(stop_at=world.now + timedelta(minutes=minutes), max_turns=40)
        return world, sent

    def test_an_npc_wake_briefing_binds_delivery_to_tools(self):
        """NPC 唤醒拿到的 `[director]` 块必须带上两条约束——且只出现在 NPC 那里。

        报告 §P2 的两处失效（七次"我马上给你打"零交付；"长柄勺找不着"断言了世界
        从未发生的移动）都发生在同一个角色、同一段简报之下。这条断言读的是
        **组装后的世界消息**：引擎这次不给 `director_brief`（种子没写本场目标时
        的真实状态），约束仍然在——它是提示层的固定开头，不是种子数据的一部分。
        """
        ask = {"name": "speak",
               "arguments": {"text": "大妈，我要一份一荤一素配米饭。",
                             "volume": "normal", "to": ["食堂大妈"]}}
        world, sent = self._run_capturing({"唐小岚": [{"text": "", "calls": [ask]}]},
                                          locate={"唐小岚": "食堂"})
        self.assertTrue([e for e in world.event_log
                         if e.kind == "speech" and e.actor == "唐小岚"],
                        "夹具前提：唐小岚真的在食堂开了口")
        self.assertTrue(sent["食堂大妈"], "夹具前提：食堂大妈被这句话唤醒并拿到简报")
        briefing = sent["食堂大妈"][0]
        self.assertIn("[director]", briefing, "NPC 唤醒必须带 [director] 块")
        self.assertIn("只有工具调用能改变世界", briefing,
                      "NPC 简报必须说明话不改变世界")
        self.assertIn("give", briefing, "并指名交付要走 give")
        self.assertIn("不许断言或否认世界状态的改变", briefing,
                      "NPC 简报必须禁止断言未见的世界变化")

        # 负面：同一句约束不许漏进 MC 的提示（MC 永远看不到 [director] 块）。
        for mc in ("陈默", "唐小岚", "林瑶"):
            for message in sent[mc]:
                self.assertNotIn("[director]", message, f"{mc} 不该看到导演块")
                self.assertNotIn("不许断言或否认世界状态的改变", message,
                                 f"{mc} 不该看到 NPC 简报的约束")

    def test_an_extra_prompt_binds_delivery_to_tools(self):
        """extra 的固定提示必须说清：话不改变世界，且不得否认世界状态。"""
        from harness.npc_agent import build_extra_system_prompt
        prompt = build_extra_system_prompt("打饭阿姨", "", "食堂", name="王阿姨")
        self.assertIn("只有这些工具调用改变世界", prompt)
        self.assertIn("说“我给你”“我去拿”什么都不会发生", prompt)
        self.assertIn("give", prompt)
        self.assertIn("不许断言或否认世界的变化", prompt)
        self.assertIn("除非你亲眼看见那条事件", prompt)
        # 负面：路人的提示里不该出现不属于它的东西——没有 [director] 块，
        # 也没有只属于 MC 的写记录动作。
        self.assertNotIn("[director]", prompt)
        self.assertNotIn("leave_note", prompt)

    def test_mc_tool_notes_say_words_are_not_delivery(self):
        """MC 只从工具说明学到动作语义，所以那句话必须写在 give/take/leave_note 里。

        报告 §P1 是第三类失效：林瑶 13:13 拿着纸笔写"没有可用工具把个人事实记录
        实际写入纸面"，而 `leave_note` 就在她的工具表里。三件工具各补一句，
        并且这句约束只出现在工具说明里，不落进 MC 的世界消息。
        """
        from harness.action_schema import TOOLS
        described = {tool["function"]["name"]: tool["function"]["description"]
                     for tool in TOOLS}
        self.assertIn("不会让任何东西移动", described["give"],
                      "交付的说明要说明话不搬运东西")
        self.assertIn("不会让东西到你手里", described["take"],
                      "取物的说明要说明话不搬运东西")
        self.assertIn("写记录", described["leave_note"])
        self.assertIn("书面记录", described["leave_note"],
                      "要留下书面记录就用它——报告 §P1 的桥就在这里")
        self.assertIn("不需要先拿到纸笔", described["leave_note"])

        # 负面：NPC 唤醒块的措辞是给导演简报的，不该混进工具说明。
        from harness.prompt import NPC_WAKE_RULES
        for name, description in described.items():
            self.assertNotIn(NPC_WAKE_RULES.strip(), description, name)
            self.assertNotIn("不许断言或否认世界状态的改变", description, name)

    def test_the_docs_name_the_same_three_bindings(self):
        """两份文档与代码指同一个落点：改提示却不改文档，或反过来，都会被拦住。"""
        root = Path(__file__).parents[2]
        interface = (root / "docs" / "V4-AGENT-INTERFACE.md").read_text(encoding="utf-8")
        cast = (root / "docs" / "V4-CAST.md").read_text(encoding="utf-8")
        for anchor in ("NPC_WAKE_RULES", "PromptDeliveryConsistencyGates", "leave_note"):
            self.assertIn(anchor, interface, f"V4-AGENT-INTERFACE 必须点名 {anchor}")
        self.assertIn("PromptDeliveryConsistencyGates", cast,
                      "V4-CAST 的导演简报一节必须指向看守测试")
        self.assertIn("give", cast)


class PersistentNoteGates(unittest.TestCase):
    """E89（报 86 §1，窗口 2 12:11–15:02）：世界里的"书面稿"只能留给下一位进入者、
    读后即焚，于是"写一份说明并交上去"整条链不可表达。

    3 小时里 21 次 `item_given` 全是纸笔在三人之间往返，0 次成稿；96 个回合
    （9.9%）的私有推理在讨论"留条能不能算稿"（12:47/13:18/14:55 陈默与班长）。
    根因不是缺动作：`leave_note` 的投递语义是"给之后第一位非作者、阅后即焚"，
    **按定义不能交给在场的收件人，也不能被同一个人读第二遍**。
    修法是一处泛化而不是新原语：`leave_note` 增加可选 `persist`（缺省 false，
    旧语义一字节不改）；persist 时笔记成为可寻址实体（`note-<作者>-<序号>`），
    留在原地点、进知觉与 `read` 的可用目标、可重复读、可 `trash`，事件里带
    id 与 text，所以 replay 能重建。"交付到某处"= 把它留在目标地点的桌上。
    """

    TEXT = "审计说明：3/16 现场所见与转述已分开记，待班长复核。"

    def _world_with_note(self):
        world = load_story_pack().build_world()
        world.submit(Intention("陈默", "leave_note",
                               {"text": self.TEXT, "persist": True}, world.version))
        world.advance()
        return world

    def test_a_persistent_note_can_be_read_twice_with_the_same_text(self):
        """① 同一张 persist 便条读两次都成功、内容一致，且读后仍留在原处。"""
        world = self._world_with_note()
        note_id = next(iter(world.persistent_notes))
        self.assertTrue(note_id.startswith("note-陈默-"), note_id)
        self.assertEqual(world.persistent_notes[note_id]["location"], "男生宿舍")
        # 它没有退化成"房间里等着烧掉的字条"。
        self.assertEqual(world.locations["男生宿舍"].notes, [])
        # 留在原地的人当场就能读到：read 的可用目标里有它。
        self.assertIn({"kind": "read", "item": note_id}, world.affordances("陈默"))
        for _ in range(2):
            world.submit(Intention("陈默", "read", {"item": note_id}, world.version))
            world.advance()
        reads = [event.payload["content"] for event in world.event_log
                 if event.kind == "document_read" and event.payload["document"] == note_id]
        self.assertEqual(reads, [self.TEXT, self.TEXT], "persist 便条必须能重复读到全文")
        self.assertIn(note_id, world.persistent_notes, "读一次不能把持久便条烧掉")
        # 他人到场后同样读得到（知觉里有它的编号，read 成功）。
        world.actors["班长"].location = "男生宿舍"
        self.assertEqual([note["id"] for note in world.poll("班长")["notes_here"]], [note_id])
        world.submit(Intention("班长", "read", {"item": note_id}, world.version))
        world.advance()
        self.assertEqual([event.payload["content"] for event in world.event_log
                          if event.kind == "document_read"
                          and event.actor == "班长"], [self.TEXT])
        self.assertIn(note_id, world.persistent_notes)

    def test_a_default_note_still_burns_after_its_first_reader(self):
        """② 反夹具：不带 persist 的字条保持 2026-09-22 裁定的语义（读后即焚）。"""
        world = load_story_pack().build_world()
        world.submit(Intention("陈默", "leave_note", {"text": "去后街找我。"},
                               world.version))
        events = world.advance()
        self.assertTrue([e for e in events if e.kind == "note_left"])
        self.assertEqual(world.persistent_notes, {}, "默认字条不是实体、没有编号")
        self.assertEqual([note["text"] for note in world.locations["男生宿舍"].notes],
                         ["去后街找我。"])
        world.submit(Intention("班长", "move", {"target": "男生宿舍"}, world.version))
        world.advance(until=world.now + timedelta(minutes=30))
        self.assertEqual(world.locations["男生宿舍"].notes, [], "默认字条被第一位非作者读者烧掉")
        self.assertTrue([e for e in world.event_log if e.kind == "note_read"])
        self.assertFalse([e for e in world.event_log if e.kind == "document_read"],
                         "默认字条不提供可寻址的 read 通道")

    def test_replay_rebuilds_the_same_persistent_note_id(self):
        """③ replay 用事件里的 id 与 text 重建同一张便条，仍可读。"""
        world = self._world_with_note()
        note_id = next(iter(world.persistent_notes))
        world.submit(Intention("陈默", "read", {"item": note_id}, world.version))
        world.advance()
        replayed = replay_world(load_story_pack().build_world(), world.replayable_log())
        self.assertEqual(replayed.persistent_notes.get(note_id, {}).get("text"), self.TEXT)
        self.assertEqual(replayed.locations["男生宿舍"].notes, [])
        replayed.submit(Intention("陈默", "read", {"item": note_id}, replayed.version))
        replayed.advance()
        self.assertTrue([e for e in replayed.event_log
                         if e.kind == "document_read"
                         and e.payload["document"] == note_id
                         and e.payload["content"] == self.TEXT])
        # 销毁也要可重建：trash 后的世界与 replay 后的世界都读不到了。
        world.submit(Intention("陈默", "trash", {"item": note_id}, world.version))
        world.advance()
        self.assertNotIn(note_id, world.persistent_notes)
        replayed_trash = replay_world(load_story_pack().build_world(),
                                      world.replayable_log())
        self.assertNotIn(note_id, replayed_trash.persistent_notes)

    def test_a_checkpoint_keeps_the_note_and_never_reuses_its_id(self):
        """检查点带着便条与编号计数器往返：恢复后新写的一张不会撞上旧编号。"""
        world = self._world_with_note()
        first = next(iter(world.persistent_notes))
        restored = World.from_checkpoint(load_story_pack().build_world(),
                                         world.checkpoint_state())
        self.assertIn(first, restored.persistent_notes)
        self.assertIn({"kind": "read", "item": first}, restored.affordances("陈默"))
        restored.submit(Intention("陈默", "leave_note",
                                  {"text": "第二张。", "persist": True}, restored.version))
        restored.advance()
        second = next(note_id for note_id in restored.persistent_notes if note_id != first)
        self.assertNotEqual(first, second, "恢复后不得复用已用过的便条编号")

    def test_an_old_checkpoint_without_notes_still_loads(self):
        """向后兼容：没有 persistent_notes/next_note_serial 的旧检查点照常加载。"""
        world = load_story_pack().build_world()
        state = world.checkpoint_state()
        state.pop("persistent_notes", None)
        state.pop("next_note_serial", None)
        restored = World.from_checkpoint(load_story_pack().build_world(), state)
        self.assertEqual(restored.persistent_notes, {})
        restored.submit(Intention("陈默", "leave_note",
                                  {"text": "旧检查点之后的第一张。", "persist": True},
                                  restored.version))
        restored.advance()
        self.assertEqual(len(restored.persistent_notes), 1)

    ARCHIVED_CHECKPOINT = (Path(__file__).parents[2] / "runs" / "archive-20261016-attempt1"
                           / "d1-am.json")

    @unittest.skipUnless(ARCHIVED_CHECKPOINT.is_file(), "归档检查点不在本工作树")
    def test_the_archived_d1_am_checkpoint_still_loads(self):
        """窗口 1 的旧检查点（v4-checkpoint-2）必须仍能恢复：本轮只做向后兼容增量。"""
        checkpoint = json.loads(self.ARCHIVED_CHECKPOINT.read_text(encoding="utf-8"))
        world = World.from_checkpoint(load_story_pack().build_world(), checkpoint["world"])
        self.assertEqual(world.now.isoformat(), "2026-03-16T12:59:00+08:00")
        self.assertEqual(len(world.event_log), 1535)
        self.assertEqual(world.persistent_notes, {}, "旧检查点没有持久便条")
        self.assertEqual(world._note_serial, 1)


class ExtraEmptyTurnGates(unittest.TestCase):
    """E90（报 86 §2，E86 覆盖不完整）：零动作的 extra 回合在 trace 里仍是空白行。

    窗口 2 的 `system_turns` 有 6 条 `empty_turn`（MC/NPC 全覆盖），但 trace 里
    `result: none` 的回合有 8 条：09:33 林大爷、14:13 陈师傅 的 `calls=[]` 与空
    `inner` 没有任何记录。`engine._execute_chain` 的 `empty_turn` 只在 MC/NPC 链
    路径上记；extra 走 `_extra_turn`，于是"零动作"与"没发生"在 trace 上不可分。
    修法只加诊断：extra 真正被问了（`needs_response`）却一个调用都没有时记一条
    `empty_turn`（role=extra、reason=no_output），世界不变、不惩罚角色。
    """

    def _run(self, replies):
        """一次 6 分钟的对话：陈默向路人搭话，路人按 replies 依次回答。"""
        world = load_story_pack().build_world()
        asked = set()

        def agent(state, perception, affordances):
            if state.actor_id == "陈默" and "ask" not in asked:
                asked.add("ask")
                return Intention(state.actor_id, "speak",
                                 {"text": "请问台账的事？", "volume": "normal",
                                  "to": ["陌生人"], "wait_response": False},
                                 perception["world_version"])
            return Intention(state.actor_id, "wait",
                             {"duration_seconds": 3600},
                             perception["world_version"])

        class _Stub:
            def __init__(self, rows):
                self.rows = list(rows)

            def chat_with_tools(self, messages, tools):
                row = self.rows.pop(0) if len(self.rows) > 1 else self.rows[0]
                return row

        non_extra = [actor for actor in world.actors if world.actors[actor].role != "extra"]
        trace = Trace("v4-test", "ticket88-extra-empty-turn")
        _call_pool().submit(lambda: None).result(timeout=5)
        engine = AsyncEngine(world, {a: agent for a in non_extra},
                             {a: PrivateState(a) for a in non_extra}, trace, None,
                             extra_call=_Stub(replies), decision_timeout=10,
                             max_wall_seconds=60, extra_idle_seconds=3600)
        engine.run(stop_at=world.now + timedelta(minutes=6), max_turns=300)
        return world, trace

    @staticmethod
    def _empty_turns(trace, actor):
        return [turn for turn in trace.system_turns
                if turn["request"].get("kind") == "empty_turn"
                and turn["result"].get("actor") == actor]

    def test_a_zero_action_extra_turn_is_recorded_with_its_reason(self):
        world, trace = self._run([{"role": "assistant", "content": "", "tool_calls": []}])
        extra = next(a for a in world.actors.values() if a.role == "extra")
        rows = self._empty_turns(trace, extra.id)
        self.assertTrue(rows, "零动作的 extra 回合必须留下可审计记录")
        self.assertEqual(rows[0]["result"]["role"], "extra")
        self.assertEqual(rows[0]["result"]["reason"], "no_output")
        self.assertEqual(rows[0]["result"]["private_chars"], 0)
        # 不改世界、不惩罚：路人什么也没说，世界照常结束。
        self.assertFalse([e for e in world.event_log
                          if e.kind == "speech" and e.actor == extra.id])

    def test_an_answering_extra_turn_is_not_an_empty_turn(self):
        """负向守卫：真的说了话的 extra 回合不是空回合。"""
        world, trace = self._run([{"role": "assistant", "content": "我听见了。",
                                   "tool_calls": []}])
        extra = next(a for a in world.actors.values() if a.role == "extra")
        self.assertTrue([e for e in world.event_log
                         if e.kind == "speech" and e.actor == extra.id])
        self.assertFalse(self._empty_turns(trace, extra.id))


class ExtraPoolAliasGates(unittest.TestCase):
    """E91（报 86 §3/§6，窗口 2 15:00）：点名的角色被随机姓名替换。

    后街糕点铺的池条目是"后街糕点铺的老板娘"，但 `_spawn_extra` 用
    `generate_stranger_name()` 取名，于是 13:14 生成的是李师傅、15:09 是王学长；
    唐小岚两次到场都在问"李师傅或店里负责人现在在吗"，她要找的"老板娘"从未出现，
    15:12 只能靠"反正有人听见了"结案。修法是一处泛化：池条目可声明
    `aliases:`；角色用该别名 `speak(to=[...])` 时按同一条搭话通道优先取该条目，
    别名成为它的名字（被别人占用时才退回随机名，并把别名写进身份描写），
    未点名时仍走既有随机取样；生命周期机制（idle despawn / E84 落物）不变。
    """

    ENTRY = {"fragment": "后街糕点铺的老板娘", "rarity": "common",
             "aliases": ["老板娘"], "weight": 1,
             "knowledge_notes": "熟客都认得我。"}
    OTHER = {"fragment": "铺子里的伙计", "rarity": "common", "weight": 1,
             "knowledge_notes": "我只管揉面。"}

    def _run(self, addressed, entries):
        world = World(start=datetime.fromisoformat("2026-03-16T15:00:00+08:00"),
                      actors=[ActorState("唐小岚", "后街糕点铺")],
                      locations=[LocationState("后街糕点铺", extras=tuple(entries))])
        asked = set()

        def agent(state, perception, affordances):
            if state.actor_id == "唐小岚" and "ask" not in asked:
                asked.add("ask")
                spoken = ["老板娘"] if addressed == "alias" else ["陌生人"]
                return Intention(state.actor_id, "speak",
                                 {"text": "稿子的事老板娘说，别再往吧台上放。",
                                  "volume": "normal", "to": spoken,
                                  "wait_response": False},
                                 perception["world_version"])
            return Intention(state.actor_id, "wait",
                             {"duration_seconds": 3600},
                             perception["world_version"])

        class _PromptRecordingStub:
            def __init__(self):
                self.prompts = []

            def chat_with_tools(self, messages, tools):
                self.prompts.append(str(messages[0]["content"]))
                return {"role": "assistant", "content": "在的，你找谁？",
                        "tool_calls": []}

        trace = Trace("v4-test", "ticket88-pool-alias")
        stub = _PromptRecordingStub()
        _call_pool().submit(lambda: None).result(timeout=5)
        engine = AsyncEngine(world, {"唐小岚": agent},
                             {"唐小岚": PrivateState("唐小岚")}, trace, None,
                             extra_call=stub, decision_timeout=10,
                             max_wall_seconds=60, extra_idle_seconds=3600)
        engine.run(stop_at=world.now + timedelta(minutes=6), max_turns=200)
        return world, stub

    def test_naming_a_pool_alias_spawns_that_entry_under_that_name(self):
        world, stub = self._run("alias", [self.ENTRY, self.OTHER])
        arrives = [e for e in world.event_log if e.kind == "extra_arrived"]
        self.assertEqual(len(arrives), 1)
        self.assertEqual(arrives[0].actor, "老板娘", "点名的别名就是这个角色的名字")
        self.assertEqual(arrives[0].payload.get("location"), "后街糕点铺")
        self.assertTrue(stub.prompts, "路人必须真的被问过")
        self.assertIn("后街糕点铺的老板娘", stub.prompts[0], "生成的正是那条池条目")
        self.assertNotIn("铺子里的伙计", stub.prompts[0], "不能退化成随机抽到的另一条")
        asked = [e for e in world.event_log if e.kind == "stranger_asked"]
        self.assertEqual(asked[0].payload.get("alias"), "老板娘")
        self.assertIn("老板娘", [str(name) for name in
                                 next(e for e in world.event_log
                                      if e.kind == "speech").payload.get("to", [])])

    def test_an_unnamed_ask_still_samples_the_pool(self):
        """未点名时不改变既有行为：随机名 + 池条目，别名不生效。"""
        world, stub = self._run("stranger", [self.ENTRY, self.OTHER])
        arrives = [e for e in world.event_log if e.kind == "extra_arrived"]
        self.assertEqual(len(arrives), 1)
        self.assertNotEqual(arrives[0].actor, "老板娘")
        self.assertTrue(stub.prompts)
        self.assertNotIn("人称「老板娘」", stub.prompts[0])
        asked = [e for e in world.event_log if e.kind == "stranger_asked"]
        self.assertNotIn("alias", asked[0].payload)


class _DialogueChainAgent:
    """`_execute_chain` 的会话桩（E92/E93）：记下引擎交回的工具结果与自纠。

    只用引擎真正会问的那几个接缝：`session_obj`（自纠通道）与
    `deliver_tool_results`（执行回执）。`_execute_chain` 是 `_take_turn` 走的那
    条链路径，所以这里测的就是生产路径，不是旁路。
    """

    def __init__(self):
        self.results = []
        self.notes = []
        self.session_obj = self

    def deliver_tool_results(self, results):
        self.results.extend(dict(result) for result in results)

    def note_no_action(self, streak=1):
        self.notes.append(f"no_action:{streak}")

    def note_unspoken_content(self):
        self.notes.append("unspoken")

    def note_private_content(self):
        self.notes.append("private")

    def consume_compaction(self):
        return False

    def session_snapshot(self):
        return None


def _dialogue_engine(world, *, system=None, agent=None):
    """一个不跑事件循环的引擎：只用来逐回合调 `_execute_chain`。"""
    agent = agent or _DialogueChainAgent()
    engine = AsyncEngine(world, {actor: agent for actor in world.actors},
                         {actor: PrivateState(actor) for actor in world.actors},
                         Trace("v4-test", "chain"), system,
                         decision_timeout=10, max_wall_seconds=30)
    engine._scheduler_wake = threading.Event()
    engine._stop_horizon = None
    return engine, agent


def _dialogue_turn(engine, world, actor, calls, *, text=""):
    """跑一个回合（= `_take_turn` 的执行半步），并把时钟推到动作完成。"""
    perception = world.poll(actor)
    engine._execute_chain(actor, list(calls), perception,
                          world.affordances(actor), world.version,
                          content_private=text or None)
    busy = world.actors[actor].busy_until
    if busy is not None and busy > world.now:
        world.advance(until=busy)


class LedgerDialogueGates(unittest.TestCase):
    """E92（报 90 §1，窗口 3 09:02）：台账在对话里够不着它。

    窗口 3 全段的 `system_answer` 是 0：陈默把台账当人说话
    （`speak(to=["2013年台风台账"])`）被内核判成"未知收件人"，而 v4 的动作面既
    没有 `ask` 也没有 `system_query`——`Ledger.affordances()` 按工单 14 返回 `[]`，
    文档 §5 却写着"它是世界内对话者……所有交互走对话"。修法不是新增动作种类：
    `speak` 的收件人解析扩展到一个已接受案件的 System 对话者——受约束角色点名它的
    名字（种子 `system.name`）时，引擎走既有的 fact table 应答通道，答案以既有
    `system_answer` 私有事件只投递给这个人。约束照旧：只答事实表内的条目（答不了
    就说不知道），查询次数硬上限（用尽只回“闭口”）；未受约束的角色点名它不被应答。
    **结案不在这里**（票 93：命中即结案是旧语义，结案现由种子排程的结算节拍驱动，
    见 `LedgerClosureGates`）。
    """

    QUESTION = "红色哨子在哪里？"
    OUTSIDE = "今天的课表在哪间教室？"

    def _ask(self, text, who="台账"):
        return {"name": "speak", "tool_call_id": "speak-1",
                "arguments": {"text": text, "volume": "normal", "to": [who],
                              "wait_response": False}}

    def _world(self):
        pack = load_story_pack()
        world = pack.build_world()
        ledger = Ledger(pack.system.get("facts", {}), pack.system)
        return pack, world, ledger

    @staticmethod
    def _answers(world):
        return [event for event in world.event_log if event.kind == "system_answer"]

    def test_the_bound_character_gets_a_fact_table_answer_by_naming_the_ledger(self):
        from harness.prompt import render_world_message
        pack, world, ledger = self._world()
        expected = ledger.facts[self.QUESTION]
        engine, agent = _dialogue_engine(world, system=ledger)
        _dialogue_turn(engine, world, "陈默", [self._ask(self.QUESTION)])

        answers = self._answers(world)
        self.assertEqual(len(answers), 1, "点名台账必须得到一次既有 system_answer")
        self.assertEqual(answers[0].payload["answer"], expected)
        self.assertEqual(answers[0].visible_to, frozenset({"陈默"}),
                         "答案只投递给受约束角色")
        self.assertFalse([e for e in world.event_log if e.kind == "speech"],
                         "对台账说的话不进公开 speech（那不是对在场的人说的）")
        self.assertEqual(ledger.queries_used, 1)
        self.assertEqual(len(agent.results), 1, agent.results)
        self.assertTrue(agent.results[0]["ok"])
        self.assertIn("台账", agent.results[0]["text"])
        # 答案经既有私有事件进了他自己的知觉，别人一条都收不到。
        mine = render_world_message(world.poll("陈默"))
        self.assertIn(expected, mine)
        self.assertFalse([e for e in world.poll("林瑶")["events"]
                          if str(e.get("kind", "")).startswith("system_")])

    def test_a_question_outside_the_fact_table_gets_the_ledger_s_dont_know(self):
        _, world, ledger = self._world()
        engine, agent = _dialogue_engine(world, system=ledger)
        _dialogue_turn(engine, world, "陈默", [self._ask(self.OUTSIDE)])
        self.assertFalse(self._answers(world), "答不了就不答，不编一条答案出来")
        self.assertEqual(ledger.queries_used, 0, "答不了的问题不吞查询额度")
        reply = agent.results[0]
        self.assertTrue(reply["ok"], "话送到了：这是一次对话，不是格式错误")
        self.assertIn("不知道", reply["text"])
        self.assertNotIn("speech", {event.kind for event in world.event_log})

    def test_a_used_up_ledger_stops_answering_instead_of_answering_again(self):
        _, world, ledger = self._world()
        engine, agent = _dialogue_engine(world, system=ledger)
        _dialogue_turn(engine, world, "陈默", [self._ask(self.QUESTION)])
        _dialogue_turn(engine, world, "陈默", [self._ask(self.QUESTION)])
        self.assertEqual(len(self._answers(world)), 1, "同一条目不会答第二遍")
        self.assertEqual(ledger.queries_used, 1)
        self.assertIn("闭口", agent.results[1]["text"], agent.results[1]["text"])

    def test_the_query_limit_silences_the_ledger_without_closing_the_case(self):
        """票 93：`query_limit: 0` = 一次也不答，但**不结案**（结案由结算节拍驱动）。

        票 95（E95）：拒绝也留一条只给提问者的 `system_dialogue` 审计事件（不编造
        答案）；它不是 `system_answer`，也不消耗额度。
        """
        world = World(start=datetime.fromisoformat("2026-03-16T09:00:00+08:00"),
                      actors=[ActorState("陈默", "room")], locations=[LocationState("room")])
        ledger = Ledger({"known": "answer"}, {"name": "台账", "bound_actor": "陈默",
                                             "query_limit": 0})
        ledger.auto_accept(world)
        reply, events = ledger.converse(world, "陈默", "known")
        self.assertEqual([event.kind for event in events], ["system_dialogue"])
        self.assertFalse(events[0].payload["matched"])
        self.assertEqual(events[0].payload["outcome"], "limit")
        self.assertNotIn("answer_event_id", events[0].payload)
        self.assertEqual(events[0].visible_to, frozenset({"陈默"}))
        self.assertEqual(reply, DIALOGUE_REPLIES["limit"].format(name=ledger.name))
        self.assertEqual(ledger.status, "accepted", "额度用尽不是结案")

    def test_an_unbound_character_naming_the_ledger_is_not_answered_by_it(self):
        _, world, ledger = self._world()
        engine, agent = _dialogue_engine(world, system=ledger)
        _dialogue_turn(engine, world, "林瑶", [self._ask(self.QUESTION)])
        self.assertFalse(self._answers(world), "台账只对受约束角色应声")
        self.assertEqual(ledger.queries_used, 0)
        reply = agent.results[0]
        self.assertFalse(reply["ok"], "未受约束者的点名照旧是未知收件人拒绝")
        self.assertIn("unknown or ambiguous speak recipient", reply["text"])
        self.assertNotIn("台账是世界内的对话者", reply["text"],
                         "不向未受约束的角色解释台账这条通道")

    def test_a_line_naming_the_ledger_and_others_is_not_dropped_silently(self):
        """同一句里既点台账又点人：话只对台账说了，回执必须说出这件事。

        不静默丢收件人是票 46 的既有契约；台账这条通道不产生 speech 事件，所以
        只在 tool 结果里交代清楚，并给出重发的写法。
        """
        _, world, ledger = self._world()
        engine, agent = _dialogue_engine(world, system=ledger)
        call = self._ask(self.QUESTION)
        call["arguments"]["to"] = ["台账", "林瑶"]
        _dialogue_turn(engine, world, "陈默", [call])
        self.assertEqual(len(self._answers(world)), 1)
        self.assertFalse([e for e in world.event_log if e.kind == "speech"])
        reply = agent.results[0]
        self.assertTrue(reply["ok"])
        self.assertIn("同场的人没有听到", reply["text"])
        self.assertIn("林瑶", reply["text"])

    def test_a_busy_actor_cannot_address_the_ledger_mid_action(self):
        """忙态照旧：一个回合只应有一个耗时动作，回执写明完成时刻。"""
        _, world, ledger = self._world()
        engine, agent = _dialogue_engine(world, system=ledger)
        world.submit(Intention("陈默", "wait", {"duration_seconds": 120}, world.version))
        now = world.now.isoformat()
        engine._execute_chain("陈默", [self._ask(self.QUESTION)],
                              {"time": now, "events": []},
                              world.affordances("陈默"), world.version)
        self.assertFalse(self._answers(world), "忙态下这句话没有送到台账")
        self.assertFalse(agent.results[0]["ok"])
        self.assertIn("not executed", agent.results[0]["text"])
        self.assertIn("下一回合", agent.results[0]["text"])

    def test_a_misnamed_attempt_gets_the_ledger_s_real_address_back(self):
        """09:02 的原样：陈默把台账叫成"2013年台风台账"（档案室里那份纸的名字）。

        拒绝照旧（不能悄悄改收件人），但回执要说明台账就在对话里、该用哪个名字。
        """
        _, world, ledger = self._world()
        engine, agent = _dialogue_engine(world, system=ledger)
        _dialogue_turn(engine, world, "陈默", [self._ask(
            "这是2013年台风后用于确认邻里撤离与互助事项的通知书。",
            who="2013年台风台账")])
        self.assertFalse(self._answers(world))
        self.assertEqual(ledger.queries_used, 0)
        reply = agent.results[0]
        self.assertFalse(reply["ok"])
        self.assertIn("台账是世界内的对话者", reply["text"])
        self.assertIn('to=["台账"]', reply["text"])


class LedgerClosureGates(unittest.TestCase):
    """E94（票 91 §4-2，用户裁定 2026-10-18）：结案 ≠ 首次命中。

    旧语义下 `Ledger.query` 一命中就把 `status` 置成 `completed` 并发报酬，于是
    `query_limit > 1` 的种子实际只答一次，`limit` 分支在正常流程下不可达；而文档
    （`V4-AGENT-INTERFACE.md` §5）写的是“查询次数硬上限”、`V4-STORY-MILESTONES.md`
    把结算排到 d7/d12。裁定：**结案由种子排程的结算事件驱动**（既有
    `system_reward_granted` 私有路径），首次命中只给答案；额度按既有上限递减，
    超限只回“闭口”、不消耗、也不结案。

    红绿：① 连续两次命中都得到答案且都产生 `system_answer`；② 超限后闭口而案子
    仍未结；③ 结算节拍到达后才 `closed`（真种子冒烟一起钉在这里）。
    """

    FACTS = {"红色哨子在哪里？": "老家属院的地下室",
             "当前记录的期限是什么？": "学生会审计核对，2026-03-16T16:00:00+08:00"}
    SETTLE_AT = "2026-03-16T09:00:00+08:00"

    @staticmethod
    def _ask(text):
        return {"name": "speak", "tool_call_id": "speak-1",
                "arguments": {"text": text, "volume": "normal", "to": ["台账"],
                              "wait_response": False}}

    def _setup(self, *, beat="ledger_settlement"):
        world = World(start=datetime.fromisoformat("2026-03-16T08:00:00+08:00"),
                      actors=[ActorState("陈默", "room"), ActorState("林瑶", "room")],
                      locations=[LocationState("room")],
                      scheduled=[{"event": beat, "time": self.SETTLE_AT,
                                  "target": "陈默", "notice": "那边静了一瞬。"}])
        ledger = Ledger(self.FACTS, {"name": "台账", "bound_actor": "陈默",
                                    "query_limit": 2, "settle_on": "ledger_settlement"})
        ledger.auto_accept(world)
        engine, agent = _dialogue_engine(world, system=ledger)
        return world, ledger, engine, agent

    @staticmethod
    def _kinds(world, kind):
        return [event for event in world.event_log if event.kind == kind]

    def test_two_hits_in_a_row_each_produce_an_answer_and_the_case_stays_open(self):
        world, ledger, engine, agent = self._setup()
        _dialogue_turn(engine, world, "陈默", [self._ask("红色哨子在哪里？")])
        _dialogue_turn(engine, world, "陈默", [self._ask("当前记录的期限是什么？")])
        answers = self._kinds(world, "system_answer")
        self.assertEqual([event.payload["answer"] for event in answers],
                         [self.FACTS["红色哨子在哪里？"],
                          self.FACTS["当前记录的期限是什么？"]],
                         "两次命中都得到答案（不是答一次就闭口）")
        self.assertEqual(ledger.queries_used, 2)
        self.assertEqual(ledger.status, "accepted", "命中不结案")
        self.assertFalse(self._kinds(world, "system_reward_granted"),
                         "报酬不在命中时发")
        self.assertTrue(all(result["ok"] for result in agent.results), agent.results)

    def test_after_the_limit_the_ledger_silences_without_closing_the_case(self):
        world, ledger, engine, agent = self._setup()
        for question in ("红色哨子在哪里？", "当前记录的期限是什么？", "红色哨子在哪里？"):
            _dialogue_turn(engine, world, "陈默", [self._ask(question)])
        self.assertEqual(len(self._kinds(world, "system_answer")), 2)
        self.assertTrue(agent.results[1]["ok"], "额度内的第二问照样得到答案")
        reply = agent.results[2]["text"]
        self.assertIn("用尽", reply, "超限是“额度用尽”，不是“案子了结”")
        self.assertNotIn("已经了结", reply)
        self.assertEqual(ledger.queries_used, 2, "闭口不再消耗额度")
        self.assertEqual(ledger.status, "accepted", "超限不结案")
        self.assertFalse(self._kinds(world, "system_reward_granted"))

    def test_the_seeded_settlement_beat_closes_the_case(self):
        world, ledger, engine, agent = self._setup()
        _dialogue_turn(engine, world, "陈默", [self._ask("红色哨子在哪里？")])
        answer = self._kinds(world, "system_answer")[-1]
        self.assertEqual(ledger.status, "accepted")
        world.advance(until=datetime.fromisoformat(self.SETTLE_AT))
        engine._after_advance()
        self.assertEqual(ledger.status, "closed", "种子结算节拍到达才结案")
        rewards = self._kinds(world, "system_reward_granted")
        self.assertEqual(len(rewards), 1, "结算只发一次")
        self.assertEqual(rewards[0].visible_to, frozenset({"陈默"}), "报酬只投给受约束角色")
        self.assertEqual(rewards[0].payload["evidence_event_id"], answer.id)
        self.assertTrue(ledger.reward_granted)
        _dialogue_turn(engine, world, "陈默", [self._ask("当前记录的期限是什么？")])
        self.assertIn("已经了结", agent.results[-1]["text"], "结案之后才是“闭口”")
        self.assertEqual(len(self._kinds(world, "system_answer")), 1,
                         "结案后的提问不再产生答案")

    def test_a_world_beat_that_is_not_the_settlement_keeps_the_case_open(self):
        """负向守卫：只认 `system.settle_on` 点名的那条，不是“任何世界事件”。"""
        world, ledger, engine, _agent = self._setup(beat="morning_bell")
        _dialogue_turn(engine, world, "陈默", [self._ask("红色哨子在哪里？")])
        world.advance(until=datetime.fromisoformat(self.SETTLE_AT))
        engine._after_advance()
        self.assertEqual(ledger.status, "accepted")
        self.assertFalse(self._kinds(world, "system_reward_granted"))

    def test_the_real_seed_schedules_the_settlement_and_it_closes_the_case(self):
        """真种子冒烟（用户裁定要求）：排程里确有其事，到点才结案，报酬只给陈默。"""
        pack = load_story_pack()
        settle_on = pack.system.get("settle_on")
        self.assertEqual(settle_on, "ledger_settlement")
        rows = [row for row in pack.scheduled if row.get("event") == settle_on]
        self.assertEqual(len(rows), 1, "种子排程里有且只有一条结算节拍")
        self.assertEqual(rows[0]["time"], "2026-03-22T15:00:00+08:00",
                         "d7 15:00（V4-STORY-MILESTONES §3“d7-台账结算”）")
        world = pack.build_world()
        ledger = Ledger(pack.system.get("facts", {}), pack.system)
        engine, _agent = _dialogue_engine(world, system=ledger)
        question = "红色哨子在哪里？"
        _dialogue_turn(engine, world, "陈默", [self._ask(question)])
        self.assertEqual(len(self._kinds(world, "system_answer")), 1)
        self.assertEqual(ledger.status, "accepted", "D1 答对了也不结案")
        world.advance(until=datetime.fromisoformat(rows[0]["time"]))
        engine._after_advance()
        self.assertEqual(ledger.status, "closed")
        rewards = self._kinds(world, "system_reward_granted")
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards[0].visible_to, frozenset({"陈默"}))
        self.assertEqual(rewards[0].payload["reward"], pack.system["reward"])
        for actor in world.actors:
            if actor == "陈默":
                continue
            self.assertFalse([event for event in world.poll(actor)["events"]
                              if str(event.get("kind", "")).startswith("system_")],
                             f"{actor} 不该听见台账的任何一笔")


class LedgerFactMatchingGates(unittest.TestCase):
    """E95（报 94 §1，窗口 4 07:00–09:10）：台账事实表不可猜、拒绝零痕迹。

    窗口 4 陈默 5 次用 `speak(to=["台账"])` 提问，全部 `submitted`，`system_answer`
    仍是 0：`Ledger.query` 用 `facts.get(question.strip())` 逐字匹配，而他从没见过
    那三句原始问句，只能按 terms 泛问；这 5 次拒绝在世界日志里也一条痕迹都没有。

    修法（不新增动作、不引入模型判定）：事实条目可声明 `keywords`（缺省回落到
    条目问句本身）；问句归一化（全角/半角、空白、标点）后按关键词命中数打分，
    唯一最高分即答，并列或零分答“不知道”；每次对话（命中或拒绝）都在世界日志留
    一条只给提问者的 `system_dialogue` 私有事件（提问原文、matched、outcome、
    答案事件 id），仍然不产生公开 `speech`。
    """

    FACTS = {
        "2013年邻里撤离通知书的责任人是谁？": {
            "answer": "当年在许可证上签名的那个人",
            "keywords": ["邻里撤离通知书", "撤离通知书", "责任人", "谁签的字"],
        },
        "当前记录的期限是什么？": {
            "answer": "学生会审计核对，2026-03-16T16:00:00+08:00",
            "keywords": ["期限", "最迟什么时候"],
        },
    }

    def _setup(self):
        world = World(start=datetime.fromisoformat("2026-03-16T09:00:00+08:00"),
                      actors=[ActorState("陈默", "room"), ActorState("林瑶", "room")],
                      locations=[LocationState("room")])
        ledger = Ledger(self.FACTS, {"name": "台账", "bound_actor": "陈默",
                                    "query_limit": 3})
        ledger.auto_accept(world)
        engine, agent = _dialogue_engine(world, system=ledger)
        return world, ledger, engine, agent

    @staticmethod
    def _ask(text, who="台账"):
        return {"name": "speak", "tool_call_id": "speak-1",
                "arguments": {"text": text, "volume": "normal", "to": [who],
                              "wait_response": False}}

    @staticmethod
    def _kinds(world, kind):
        return [event for event in world.event_log if event.kind == kind]

    def test_a_natural_question_hits_by_keywords(self):
        """窗口 4 09:10 的原话（一段长问句里带着“责任人”）不再 miss。"""
        world, ledger, engine, agent = self._setup()
        _dialogue_turn(engine, world, "陈默", [self._ask(
            "台账，你案卷里关于《2013年台风台账》两台抽水泵外借时间从纸本22:05"
            "变成导出件23:30这条记录，记载的经手责任人是谁？")])
        answers = self._kinds(world, "system_answer")
        self.assertEqual(len(answers), 1, agent.results)
        self.assertEqual(answers[0].payload["answer"],
                         self.FACTS["2013年邻里撤离通知书的责任人是谁？"]["answer"])
        self.assertEqual(ledger.queries_used, 1)
        self.assertTrue(agent.results[0]["ok"])
        self.assertFalse([e for e in world.event_log if e.kind == "speech"])

    def test_a_question_with_no_keyword_gets_dont_know_and_a_private_audit(self):
        world, ledger, engine, agent = self._setup()
        _dialogue_turn(engine, world, "陈默", [self._ask("今天天气如何？")])
        self.assertFalse(self._kinds(world, "system_answer"), "零分不编答案")
        self.assertEqual(ledger.queries_used, 0, "答不上不吞额度")
        self.assertIn("不知道", agent.results[0]["text"])
        audits = self._kinds(world, "system_dialogue")
        self.assertEqual(len(audits), 1, "拒绝也要在世界日志里留痕")
        self.assertEqual(audits[0].payload["question"], "今天天气如何？")
        self.assertFalse(audits[0].payload["matched"])
        self.assertEqual(audits[0].payload["outcome"], "unknown")
        self.assertNotIn("answer_event_id", audits[0].payload)
        self.assertEqual(audits[0].visible_to, frozenset({"陈默"}))
        self.assertFalse([e for e in world.event_log if e.kind == "speech"])

    def test_a_tie_between_two_entries_gets_dont_know(self):
        """窗口 4 07:00 原话：一句里同时问“责任人”与“期限”→ 并列 → 不知道。"""
        world, ledger, engine, agent = self._setup()
        _dialogue_turn(engine, world, "陈默", [self._ask(
            "台账，关于我接下的案子，请告诉我：这案子是什么、责任人是谁、期限是什么？")])
        self.assertFalse(self._kinds(world, "system_answer"))
        self.assertEqual(ledger.queries_used, 0)
        audit = self._kinds(world, "system_dialogue")[0]
        self.assertEqual(audit.payload["outcome"], "tie")
        self.assertFalse(audit.payload["matched"])
        self.assertIn("不知道", agent.results[0]["text"])

    def test_every_dialogue_leaves_one_private_audit_with_the_answer_event_id(self):
        world, ledger, engine, agent = self._setup()
        _dialogue_turn(engine, world, "陈默", [self._ask(
            "台账，你记着的《2013年台风台账》的借出记录里，责任人是谁？")])
        _dialogue_turn(engine, world, "陈默", [self._ask("今天天气如何？")])
        answers = self._kinds(world, "system_answer")
        audits = self._kinds(world, "system_dialogue")
        self.assertEqual(len(answers), 1)
        self.assertEqual(len(audits), 2, "每次对话恰一条审计事件")
        hit, miss = audits
        self.assertTrue(hit.payload["matched"])
        self.assertEqual(hit.payload["answer_event_id"], answers[0].id)
        self.assertEqual(hit.payload["question"],
                         "台账，你记着的《2013年台风台账》的借出记录里，责任人是谁？")
        self.assertFalse(miss.payload["matched"])
        self.assertEqual({event.visible_to for event in audits}, {frozenset({"陈默"})},
                         "审计只给提问者")
        self.assertFalse([e for e in world.event_log if e.kind == "speech"])
        # 审计不是角色能“听见”的一句话，也不进别人的知觉。
        self.assertFalse([event for event in world.poll("林瑶")["events"]
                          if str(event.get("kind", "")).startswith("system_")])
        from harness.prompt import render_world_message
        rendered = render_world_message(world.poll("陈默"))
        self.assertNotIn("system_dialogue", rendered)
        self.assertNotIn("记下了这一笔", rendered)

    def test_an_entry_without_keywords_still_answers_its_own_question(self):
        """缺省回落：不写 keywords 的旧条目，逐字（归一化后）问仍然命中。"""
        world = World(start=datetime.fromisoformat("2026-03-16T09:00:00+08:00"),
                      actors=[ActorState("陈默", "room")], locations=[LocationState("room")])
        ledger = Ledger({"红色哨子在哪里？": "老家属院的地下室"},
                        {"name": "台账", "bound_actor": "陈默", "query_limit": 2})
        ledger.auto_accept(world)
        engine, agent = _dialogue_engine(world, system=ledger)
        _dialogue_turn(engine, world, "陈默", [self._ask("红色哨子在哪里？")])
        self.assertEqual([event.payload["answer"] for event in self._kinds(world, "system_answer")],
                         ["老家属院的地下室"])

    def test_the_real_seed_answers_five_natural_questions_with_plain_text(self):
        """真种子冒烟（票 95）：keywords 在加载后仍然生效，答案不是 dict 字面量。"""
        pack = load_story_pack()
        facts = pack.system.get("facts") or {}
        def answer_of(key):
            value = facts[key]
            return value["answer"] if isinstance(value, dict) else value
        cases = [
            ("台账，那只红色哨子在哪里？", answer_of("红色哨子在哪里？")),
            ("台账，老家属院的地下室里放着什么？", answer_of("红色哨子在哪里？")),
            ("台账，2013年邻里撤离通知书的责任人是谁？",
             answer_of("2013年邻里撤离通知书的责任人是谁？")),
            ("台账，当年是谁签的字？", answer_of("2013年邻里撤离通知书的责任人是谁？")),
            ("台账，学生会审计核对到什么时候截止？",
             answer_of("学生会审计核对的期限是什么？")),
        ]
        world = pack.build_world()
        ledger = Ledger(facts, {**pack.system, "query_limit": 99})
        ledger.auto_accept(world)
        engine, agent = _dialogue_engine(world, system=ledger)
        for question, _ in cases:
            _dialogue_turn(engine, world, "陈默", [self._ask(question)])
        answers = [event.payload["answer"] for event in self._kinds(world, "system_answer")]
        self.assertEqual(answers, [expected for _, expected in cases])
        for answer in answers:
            self.assertIsInstance(answer, str)
            self.assertNotIn("{'", answer, "答案不能是 Python dict 字面量")
            self.assertNotIn("keywords", answer)
        self.assertEqual(ledger.queries_used, len(cases))
        for question in ("今天天气如何？", "食堂中午有什么饭？", "教学楼三楼怎么走？"):
            _dialogue_turn(engine, world, "陈默", [self._ask(question)])
            self.assertEqual(self._kinds(world, "system_dialogue")[-1].payload["outcome"],
                             "unknown", question)
        self.assertEqual(len(self._kinds(world, "system_answer")), len(cases),
                         "表外问题不编造答案")
        self.assertEqual(ledger.queries_used, len(cases), "表外问题不吞额度")


class EscortMoveGates(unittest.TestCase):
    """E96（报 94 §4，窗口 4 10:00–16:51）：没有“带某人一起走”的原语。

    世界里有视障角色要被人扶着走到教室，`move` 只能自己走，305 又不是地点，
    于是 6 小时 51 分里 17 个角色重复“我不能实际扶你”。修法不新增动作种类：
    `move` 增加可选 `with: [...]`，发起者与被携带者同处一地且未被锁死时，
    按发起者的路线逐跳共同移动，每位被携带者产生自己的 `leave`/`enter`；
    被携带者仍保有感知与自主（不替他行动）。若其当前动作不可打断，整次 move
    结构化拒绝并说明是哪一个人、为什么。
    """

    START = "2026-03-16T09:00:00+08:00"

    def _world(self):
        return World(start=datetime.fromisoformat(self.START),
                     actors=[ActorState("陈默", "平台"), ActorState("小满", "平台"),
                             ActorState("路人", "平台")],
                     locations=[LocationState("平台"), LocationState("走廊"),
                                LocationState("教室")],
                     routes={("平台", "走廊"): 120, ("走廊", "教室"): 180})

    @staticmethod
    def _moves(world):
        return [(event.kind, event.actor, str(event.payload.get("location")))
                for event in world.event_log if event.kind in {"leave", "enter"}]

    def test_two_people_arrive_together_with_one_synchronised_sequence(self):
        world = self._world()
        world.submit(Intention("陈默", "move", {"target": "教室", "with": ["小满"]},
                               world.version))
        world.advance()
        self.assertEqual(world.actors["陈默"].location, "教室")
        self.assertEqual(world.actors["小满"].location, "教室", "被携带者一起到了")
        self.assertEqual(world.actors["路人"].location, "平台", "没被带上的人留在原地")
        self.assertEqual(self._moves(world), [
            ("leave", "陈默", "平台"), ("leave", "小满", "平台"),
            ("enter", "陈默", "走廊"), ("leave", "陈默", "走廊"),
            ("enter", "小满", "走廊"), ("leave", "小满", "走廊"),
            ("enter", "陈默", "教室"), ("enter", "小满", "教室"),
        ])
        verify_event_log(world.replayable_log())
        versions = [event.world_version for event in world.event_log]
        self.assertEqual(versions, list(range(1, len(world.event_log) + 1)),
                         "共同移动的每条事件都占一个连续的 world version")
        # 被携带者没有自己的动作事件：走路是发起者的事，他只被带着移动。
        self.assertFalse([event for event in world.event_log
                          if event.actor == "小满" and event.kind == "action_started"])

    def test_a_companion_locked_in_an_uninterruptable_action_rejects_the_move(self):
        world = self._world()
        world.submit(Intention("小满", "wait", {"duration_seconds": 600}, world.version,
                               uninterruptable=True))
        before = len(world.event_log)
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("陈默", "move", {"target": "教室", "with": ["小满"]},
                                   world.version))
        self.assertIn("小满", str(rejected.exception))
        self.assertIn("不能被打断", str(rejected.exception))
        self.assertEqual(rejected.exception.context.get("with"), "小满")
        self.assertEqual(len(world.event_log), before, "整次 move 没有开始")
        self.assertEqual(world.actors["陈默"].location, "平台")

    def test_replay_after_an_escort_keeps_everyone_in_the_same_place(self):
        world = self._world()
        world.submit(Intention("陈默", "move", {"target": "教室", "with": ["小满"]},
                               world.version))
        world.advance()
        replayed = replay_world(self._world(), world.replayable_log())
        self.assertEqual(replayed.actors["陈默"].location, "教室")
        self.assertEqual(replayed.actors["小满"].location, "教室")
        self.assertEqual(replayed.actors["路人"].location, "平台")

    def test_a_companion_who_is_not_here_is_rejected(self):
        world = self._world()
        world.actors["小满"].location = "教室"
        world.actors["陈默"].known_contacts.add("小满")  # 名字能解析，人不在身边
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("陈默", "move", {"target": "教室", "with": ["小满"]},
                                   world.version))
        self.assertIn("不在这里", str(rejected.exception))


class WorldEventScopeGates(unittest.TestCase):
    """E97（报 94 §2，窗口 4 16:00/16:20/16:45）：无 target 的 world_event 全场广播。

    `_visibility` 对 actor is None 的 `world_event` 返回 `set(self.actors)`，于是
    排程事件连正文一起广播全场：陈默整天在档案室，却在 16:02 引用了 16:05 才定向
    告诉他的原话，16:22 又“刚获知”学生会办公室长桌上的审计包。修法：`world_event`
    payload 支持可选 `location`——有它时可见性 = 该地点在场者 +（若有）target；
    无 location 且无 target 的仍是既有全局广播（校园公告、铃声、天气）。
    """

    EVENT = {"event": "audit_pack_review", "time": "2026-03-16T16:20:00+08:00",
             "notice": "长桌上摊开了审计包和一张还空着的面核记录。"}

    def _world(self, **extra):
        return World(start=datetime.fromisoformat("2026-03-16T16:00:00+08:00"),
                     actors=[ActorState("班长", "办公室"), ActorState("陈默", "档案室"),
                             ActorState("唐小岚", "咖啡馆")],
                     locations=[LocationState("办公室"), LocationState("档案室"),
                                LocationState("咖啡馆")],
                     scheduled=[{**self.EVENT, **extra}])

    @staticmethod
    def _event(world):
        return next(event for event in world.event_log if event.kind == "world_event")

    def test_a_location_scopes_the_audience_instead_of_broadcasting(self):
        global_world = self._world()
        global_world.advance()
        self.assertEqual(self._event(global_world).visible_to,
                         frozenset({"班长", "陈默", "唐小岚"}),
                         "既没有 location 也没有 target = 既有全局广播")
        scoped = self._world(location="办公室")
        scoped.advance()
        self.assertEqual(self._event(scoped).visible_to, frozenset({"班长"}),
                         "只有当时在该地点的人看得见")

    def test_a_location_scoped_event_still_reaches_its_explicit_target(self):
        world = self._world(location="办公室", target="陈默")
        world.advance()
        self.assertEqual(self._event(world).visible_to, frozenset({"班长", "陈默"}))

    def test_replay_preserves_the_scoped_audience(self):
        world = self._world(location="办公室")
        world.advance()
        replayed = replay_world(self._world(location="办公室"), world.replayable_log())
        self.assertEqual(self._event(replayed).visible_to, frozenset({"班长"}))
        self.assertEqual(self._event(replayed).payload["notice"], self.EVENT["notice"])


class DocumentAnnotationGates(unittest.TestCase):
    """E98（报 94 §3，窗口 4 16:20–16:42）：工具面没有“在文书上写”。

    `面核记录` 正文要求“谁到场核对，谁就往自己那一栏里填”，但工具面没有
    annotate，`document_annotated` 事件与 `annotations` 存储早已存在却无入口，
    班长只能另贴字条，面核记录 0 人签。修法是既有动作的一处参数化：
    `leave_note` 增加可选 `on=<文书 id>`——文字作为一条 annotation 追加进该文书
    （须同处一地或持在手上且可读），产生既有的 `document_annotated`（同地点
    可见，正文仍只属于读过它的人），不覆盖别人写的条目。
    """

    START = "2026-03-16T16:30:00+08:00"

    def _world(self):
        return World(start=datetime.fromisoformat(self.START),
                     actors=[ActorState("班长", "办公室"), ActorState("辅导员", "办公室")],
                     locations=[LocationState("办公室")],
                     item_locations={"面核记录": "办公室"},
                     document_defs={"面核记录": {
                         "title": "面核记录",
                         "content": "谁到场核对，谁就往自己那一栏里填。",
                         "reading_seconds": 30}})

    @staticmethod
    def _annotations(world):
        return world.document_defs["面核记录"].get("annotations", [])

    def test_signature_is_an_appended_annotation_that_others_can_read(self):
        world = self._world()
        world.submit(Intention("班长", "leave_note",
                               {"text": "到场核对：材料三份，缺说明一页。",
                                "on": "面核记录"}, world.version))
        world.advance()
        self.assertEqual([entry["text"] for entry in self._annotations(world)],
                         ["到场核对：材料三份，缺说明一页。"])
        self.assertEqual(self._annotations(world)[0]["by"], "班长")
        annotated = [event for event in world.event_log if event.kind == "document_annotated"]
        self.assertEqual(len(annotated), 1, "产生既有的 document_annotated")
        self.assertEqual(annotated[0].payload["document"], "面核记录")
        self.assertEqual(annotated[0].visible_to, frozenset({"班长", "辅导员"}))
        self.assertFalse([event for event in world.event_log if event.kind == "note_left"],
                         "写在文书上不是另贴一张字条")
        # 同地点的人只看见“谁写了字”，正文要自己 read；读过的人能看到全部批注。
        seen = next(event for event in world.poll("辅导员")["events"]
                    if event["kind"] == "document_annotated")
        self.assertNotIn("annotation", seen["payload"], "批注正文不随事件广播")
        world.submit(Intention("辅导员", "read", {"item": "面核记录"}, world.version))
        world.advance()
        read = next(event for event in world.event_log if event.kind == "document_read")
        self.assertEqual([entry["text"] for entry in read.payload["annotations"]],
                         ["到场核对：材料三份，缺说明一页。"])
        self.assertEqual(read.visible_to, frozenset({"辅导员"}), "正文只给读者")

    def test_a_second_writer_appends_without_overwriting(self):
        world = self._world()
        world.submit(Intention("班长", "leave_note", {"text": "缺说明。", "on": "面核记录"},
                               world.version))
        world.advance()
        world.submit(Intention("辅导员", "leave_note", {"text": "已复核。", "on": "面核记录"},
                               world.version))
        world.advance()
        self.assertEqual([entry["text"] for entry in self._annotations(world)],
                         ["缺说明。", "已复核。"])
        self.assertEqual([entry["by"] for entry in self._annotations(world)],
                         ["班长", "辅导员"])

    def test_replay_rebuilds_the_annotations(self):
        world = self._world()
        world.submit(Intention("班长", "leave_note", {"text": "缺说明。", "on": "面核记录"},
                               world.version))
        world.advance()
        replayed = replay_world(self._world(), world.replayable_log())
        self.assertEqual([entry["text"] for entry in self._annotations(replayed)],
                         ["缺说明。"])
        self.assertEqual(self._annotations(replayed)[0]["by"], "班长")

    def test_writing_on_a_document_that_is_not_here_is_rejected(self):
        world = self._world()
        world.item_locations.pop("面核记录")
        before = len(world.event_log)
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("班长", "leave_note",
                                   {"text": "补签。", "on": "面核记录"}, world.version))
        self.assertIn("没有可以在上面写字的文书", str(rejected.exception))
        self.assertEqual(rejected.exception.context.get("writable_documents"), [])
        self.assertEqual(len(world.event_log), before)


class GiveAtHandAffordanceGates(unittest.TestCase):
    """E99（报 94 §R6/C，窗口 4 11:00–11:48）：食堂大妈的 give 候选是空的。

    引擎早已支持“把就在自己手边的物品直接 give 给面前的人”（ticket 63 的
    take-then-give 就地分支），但 `affordances()` 只列背包里的东西。于是
    “把这份饭递给面前的人”不在可见选项里，她只招呼、饭被学生自取。
    """

    def _world(self):
        return World(start=datetime.fromisoformat("2026-03-16T11:00:00+08:00"),
                     actors=[ActorState("食堂大妈", "食堂"), ActorState("唐小岚", "食堂")],
                     locations=[LocationState("食堂")],
                     item_locations={"一份午饭": "食堂", "灶台": "食堂"},
                     fixed_items={"灶台": "砌在墙边，抬不走"})

    def test_an_item_at_my_location_is_a_visible_give_candidate(self):
        world = self._world()
        gives = [option for option in world.affordances("食堂大妈")
                 if option.get("kind") == "give"]
        self.assertIn({"kind": "give", "target": "唐小岚", "item": "一份午饭"}, gives)
        self.assertNotIn({"kind": "give", "target": "唐小岚", "item": "灶台"}, gives,
                         "固定陈设不是可递交的候选")
        world.submit(Intention("食堂大妈", "give",
                               {"target": "唐小岚", "item": "一份午饭"}, world.version))
        world.advance()
        self.assertIn("一份午饭", world.actors["唐小岚"].inventory)
        self.assertNotIn("一份午饭", world.item_locations)


class BlankNoteOnGates(unittest.TestCase):
    """E100（报 97 §E1，窗口 5 08:06–17:19）：`leave_note on: ""` 被当成“在文书上补写”。

    窗 5 全天 106 条拒绝（陈默 60、林瑶 23……）都是同一个形状：
    `leave_note {"text": …, "persist": true, "on": ""}`。校验用
    `if on is not None` 判“同时声明了 on 与 persist”，空串于是把“留一份新文稿”
    自己判成冲突；陈默因此从 11:25 起逢人就说“我三次尝试留书面说明都没有成功”，
    而世界给他的理由是假的（他的《个人情况说明》全天没写成）。

    语义：`on` 只有**非空字符串**才进入批注分支；空串/纯空白等于没提供，
    照常走普通便条（`persist` 生效）。
    """

    BODY = "3月16日 08:06，陈默核对记录：材料三份，缺说明一页。"

    def _world(self):
        return World(start=datetime.fromisoformat("2026-03-16T08:06:00+08:00"),
                     actors=[ActorState("陈默", "档案室")],
                     locations=[LocationState("档案室")],
                     item_locations={"面核记录": "档案室"},
                     document_defs={"面核记录": {
                         "title": "面核记录",
                         "content": "谁到场核对，谁就往自己那一栏里填。",
                         "reading_seconds": 30}})

    @staticmethod
    def _annotations(world):
        return world.document_defs["面核记录"].get("annotations", [])

    def test_a_blank_on_writes_an_ordinary_persistent_note(self):
        world = self._world()
        world.submit(Intention("陈默", "leave_note",
                               {"text": self.BODY, "persist": True, "on": ""},
                               world.version))
        world.advance()
        notes = [event for event in world.event_log if event.kind == "note_left"]
        self.assertEqual(len(notes), 1, "空的 on 等于没提供：这是一张普通便条")
        self.assertTrue(notes[0].payload.get("persist"))
        self.assertIn(notes[0].payload["note"], world.persistent_notes)
        self.assertEqual(self._annotations(world), [], "没有往任何文书上写")
        self.assertFalse([event for event in world.event_log
                          if event.kind == "document_annotated"])

    def test_a_whitespace_only_on_is_the_same_as_no_on(self):
        world = self._world()
        world.submit(Intention("陈默", "leave_note", {"text": self.BODY, "on": "   "},
                               world.version))
        world.advance()
        self.assertEqual([event.kind for event in world.event_log
                          if event.kind in {"note_left", "document_annotated"}],
                         ["note_left"])
        self.assertEqual(len(world.locations["档案室"].notes), 1)
        self.assertEqual(self._annotations(world), [])

    def test_a_real_document_still_takes_the_annotation_path(self):
        world = self._world()
        world.submit(Intention("陈默", "leave_note",
                               {"text": self.BODY, "on": "面核记录"}, world.version))
        world.advance()
        self.assertEqual([entry["text"] for entry in self._annotations(world)], [self.BODY])
        self.assertTrue([event for event in world.event_log
                         if event.kind == "document_annotated"])
        self.assertFalse([event for event in world.event_log if event.kind == "note_left"])


class BlankCompanionGates(unittest.TestCase):
    """E101（报 97 §E2，窗口 5 08:27–17:49）：`move with: [""]` 被当成“有同行者”。

    窗 5 有 76 条“move 的 with 里有一个空名字”，相邻形态还有 `with: ["_self"]`、
    `with: ["陈默(you)"]`、`with: ["唐小岚"]`（自己）——模型在找“一个人走”的表达法，
    而接口只有“不带 with”，拒绝回执的 Valid call 实测 7 连未纠正（唐小岚 08:29–08:59），
    于是唐小岚 13:04 对外说出“移动需要明确同行者”，花 88 分钟逐人求同行。

    语义：`with` 的空项/重复项先过滤；过滤后为空 = 独自走，等同没写 `with`；
    拒绝回执与 `action_schema` 都明写“独自走就只写 target，别写 with”。
    """

    def _world(self):
        return World(start=datetime.fromisoformat("2026-03-16T08:27:00+08:00"),
                     actors=[ActorState("唐小岚", "半坡咖啡馆"),
                             ActorState("林瑶", "半坡咖啡馆")],
                     locations=[LocationState("半坡咖啡馆"), LocationState("后街糕点铺")],
                     routes={("半坡咖啡馆", "后街糕点铺"): 120})

    @staticmethod
    def _moves(world):
        return [(event.kind, event.actor) for event in world.event_log
                if event.kind in {"leave", "enter"}]

    def test_an_empty_companion_entry_means_walking_alone(self):
        world = self._world()
        world.submit(Intention("唐小岚", "move",
                               {"target": "后街糕点铺", "with": [""]}, world.version))
        world.advance()
        self.assertEqual(world.actors["唐小岚"].location, "后街糕点铺")
        self.assertEqual(world.actors["林瑶"].location, "半坡咖啡馆", "空项不是同行者")
        self.assertEqual(self._moves(world), [("leave", "唐小岚"), ("enter", "唐小岚")])

    def test_an_empty_with_list_means_walking_alone(self):
        world = self._world()
        world.submit(Intention("唐小岚", "move",
                               {"target": "后街糕点铺", "with": []}, world.version))
        world.advance()
        self.assertEqual(world.actors["唐小岚"].location, "后街糕点铺")
        self.assertEqual(self._moves(world), [("leave", "唐小岚"), ("enter", "唐小岚")])

    def test_a_real_companion_still_comes_along(self):
        world = self._world()
        world.submit(Intention("唐小岚", "move",
                               {"target": "后街糕点铺", "with": ["林瑶", "林瑶"]},
                               world.version))
        world.advance()
        self.assertEqual(world.actors["林瑶"].location, "后街糕点铺",
                         "重复项不改变“带上这个人”")

    def test_a_placeholder_companion_name_teaches_walking_alone(self):
        world = self._world()
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("唐小岚", "move",
                                   {"target": "后街糕点铺", "with": ["_self"]},
                                   world.version))
        self.assertIn("target", str(rejected.exception),
                      "拒绝必须说清“一个人走就只写 target”")
        self.assertNotIn("with 里有一个空名字", str(rejected.exception))


class SingleInstanceTakeGates(unittest.TestCase):
    """E102（报 97 §E3，窗口 5 17:56–17:58）：同一件东西被两个人同时 take 都算成功。

    事件序列（run real-20261018T062031，4675 之后的 #4707–#4719）：
    17:57 `action_started 陈默 take 一份晚饭` 与 #4708 `action_started 辅导员 take
    一份晚饭` 相继成立——`take` 的归属只在**完成时**写进世界，两次提交之间
    `item_locations` 还没变，于是两人都通过校验、两条 `action_completed` 都写下
    “拿起了”，只有先完成的那一位背包里真的有它：陈默拿到，辅导员 17:59 对食堂
    大妈说“谢谢，我们都拿了晚饭”。回执说成功、世界没变 = 票 75 的同一族。

    不变量：一件东西在任一时刻只有一个持有者或一个地点。它覆盖两条能把东西从原地
    拿走的路径——`take`，以及 `give` 的“就地拿起再递出”（票 63）。
    """

    def _world(self):
        return World(start=datetime.fromisoformat("2026-03-16T17:56:00+08:00"),
                     actors=[ActorState("辅导员", "食堂"), ActorState("陈默", "食堂")],
                     locations=[LocationState("食堂")],
                     item_locations={"一份晚饭": "食堂", "例汤": "食堂"})

    @staticmethod
    def _completions(world):
        return [event for event in world.event_log
                if event.kind == "action_completed"
                and str(event.payload.get("action")) == "take"]

    def test_the_second_taker_is_rejected_while_the_first_is_still_taking(self):
        world = self._world()
        world.submit(Intention("陈默", "take", {"item": "一份晚饭"}, world.version))
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("辅导员", "take", {"item": "一份晚饭"}, world.version))
        self.assertIn("陈默", str(rejected.exception), "拒绝要点名正在拿这一件的人")
        self.assertEqual(rejected.exception.context.get("claimed_by"), "陈默")
        world.advance()
        self.assertEqual(len(self._completions(world)), 1,
                         "只有一次 take 真的发生")
        self.assertIn("一份晚饭", world.actors["陈默"].inventory)
        self.assertNotIn("一份晚饭", world.actors["辅导员"].inventory)

    def test_an_item_never_has_two_holders(self):
        world = self._world()
        world.submit(Intention("陈默", "take", {"item": "一份晚饭"}, world.version))
        try:
            world.submit(Intention("辅导员", "take", {"item": "一份晚饭"}, world.version))
        except ActionRejected:
            pass
        world.advance()
        holders = [actor.id for actor in world.actors.values()
                   if "一份晚饭" in actor.inventory]
        self.assertEqual(holders, ["陈默"])
        self.assertNotIn("一份晚饭", world.item_locations)
        self.assertEqual(len(self._completions(world)), 1,
                         "世界日志里不能有第二句“拿起了”而世界没变")

    def test_a_late_take_names_where_the_item_actually_is(self):
        world = self._world()
        world.submit(Intention("陈默", "take", {"item": "一份晚饭"}, world.version))
        world.advance()
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("辅导员", "take", {"item": "一份晚饭"}, world.version))
        message = str(rejected.exception)
        self.assertIn("陈默", message, "回执要说出这件东西现在在谁手上")
        self.assertEqual(rejected.exception.context.get("held_by"), "陈默")
        self.assertNotIn("这里没有「一份晚饭」可拿", message)

    def test_an_abandoned_take_releases_the_item(self):
        world = self._world()
        world.submit(Intention("陈默", "take", {"item": "一份晚饭"}, world.version))
        self.assertTrue(world.force_interrupt("陈默", "辅导员"))
        world.submit(Intention("陈默", "abandon_action", {}, world.version))
        world.submit(Intention("辅导员", "take", {"item": "一份晚饭"}, world.version))
        world.advance()
        self.assertIn("一份晚饭", world.actors["辅导员"].inventory)
        self.assertNotIn("一份晚饭", world.actors["陈默"].inventory)

    def test_two_hand_overs_of_one_item_cannot_duplicate_it(self):
        """同一族的另一半：`give` 的“就地拿起再递出”分支（票 63）也把东西从
        原地拿走，于是两个人各递一次同一份饭，两个收件人背包里都会有一份。
        不变量对这条路径同样成立：第二个就地递出结构化拒绝。"""
        world = World(start=datetime.fromisoformat("2026-03-16T17:56:00+08:00"),
                      actors=[ActorState("食堂大妈", "食堂"), ActorState("宿管阿姨", "食堂"),
                              ActorState("陈默", "食堂"), ActorState("林瑶", "食堂")],
                      locations=[LocationState("食堂")],
                      item_locations={"一份晚饭": "食堂"})
        world.submit(Intention("食堂大妈", "give",
                               {"target": "陈默", "item": "一份晚饭"}, world.version))
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("宿管阿姨", "give",
                                   {"target": "林瑶", "item": "一份晚饭"}, world.version))
        self.assertEqual(rejected.exception.context.get("claimed_by"), "食堂大妈")
        world.advance()
        holders = sorted(actor.id for actor in world.actors.values()
                         if "一份晚饭" in actor.inventory)
        self.assertEqual(holders, ["陈默"], "一份晚饭只能有一个人拿到")
        self.assertNotIn("一份晚饭", world.item_locations)


class ExtraScenePrivacyGates(unittest.TestCase):
    """E103（报 97 §E4，窗口 5 15:04–15:06）：陌生人的输入带着别人还没送到的便条正文。

    15:04 唐小岚读了 `代话便条`（正文：“…稿子的事我晓得了，别再往吧台上放…”）；
    15:06 她朝“陌生人”搭话求同行，回话的是当场生成的 `张学长`：
    “愿意啊。老板娘还留了话：稿子的事我晓得了，别再往吧台上放……”——一句她还没
    送到的话被提前兑付了。诊断（该回合的 perception 实录）：extra 没有拿到提问者的
    KB/记忆，泄漏通道是**场景事实块**——`scene_perception` 把同地每件东西的
    `entity_descriptions` 全文发给它，而 `代话便条` 的客观描述就是便条正文，尽管
    种子把这份便条声明为 `known_to: [唐小岚]`。

    修法：extra 只接收“当面听到的话 + 该地点的**公开**可见物 + 自己身份”。
    被 `known_to` 限定给别人的东西，extra 看得见它在场（`nearby_items` 保留，
    因为它确实摆在吧台上），但不拿到它的描述正文。
    """

    SECRET = "别再往吧台上放"

    def _scene(self):
        from harness.npc_agent import build_extra_scene
        world = load_story_pack().build_world()
        world.actors["唐小岚"].location = "半坡咖啡馆"
        world.add_extra("张学长", "半坡咖啡馆")
        perception = world.scene_perception("张学长")
        return world, perception, build_extra_scene(perception, world.affordances("张学长"))

    def test_a_stranger_never_receives_a_note_that_is_not_his(self):
        _world, perception, scene = self._scene()
        self.assertNotIn(self.SECRET, scene,
                         "陌生人的场景事实里不能有别人便条的正文")
        self.assertNotIn(self.SECRET, json.dumps(perception, ensure_ascii=False))
        self.assertIn("代话便条", perception["nearby_items"],
                      "摆在吧台上的纸，陌生人是看得见它在场的")

    def test_a_public_prop_still_grounds_its_own_description(self):
        _world, perception, scene = self._scene()
        self.assertIn("校报草稿", scene, "没有 known_to 限定的物件照旧给描述")
        self.assertIn("一份", scene, "数量类断言仍有根据")

    def test_the_owner_still_sees_her_own_note(self):
        world = load_story_pack().build_world()
        world.actors["唐小岚"].location = "半坡咖啡馆"
        poll = world.poll("唐小岚")
        self.assertIn(self.SECRET, poll["descriptions"].get("代话便条", ""),
                      "种子声明 known_to 的人照旧看得见")
        self.assertIn(self.SECRET, world.readable_body("代话便条")["content"])


class EscortIdleGates(unittest.TestCase):
    """E104（票 98 §5.3 顺带发现，窗口 5 15:15–15:33，run real-20261018T062031）：
    同行途中的 extra 被当成“闲”回收。

    15:06 张学长应下“愿意陪你去”，15:08 随唐小岚 `move 后街糕点铺 with 张学长`
    出发，15:15 两人同到小卖部，15:19 它在下一跳（780s）途中得到
    `extra_removed reason: idle`——唐小岚 15:28 独自到夜市、15:33 独自到糕点铺。
    成因：idle 判据只看 `last_active`（上一次开口/动手的时刻），把“没人跟它说话”
    当成“它站在原地”；被携带的整段路上它没有也不该有动作事件。

    修法：`AsyncEngine._extra_is_idle` 把两种在场状态排除在 idle 之外——正被一次
    `move` 携带着赶路（自己也在这段路上，或它是别人 `with` 里的同行者），或还有
    一笔没结的对话（未答的问题 / 已听到还没回的话 / 供给方还在写的那一句）。
    被携带者要离开仍走既有“途中可脱离”的路：他自己开始走另一段 move，
    `_follows_escort` 便不再带他；到了地方站定，idle 照常计时。
    """

    START = datetime.fromisoformat("2026-03-16T07:00:00+08:00")

    class _QuietExtra:
        """一个应一声就沉默跟着走的路人（被携带时本来就不会有动作）。"""

        def __init__(self):
            self.calls = 0

        def chat_with_tools(self, messages, tools):
            self.calls += 1
            return {"role": "assistant", "content": "", "tool_calls": [
                {"id": f"c-{self.calls}", "type": "function",
                 "function": {"name": "speak", "arguments": json.dumps(
                     {"inner": "应一声", "text": "行，我陪你去。"},
                     ensure_ascii=False)}}]}

    def _run(self, *, walk: bool, minutes: int):
        world = load_story_pack().build_world()
        trace = Trace("v4-test", "e104-escort-idle")
        script = {"asked": False, "walked": False}

        def agent(state, perception, affordances):
            if state.actor_id != "唐小岚":
                return Intention(state.actor_id, "wait", {"duration_seconds": 3600},
                                 perception["world_version"])
            if not script["asked"]:
                script["asked"] = True
                return Intention("唐小岚", "speak",
                                 {"text": "同学，我受老板娘所托去后街糕点铺带句话，"
                                          "你愿意陪我一起去吗？",
                                  "volume": "normal", "to": ["陌生人"]},
                                 perception["world_version"])
            companions = [name for name in perception.get("nearby_actors", ())
                          if name in world.actors and world.actors[name].role == "extra"]
            if walk and companions and not script["walked"]:
                script["walked"] = True
                return Intention("唐小岚", "move",
                                 {"target": "后街糕点铺", "with": companions},
                                 perception["world_version"])
            return Intention("唐小岚", "wait", {"duration_seconds": 600},
                             perception["world_version"])

        states = {actor: PrivateState(actor) for actor in world.actors}
        agents = {actor: agent for actor in world.actors
                  if world.actors[actor].role != "extra"}
        # 阈值 300s 小于路线的第一跳（420s），但比生成路人的回合延迟宽：
        # 票 73 §6.1 的 extra 时序族曾把“应一声”推到 120s，留出余量才不误红。
        engine = AsyncEngine(world, agents, states, trace, None,
                             extra_call=self._QuietExtra(), decision_timeout=10,
                             max_wall_seconds=60, extra_idle_seconds=300)
        engine.run(stop_at=self.START + timedelta(minutes=minutes), max_turns=400)
        return world, trace

    @staticmethod
    def _extra_name(trace) -> str:
        return next(turn["actor"] for turn in trace.agent_turns
                    if turn.get("role") == "extra")

    def test_a_carried_extra_rides_out_the_idle_threshold(self):
        """同行在飞超过 idle 阈值不被回收：每一跳都跟上，并随队到达目的地。"""
        world, trace = self._run(walk=True, minutes=40)
        name = self._extra_name(trace)
        move_done = next(event for event in world.event_log
                         if event.actor == "唐小岚"
                         and event.kind == "action_completed"
                         and event.payload.get("action") == "move")
        self.assertEqual(move_done.payload.get("with"), [name], "这次确实是同行")
        removed = [event for event in world.event_log
                   if event.kind == "extra_removed" and event.actor == name]
        self.assertFalse([event for event in removed
                          if event.payload.get("reason") == "idle"
                          and event.time < move_done.time],
                         "同行在飞时不得被当成闲回收")
        entered = [event for event in world.event_log
                   if event.kind == "enter" and event.actor == name]
        self.assertEqual([event.payload.get("location") for event in entered],
                         ["小卖部", "夜市", "后街糕点铺"],
                         "每一跳都跟上，一步不少")
        self.assertEqual({event.payload.get("escorted_by") for event in entered},
                         {"唐小岚"})
        self.assertEqual(entered[-1].time, move_done.time, "与发起者同时到达")

    def test_a_silent_extra_with_no_walk_is_still_reclaimed(self):
        """守卫：没有同行的沉默路人照旧被 idle 回收——豁免只属“在途”。"""
        world, trace = self._run(walk=False, minutes=12)
        name = self._extra_name(trace)
        removed = [event for event in world.event_log
                   if event.kind == "extra_removed" and event.actor == name]
        self.assertEqual([event.payload.get("reason") for event in removed], ["idle"])
        self.assertNotIn(name, world.actors)

    def _idle_engine(self):
        world = load_story_pack().build_world()
        trace = Trace("v4-test", "e104-idle-predicate")

        def agent(state, perception, affordances):
            return Intention(state.actor_id, "wait", {"duration_seconds": 600},
                             perception["world_version"])

        states = {actor: PrivateState(actor) for actor in world.actors}
        agents = {actor: agent for actor in states}
        engine = AsyncEngine(world, agents, states, trace, None,
                             extra_call=self._QuietExtra(), decision_timeout=10,
                             max_wall_seconds=60, extra_idle_seconds=60)
        world.add_extra("路人", "半坡咖啡馆")
        info = {"partner": "唐小岚",
                "last_active": world.now - timedelta(seconds=120),
                "pending_question": "", "pending_heard_speech": False}
        return engine, info

    def test_the_idle_clock_is_held_by_an_unanswered_conversation(self):
        """没结的对话同样不是“闲”：未答的问题、已听到未回的话、在飞的回答。"""
        engine, info = self._idle_engine()
        self.assertTrue(engine._extra_is_idle("路人", info),
                        "沉默过阈值的路人本来就会回收")
        info["pending_question"] = "三点方老师来取草稿，先放你这儿。"
        self.assertFalse(engine._extra_is_idle("路人", info), "问题还没答，它欠一回")
        info["pending_question"] = ""
        info["pending_heard_speech"] = True
        self.assertFalse(engine._extra_is_idle("路人", info), "听见了还没回，它欠一回")
        info["pending_heard_speech"] = False
        engine._extra_inflight["路人"] = engine.world.now
        self.assertFalse(engine._extra_is_idle("路人", info), "供给方还在写那一名")

    def test_an_extra_walking_on_its_own_is_not_idle(self):
        """自己也在这段路上（自己发起的 move）同样不是“闲”；到站后照常计时。"""
        engine, info = self._idle_engine()
        world = engine.world
        world.submit(Intention("路人", "move", {"target": "中庭"}, world.version))
        self.assertFalse(engine._extra_is_idle("路人", info), "走在路上不是闲着")
        world.advance(until=world.now + timedelta(seconds=720))
        self.assertTrue(engine._extra_is_idle("路人", info), "到了地方站定，idle 照常计时")

    def test_a_carried_extra_leaves_by_walking_to_its_own_target(self):
        """被携带者要离开仍走既有“途中可脱离”的路：自己走另一段 move。"""
        start = datetime.fromisoformat("2026-03-16T09:00:00+08:00")
        world = World(start=start,
                      actors=[ActorState("唐小岚", "平台"),
                              ActorState("张学长", "平台", role="extra")],
                      locations=[LocationState("平台"), LocationState("走廊"),
                                 LocationState("教室"), LocationState("图书馆")],
                      routes={("平台", "走廊"): 120, ("走廊", "教室"): 180,
                              ("走廊", "图书馆"): 90})
        world.submit(Intention("唐小岚", "move",
                               {"target": "教室", "with": ["张学长"]}, world.version))
        world.advance(until=start + timedelta(seconds=120))
        self.assertEqual(world.actors["张学长"].location, "走廊")
        world.submit(Intention("张学长", "move", {"target": "图书馆"}, world.version))
        world.advance()
        self.assertEqual(world.actors["唐小岚"].location, "教室")
        self.assertEqual(world.actors["张学长"].location, "图书馆",
                         "脱离是一次显式动作，不是被静默回收")
        self.assertFalse([event for event in world.event_log
                          if event.kind == "extra_removed"],
                         "没有人替他离开")


class ConsecutiveEmptyTurnGates(unittest.TestCase):
    """E93（报 90 §2，窗口 3 08:42–09:04）：连续空回合的后果没人告诉角色。

    陈默那 22 分钟里 9 个回合只有正文、零工具调用，每个回合世界照常往前走
    （版本 482→798、时钟每拍两分钟）；`empty_turn{reason: prose_only}` 记了，
    但那一回合的后果从没回到他的输入里——他在正文里把台账的三条款答了五遍，
    每一遍都像已经答过了（ticket 64 的自纠只在正文像在对人说话时发；他写的是
    一份"已答好"的答案，既没有引号也没有第二人称）。裁定：
    (a) 时钟不改——发呆一拍是 §4 的既定语义，而且每一拍都由一条显式 `wait`
        事件归因（诊断见票 91：那 20 分钟是"零调用的模型输出 + 一拍 wait"，
        不是引擎重试，provider 故障计数为 0）；
    (b) 提示层补一条一次性反馈：上一回合只有想法、零调用时，告诉下一回合
        "那段想法没有改变世界"，并给出两条出路（工具、或明确 wait）。
    有界：一拍一条，一旦有调用就不再追加。
    """

    PROSE = ("我能确认：这是 **2013年邻里撤离与互助事项的确认通知书**；"
             "负责确认的是家属院推举的老街坊代表，儿子只是代笔。")

    def _world(self):
        return load_story_pack().build_world()

    @staticmethod
    def _empty_rows(trace, actor):
        return [turn["result"] for turn in trace.system_turns
                if turn["request"].get("kind") == "empty_turn"
                and turn["result"].get("actor") == actor]

    def test_each_empty_turn_is_recorded_as_a_streak_and_owns_one_wait(self):
        world = self._world()
        engine, agent = _dialogue_engine(world)
        for _ in range(3):
            _dialogue_turn(engine, world, "陈默", [], text=self.PROSE)
        rows = self._empty_rows(engine.trace, "陈默")
        self.assertEqual([row["streak"] for row in rows], [1, 2, 3])
        self.assertTrue(all(row["reason"] == "prose_only" for row in rows))
        self.assertTrue(all(row["private_chars"] > 0 for row in rows))
        actions = [event for event in world.event_log
                   if event.actor == "陈默"
                   and event.kind in {"speech", "action_started", "action_completed"}]
        self.assertFalse([e for e in actions if e.kind == "speech"],
                         "空回合不代填说话")
        self.assertEqual({e.payload.get("action") for e in actions}, {"wait"},
                         "空回合除了发呆一拍不得代填任何动作")
        self.assertEqual({e.payload.get("duration_seconds") for e in actions},
                         {TICK_SECONDS}, "发呆就是一拍")

    def test_the_next_input_says_the_thought_changed_nothing(self):
        world = self._world()
        engine, agent = _dialogue_engine(world)
        for _ in range(3):
            _dialogue_turn(engine, world, "陈默", [], text=self.PROSE)
        self.assertEqual(agent.notes, ["no_action:1", "no_action:2", "no_action:3"],
                         "每拍一条，带连续次数")

    def test_a_turn_with_a_call_resets_the_streak_and_gets_no_notice(self):
        world = self._world()
        engine, agent = _dialogue_engine(world)
        _dialogue_turn(engine, world, "陈默", [], text=self.PROSE)
        _dialogue_turn(engine, world, "陈默",
                    [{"name": "wait", "tool_call_id": "w-1",
                      "arguments": {"duration_seconds": TICK_SECONDS}}])
        _dialogue_turn(engine, world, "陈默", [], text=self.PROSE)
        rows = self._empty_rows(engine.trace, "陈默")
        self.assertEqual([row["streak"] for row in rows], [1, 1],
                         "有调用的回合把连续计数清零")
        self.assertEqual(agent.notes, ["no_action:1", "no_action:1"],
                         "有调用的回合自己不产生空回合反馈")
        self.assertNotIn("unspoken", agent.notes,
                         "这段正文不像对人说话，ticket 64 的自纠不该抢这条反馈")


class NoActionNoticeTextGates(unittest.TestCase):
    """E93 的提示层文本：那段反馈要说清后果与两条出路，并带连续次数。"""

    def test_the_note_states_the_consequence_and_the_two_ways_out(self):
        from harness.natural_agent import NO_ACTION_NOTE, V4Session
        self.assertIn("没有调用任何工具", NO_ACTION_NOTE)
        self.assertIn("时间照常过去", NO_ACTION_NOTE)
        self.assertIn("speak", NO_ACTION_NOTE)
        self.assertIn("wait", NO_ACTION_NOTE)
        session = V4Session("陈默", provider=None)   # 只测追加，不调用模型
        session.note_no_action(3)
        self.assertEqual(session.messages[-1]["role"], "user")
        self.assertIn("连续第 3 个", session.messages[-1]["content"])
        session.note_no_action(1)
        self.assertNotIn("连续第", session.messages[-1]["content"])


class NoteDeliveryGates(unittest.TestCase):
    """E105（票 101，窗口 6 18:44–21:30，run real-20261018T073833）：字条能写、能读，递不出去。

    夜段 12 个回合、四种写法全部撞在同一堵墙上：18:48 `give note-陈默-1` 给辅导员
    被拒（"你没有拿着「note-陈默-1」…可行调用：give 2013年邻里撤离通知书"），
    19:07 `leave_note on:"空白纸"` 被拒（`on` 只认当前地点的 `document_defs`），
    19:11 不带 on 留字成功但那张字条只由后到者读。主角 D1 的核心目标（"自己写好、
    签名、亲手交给辅导员"）因此在世界里**结构上不可达**。修法不新增动作种类：
    ① `give` 的目标物 = item ∪ 已存在的便条 id（便条本来就在世界上，递它就是递纸），
    持有关系沿用背包（→ replay 可重建），完成时字条随收件人移动；
    ② `leave_note on=<空白纸>` 把那张纸写成一份带编号的文稿（可读、可递）；
    ③ 拒绝回执不再拿无关文书当替代。
    """

    TEXT = "个人情况说明：3/16 现场所见与转述已分开记，落款陈默。"

    def _world(self):
        world = load_story_pack().build_world()
        world.actors["陈默"].location = "学生会办公室"
        world.actors["辅导员"].location = "学生会办公室"
        # 票 113（112 §E1/E2）：种子的排程现在会把值班 npc 放到岗位上
        # （`place_actor`），而 `advance()` 不带上限会走完整个排程——19:00 的收件档
        # 会把辅导员从这间屋子挪回她的办公室。这条门禁测的是“写好的纸能不能递
        # 出去”，场景由测试自己摆定，所以清掉排程。
        world._queue.clear()
        return world

    def _written_sheet(self, world):
        """一张写好的纸：写在 空白纸 上，文稿因此在他手上。"""
        world.submit(Intention("陈默", "leave_note",
                               {"text": self.TEXT, "on": "空白纸"}, world.version))
        world.advance()
        return next(note_id for note_id, row in world.persistent_notes.items()
                    if row.get("text") == self.TEXT)

    def test_a_written_sheet_is_a_note_that_can_be_handed_over_and_read(self):
        """① 写在一张纸上的说明：作者拿着 → 递给在场的人 → 收件人读得到全文。"""
        world = self._world()
        self.assertIn("空白纸", world._writable_sheets(world.actors["陈默"]),
                      "手边的空白纸必须是一个真的能写的目标")
        note_id = self._written_sheet(world)
        self.assertIn(note_id, world.actors["陈默"].inventory, "写好的纸在他手上")
        # 票 113（112 §E1）：种子里的「空白纸」是一沓（`sheets: 12`）——写一张只少
        # 一张，纸本身仍是可用的纸；耗尽之前它不能被说成“已经写满了”。
        self.assertEqual(world.item_sheets["空白纸"], 11, "写一张只少一张")
        self.assertEqual(world.item_locations.get("空白纸"), "学生会办公室",
                         "一沓纸还在桌上，别人还能接着写")
        self.assertIn({"kind": "read", "item": note_id}, world.affordances("陈默"))
        self.assertIn({"kind": "give", "target": "辅导员", "item": note_id},
                      world.affordances("陈默"), "拿着它就该能在选项里递给面前的人")
        world.submit(Intention("陈默", "give",
                               {"target": "辅导员", "item": note_id}, world.version))
        world.advance()
        given = next(event for event in world.event_log if event.kind == "item_given")
        self.assertEqual(given.payload["item"], note_id)
        self.assertEqual((given.payload["from"], given.payload["to"]), ("陈默", "辅导员"))
        self.assertIn(note_id, world.actors["辅导员"].inventory, "递出去就是递那张纸")
        self.assertNotIn(note_id, world.actors["陈默"].inventory, "递出去之后不再在他手上")
        world.submit(Intention("辅导员", "read", {"item": note_id}, world.version))
        world.advance()
        self.assertEqual([event.payload["content"] for event in world.event_log
                          if event.kind == "document_read"], [self.TEXT])

    def test_a_persistent_note_left_on_the_table_can_also_be_handed_over(self):
        """② 先留一份 persist 文稿（untaken），再当场递出去：纸本来就在世界上。"""
        world = self._world()
        world.submit(Intention("陈默", "leave_note",
                               {"text": self.TEXT, "persist": True}, world.version))
        world.advance()
        note_id = next(iter(world.persistent_notes))
        world.submit(Intention("陈默", "give", {"target": "辅导员", "item": note_id},
                               world.version))
        world.advance()
        self.assertIn(note_id, world.actors["辅导员"].inventory)
        # 收件人拿在手上：别人（包括作者）不能隔着手读这张纸。
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("陈默", "read", {"item": note_id}, world.version))
        self.assertIn("辅导员", str(rejected.exception), "要说清现在在谁手上")
        self.assertEqual(rejected.exception.alternatives, [],
                         "字条在别人手上时不得推荐无关文书当替代")

    def test_a_rejected_note_handover_never_offers_an_unrelated_document(self):
        """③ 回执护栏：窗口 6 18:48 那条“可行调用：give 2013年邻里撤离通知书”
        既无关又误导；字条不在手上时只说它在谁手上/哪里。"""
        world = self._world()
        note_id = self._written_sheet(world)
        world.submit(Intention("陈默", "give", {"target": "辅导员", "item": note_id},
                               world.version))
        world.advance()
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("陈默", "give",
                                   {"target": "辅导员", "item": note_id}, world.version))
        message = str(rejected.exception)
        self.assertIn("字条", message)
        self.assertIn("辅导员", message, "要说清它现在在谁手上")
        self.assertNotIn("2013年邻里撤离通知书", message, "不得推荐无关文书")
        self.assertTrue(rejected.exception.context.get("note"))

    def test_replay_rebuilds_the_handed_over_note_and_the_used_sheet(self):
        """④ replay 一致：字条、持有者、被写掉的那张纸都从事件重建。"""
        world = self._world()
        note_id = self._written_sheet(world)
        world.submit(Intention("陈默", "give", {"target": "辅导员", "item": note_id},
                               world.version))
        world.advance()
        replayed = replay_world(load_story_pack().build_world(), world.replayable_log())
        self.assertIn(note_id, replayed.actors["辅导员"].inventory,
                      "递出的字条必须随事件重建在同一只手上")
        self.assertNotIn(note_id, replayed.actors["陈默"].inventory)
        self.assertEqual(replayed.item_sheets["空白纸"], 11,
                         "被写掉的那一张不能又变回空白纸：张数随事件重建")
        self.assertEqual(replayed.persistent_notes[note_id]["text"], self.TEXT)
        replayed.submit(Intention("辅导员", "read", {"item": note_id}, replayed.version))
        replayed.advance()
        self.assertEqual([event.payload["content"] for event in replayed.event_log
                          if event.kind == "document_read"], [self.TEXT])

    def test_the_sheet_route_is_offered_and_a_non_paper_is_refused(self):
        """提示层：`on` 的候选里说得出能写的纸；不是纸的东西被拒且不推荐别的文书。"""
        world = self._world()
        hint = next(option["hint"] for option in world.affordances("陈默")
                    if option.get("kind") == "leave_note")
        self.assertIn("空白纸", hint, "写的入口必须把纸说出来")
        self.assertIn("give", hint, "写好的纸可以递出去，这条路也要说出来")
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("陈默", "leave_note",
                                   {"text": "随手一记。", "on": "圆珠笔"},
                                   world.version))
        message = str(rejected.exception)
        self.assertIn("空白纸", message, "拒绝要列出真的能写的纸")
        sheets = rejected.exception.context.get("writable_sheets")
        self.assertIn("空白纸", sheets)
        self.assertNotIn("圆珠笔", sheets, "不是纸就不该出现在可写清单里")


class SleepWaitGates(unittest.TestCase):
    """E106（票 101，窗口 6 夜间）：睡觉没有表达法，夜段 43% 的回合是 `wait 900`。

    7 次 `wait 34200–48960`（≈9.5–13.6 小时，“睡到明早”）被 900 秒上限拒收，模型只能
    15 分钟一觉熬到天亮；19:14–21:24 有 2h10m 结构空转。修法不新增动作种类（§2 早已
    裁定 sleep 并入 wait）：`wait` 增加可选 `sleep: true`，上限 12 小时，语义是
    “睡到指定时长，或被打断/被叫醒”；复用既有 `sleeping` 字段与可见性（他人看不见你在睡），
    `wake_waiter` 的唤醒类照旧能打断，点名的排程事件也能叫醒他。
    """

    def _world(self):
        return load_story_pack().build_world()

    def test_eight_hours_of_sleep_is_accepted_and_advances_the_clock(self):
        """① 8 小时睡眠成功，世界时钟真的走到天亮。"""
        world = self._world()
        with self.assertRaises(ActionRejected) as rejected:
            world.submit(Intention("陈默", "wait", {"duration_seconds": 8 * 3600},
                                   world.version))
        self.assertIn("sleep: true", str(rejected.exception),
                      "超上限的等待必须教给模型 sleep 这条路")
        start = world.now
        world.submit(Intention("陈默", "wait",
                               {"duration_seconds": 8 * 3600, "sleep": True}, world.version))
        self.assertTrue(world.actors["陈默"].sleeping)
        world.advance(until=start + timedelta(hours=8))
        self.assertEqual(world.now, start + timedelta(hours=8))
        done = [event for event in world.event_log
                if event.kind == "action_completed" and event.payload.get("sleep")]
        self.assertEqual(len(done), 1)
        self.assertFalse(world.actors["陈默"].sleeping, "睡完就不再是睡着的状态")
        # 他人看不见你在睡：同地的人也读不到这条动作。
        self.assertEqual([event for event in world.event_log
                          if event.kind == "action_started"
                          and event.payload.get("sleep")][0].visible_to,
                         frozenset({"陈默"}))

    def test_a_sleeping_actor_is_woken_before_its_hour_is_up(self):
        """② 睡眠中被叫醒/被打断则提前结束，而且醒着的人不被打扰。"""
        world = self._world()
        start = world.now
        world.submit(Intention("陈默", "wait",
                               {"duration_seconds": 8 * 3600, "sleep": True}, world.version))
        # 普通 wait 不走这条点名唤醒（守卫）：先确认只对睡眠生效。
        world.submit(Intention("班长", "wait", {"duration_seconds": 900}, world.version))
        self.assertFalse(world.wake_sleeper("班长"))
        self.assertTrue(world.wake_sleeper("陈默"))
        self.assertFalse(world.actors["陈默"].sleeping)
        self.assertTrue([event for event in world.event_log if event.kind == "wait_woken"])
        self.assertEqual(world.now, start, "被叫醒不消耗剩余时长")
        self.assertLess(world.now, start + timedelta(hours=8))
        # 醒了就能做事：不再被自己的睡眠挡住。
        world.submit(Intention("陈默", "wait", {"duration_seconds": 60}, world.version))
        world.advance()
        self.assertFalse([event for event in world.event_log
                          if event.kind == "action_completed"
                          and event.payload.get("sleep")], "那一觉已经被叫醒，不会再睡满")

    def test_a_named_scheduled_event_wakes_a_sleeper_and_a_broadcast_does_not(self):
        """③ 点名叫他的排程事件能叫醒他；全场广播不叫醒睡着的人。

        这是引擎侧的那一半：`_wake_waiters` 只对 payload 里 `target` 点名的事件
        调用 `wake_sleeper`。窗口 6 的夜段若允许 8 小时睡眠而 19:30 的妈妈电话
        叫不醒他，那就是用一个更贵的问题换掉一个便宜的问题。"""
        def run(with_target):
            event = {"event": "mom_evening_call",
                     "time": "2026-03-16T09:00:00+08:00",
                     "notice": "妈妈又打来电话。"}
            if with_target:
                event["target"] = ["陈默"]
            world = World(start=datetime.fromisoformat("2026-03-16T07:00:00+08:00"),
                          actors=[ActorState("陈默", "宿舍", role="mc")],
                          locations=[LocationState("宿舍")],
                          scheduled=[event])
            turns = []

            def agent(state, perception, affordances):
                turns.append(perception["time"])
                if len(turns) == 1:
                    return Intention(state.actor_id, "wait",
                                     {"duration_seconds": 8 * 3600, "sleep": True},
                                     perception["world_version"])
                return Intention(state.actor_id, "wait",
                                 {"duration_seconds": 60}, perception["world_version"])

            trace = Trace("v4-test", f"sleep-wake-{with_target}")
            _call_pool().submit(lambda: None).result(timeout=5)
            engine = AsyncEngine(world, {"陈默": agent},
                                 {"陈默": PrivateState("陈默")}, trace, None,
                                 decision_timeout=10, max_wall_seconds=60,
                                 mc_idle_heartbeat=10 ** 6)
            engine.run(stop_at=datetime.fromisoformat("2026-03-16T12:00:00+08:00"),
                       max_turns=40)
            return world, turns

        world, turns = run(with_target=True)
        self.assertIn("2026-03-16T09:00:00+08:00", turns,
                      "点名叫他的事件必须叫醒他（那一回合就是 09:00）")
        self.assertTrue([event for event in world.event_log if event.kind == "wait_woken"])
        world_quiet, turns_quiet = run(with_target=False)
        self.assertEqual(turns_quiet, ["2026-03-16T07:00:00+08:00"],
                         "全场广播不该把睡着的人叫起来")
        self.assertFalse([event for event in world_quiet.event_log
                          if event.kind == "wait_woken"])

    def test_replay_and_checkpoint_keep_the_sleep(self):
        """④ replay 一致 + 检查点：事件与时钟重建，睡着这件事跨检查点还在。"""
        world = self._world()
        start = world.now
        world.submit(Intention("陈默", "wait",
                               {"duration_seconds": 8 * 3600, "sleep": True}, world.version))
        world.advance(until=start + timedelta(hours=2))
        restored = World.from_checkpoint(load_story_pack().build_world(),
                                         world.checkpoint_state())
        self.assertTrue(restored.actors["陈默"].sleeping, "检查点带着 sleep 状态")
        self.assertTrue(restored.wake_sleeper("陈默"), "恢复后仍叫得醒")
        replayed = replay_world(load_story_pack().build_world(), world.replayable_log())
        self.assertEqual(replayed.now, world.now)
        self.assertEqual([event.kind for event in replayed.event_log],
                         [event.kind for event in world.event_log])
        self.assertEqual([(event.kind, event.payload.get("sleep"))
                          for event in replayed.event_log
                          if event.kind == "action_started"],
                         [("action_started", True)])


class _ScriptedV4Agent:
    """Minimal v4-session agent: one scripted tool-call list per turn.

    `session_obj` routes the turn through `_execute_chain` — the production
    path (`SleepWaitGates`③ 用的是旧 callable 路径，所以那条门在真实种子上
    仍会红：本类补的正是这一段）。"""

    session_obj = object()

    def __init__(self, script):
        self.script = [list(turn) for turn in script]
        self.turns = 0

    def __call__(self, world_message, state):
        script = self.script[min(self.turns, len(self.script) - 1)]
        self.turns += 1
        return {"text": "",
                "calls": [{"name": name, "arguments": dict(args)}
                          for name, args in script]}

    def session_snapshot(self):
        return None

    def deliver_tool_results(self, results):
        pass

    def consume_compaction(self):
        return False


def _turns_from(trace, at: datetime):
    return [turn for turn in trace.agent_turns
            if datetime.fromisoformat(str(turn["perception"]["time"])) == at]


class WakeReachabilityGates(unittest.TestCase):
    """E109（票 106，D1 工件 real-20261018T085705）：睡眠把整个夜吞掉。

    D1 18:35 林瑶 `wait 28800 sleep:true` 那一回合里，`_execute_chain` 为了“让
    同一回合的后续调用落在动作完成之后”把世界时钟一路推进到 `_stop_horizon`
    （22:00）——一次 `world.advance` 就把 18:40–22:00 的六条夜间排程、三条
    `private_wake`、四条 `reminder_due` 全部记进日志而不派任何回合，然后循环顶部
    的 `_stop_check` 直接 `stop_at_reached`。于是“点名叫他的事件叫得醒他”这条
    不变式（票 101 的 SleepWaitGates③）在真实种子上不成立：那条门走的是旧
    callable 路径（`_submit`），而真实回合走的是 v4 链式路径。

    不变式（唤醒可达）：**一次回合内的时钟推进不得越过世界上下一个排程作业**
    （`World.next_event_time()`）——它会交出回合的作业里既有 `world_event` /
    `private_wake` / `reminder_due`，也有别人的 `action_completed`；越过任何一条，
    那些事件都既到不了角色的游标，也换不来回合。修法是把这条界加进链式推进的
    `limit`（V4-ENGINE §3.1），而不是每隔 N 分钟叫醒所有人。
    """

    def test_a_private_wake_still_reaches_an_awake_actor_while_another_sleeps(self):
        """① 全部角色 wait/睡下之后，07:30 的 private_wake 仍要在活人身上落成回合。

        07:15 陈默入睡（12 小时；那一刻没有别人在思考，`_horizon_bound()` 为
        None——正是 D1 18:35 的形状），唐小岚从 07:00 起就在等 30 分钟（先替她
        提交这一拍，免得 07:00 两个人同时起跳把这条门变成竞态）。修复前那次睡眠
        把时钟一次推到 stop_at（10:00）：唐小岚 07:30 的唤醒连同之后每一拍都被记
        进日志而不派回合。修复后推进停在 07:30，她在那一拍拿到回合，感知里带着
        那条 `private_wake`。"""
        start = datetime.fromisoformat("2026-03-16T07:00:00+08:00")
        wake_time = datetime.fromisoformat("2026-03-16T07:30:00+08:00")
        actors = [ActorState("陈默", "宿舍", role="mc"),
                  ActorState("唐小岚", "食堂", role="mc")]
        agents = {
            "陈默": _ScriptedV4Agent([[("wait", {"duration_seconds": 900})],
                                      [("wait", {"duration_seconds": 12 * 3600,
                                                  "sleep": True})],
                                      [("wait", {"duration_seconds": 60})]]),
            "唐小岚": _ScriptedV4Agent([[("wait", {"duration_seconds": 1800})]]),
        }
        world = World(start=start, actors=actors,
                      locations=[LocationState("宿舍"), LocationState("食堂")],
                      routes={("宿舍", "食堂"): 300, ("食堂", "宿舍"): 300})
        world.submit(Intention("唐小岚", "wait", {"duration_seconds": 1800},
                               world.version))
        world.schedule_private_wake("唐小岚", wake_time)
        trace = Trace("v4-test", "wake-reachability-private-wake")
        _call_pool().submit(lambda: None).result(timeout=5)
        engine = AsyncEngine(world, agents,
                             {actor.id: PrivateState(actor.id) for actor in actors},
                             trace, None, decision_timeout=10,
                             max_wall_seconds=60, mc_idle_heartbeat=0)
        engine.run(stop_at=datetime.fromisoformat("2026-03-16T10:00:00+08:00"),
                   max_turns=200)

        def at(turn):
            return datetime.fromisoformat(str(turn["perception"]["time"]))

        hers = [turn for turn in trace.agent_turns if turn["actor"] == "唐小岚"]
        self.assertTrue([turn for turn in hers if at(turn) > wake_time],
                        "睡眠中的长动作把 07:30 之后唐小岚的每一拍都吞掉了")
        delivered = [event["kind"] for turn in hers if at(turn) >= wake_time
                     for event in turn["perception"]["events"]]
        self.assertIn("private_wake", delivered,
                      "被唤醒的角色必须在自己的感知里看到那次唤醒（游标前移）")

    def test_a_named_scheduled_event_wakes_a_sleeper_on_the_chain_path(self):
        """② 睡眠中被点名的事件：先有可见的唤醒（`wait_woken`），再拿到回合。

        与 SleepWaitGates③ 同一断言，但走真实回合路径（`_execute_chain`）。
        修复前：08:00 的叫醒事件被 07:10 那次睡眠的推进吞掉，既没有 `wait_woken`
        也没有回合——D1 夜里的 `private_wake`/`reminder_due` 就是这样变成死信的。"""
        start = datetime.fromisoformat("2026-03-16T07:00:00+08:00")
        event = {"event": "mom_evening_call",
                 "time": "2026-03-16T08:00:00+08:00",
                 "notice": "妈妈又一次打来电话。",
                 "target": ["陈默"]}
        world = World(start=start, actors=[ActorState("陈默", "宿舍", role="mc")],
                      locations=[LocationState("宿舍")], scheduled=[event])
        agents = {"陈默": _ScriptedV4Agent([
            [("wait", {"duration_seconds": 600})],
            [("wait", {"duration_seconds": 12 * 3600, "sleep": True})],
            [("wait", {"duration_seconds": 60})]])}
        trace = Trace("v4-test", "wake-reachability-sleeper")
        _call_pool().submit(lambda: None).result(timeout=5)
        engine = AsyncEngine(world, agents, {"陈默": PrivateState("陈默")},
                             trace, None, decision_timeout=10,
                             max_wall_seconds=60, mc_idle_heartbeat=0)
        engine.run(stop_at=datetime.fromisoformat("2026-03-16T08:30:00+08:00"),
                   max_turns=200)

        call_time = datetime.fromisoformat("2026-03-16T08:00:00+08:00")
        woken = [event for event in world.event_log if event.kind == "wait_woken"]
        self.assertTrue(woken, "点名事件必须产生一次可见的唤醒")
        self.assertEqual(woken[0].time, call_time, "唤醒发生在点名的那一刻，不是之后")
        calls = _turns_from(trace, call_time)
        self.assertTrue(calls, "被叫醒之后必须在 08:00 拿到一个回合")
        self.assertIn("world_event", [event["kind"] for event in calls[0]["perception"]["events"]])


class PrivateWakeDeliveryGates(unittest.TestCase):
    """E110（票 109 D1-2-E5，D1 工件 real-20261018T100115）：心跳对睡着的人是死信。

    D1 20:41 与 21:36 给林瑶、21:40 给陈默的三条 `private_wake` 都落在 `wait
    sleep:true` 期间（林瑶 20:11→07:31、21:06→07:16，陈默 21:10→07:10）：
    `World.advance` 只把这个 kind `_commit` 进日志（可见性 {本人}），唤醒路径只
    在引擎的 `_wake_waiters` 里为 `world_event` 走，于是既没有 `wait_woken`，也没有
    任何回合——两人的最后一个回合停在 21:05 / 21:09，事件在游标之后等到天亮。

    不变式：一条点名某人的私有排程事件就是叫他（E106 的判据同样适用于
    `private_wake`）。到点时若目标在睡，先用 `World.wake_sleeper` 结束睡眠、留下
    可见的 `wait_woken`，再在那一拍给出回合；目标已不在世界里时记一条带 `reason`
    的 `private_wake_failed`，不静默成死信。
    """

    def test_a_private_wake_wakes_a_sleeping_mc_and_lands_a_turn(self):
        """07:00 入睡 12 小时，07:30 的心跳（生产路径 `_rearm_heartbeat`）
        必须叫醒他并在 07:30 换出一回合。

        修复前：07:30 的 `private_wake` 只进日志，陈默的下一个回合要等到 19:00
        睡眠自然完成——心跳对睡着的人是死信。"""
        start = datetime.fromisoformat("2026-03-16T07:00:00+08:00")
        wake_time = datetime.fromisoformat("2026-03-16T07:30:00+08:00")
        world = World(start=start, actors=[ActorState("陈默", "宿舍", role="mc")],
                      locations=[LocationState("宿舍")])
        agents = {"陈默": _ScriptedV4Agent([
            [("wait", {"duration_seconds": 12 * 3600, "sleep": True})],
            [("wait", {"duration_seconds": 60})]])}
        trace = Trace("v4-test", "private-wake-sleeper")
        _call_pool().submit(lambda: None).result(timeout=5)
        engine = AsyncEngine(world, agents, {"陈默": PrivateState("陈默")},
                             trace, None, decision_timeout=10,
                             max_wall_seconds=60, mc_idle_heartbeat=1800)
        engine.run(stop_at=datetime.fromisoformat("2026-03-16T07:33:00+08:00"),
                   max_turns=200)

        woken = [event for event in world.event_log if event.kind == "wait_woken"]
        self.assertEqual(len(woken), 1, "心跳必须留下一条可见的唤醒事实")
        self.assertEqual(woken[0].actor, "陈默")
        self.assertEqual(woken[0].time, wake_time)
        self.assertIn("陈默", woken[0].visible_to)
        calls = _turns_from(trace, wake_time)
        self.assertEqual([turn["actor"] for turn in calls], ["陈默"],
                         "被叫醒之后必须在 07:30 拿到一个回合")
        kinds = [event["kind"] for event in calls[0]["perception"]["events"]]
        self.assertIn("private_wake", kinds, "唤醒事件必须进得了他的游标")
        self.assertIn("wait_woken", kinds)
        self.assertFalse(world.actors["陈默"].sleeping)
        self.assertFalse([event for event in world.event_log
                          if event.kind == "action_completed"
                          and event.payload.get("sleep")],
                         "叫醒必须真的结束那段睡眠，而不是等它自然完成")

    def test_a_private_wake_for_an_absent_target_records_the_reason(self):
        """目标已不在世界里：记一条带 reason 的失败，不是一条没人能读的事件。

        修复前它照样写成 `private_wake`（可见性 {那个不存在的 id}），日志里
        与一条正常送达的心跳无法区分。"""
        start = datetime.fromisoformat("2026-03-16T07:00:00+08:00")
        fire = start + timedelta(minutes=5)
        world = World(start=start, actors=[ActorState("陈默", "宿舍", role="mc")],
                      locations=[LocationState("宿舍")])
        world.schedule_private_wake("早已离开的人", fire)
        world.advance(until=start + timedelta(minutes=10))

        wakes = [event for event in world.event_log
                 if event.kind.startswith("private_wake")]
        self.assertEqual([(event.kind, event.payload.get("reason")) for event in wakes],
                         [("private_wake_failed", "actor_not_present")])
        self.assertEqual(wakes[0].time, fire)
        self.assertFalse(wakes[0].visible_to & set(world.actors),
                         "一条没人能读的失败不得落进任何活人的感知")


class ExtraNoRequestTurnGates(unittest.TestCase):
    """E107（票 101，窗口 6 18:00）：extra 的零动作回合仍然静默。

    E90 修的是“模型被问了却没输出”（`reason: no_output`）。窗口 6 18:00 胡大叔那条
    （`result: none`、`calls: []`、`inner: null`、夜间 `system_turns` 无任何
    `empty_turn`）不是这一种：18:00 正是从窗口 5 检查点续跑的那一刻，restored extra
    的 `_extra_loop(name, "")` 第一拍既没有待答问题、也没有新听到的话，`needs_response`
    为假——**这一回合根本没有请求模型**（所以没有调用、没有 inner、没有 provider 错误）。
    判定依据就是本测试的两条读数：resume 后 provider 调用 0 次，而 trace 里仍有一行
    `result: none` 的 agent 回合。修法只加诊断：这一种也记一条 `empty_turn`
    （`reason: no_request`），让“没被问”与“被问了但没输出”在 trace 上可分辨。
    """

    def _engine(self, world, trace, stub):
        non_extra = [actor for actor in world.actors if world.actors[actor].role != "extra"]

        def agent(state, perception, affordances):
            return Intention(state.actor_id, "wait", {"duration_seconds": 60},
                             perception["world_version"])

        _call_pool().submit(lambda: None).result(timeout=5)
        return AsyncEngine(world, {actor: agent for actor in non_extra},
                           {actor: PrivateState(actor) for actor in non_extra},
                           trace, None, extra_call=stub, decision_timeout=10,
                           max_wall_seconds=60, extra_idle_seconds=3600)

    def test_a_wake_without_a_question_records_the_reason_instead_of_a_blank_line(self):
        world = load_story_pack().build_world()
        asked = set()

        def agent(state, perception, affordances):
            if state.actor_id == "陈默" and "ask" not in asked:
                asked.add("ask")
                return Intention(state.actor_id, "speak",
                                 {"text": "请问台账的事？", "volume": "normal",
                                  "to": ["陌生人"], "wait_response": False},
                                 perception["world_version"])
            return Intention(state.actor_id, "wait", {"duration_seconds": 60},
                             perception["world_version"])

        class _Stub:
            def __init__(self, replies):
                self.replies = list(replies)
                self.calls = 0

            def chat_with_tools(self, messages, tools):
                self.calls += 1
                return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]

        non_extra = [actor for actor in world.actors if world.actors[actor].role != "extra"]
        first_stub = _Stub([{"role": "assistant", "content": "我听见了。", "tool_calls": []}])
        trace = Trace("v4-test", "ticket101-extra-no-request")
        _call_pool().submit(lambda: None).result(timeout=5)
        engine = AsyncEngine(world, {actor: agent for actor in non_extra},
                             {actor: PrivateState(actor) for actor in non_extra},
                             trace, None, extra_call=first_stub, decision_timeout=10,
                             max_wall_seconds=60, extra_idle_seconds=3600)
        engine.run(stop_at=world.now + timedelta(minutes=6), max_turns=300)
        extra = next(a for a in world.actors.values() if a.role == "extra")
        self.assertTrue(first_stub.calls, "第一段里路人真的被问过")

        resume_stub = _Stub([{"role": "assistant", "content": "", "tool_calls": []}])
        resumed_trace = Trace("v4-test", "ticket101-extra-no-request-resume")
        resumed = self._engine(world, resumed_trace, resume_stub)
        resumed.restore_checkpoint(engine.checkpoint_state())
        resumed.run(stop_at=world.now + timedelta(minutes=3), max_turns=100)
        self.assertEqual(resume_stub.calls, 0,
                         "续跑的第一拍没有可答的东西，模型根本不该被请求")
        rows = [turn for turn in resumed_trace.system_turns
                if turn["request"].get("kind") == "empty_turn"
                and turn["result"].get("actor") == extra.id]
        self.assertTrue(rows, "没被问的回合也必须留一行可审计记录")
        self.assertEqual(rows[0]["result"]["reason"], "no_request")
        self.assertEqual(rows[0]["result"]["role"], "extra")
        silent_turns = [turn for turn in resumed_trace.agent_turns
                        if turn.get("actor") == extra.id and turn.get("result") == "none"]
        self.assertTrue(silent_turns, "被诊断的就是那一行 result: none 的回合")


class NoMechanismInSpeechGates(unittest.TestCase):
    """E108（票 101，窗口 6 19:12）：引擎机制被当众说成了剧情。

    陈默对在场三人说“刚才的留字只生成了下一位进入者才看得到的字条”。这句话在机制上
    是对的（burn 字条确实只给后到者），正因为对，才证明它是从 affordance hint 与回执
    里推出来的引擎知识，而不是任何世界内的感知。修法是一句提示层规则，只加在 MC 的
    工具说明上：主角可以说自己做了什么、谁看见了什么，不得向别人描述引擎怎么运作。
    """

    def test_the_mc_tool_surface_carries_the_rule(self):
        from harness.action_schema import EXTRA_TOOLS, NO_MECHANISM_IN_SPEECH, TOOLS
        leave_note = next(tool for tool in TOOLS
                          if tool["function"]["name"] == "leave_note")
        self.assertIn(NO_MECHANISM_IN_SPEECH, leave_note["function"]["description"])
        for tool in EXTRA_TOOLS:
            self.assertNotIn(NO_MECHANISM_IN_SPEECH, tool["function"]["description"],
                             f"路人的工具面不重复这条主角规则：{tool['function']['name']}")

    def test_the_npc_and_extra_prompts_do_not_carry_it(self):
        from harness.action_schema import NO_MECHANISM_IN_SPEECH
        from harness.character_loader import CharacterSeed
        from harness.npc_agent import (build_extra_briefing, build_extra_system_prompt,
                                       build_npc_system_prompt)
        npc_prompt = build_npc_system_prompt(
            CharacterSeed("宿管阿姨", "你是宿管阿姨。", "宿管阿姨自己的备忘。"), "今晚查寝。")
        extra_prompt = build_extra_system_prompt("咖啡店里的客人", "我只管喝咖啡。", "咖啡馆",
                                                 name="胡大叔")
        extra_briefing = build_extra_briefing(transcript=[], scene="（这里是咖啡馆）")
        for text, where in ((npc_prompt, "NPC 提示"), (extra_prompt, "路人系统提示"),
                            (extra_briefing, "路人简报")):
            self.assertNotIn(NO_MECHANISM_IN_SPEECH, text, where)
