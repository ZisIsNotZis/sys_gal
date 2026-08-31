import unittest
import json
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
from harness.kernel import ActionRejected, ActorState, Intention, LocationState, World
from harness.agent_state import PrivateState
from harness.prompt import build_prompt
from harness.trace import verify_event_log
from harness.adapter import parse_intention
from harness.replay import replay_world
from harness.system import Ledger
from harness.provider import OpenAICompatible
from urllib.error import HTTPError
from io import BytesIO


class WorldTests(unittest.TestCase):
    def world(self):
        return World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                     actors=[ActorState("a", "room"), ActorState("b", "room")],
                     locations=[LocationState("room")])

    def test_message_is_concrete_and_private(self):
        w = self.world(); w.submit(Intention("a", "send_message", {"target": "b", "text": "I was afraid."}, w.version)); w.advance()
        self.assertEqual(w.actors["b"].inbox[0]["text"], "I was afraid.")
        self.assertEqual([e.kind for e in w.event_log], ["action_started", "message_sent", "action_completed", "message_delivered"])
        self.assertNotIn("b", w.event_log[1].visible_to)
        self.assertEqual(w.poll("b")["inbox"][0]["text"], "I was afraid.")
        self.assertEqual(w.poll("b")["inbox"], [])

    def test_poll_exposes_busy_until_and_sender_sees_delivery(self):
        w = self.world()
        w.submit(Intention("a", "send_message", {"target": "b", "text": "secret"}, w.version))
        self.assertEqual(w.poll("a")["busy_until"], "2026-01-01T00:00:05+00:00")
        w.advance()
        perception = w.poll("a")
        self.assertIsNone(perception["busy_until"])
        self.assertTrue(any(e["kind"] == "message_delivered" for e in perception["events"]))

    def test_invalid_intention_does_not_mutate(self):
        w = self.world(); version = w.version
        with self.assertRaises(ActionRejected): w.submit(Intention("a", "apologize", {"target": "b"}, version))
        self.assertEqual(w.version, version)

    def test_inspect_item_is_offered_only_when_present_and_reports_objective_fact(self):
        w = self.world()
        w.item_locations["folder"] = "room"
        self.assertIn({"kind": "inspect", "item": "folder"}, w.affordances("a"))
        w.submit(Intention("a", "inspect", {"item": "folder"}, w.version))
        event = w.event_log[-1]
        self.assertEqual(event.kind, "item_inspected")
        self.assertEqual(dict(event.payload), {"item": "folder", "location": "room", "held": False})
        self.assertIn("a", event.visible_to)
        self.assertNotIn("b", event.visible_to)

    def test_search_current_location_lists_only_physically_present_items(self):
        w = self.world()
        w.item_locations.update({"folder": "room", "elsewhere": "other"})
        w.locations["other"] = LocationState("other")
        self.assertIn({"kind": "search"}, w.affordances("a"))
        w.submit(Intention("a", "search", {}, w.version))
        self.assertEqual(w.event_log[-1].kind, "location_searched")
        self.assertEqual(w.event_log[-1].payload["items"], ["folder"])

    def test_inspect_rejects_item_not_at_actor_location(self):
        w = self.world()
        w.item_locations["folder"] = "other"
        w.locations["other"] = LocationState("other")
        with self.assertRaises(ActionRejected):
            w.submit(Intention("a", "inspect", {"item": "folder"}, w.version))

    def test_give_transfers_held_item_to_co_located_actor(self):
        w = self.world()
        w.actors["a"].inventory.add("folder")
        self.assertIn({"kind": "give", "target": "b", "item": "folder"}, w.affordances("a"))
        w.submit(Intention("a", "give", {"target": "b", "item": "folder"}, w.version))
        w.advance()
        self.assertNotIn("folder", w.actors["a"].inventory)
        self.assertIn("folder", w.actors["b"].inventory)
        transfer = next(event for event in w.event_log if event.kind == "item_given")
        self.assertEqual(transfer.payload, {"item": "folder", "from": "a", "to": "b"})
        self.assertEqual(transfer.visible_to, frozenset({"a", "b"}))

    def test_give_rejects_non_colocated_target_and_unheld_item(self):
        w = self.world()
        with self.assertRaises(ActionRejected):
            w.submit(Intention("a", "give", {"target": "b", "item": "folder"}, w.version))
        w.locations["other"] = LocationState("other")
        w.actors["b"].location = "other"
        w.actors["a"].inventory.add("folder")
        with self.assertRaises(ActionRejected):
            w.submit(Intention("a", "give", {"target": "b", "item": "folder"}, w.version))

    def test_give_replay_preserves_inventory_transfer(self):
        w = self.world()
        w.actors["a"].inventory.add("folder")
        w.submit(Intention("a", "give", {"target": "b", "item": "folder"}, w.version))
        w.advance()
        replayed = replay_world(self.world(), w.replayable_log())
        self.assertIn("item_given", [event["kind"] for event in replayed.replayable_log()])

    def test_interaction_events_replay_without_inventing_state_changes(self):
        initial = self.world()
        initial.item_locations["folder"] = "room"
        w = self.world()
        w.item_locations["folder"] = "room"
        w.submit(Intention("a", "inspect", {"item": "folder"}, w.version))
        w.submit(Intention("b", "search", {}, w.version))
        replayed = replay_world(initial, w.replayable_log())
        self.assertEqual(
            [event["kind"] for event in replayed.replayable_log()],
            [event["kind"] for event in w.replayable_log()],
        )
        self.assertEqual(replayed.item_locations, w.item_locations)
        self.assertEqual(replayed.actors["a"].location, "room")

    def test_inspect_completion_does_not_disclose_item_to_roommate(self):
        w = self.world()
        w.item_locations["folder"] = "room"
        w.submit(Intention("a", "inspect", {"item": "folder"}, w.version))
        self.assertNotIn("b", next(event for event in w.event_log
                                   if event.kind == "action_completed").visible_to)

    def test_interaction_results_are_private_but_knock_reaches_closed_occupant(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "outside"), ActorState("b", "office"), ActorState("c", "outside")],
                  locations=[LocationState("outside"), LocationState("office", open=False)],
                  routes={("outside", "office"): 60})
        w.submit(Intention("a", "knock", {"target": "office"}, w.version))
        w.advance()
        knock = next(event for event in w.event_log if event.kind == "knock")
        self.assertEqual(knock.visible_to, frozenset({"a", "b"}))
        self.assertNotIn("c", knock.visible_to)

    def test_knock_at_closed_place_is_a_request_and_does_not_open_it(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "outside"), ActorState("b", "office")],
                  locations=[LocationState("outside"), LocationState("office", open=False)],
                  routes={("outside", "office"): 60})
        self.assertIn({"kind": "knock", "target": "office"}, w.affordances("a"))
        w.submit(Intention("a", "knock", {"target": "office"}, w.version))
        self.assertFalse(w.locations["office"].open)
        w.advance()
        event = w.event_log[-1]
        self.assertEqual(event.kind, "knock")
        self.assertEqual(event.payload, {"target": "office"})
        self.assertIn("b", event.visible_to)

    def test_knock_rejects_open_or_unreachable_places(self):
        w = self.world()
        with self.assertRaises(ActionRejected):
            w.submit(Intention("a", "knock", {"target": "room"}, w.version))
        w.locations["closed"] = LocationState("closed", open=False)
        with self.assertRaises(ActionRejected):
            w.submit(Intention("a", "knock", {"target": "closed"}, w.version))

    def test_scheduled_events_advance_without_plot_state(self):
        w = self.world(); w._schedule(w.now + timedelta(minutes=5), "world_event", None, {"event": "rain"}, None); w.advance()
        self.assertEqual(w.event_log[-1].kind, "world_event")
        self.assertFalse(any(name in vars(w) for name in ("story_phase", "romance", "affection", "relationship_score")))

    def test_external_commit_is_namespaced(self):
        w = self.world()
        event = w.commit_external("system_answer", "a", {"answer": "objective"})
        self.assertEqual(event.id, 1)
        with self.assertRaises(ValueError):
            w.commit_external("story_phase", "a", {})

    def test_replay_reconstructs_objective_consequences(self):
        initial = self.world()
        w = self.world()
        w.submit(Intention("a", "send_message", {"target": "b", "text": "recorded"}, w.version))
        w.advance()
        replayed = replay_world(initial, w.replayable_log())
        self.assertEqual(replayed.now, w.now)
        self.assertEqual(replayed.actors["a"].location, w.actors["a"].location)
        self.assertEqual(replayed.actors["b"].inbox, w.actors["b"].inbox)

    def test_replay_preserves_private_system_visibility(self):
        initial = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                        actors=[ActorState("a", "room"), ActorState("b", "room")],
                        locations=[LocationState("room")])
        w = self.world(); w.commit_external("system_answer", "a", {"answer": "secret"})
        replayed = replay_world(initial, w.replayable_log())
        self.assertIn("a", replayed.event_log[0].visible_to)
        self.assertNotIn("b", replayed.event_log[0].visible_to)

    def test_system_event_is_private_to_bound_actor(self):
        w = self.world()
        w.commit_external("system_answer", "a", {"answer": "secret"})
        self.assertTrue(w.poll("a")["events"])
        self.assertFalse(w.poll("b")["events"])

    def test_speech_hearing_uses_map_distance_and_barriers(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "near"), ActorState("b", "near"), ActorState("c", "far"), ActorState("d", "blocked")],
                  locations=[LocationState("near", x=0, y=0, sound_radius=10),
                             LocationState("far", x=30, y=0), LocationState("blocked", x=2, y=0)],
                  sound_barriers={("near", "blocked"): 20})
        w.submit(Intention("a", "speak", {"text": "quietly", "volume": "normal"}, w.version))
        heard = w.event_log[1].visible_to
        self.assertIn("a", heard); self.assertIn("b", heard)
        self.assertNotIn("c", heard); self.assertNotIn("d", heard)

    def test_move_completion_is_visible_at_destination(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "start"), ActorState("b", "finish")],
                  locations=[LocationState("start"), LocationState("finish")],
                  routes={("start", "finish"): 60})
        w.submit(Intention("a", "move", {"target": "finish", "duration_seconds": 60}, w.version))
        w.advance()
        self.assertTrue(any(e["kind"] == "action_completed" and e["actor"] == "a"
                            for e in w.poll("b")["events"]))

    def test_closed_source_does_not_project_speech(self):
        w = self.world(); w.locations["room"] = LocationState("room", False)
        w.submit(Intention("a", "speak", {"text": "inside", "volume": "normal"}, w.version))
        self.assertEqual(w.event_log[1].visible_to, frozenset({"a"}))

    def test_closed_listener_does_not_hear_external_speech(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "outside"), ActorState("b", "inside")],
                  locations=[LocationState("outside", x=0, y=0, sound_radius=10),
                             LocationState("inside", open=False, x=1, y=0)],
                  sound_barriers={("outside", "inside"): 0})
        w.submit(Intention("a", "speak", {"text": "outside", "volume": "normal"}, w.version))
        self.assertNotIn("b", w.event_log[1].visible_to)
        self.assertNotIn("b", w.event_log[0].visible_to)

    def test_invalid_ledger_query_does_not_consume_quota(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("chen-mo", "room")], locations=[LocationState("room")])
        ledger = Ledger({"known": "answer"})
        ledger.accept(w, "chen-mo", "ambiguous-obligations")
        with self.assertRaises(ActionRejected):
            ledger.query(w, "chen-mo", "unknown")
        self.assertEqual(ledger.queries_used, 0)
        ledger.query(w, "chen-mo", "known")

    def test_ledger_reward_is_emitted_only_after_seeded_objective_condition(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("chen-mo", "room")], locations=[LocationState("room")])
        ledger = Ledger({"known": "answer"})
        accepted = ledger.accept(w, "chen-mo", "ambiguous-obligations")
        self.assertEqual(ledger.status, "accepted")
        self.assertNotIn("reward_granted", accepted.payload)
        answer = ledger.query(w, "chen-mo", "known")
        self.assertEqual(answer.kind, "system_answer")
        self.assertEqual(ledger.status, "completed")
        reward = w.event_log[-1]
        self.assertEqual(reward.kind, "system_reward_granted")
        self.assertEqual(reward.payload["condition"], "correct objective fact query")
        self.assertEqual(reward.payload["reward"], "one narrow objective clarification")

    def test_ledger_penalty_is_an_auditable_consequence_of_voluntary_decline(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("chen-mo", "room")], locations=[LocationState("room")])
        ledger = Ledger({"known": "answer"})
        event = ledger.decline_offer(w, "chen-mo")
        self.assertEqual(ledger.status, "declined")
        self.assertEqual(event.kind, "system_penalty_applied")
        self.assertEqual(event.payload["penalty"], "the offered clarification is forfeited")
        self.assertTrue(ledger.penalty_applied)
        self.assertFalse(ledger.reward_granted)
        self.assertEqual(ledger.affordances("chen-mo"), [])
        with self.assertRaises(ActionRejected):
            ledger.query(w, "chen-mo", "known")

    def test_targeted_world_event_is_private(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "room"), ActorState("b", "room")],
                  locations=[LocationState("room")],
                  scheduled=[{"event": "private_call", "target": "a", "time": "2026-01-01T00:05:00+00:00"}])
        w.advance()
        self.assertTrue(any(e["kind"] == "world_event" for e in w.poll("a")["events"]))
        self.assertFalse(any(e["kind"] == "world_event" for e in w.poll("b")["events"]))

    def test_private_message_start_is_not_a_room_announcement(self):
        w = self.world()
        w.submit(Intention("a", "send_message", {"target": "b", "text": "secret"}, w.version))
        self.assertFalse(any(e.kind == "action_started" and "b" in e.visible_to for e in w.event_log))

    def test_prompt_contains_only_the_actor_packet_and_concrete_actions(self):
        state = PrivateState("a", goals=("find the missing folder",))
        prompt = build_prompt(identity="A", private_seed="A's private fact", state=state,
                              perception={"observer": "a", "events": []},
                              affordances=[{"kind": "send_message", "target": "b"}])
        self.assertIn("A's private fact", prompt)
        self.assertNotIn("b's private fact", prompt)
        self.assertIn("exact message text", prompt)

    def test_prompt_describes_physical_interaction_limits(self):
        from harness.prompt import render_world_message
        text = render_world_message(
            {"time": "now", "location": "room", "observer": "a", "inbox": [], "events": []},
            [{"kind": "inspect", "item": "folder"}, {"kind": "search"}, {"kind": "knock", "target": "office"}],
        )
        self.assertIn("inspect folder", text)
        self.assertIn("search this location", text)
        self.assertIn("knock at closed office", text)

    def test_prompt_renders_inspection_and_transfer_results_explicitly(self):
        from harness.prompt import render_world_message
        text = render_world_message(
            {"time": "now", "location": "room", "observer": "a", "inbox": [], "events": [
                {"kind": "item_inspected", "actor": "a",
                 "payload": {"item": "folder", "location": "room", "held": True}},
                {"kind": "item_given", "actor": "a",
                 "payload": {"item": "folder", "from": "a", "to": "b"}},
            ]}, [],
        )
        self.assertIn("inspected folder", text)
        self.assertIn("gave folder to b", text)

    def test_world_message_spells_out_self_move_completion(self):
        from harness.prompt import render_world_message
        text = render_world_message({"observer": "a", "time": "now", "location": "finish",
                                     "events": [{"kind": "action_completed", "actor": "a",
                                                 "payload": {"action": "move", "target": "finish"}}]}, [])
        self.assertIn("completed successfully", text)
        self.assertIn("now at finish", text)

    def test_replay_log_verifier_rejects_truncation_and_accepts_real_log(self):
        w = self.world(); w.submit(Intention("a", "send_message", {"target": "b", "text": "hi"}, w.version)); w.advance()
        verify_event_log(w.replayable_log())
        broken = list(w.replayable_log()); broken[1]["id"] = 99
        with self.assertRaises(ValueError): verify_event_log(broken)

    def test_adapter_rejects_vague_or_extra_model_output(self):
        with self.assertRaises(ValueError): parse_intention("a", '{"kind":"apologize","target":"b"}', 0)
        with self.assertRaises(ValueError): parse_intention("a", '{"kind":"send_message","args":{},"reason":"plot"}', 0)
        self.assertEqual(parse_intention("a", {"kind": "wait", "args": {"duration_seconds": 60}}, 4).expected_version, 4)

    def test_provider_requires_explicit_model(self):
        with patch.dict("os.environ", {"OPENAI_MODEL": ""}, clear=False):
            with self.assertRaises(ValueError):
                OpenAICompatible(base_url="http://127.0.0.1:1", model="")

    def test_provider_drops_local_message_metadata_not_supported_by_api(self):
        success = Mock()
        success.__enter__ = lambda self: self
        success.__exit__ = Mock(return_value=False)
        success.read.return_value = b'{"output_text":"ok"}'
        with patch("harness.provider.urlopen", return_value=success) as opened:
            OpenAICompatible(model="m")([
                {"role": "user", "name": "world", "content": "The action completed."},
            ])
        body = json.loads(opened.call_args.args[0].data.decode())
        self.assertEqual(body["input"], [{"role": "user", "content": "The action completed."}])

    def test_provider_retries_transient_http_failure(self):
        failure = HTTPError("http://test", 502, "bad gateway", {}, BytesIO(b"upstream"))
        success = Mock()
        success.__enter__ = lambda self: self
        success.__exit__ = Mock(return_value=False)
        success.read.return_value = b'{"output_text":"{\\"kind\\":\\"wait\\",\\"args\\":{\\"duration_seconds\\":60}}"}'
        pauses = []
        with patch("harness.provider.urlopen", side_effect=[failure, success]) as opened:
            result = OpenAICompatible(model="m", retries=2, retry_backoff=0.25,
                                      sleep=pauses.append)([{"role":"user","content":"x"}])
        self.assertIn('"kind"', result)
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(pauses, [0.25])

    def test_provider_does_not_retry_permanent_http_failure(self):
        failure = HTTPError("http://test", 400, "bad request", {}, BytesIO(b"bad"))
        with patch("harness.provider.urlopen", side_effect=failure) as opened:
            with self.assertRaisesRegex(RuntimeError, "provider HTTP 400"):
                OpenAICompatible(model="m", retries=3, sleep=lambda _: None)([])
        self.assertEqual(opened.call_count, 1)

    def test_provider_retries_socket_timeout(self):
        success = Mock()
        success.__enter__ = lambda self: self
        success.__exit__ = Mock(return_value=False)
        success.read.return_value = b'{"output_text":"ok"}'
        pauses = []
        with patch("harness.provider.urlopen", side_effect=[TimeoutError("slow"), success]) as opened:
            result = OpenAICompatible(model="m", retries=1, retry_backoff=0.1,
                                      sleep=pauses.append)([])
        self.assertEqual(result, "ok")
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(pauses, [0.1])

    def test_provider_exhausted_502_reports_retry_metadata(self):
        failures = [HTTPError("http://test", 502, "bad gateway", {}, BytesIO(b"upstream")) for _ in range(3)]
        pauses = []
        with patch("harness.provider.urlopen", side_effect=failures) as opened:
            with self.assertRaisesRegex(RuntimeError, r"provider HTTP 502 after 3 attempts") as raised:
                OpenAICompatible(model="m", retries=2, retry_backoff=0.1,
                                  sleep=pauses.append)([])
        self.assertEqual(opened.call_count, 3)
        self.assertEqual(pauses, [0.1, 0.2])
        self.assertEqual(getattr(raised.exception, "provider_code", None), 502)
        self.assertEqual(getattr(raised.exception, "attempts", None), 3)

    def test_provider_retry_budget_is_bounded(self):
        failure = HTTPError("http://test", 503, "unavailable", {}, BytesIO(b"down"))
        pauses = []
        with patch("harness.provider.urlopen", side_effect=failure) as opened:
            with self.assertRaises(RuntimeError):
                OpenAICompatible(model="m", retries=4, retry_backoff=0.1,
                                  max_retries=2, sleep=pauses.append)([])
        self.assertEqual(opened.call_count, 3)
        self.assertEqual(pauses, [0.1, 0.2])

    def test_provider_caps_exponential_backoff(self):
        failure = HTTPError("http://test", 502, "bad gateway", {}, BytesIO(b"upstream"))
        pauses = []
        with patch("harness.provider.urlopen", side_effect=failure):
            with self.assertRaises(RuntimeError):
                OpenAICompatible(model="m", retries=4, retry_backoff=10,
                                  max_backoff=3, sleep=pauses.append)([])
        self.assertEqual(pauses, [3, 3, 3, 3])

    def test_provider_does_not_start_retry_after_deadline(self):
        failure = HTTPError("http://test", 502, "bad gateway", {}, BytesIO(b"upstream"))
        clock = iter([0.0, 0.0, 2.0, 2.0])
        pauses = []
        with patch("harness.provider.urlopen", side_effect=failure) as opened, \
             patch("harness.provider.time.monotonic", side_effect=lambda: next(clock)):
            with self.assertRaisesRegex(RuntimeError, "retry deadline exhausted"):
                OpenAICompatible(model="m", retries=5, max_duration=1.0,
                                  retry_backoff=0.1, sleep=pauses.append)([])
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(pauses, [])

    def test_provider_worst_case_budget_is_explicit_and_bounded(self):
        provider = OpenAICompatible(model="m", timeout=2, retries=5,
                                    max_retries=5, max_duration=10,
                                    retry_backoff=0.25, max_backoff=2,
                                    sleep=lambda _: None)
        # A request already in flight when max_duration expires can consume
        # one socket timeout; the bound must include that final timeout.
        self.assertEqual(provider.worst_case_seconds(), 12)

    def test_provider_deadline_timing_does_not_exceed_runner_budget(self):
        provider = OpenAICompatible(model="m", timeout=2, retries=5,
                                    max_retries=5, max_duration=10,
                                    retry_backoff=0.25, max_backoff=2,
                                    sleep=lambda _: None)
        self.assertLess(provider.worst_case_seconds(), 15)

    def test_prompt_explicitly_satisfies_provider_json_mode(self):
        state = PrivateState("a")
        prompt = build_prompt(identity="A", private_seed="fact", state=state,
                              perception={"observer": "a"}, affordances=[])
        self.assertIn("valid json", prompt)

    def test_prompt_requires_identity_not_fast_decision(self):
        state = PrivateState("a")
        prompt = build_prompt(identity="A", private_seed="fact", state=state,
                              perception={"observer": "a"}, affordances=[])
        self.assertIn("not an assistant portraying them", prompt)
        self.assertNotIn("do not deliberate at length", prompt)


if __name__ == "__main__": unittest.main()
