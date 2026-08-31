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
F5  rejection retry loop (Gao archive move x3) ................. test_runner (repeated_rejection, alternatives),
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
H1/H4 empty checkpoint written at launch ...................... test_launch_checkpoint_is_a_valid_loadable_trace
H2  duplicate run artifacts ................................... test_runner (unique run ids)
H3  failed/truncated artifact mislabeled as clean .............. test_trace_completion_gate_rejects_truncated_run (runner)
"""

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.agent_state import PrivateState
from harness.kernel import Intention
from harness.runner import Runner
from harness.seed import load_story_pack
from harness.system import Ledger
from harness.trace import Trace, verify_event_log
from harness.replay import replay_world


def _lean_wait_agents(world):
    """Deterministic agents that accept the System once, then wait."""
    def agent(state, perception, affordances):
        offered = {str(option.get("kind")) for option in affordances}
        if state.actor_id == "chen-mo" and "system_accept" in offered:
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
        endpoint = str(pack.manifest["clock"]["stop"])
        trace = Trace("v3-test", "historical-gate-endpoint")
        reason = Runner(world, _lean_wait_agents(world), states, trace, ledger).run(
            stop_at=datetime.fromisoformat(endpoint), max_turns=100_000)
        self.assertEqual(reason, "stop_at_reached")
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
            if state.actor_id == "chen-mo":
                step = steps[state.actor_id]
                steps[state.actor_id] += 1
                if step == 0:
                    return Intention("chen-mo", "wait", {"duration_seconds": 60},
                                     perception["world_version"])
                if step == 1:
                    return Intention("chen-mo", "search", {}, perception["world_version"])
                if step == 2:
                    return Intention("chen-mo", "drop", {"item": "old-permit-form"},
                                     perception["world_version"])
                if step == 3:
                    return Intention("chen-mo", "send_message",
                                     {"target": "lin-yao", "text": "The form is filed."},
                                     perception["world_version"])
                if step == 4:
                    return Intention("chen-mo", "read", {"document": "old-permit-form"},
                                     perception["world_version"])
                if step == 5:
                    return Intention("chen-mo", "move", {"target": "archive",
                                                         "duration_seconds": 900},
                                     perception["world_version"])
            return None

        def recorder(state, perception, affordances):
            return agent(state, perception, affordances)

        def record_world_result(message):
            feedback.append(message)

        recorder.record_world_result = record_world_result
        agents = {actor: (recorder if actor == "chen-mo" else agent)
                  for actor in world.actors}
        Runner(world, agents, states, Trace("v3-test", "historical-gate-feedback")).run(
            stop_at=datetime.fromisoformat("2026-03-16T20:00:00+08:00"), max_turns=1000)
        combined = " ".join(feedback)
        self.assertNotIn("no immediate physical change", combined)
        self.assertIn("wait", combined)          # wait in progress
        self.assertIn("searched", combined)      # search result
        self.assertIn("dropped", combined)       # drop consequence
        self.assertIn("delivered", combined)     # message delivery
        self.assertIn("read", combined)          # document read
        self.assertIn("walking", combined)       # move in progress

    def test_rejected_loop_is_safe_and_instructive(self):
        """F5/P2: a stubborn agent keeps rejecting with actionable reasons,
        never produces an engine error, and never freezes the world."""
        world = load_story_pack().build_world()
        states = {actor: PrivateState(actor) for actor in world.actors}

        def stubborn(state, perception, affordances):
            if state.actor_id == "chen-mo":
                return Intention("chen-mo", "move", {
                    "target": "old-basement", "duration_seconds": 1200},
                    perception["world_version"])
            return None

        trace = Trace("v3-test", "historical-gate-rejected-loop")
        Runner(world, {actor: stubborn for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-21T10:00:00+08:00"), max_turns=2000)
        turns = [turn for turn in trace.agent_turns if turn["actor"] == "chen-mo"]
        self.assertTrue(turns)
        self.assertTrue(all(turn["result"] == "rejected" for turn in turns))
        self.assertTrue(all(turn["error"] for turn in turns))
        self.assertFalse(any(event.kind == "action_started" for event in world.event_log))
        # Rejection feedback tracks state instead of repeating one stale reason:
        # while the basement is closed the reason says so; after it opens on
        # March 18 the reason becomes a path explanation. This is the regression
        # for the v2/v3 pattern of re-attempting one illegal move unchanged.
        reasons = [turn["error"] for turn in turns]
        self.assertTrue(any("closed" in reason for reason in reasons))
        self.assertTrue(any("no direct path" in reason for reason in reasons))
        # The world still advanced through the schedule; one stuck actor is not a deadlock.
        self.assertGreaterEqual(world.now.isoformat(), "2026-03-18T10:00:00+08:00")

    def test_seed_closed_locations_all_have_a_scheduled_opening_effect(self):
        """I02/P4: no seed location may be a permanent dead-end."""
        pack = load_story_pack()
        closed = [row["id"] for row in pack.locations if not row.get("open", True)]
        self.assertTrue(closed, "expected at least one intentionally closed location")
        opened = {str(effect["id"]) for row in pack.scheduled
                  for effect in row.get("effects", []) if effect.get("op") == "open_location"}
        self.assertEqual(opened, set(closed),
                         "every closed location must have a scheduled opening effect")

    def test_seed_route_graph_is_connected(self):
        """P5: any two characters can reach a common place; co-location is feasible."""
        pack = load_story_pack()
        graph = {row["id"]: set() for row in pack.locations}
        for row in pack.routes:
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

    def test_send_message_without_target_is_helpful(self):
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
            world.submit(Intention("a", "send_message",
                                   {"text": "hello"}, world.version))
        self.assertIn("target", str(ctx.exception))
        with self.assertRaises(ActionRejected) as ctx:
            world.submit(Intention("a", "send_message",
                                   {"to": "b", "text": "hello"}, world.version))
        self.assertIn("target", str(ctx.exception))
        self.assertIn("to", str(ctx.exception))
        with self.assertRaises(ActionRejected) as ctx:
            world.submit(Intention("a", "give", {"item": "x"}, world.version))
        self.assertIn("target", str(ctx.exception))

    def test_document_action_with_wrong_key_is_helpful(self):
        """P8: read/copy/label/annotate submitted with the wrong argument key
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
        for kind in ("read", "copy", "label", "annotate"):
            args = {"item": "ledger"} if kind in ("read", "copy") else {"item": "ledger", "label": "x"}
            with self.assertRaises(ActionRejected) as ctx:
                world.submit(Intention("a", kind, args, world.version))
            self.assertIn("document", str(ctx.exception), kind)
            self.assertIn("item", str(ctx.exception), kind)

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


if __name__ == "__main__":
    unittest.main()
