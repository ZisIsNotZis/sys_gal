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
T1a world clock races during a slow deliberation (7:35->7:40) ... test_deliberation_pins_the_world_clock
T1b no auto-wait after text (reply arrives to a departed actor) . test_text_auto_wait_and_npc_reply_followup
T1c NPC memory-only turn parks with the reply uncomposed ........ test_text_auto_wait_and_npc_reply_followup
T2  compaction leaves an orphaned tool message at the head ...... test_compaction_never_keeps_an_orphaned_tool_message
T3  compaction call sends role:tool to the Responses endpoint ... test_compaction_call_translates_tool_roles_for_responses
T4  authored pre-run history compiles + flashback replays it .... test_authored_history_compiles_and_flashback_replays_it
E1  extra turns die silently at trace-record time ............. test_extra_turns_are_recorded_and_conversational
E2  extra self-wake chatter loop (replies to own speech) ...... test_extra_turns_are_recorded_and_conversational
E3  extras permanently silent: content-only replies dropped ... test_extra_turns_are_recorded_and_conversational
H1/H4 empty checkpoint written at launch ...................... test_launch_checkpoint_is_a_valid_loadable_trace
H2  duplicate run artifacts ................................... test_runner (unique run ids)
H3  failed/truncated artifact mislabeled as clean .............. test_trace_completion_gate_rejects_truncated_run (runner)
"""

import json
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.agent_state import PrivateState
from harness.engine import TICK_SECONDS, AsyncEngine
from harness.kernel import Intention, World
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


if __name__ == "__main__":
    unittest.main()
