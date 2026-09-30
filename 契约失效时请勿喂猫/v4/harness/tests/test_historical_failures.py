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
H1/H4 empty checkpoint written at launch ...................... test_launch_checkpoint_is_a_valid_loadable_trace
H2  duplicate run artifacts ................................... test_runner (unique run ids)
H3  failed/truncated artifact mislabeled as clean .............. test_trace_completion_gate_rejects_truncated_run (runner)
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
        """E42 (tickets 42-2/3/4): the extra prompt never said who it was, so
        韩大叔 called itself by third person and mailed its own name into
        `to` (`unknown or ambiguous speak recipient`); with no capability or
        assertion bounds it invented a 抄件 signature date (unregistered
        entity) and narrated 开柜/递件 as done while its only tool is speak."""
        from harness.npc_agent import build_extra_system_prompt

        prompt = build_extra_system_prompt("兼职店员", "三点前守好吧台", "半坡咖啡馆",
                                           name="韩大叔")
        self.assertIn("韩大叔", prompt, "extra 提示词必须带上自己的名字")
        self.assertIn("第三人称", prompt, "必须禁止第三人称自称")
        self.assertIn("to", prompt)  # to 只能是在场他人
        self.assertIn("在场", prompt)
        self.assertIn("只能说话", prompt, "只能 speak 的角色不得叙述物理动作")
        self.assertIn("已经发生", prompt)
        self.assertIn("传闻", prompt)
        self.assertIn("具体细节", prompt)
        self.assertIn("签名", prompt)  # 反例清单：签名/日期这类细节
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


class ExtraCheckpointGates(unittest.TestCase):
    """E50 (ticket 50): a live extra's full mutable state must survive a
    checkpoint round-trip. A half-day resume (d1-am -> d1-pm) starts a new
    engine from a checkpoint that already has an extra on stage; if the
    checkpoint dropped system_prompt the extra's loop died with a KeyError,
    and dropping context_cursor/pending_question lost the reply window and
    the unanswered question."""

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


if __name__ == "__main__":
    unittest.main()
