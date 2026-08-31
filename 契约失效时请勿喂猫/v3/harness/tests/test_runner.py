import unittest
import time
from datetime import datetime

from harness.agent_state import PrivateState
from harness.kernel import Intention
from harness.prompt import render_world_message
from harness.runner import Runner
from harness.seed import create_world
from harness.trace import Trace
from harness.system import Ledger
from harness.character_loader import CharacterSeed
from harness.natural_agent import make_persistent_agent


class RunnerTests(unittest.TestCase):
    def test_trace_failure_checkpoint_is_auditable_and_does_not_add_fake_event(self):
        world = create_world()
        trace = Trace("v2-test", "failed-checkpoint")
        before = len(world.event_log)
        error = RuntimeError("provider HTTP 502 after 3 attempts")
        trace.fail(reason="aborted_provider_or_runtime_error", world=world, error=error)
        snapshot = trace.snapshot(world)
        self.assertEqual(snapshot["outcome"]["reason"], "aborted_provider_or_runtime_error")
        self.assertEqual(snapshot["outcome"]["error"]["message"], str(error))
        self.assertEqual(len(world.event_log), before)
        self.assertEqual(snapshot["replay"]["last_event_id"], None)

    def test_exhausted_provider_failure_is_checkpointed_before_run_raises(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        trace = Trace("v2-test", "provider-failure")
        checkpoints = []
        error = RuntimeError("provider HTTP 502 after 6 attempts")
        def checkpoint():
            checkpoints.append(trace.snapshot(world))
        trace.fail(reason="aborted_provider_or_runtime_error", world=world, error=error)
        checkpoint()
        self.assertEqual(checkpoints[0]["outcome"]["error"]["message"], str(error))
        self.assertEqual(checkpoints[0]["replay"]["event_count"], 0)

    def test_unique_run_ids_do_not_collide(self):
        from harness.trace import new_run_id
        self.assertNotEqual(new_run_id("probe"), new_run_id("probe"))

    def test_terminal_provider_error_is_distinguished_from_retryable_error(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def broken_agent(state, perception, affordances):
            error = RuntimeError("provider retry budget exhausted")
            error.retryable = True
            error.retry_exhausted = True
            raise error
        trace = Trace("v3-test", "terminal-provider")
        reason = Runner(world, {actor: broken_agent for actor in world.actors}, states, trace,
                        decision_timeout=1, fail_fast=True).run(max_turns=20)
        self.assertEqual(reason, "agent_failure")
        self.assertTrue(all(t["error"].startswith("retry-exhausted:")
                            for t in trace.agent_turns))

    def test_runner_records_bounded_gm_request_without_agent_error(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        seeds = {actor: CharacterSeed(actor, "A person.", "Private facts.") for actor in world.actors}
        def model(messages):
            return "I attempt an action the world did not offer."
        def malformed_gm(text, perception, affordances):
            return {"unexpected": "plot invention"}
        agents = {actor: make_persistent_agent(seeds[actor], model, malformed_gm)
                  for actor in world.actors}
        trace = Trace("v2-test", "gm-audit")
        Runner(world, agents, states, trace, decision_timeout=1).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:01:00+08:00"), max_turns=20)
        self.assertTrue(trace.gm_turns)
        self.assertTrue(all(turn["result"] == "none" for turn in trace.agent_turns))
        self.assertTrue(all(turn["error"] is None for turn in trace.agent_turns))
        self.assertTrue(all(record["actor"] in world.actors for record in trace.gm_turns))
        self.assertTrue(all("private_state" not in record["perception"] for record in trace.gm_turns))
        self.assertTrue(all(record["error"] and "ValueError" in record["error"]
                            for record in trace.gm_turns))
        snapshot = trace.snapshot(world)
        self.assertEqual(len(snapshot["gm_turns"]), len(trace.gm_turns))

    def test_batch_timeout_is_a_real_deadline_and_checkpoint_runs(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def slow_agent(state, perception, affordances):
            time.sleep(2)
            return None
        trace = Trace("v2-test", "timeout")
        checkpoints = []
        started = time.monotonic()
        Runner(world, {actor: slow_agent for actor in world.actors}, states, trace,
               decision_timeout=0.05, checkpoint=lambda: checkpoints.append(True)).run(
                   stop_at=datetime.fromisoformat("2026-03-16T07:01:00+08:00"), max_turns=20)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 0.5)
        self.assertTrue(checkpoints)
        self.assertTrue(trace.agent_turns)
        self.assertTrue(all(t["result"] == "decision_timeout" for t in trace.agent_turns))

    def test_fail_fast_stops_before_advancing_after_decision_timeout(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def slow(state, perception, affordances):
            time.sleep(0.2)
            return None
        trace = Trace("v3-test", "timeout-stop-boundary")
        reason = Runner(world, {actor: slow for actor in world.actors}, states, trace,
                        decision_timeout=0.01, fail_fast=True).run(
                            stop_at=datetime.fromisoformat("2026-03-16T08:00:00+08:00"))
        self.assertEqual(reason, "agent_failure")
        self.assertEqual(world.now.isoformat(), "2026-03-16T07:00:00+08:00")

    def test_timeout_does_not_call_a_persistent_agent_again(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        calls = {actor: 0 for actor in world.actors}
        def slow(state, perception, affordances):
            calls[state.actor_id] += 1
            time.sleep(0.2)
            return None
        trace = Trace("v3-test", "timeout-no-overlap")
        Runner(world, {actor: slow for actor in world.actors}, states, trace,
                decision_timeout=0.01, fail_fast=True).run(max_turns=100)
        self.assertEqual(calls, {actor: 1 for actor in world.actors})

    def test_agents_in_a_batch_are_called_concurrently(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def slow_agent(state, perception, affordances):
            time.sleep(0.08)
            return None
        trace = Trace("v2-test", "concurrency")
        started = time.monotonic()
        Runner(world, {actor: slow_agent for actor in world.actors}, states, trace,
               decision_timeout=1).run(stop_at=datetime.fromisoformat("2026-03-16T07:01:00+08:00"), max_turns=20)
        self.assertLess(time.monotonic() - started, 0.25)

    def test_fail_fast_stops_after_recording_provider_failure(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def broken_agent(state, perception, affordances):
            raise ValueError("malformed model response")
        trace = Trace("v2-test", "fail-fast")
        checkpoints = []
        reason = Runner(world, {actor: broken_agent for actor in world.actors}, states, trace,
                        decision_timeout=0.2, checkpoint=lambda: checkpoints.append(True),
                        fail_fast=True).run(stop_at=datetime.fromisoformat("2026-03-16T08:00:00+08:00"))
        self.assertEqual(reason, "agent_failure")
        self.assertTrue(checkpoints)
        self.assertTrue(all(t["result"] == "agent_error" for t in trace.agent_turns))

    def test_fail_fast_stops_after_exhausted_retryable_provider_failure(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def broken_agent(state, perception, affordances):
            error = RuntimeError("provider retry budget exhausted")
            error.retryable = True
            error.retry_exhausted = True
            raise error
        trace = Trace("v3-test", "retry-exhausted")
        reason = Runner(world, {actor: broken_agent for actor in world.actors}, states, trace,
                        decision_timeout=0.2, fail_fast=True).run(
                            stop_at=datetime.fromisoformat("2026-03-16T08:00:00+08:00"))
        self.assertEqual(reason, "agent_failure")
        self.assertTrue(all(t["error"].startswith("retry-exhausted:")
                            for t in trace.agent_turns))

    def test_retryable_agent_failure_does_not_stop_objective_world(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        attempts = {actor: 0 for actor in world.actors}
        def agent(state, perception, affordances):
            attempts[state.actor_id] += 1
            if state.actor_id == "chen-mo" and attempts[state.actor_id] == 1:
                error = RuntimeError("temporary upstream failure")
                error.retryable = True
                raise error
            return None
        trace = Trace("v2-test", "retryable-agent-failure")
        reason = Runner(world, {actor: agent for actor in world.actors}, states, trace,
                        decision_timeout=1, fail_fast=False, max_transient_failures=2).run(
                            stop_at=datetime.fromisoformat("2026-03-16T08:20:00+08:00"), max_turns=100)
        self.assertEqual(reason, "stop_at_reached")
        self.assertGreaterEqual(attempts["chen-mo"], 2)

    def test_exhausted_retryable_provider_failure_gets_bounded_runner_recovery(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        attempts = {actor: 0 for actor in world.actors}

        def agent(state, perception, affordances):
            attempts[state.actor_id] += 1
            if state.actor_id == "chen-mo" and attempts[state.actor_id] <= 2:
                error = RuntimeError("provider HTTP 502 after bounded retries")
                error.retryable = True
                error.retry_exhausted = True
                error.runner_retryable = True
                raise error
            return Intention(state.actor_id, "wait", {"duration_seconds": 60},
                             perception["world_version"])

        trace = Trace("v3-test", "runner-provider-recovery")
        reason = Runner(world, {actor: agent for actor in world.actors}, states, trace,
                        decision_timeout=1, fail_fast=False, max_transient_failures=3).run(
                            stop_at=datetime.fromisoformat("2026-03-16T08:20:00+00:00"),
                            max_turns=10000)
        self.assertEqual(reason, "stop_at_reached")
        self.assertGreaterEqual(attempts["chen-mo"], 3)
        self.assertFalse(any(t["result"] == "agent_error" for t in trace.agent_turns))
        self.assertGreaterEqual(sum(t["result"] == "retryable_failure" for t in trace.agent_turns), 2)

    def test_runner_retry_delay_is_simulated_and_bounded(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        attempts = {actor: 0 for actor in world.actors}
        def agent(state, perception, affordances):
            attempts[state.actor_id] += 1
            if state.actor_id == "chen-mo" and attempts[state.actor_id] == 1:
                error = RuntimeError("temporary provider failure")
                error.retryable = True
                error.runner_retryable = True
                raise error
            return None
        trace = Trace("v3-test", "runner-retry-delay")
        reason = Runner(world, {actor: agent for actor in world.actors}, states, trace,
                        retry_delay_seconds=300).run(
                            stop_at=datetime.fromisoformat("2026-03-16T07:10:00+00:00"),
                            max_turns=100)
        self.assertEqual(reason, "stop_at_reached")
        self.assertGreaterEqual(attempts["chen-mo"], 2)
        self.assertTrue(any(t["result"] == "retryable_failure" for t in trace.agent_turns))

    def test_runner_stops_repeated_provider_retry_loop_at_wall_deadline(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}

        def permanently_broken(state, perception, affordances):
            error = RuntimeError("upstream empty response")
            error.retryable = True
            error.runner_retryable = True
            raise error

        trace = Trace("v3-test", "wall-deadline")
        checkpoints = []
        started = time.monotonic()
        reason = Runner(world, {actor: permanently_broken for actor in world.actors}, states,
                        trace, decision_timeout=1, fail_fast=False,
                        max_transient_failures=100, retry_delay_seconds=1,
                        max_wall_seconds=0.25,
                        checkpoint=lambda: checkpoints.append(trace.snapshot(world))).run(
                            stop_at=datetime.fromisoformat("2027-03-16T08:00:00+00:00"),
                            max_turns=100000)
        elapsed = time.monotonic() - started
        self.assertEqual(reason, "wall_clock_deadline_reached")
        self.assertLess(elapsed, 0.5)
        self.assertTrue(trace.agent_turns)
        self.assertTrue(any(t["result"] in {"retryable_failure", "wall_clock_deadline"}
                            for t in trace.agent_turns))
        self.assertTrue(checkpoints)

    def test_realistic_long_wait_affordance_is_available(self):
        world = create_world()
        waits = [x for x in world.affordances("chen-mo") if x["kind"] == "wait"]
        self.assertIn(3600, [x["duration_seconds"] for x in waits])

    def test_malformed_private_memory_does_not_kill_valid_action(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def malformed(state, perception, affordances):
            return (Intention(state.actor_id, "wait", {"duration_seconds": 60},
                               perception["world_version"]),
                    {"memories": [42]})
        trace = Trace("v2-test", "bad-memory")
        reason = Runner(world, {actor: malformed for actor in world.actors}, states, trace,
                        fail_fast=True, checkpoint=lambda: None).run(
                            stop_at=datetime.fromisoformat("2026-03-16T08:00:00+08:00"))
        self.assertEqual(reason, "stop_at_reached")
        turn = next(t for t in trace.agent_turns if t["actor"] == "chen-mo")
        self.assertEqual(turn["result"], "submitted")
        self.assertTrue(turn["error"].startswith("private_update_ignored:"))

    def test_string_private_memory_is_normalized_without_losing_valid_action(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def agent(state, perception, affordances):
            return (Intention(state.actor_id, "wait", {"duration_seconds": 60},
                              perception["world_version"]),
                    {"memories": ["I remember the accepted wait."]})
        trace = Trace("v3-test", "string-memory")
        Runner(world, {actor: agent for actor in world.actors}, states, trace,
               fail_fast=True).run(stop_at=datetime.fromisoformat("2026-03-16T07:01:00+00:00"))
        self.assertEqual(states["chen-mo"].memories[0], {"text": "I remember the accepted wait."})
        turn = next(t for t in trace.agent_turns if t["actor"] == "chen-mo")
        self.assertIsNone(turn["error"])
    def test_runner_records_every_private_turn_and_reaches_seed_stop(self):
        world = create_world()
        states = {actor: PrivateState(actor, goals=("continue ordinary life",)) for actor in world.actors}

        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo" and perception["time"].endswith("07:00:00+08:00"):
                return Intention(state.actor_id, "system_accept", {"case": "ambiguous-obligations"}, perception["world_version"])
            return Intention(state.actor_id, "wait", {"duration_seconds": 60}, perception["world_version"])

        trace = Trace("v2-test", "runner")
        ledger = Ledger({"Where is the red whistle?": "old neighborhood basement"})
        Runner(world, {actor: agent for actor in world.actors}, states, trace, ledger).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:00:00+08:00"), max_turns=1000)
        self.assertEqual(world.now.isoformat(), "2026-03-16T08:00:00+08:00")
        self.assertGreaterEqual(len(trace.agent_turns), len(world.actors))
        self.assertTrue(ledger.accepted)
        self.assertTrue(world.replayable_log())
        self.assertEqual(trace.snapshot(world)["replay"]["world_versions_contiguous"], True)

    def test_system_is_not_a_world_action_but_can_commit_through_runner(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo" and not any(e["kind"] == "system_case_accepted" for e in perception["events"]):
                return Intention("chen-mo", "system_accept", {"case": "ambiguous-obligations"}, perception["world_version"])
            return None
        trace = Trace("v2-test", "system")
        Runner(world, {actor: agent for actor in world.actors}, states, trace, Ledger()).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:01:00+08:00"), max_turns=20)
        self.assertTrue(any(e.kind == "system_case_accepted" for e in world.event_log))
        with self.assertRaises(Exception):
            world.submit(Intention("chen-mo", "system_accept", {"case": "ambiguous-obligations"}, world.version))

    def test_system_reward_feedback_reaches_bound_character_in_natural_language(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        feedback = []

        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo":
                if not any(e["kind"] == "system_case_accepted" for e in perception["events"]):
                    return Intention("chen-mo", "system_accept", {"case": "ambiguous-obligations"}, perception["world_version"])
                if any(e["kind"] == "system_case_accepted" for e in perception["events"]):
                    return Intention("chen-mo", "system_query", {"question": "Where is the red whistle?"}, perception["world_version"])
            return None

        class Recorder:
            def __call__(self, state, perception, affordances):
                return agent(state, perception, affordances)
            def record_world_result(self, message):
                feedback.append(message)

        agents = {actor: (Recorder() if actor == "chen-mo" else agent) for actor in world.actors}
        trace = Trace("v2-test", "system-reward-feedback")
        Runner(world, agents, states, trace,
               Ledger({"Where is the red whistle?": "old neighborhood basement"})).run(
                   stop_at=datetime.fromisoformat("2026-03-16T07:01:00+00:00"), max_turns=20)
        self.assertTrue(any("The Ledger granted your reward" in message
                            and "objective clarification" in message
                            for message in feedback))
        self.assertEqual([event.kind for event in world.event_log if event.kind.startswith("system_")],
                         ["system_case_accepted", "system_answer", "system_reward_granted"])
        system_event_ids = {event.id for event in world.event_log if event.kind.startswith("system_")}
        recorded_ids = {event_id for turn in trace.agent_turns for event_id in turn["event_ids"]}
        self.assertTrue(system_event_ids <= recorded_ids)

    def test_system_acceptance_is_durable_after_event_cursor_advances(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        choices = []

        def agent(state, perception, affordances):
            if state.actor_id != "chen-mo":
                return None
            offered = {str(option.get("kind")) for option in affordances}
            choices.append((perception["time"], offered))
            if "system_accept" in offered:
                return Intention(state.actor_id, "system_accept",
                                 {"case": "ambiguous-obligations"}, perception["world_version"])
            return Intention(state.actor_id, "wait", {"duration_seconds": 60},
                             perception["world_version"])

        Runner(world, {actor: agent for actor in world.actors}, states,
               Trace("v3-test", "durable-system-status"), Ledger()).run(
                   stop_at=datetime.fromisoformat("2026-03-16T07:03:00+00:00"), max_turns=100)
        self.assertEqual([kind for _, offered in choices for kind in ("system_accept",)
                          if kind in offered], ["system_accept"])

    def test_system_penalty_feedback_reaches_bound_character_in_natural_language(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        feedback = []

        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo":
                return Intention("chen-mo", "system_decline", {"case": "ambiguous-obligations"}, perception["world_version"])
            return None

        class Recorder:
            def __call__(self, state, perception, affordances):
                return agent(state, perception, affordances)
            def record_world_result(self, message):
                feedback.append(message)

        agents = {actor: (Recorder() if actor == "chen-mo" else agent) for actor in world.actors}
        Runner(world, agents, states, Trace("v2-test", "system-penalty-feedback"), Ledger()).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:01:00+00:00"), max_turns=20)
        self.assertTrue(any("The Ledger applied a penalty" in message
                            and "offered clarification is forfeited" in message
                            for message in feedback))

    def test_system_feedback_uses_configured_name_not_hardcoded_label(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        feedback = []

        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo":
                return Intention("chen-mo", "system_accept",
                                 {"case": "ambiguous-obligations"},
                                 perception["world_version"])
            return None

        class Recorder:
            def __call__(self, state, perception, affordances):
                return agent(state, perception, affordances)

            def record_world_result(self, message):
                feedback.append(message)

        agents = {actor: (Recorder() if actor == "chen-mo" else agent)
                  for actor in world.actors}
        ledger = Ledger({}, {"name": "the Quill", "bound_actor": "chen-mo",
                             "case_id": "ambiguous-obligations",
                             "terms": ["x"], "reward": "a clue", "query_limit": 1})
        Runner(world, agents, states, Trace("v3-test", "system-name"), ledger).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:01:00+08:00"), max_turns=20)
        self.assertTrue(any("Quill" in message for message in feedback))
        self.assertFalse(any("The Ledger" in message for message in feedback))

    def test_runner_records_event_ids_and_private_updates(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo":
                return (Intention("chen-mo", "wait", {"duration_seconds": 60}, perception["world_version"]),
                        {"private_notes": ["decided to wait"]})
            return None
        trace = Trace("v2-test", "metadata")
        Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:01:00+08:00"), max_turns=20)
        turn = next(x for x in trace.agent_turns if x["actor"] == "chen-mo")
        self.assertTrue(turn["event_ids"])
        self.assertEqual(turn["version_after"], turn["version_before"] + 1)
        self.assertEqual(states["chen-mo"].private_notes, ["decided to wait"])

    def test_character_is_told_when_delayed_move_is_accepted_and_completed(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        feedback = []
        completion_updates = []

        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo" and any(
                    event["kind"] == "action_completed" for event in perception["events"]):
                completion_updates.append(render_world_message(perception, affordances))
            if state.actor_id == "chen-mo" and not feedback:
                return Intention("chen-mo", "move", {
                    "target": "archive", "duration_seconds": 900,
                }, perception["world_version"])
            return None

        class Recorder:
            def __call__(self, state, perception, affordances):
                return agent(state, perception, affordances)

            def record_world_result(self, message):
                feedback.append(message)

        agents = {actor: (Recorder() if actor == "chen-mo" else agent)
                  for actor in world.actors}
        trace = Trace("v2-test", "move-feedback")
        Runner(world, agents, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:00:00+08:00"), max_turns=1000)

        self.assertTrue(any("accepted" in message and "in progress" in message
                            for message in feedback))
        self.assertTrue(any("completed successfully" in message and "now at archive" in message
                            for message in completion_updates))
        self.assertEqual(world.actors["chen-mo"].location, "archive")

    def test_runner_does_not_poll_idle_agents_forever(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        calls = {actor: 0 for actor in world.actors}
        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return None
        trace = Trace("v2-test", "wake")
        Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:10:00+08:00"), max_turns=100)
        self.assertEqual(sum(calls.values()), len(world.actors))

    def test_null_agent_is_woken_by_its_scheduled_event_without_polling_loop(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        calls = {actor: 0 for actor in world.actors}

        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return None

        trace = Trace("v2-test", "targeted-wake")
        Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:20:00+08:00"), max_turns=100)

        self.assertEqual(calls["chen-mo"], 2)  # initial turn + class event
        self.assertEqual(sum(calls.values()), len(world.actors) + 1)
        self.assertTrue(any(
            turn["actor"] == "chen-mo" and any(
                event["kind"] == "world_event" and event["payload"].get("event") == "class_begins"
                for event in turn["perception"]["events"])
            for turn in trace.agent_turns))

    def test_delayed_completion_wakes_actor_and_visible_observer(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        calls = {actor: 0 for actor in world.actors}

        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            if state.actor_id == "chen-mo" and calls[state.actor_id] == 1:
                return Intention("chen-mo", "move", {"target": "archive", "duration_seconds": 900},
                                 perception["world_version"])
            return None

        trace = Trace("v2-test", "completion-wake")
        Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:16:00+08:00"), max_turns=100)

        self.assertEqual(world.actors["chen-mo"].location, "archive")
        self.assertGreaterEqual(calls["chen-mo"], 2)
        completion_turns = [turn for turn in trace.agent_turns if any(
            event["kind"] == "action_completed" and event["actor"] == "chen-mo"
            for event in turn["perception"]["events"])]
        self.assertTrue(completion_turns)
        self.assertTrue(any(turn["actor"] == "lin-yao" for turn in completion_turns))

    def test_rejected_action_is_persistent_actor_local_operational_fact(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        perceptions = []

        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo":
                perceptions.append(perception)
                if len(perceptions) == 1:
                    return Intention("chen-mo", "move", {
                        "target": "old-basement", "duration_seconds": 1200,
                    }, perception["world_version"])
            return None

        trace = Trace("v2-test", "rejected-action-memory")
        Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:20:00+08:00"), max_turns=100)

        rejected_turn = next(turn for turn in trace.agent_turns if turn["actor"] == "chen-mo")
        self.assertEqual(rejected_turn["result"], "rejected")
        self.assertTrue(any(
            fact["action"]["kind"] == "move"
            and fact["action"]["args"]["target"] == "old-basement"
            and fact["reason"]
            and fact["must_change_before_retry"] is True
            for fact in perceptions[1]["operational_facts"]))
        self.assertNotIn("operational_facts", trace.agent_turns[0]["perception"])

    def test_rejection_fact_is_private_to_its_actor(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        seen = {}

        def agent(state, perception, affordances):
            seen.setdefault(state.actor_id, []).append(perception)
            if state.actor_id == "chen-mo" and len(seen[state.actor_id]) == 1:
                return Intention("chen-mo", "move", {
                    "target": "old-basement", "duration_seconds": 1200,
                }, perception["world_version"])
            return None

        Runner(world, {actor: agent for actor in world.actors}, states, Trace("v2-test", "private-rejection")).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:20:00+08:00"), max_turns=100)

        self.assertTrue(any(seen["chen-mo"][1]["operational_facts"]))
        for actor, packets in seen.items():
            if actor != "chen-mo":
                self.assertTrue(all(not packet.get("operational_facts") for packet in packets))

    def test_repeated_rejection_does_not_create_an_immediate_retry_loop(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        calls = {actor: 0 for actor in world.actors}

        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            if state.actor_id == "chen-mo":
                return Intention("chen-mo", "move", {
                    "target": "old-basement", "duration_seconds": 1200,
                }, perception["world_version"])
            return None

        trace = Trace("v2-test", "bounded-rejection-retry")
        reason = Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:05:00+08:00"), max_turns=20)

        self.assertEqual(reason, "stop_at_reached")
        self.assertEqual(calls["chen-mo"], 1)
        self.assertLessEqual(len(trace.agent_turns), 2 * len(world.actors) + 1)

    def test_rejection_feedback_has_identity_and_is_delivered_once(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        seen = []
        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo":
                seen.append(perception)
                if len(seen) == 1:
                    return Intention("chen-mo", "move", {
                        "target": "old-basement", "duration_seconds": 1200},
                        perception["world_version"])
            return None
        trace = Trace("v3-test", "rejection-feedback-once")
        Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:05:00+00:00"), max_turns=20)
        facts = seen[1].get("operational_facts", [])
        self.assertEqual(len(facts), 1)
        self.assertTrue(facts[0]["feedback_id"].startswith("rejection-chen-mo-"))
        self.assertFalse(any("operational_facts" in packet for packet in seen[2:]))
        session_messages = [turn["error"] for turn in trace.agent_turns if turn["result"] == "rejected"]
        self.assertEqual(len(session_messages), 1)

    def test_rejection_feedback_includes_suggested_alternatives(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        perceptions = []
        feedback = []

        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo":
                perceptions.append(perception)
                if len(perceptions) == 1:
                    return Intention("chen-mo", "move", {
                        "target": "old-basement", "duration_seconds": 1200},
                        perception["world_version"])
            return None

        class Recorder:
            def __call__(self, state, perception, affordances):
                return agent(state, perception, affordances)

            def record_world_result(self, message):
                feedback.append(message)

        agents = {actor: (Recorder() if actor == "chen-mo" else agent)
                  for actor in world.actors}
        Runner(world, agents, states, Trace("v3-test", "rejection-alternatives")).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:20:00+08:00"), max_turns=100)
        fact = perceptions[1]["operational_facts"][0]
        self.assertIn("closed", fact["reason"])
        self.assertTrue(fact["alternatives"])
        self.assertTrue(any("Consider instead" in message for message in feedback))

    def test_world_result_feedback_is_specific_per_action(self):
        from harness.prompt import render_world_message
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        feedback = {actor: [] for actor in world.actors}
        perceived = {actor: [] for actor in world.actors}
        steps = {actor: 0 for actor in world.actors}

        def agent(state, perception, affordances):
            actor = state.actor_id
            if actor == "chen-mo":
                perceived[actor].append(render_world_message(perception, affordances))
                step = steps[actor]
                steps[actor] += 1
                if step == 0:
                    return Intention(actor, "wait", {"duration_seconds": 60},
                                     perception["world_version"])
                if step == 1:
                    return Intention(actor, "search", {}, perception["world_version"])
                if step == 2:
                    return Intention(actor, "drop", {"item": "old-permit-form"},
                                     perception["world_version"])
            return None

        class Recorder:
            def __init__(self, actor):
                self.actor = actor

            def __call__(self, state, perception, affordances):
                return agent(state, perception, affordances)

            def record_world_result(self, message):
                feedback[self.actor].append(message)

        agents = {actor: (Recorder(actor) if actor == "chen-mo" else agent)
                  for actor in world.actors}
        Runner(world, agents, states, Trace("v3-test", "action-consequence-feedback")).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:30:00+08:00"), max_turns=1000)
        combined = " ".join(feedback["chen-mo"] + perceived["chen-mo"])
        self.assertIn("waited", combined)
        self.assertIn("searched", combined)
        self.assertIn("old-permit-form", combined)

    def test_knock_result_feedback_reports_whether_someone_responded(self):
        from harness.kernel import World, ActorState, LocationState
        from harness.prompt import render_world_message

        def run_case(occupant_present: bool):
            actors = [ActorState("a", "outside")]
            if occupant_present:
                actors.append(ActorState("b", "office"))
            world = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                          actors=actors,
                          locations=[LocationState("outside"),
                                     LocationState("office", open=False)],
                          routes={("outside", "office"): 60})
            states = {actor: PrivateState(actor) for actor in world.actors}
            feedback = []
            perceived = []
            knocked = [False]

            def agent(state, perception, affordances):
                if state.actor_id == "a":
                    perceived.append(render_world_message(perception, affordances))
                    if not knocked[0]:
                        knocked[0] = True
                        return Intention("a", "knock", {"target": "office"},
                                         perception["world_version"])
                return None

            class Recorder:
                def __call__(self, state, perception, affordances):
                    return agent(state, perception, affordances)

                def record_world_result(self, message):
                    feedback.append(message)

            agents = {actor: (Recorder() if actor == "a" else agent)
                      for actor in world.actors}
            Runner(world, agents, states, Trace("v3-test", "knock-feedback")).run(
                stop_at=datetime.fromisoformat("2026-01-01T00:00:05+00:00"), max_turns=20)
            return " ".join(feedback + perceived)

        self.assertIn("Someone inside heard you", run_case(True))
        self.assertIn("No one responded", run_case(False))

    def test_idle_actor_is_not_polled_for_unrelated_private_events(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        polls = {actor: 0 for actor in world.actors}
        original_poll = world.poll

        def counted_poll(actor):
            polls[actor] += 1
            return original_poll(actor)

        world.poll = counted_poll

        def agent(state, perception, affordances):
            return None

        trace = Trace("v2-test", "private-wake-filter")
        Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:20:00+08:00"), max_turns=100)

        # class_begins is targeted at Chen.  Other idle actors must not be
        # repeatedly polled merely because simulated time advanced.
        self.assertEqual(polls["chen-mo"], 2)
        self.assertEqual(polls["lin-yao"], 1)
        self.assertEqual(polls["gao-rui"], 1)

    def test_stop_at_time_advance_does_not_repoll_idle_agents_before_stopping(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        calls = {actor: 0 for actor in world.actors}

        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return None

        trace = Trace("v2-test", "stop-boundary")
        reason = Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:05:00+08:00"), max_turns=100)

        self.assertEqual(reason, "stop_at_reached")
        self.assertEqual(world.now.isoformat(), "2026-03-16T07:05:00+08:00")
        self.assertEqual(calls, {actor: 1 for actor in world.actors})
        self.assertEqual(world.event_log[-1].kind, "time_advanced")

    def test_queue_drain_finishes_when_all_agents_return_null(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        calls = {actor: 0 for actor in world.actors}

        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return None

        trace = Trace("v2-test", "queue-drain")
        reason = Runner(world, {actor: agent for actor in world.actors}, states, trace).run(max_turns=100)

        self.assertEqual(reason, "queue_drained")
        self.assertGreaterEqual(sum(calls.values()), len(world.actors))
        self.assertLess(len(trace.agent_turns), 100)

    def test_runner_rejects_cross_actor_intention_without_world_mutation(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def agent(state, perception, affordances):
            if state.actor_id == "chen-mo":
                return Intention("lin-yao", "send_message", {"target": "chen-mo", "text": "forged"}, perception["world_version"])
            return None
        trace = Trace("v2-test", "boundary")
        Runner(world, {actor: agent for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:01:00+08:00"), max_turns=20)
        turn = next(x for x in trace.agent_turns if x["actor"] == "chen-mo")
        self.assertEqual(turn["result"], "rejected")
        self.assertFalse(any(e.kind == "action_started" for e in world.event_log))

    def test_runner_reports_max_turn_truncation(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        def agent(state, perception, affordances):
            return Intention(state.actor_id, "wait", {"duration_seconds": 60}, perception["world_version"])
        trace = Trace("v2-test", "truncated")
        runner = Runner(world, {actor: agent for actor in world.actors}, states, trace)
        self.assertEqual(runner.run(max_turns=1), "max_turns_reached")
        self.assertEqual(runner.stop_reason, "max_turns_reached")

    def test_trace_completion_gate_rejects_truncated_run(self):
        world = create_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        trace = Trace("v2-test", "complete")
        Runner(world, {actor: (lambda state, perception, affordances: None) for actor in world.actors}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:00:00+08:00"), max_turns=20)
        with self.assertRaises(ValueError):
            trace.verify_complete(world, endpoint="2026-03-27T21:30:00+08:00", stop_event="world_stops")

    def test_trace_completion_gate_rejects_agent_errors_even_at_endpoint(self):
        world = create_world()
        trace = Trace("v3-test", "endpoint-with-error")
        trace.record_agent(state=PrivateState("chen-mo"), perception={}, affordances=[],
                           intention=None, result="agent_error", error="provider failed")
        with self.assertRaises(ValueError):
            trace.verify_no_agent_errors()


if __name__ == "__main__":
    unittest.main()
