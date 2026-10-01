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
                                                               test_private_line_is_withheld_and_never_submitted,
                                                               test_withheld_text_lands_in_the_private_turn_record,
                                                               test_genuine_line_still_broadcasts,
                                                               test_self_correction_note_states_the_rule,
                                                               test_prompt_names_the_inner_channel_and_stays_verbatim,
                                                               test_checker_counts_withheld_and_still_broadcast_private,
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
"""

import json
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.agent_state import PrivateState
from harness.engine import TICK_SECONDS, AsyncEngine
from harness.kernel import ActionRejected, ActorState, Intention, LocationState, World
from harness.runner import AgentFn, Runner
from harness.seed import load_story_pack
from harness.system import Ledger
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
        文本即说话 must apply to extras too)."""
        class ProseExtra:
            def __init__(self):
                self.calls = 0

            def chat_with_tools(self, messages, tools):
                self.calls += 1
                if self.calls == 1:
                    return {"role": "assistant", "content": "", "tool_calls": [
                        {"id": "c1", "type": "function",
                         "function": {"name": "speak",
                                      "arguments": '{"text":"我知道那笔记录的事。"}'}}]}
                # Later turns: inline decision JSON instead of a tool call —
                # the shape that used to leak verbatim into the world speech.
                return {"role": "assistant",
                        "content": json.dumps({"inner": "想想再答",
                                               "name": "speak",
                                               "arguments": {"text": "后续回答"}},
                                              ensure_ascii=False),
                        "tool_calls": []}

        pack = load_story_pack()
        world = pack.build_world()
        trace = Trace("v4-test", "historical-gate-extra-turns")
        asked = set()

        def agent(state, perception, affordances):
            # Ticket 22: ask is merged into speak — to=["陌生人"] asks the
            # room's passers-by; auto-wait is engine-side, so this test's
            # intentions carry it implicitly.
            if state.actor_id == "陈默" and state.actor_id not in asked:
                asked.add(state.actor_id)
                return Intention(state.actor_id, "speak",
                                 {"text": "请问台账的事？", "volume": "normal",
                                  "to": ["陌生人"]},
                                 perception["world_version"])
            # One follow-up to the same stranger (routed to the existing
            # partner extra), then wait forever.
            if state.actor_id == "陈默" and len(asked) == 1:
                asked.add(state.actor_id + "-2")
                return Intention(state.actor_id, "speak",
                                 {"text": "那签字的人是谁？", "volume": "normal",
                                  "to": ["陌生人"]},
                                 perception["world_version"])
            return Intention(state.actor_id, "wait",
                             {"duration_seconds": 3600},
                             perception["world_version"])

        non_extra = [a for a in world.actors if world.actors[a].role != "extra"]
        agents = {a: agent for a in non_extra}
        states = {a: PrivateState(a) for a in non_extra}
        stub = ProseExtra()
        engine = AsyncEngine(world, agents, states, trace, None,
                             extra_call=stub, decision_timeout=10,
                             max_wall_seconds=60, extra_idle_seconds=60)
        stop = datetime.fromisoformat("2026-03-16T07:06:00+08:00")
        reason = engine.run(stop_at=stop, max_turns=300)
        self.assertEqual(reason, "stop_at_reached")

        # E1: the extra's turns are recorded with role="extra" — exactly one
        # extra spawned, two turns (initial + follow-up ask routed to it).
        extra_turns = [t for t in trace.agent_turns if t.get("role") == "extra"]
        self.assertEqual(len(extra_turns), 2)
        self.assertTrue(all(t["result"] == "submitted" for t in extra_turns))
        self.assertEqual(len({t["actor"] for t in extra_turns}), 1)

        # Ticket 22 timing: the passer-by spawns when the utterance LANDS
        # (the speak's completion tick, one minute after the ask), and its
        # answer lands within the pinned 1-tick window — never minutes late.
        arrived = [e for e in world.event_log if e.kind == "extra_arrived"]
        self.assertEqual(len(arrived), 1)
        self.assertEqual(arrived[0].time.strftime("%H:%M"), "07:01")
        first_answer = next(e for e in world.event_log if e.kind == "speech"
                            and "那笔记录" in str(e.payload.get("text", "")))
        self.assertLessEqual((first_answer.time - arrived[0].time).total_seconds(), 60)

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
        update_memory; 开柜/取件 -> take."""
        world = self._phone_scene()
        engine, agents = _chain_engine(world)
        cases = [("call", {"target": "陈默妈", "text": "喂"}, '"name": "text"'),
                 ("phone", {"number": "1395731xxxx"}, '"name": "text"'),
                 ("sign", {"item": "移交存根"}, "update_memory"),
                 ("annotate", {"item": "2013年台风台账"}, "update_memory"),
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
    """Ticket 56 (real-20261001T065553, five independent reviewers).

    The `inner` field was clean, but private reasoning written into the
    assistant's plain text was broadcast as speech by the T1 ruling. These
    gates pin the high-precision withholding guard, its private record and
    self-correction, and that genuine lines are untouched."""

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

    def test_private_line_is_withheld_and_never_submitted(self):
        """A private line must not become a `speak` event, even though the
        session would otherwise have handed it to T1 as plain text."""
        world, _trace, _agent = self._engine(_T56_PRIVATE_LINES[0])
        self.assertEqual(self._speeches(world), [],
                         "私密正文不得广播为 speech")

    def test_withheld_text_lands_in_the_private_turn_record(self):
        """The withheld line is kept on that actor's private turn and the
        actor is shown one self-correction so the next turn can self-fix."""
        world, trace, agent = self._engine(_T56_PRIVATE_LINES[1])
        withheld = [t for t in trace.agent_turns
                    if t["actor"] == "陈默" and t.get("withheld_private")]
        self.assertTrue(withheld, "私密正文没有记入角色私密记录")
        self.assertIn("不急着对陈默说", str(withheld[0].get("withheld_text")))
        messages = agent.session_snapshot()["messages"]
        self.assertTrue(
            any(m.get("role") == "user" and "不是你说出口的话" in str(m.get("content"))
                for m in messages),
            "缺失自纠提示（模型看不到自己错在哪）")

    def test_genuine_line_still_broadcasts(self):
        """The guard must not swallow real speech."""
        world, trace, _agent = self._engine("档案室这边我来盯着，你先去忙。")
        self.assertTrue(any("档案室这边我来盯着" in line for line in self._speeches(world)),
                        "真台词被护栏吞掉了")
        self.assertFalse(any(t.get("withheld_private") for t in trace.agent_turns))

    def test_self_correction_note_states_the_rule(self):
        from harness.natural_agent import PRIVATE_CONTENT_NOTE
        self.assertIn("那属于心里话，不是你说出口的话", PRIVATE_CONTENT_NOTE)
        self.assertIn("世界没有把它当台词", PRIVATE_CONTENT_NOTE)
        self.assertIn("inner", PRIVATE_CONTENT_NOTE)

    def test_prompt_names_the_inner_channel_and_stays_verbatim(self):
        """(1) §1 says the body is only spoken words and plans/judgements/
        asides/protocol talk go in `inner`; runtime prompt == doc §1 and §4
        agrees, so the contract cannot drift."""
        from harness.natural_agent import SYSTEM_PROMPT_V4
        doc = (Path(__file__).parents[2] / "docs" / "V4-AGENT-INTERFACE.md").read_text(
            encoding="utf-8")
        self.assertIn("正文只写你说出口的话", SYSTEM_PROMPT_V4)
        self.assertIn("对协议的说明一律写进工具调用的 inner", SYSTEM_PROMPT_V4)
        self.assertIn(SYSTEM_PROMPT_V4, doc,
                      "§1 的 system prompt 必须与运行时逐字一致")
        section4 = doc.split("## 4.", 1)[1].split("## 5.", 1)[0]
        self.assertIn("inner", section4,
                      "§4 必须与 §1 一样写明私密内容走 inner")

    def test_checker_counts_withheld_and_still_broadcast_private(self):
        """(3) The system-health block reports how many turns were withheld
        as private reasoning AND how many broadcast speeches still match the
        predicate (a pre-fix artifact's leak evidence). Review only."""
        module = _checker_module()
        leaked = _speech_artifact(
            [(9, 5, "林瑶", "记忆调用格式错了——指令词得单独占一格。")])["world_events"]
        data = {
            "agent_turns": [
                {"actor": "陈默", "role": "mc", "withheld_private": True,
                 "withheld_text": "我一个字不碰",
                 "perception": {"time": "2026-03-16T09:00:00+08:00"}},
                {"actor": "班长", "role": "mc",
                 "perception": {"time": "2026-03-16T09:01:00+08:00"}},
            ],
            "world_events": leaked,
            "sessions": {},
        }
        report = module.health_report(data, 1)
        reading = report["正文被判为私密而未广播"]
        self.assertIn("1（", reading)
        self.assertIn("仍被广播的私密正文 1", reading)


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


if __name__ == "__main__":
    unittest.main()
