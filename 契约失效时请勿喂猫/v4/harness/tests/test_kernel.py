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

    def test_remote_message_requires_seeded_known_contact(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "room", known_contacts={"b"}),
                          ActorState("b", "far"), ActorState("c", "far")],
                  locations=[LocationState("room"), LocationState("far")])
        w.submit(Intention("a", "send_message", {"target": "b", "text": "hello"}, w.version))
        with self.assertRaises(ActionRejected):
            w.submit(Intention("a", "send_message", {"target": "c", "text": "hello"}, w.version))

    def test_co_located_message_is_addressable_without_known_contact(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "room"), ActorState("b", "room")],
                  locations=[LocationState("room")])
        self.assertIn({"kind": "send_message", "target": "b"}, w.affordances("a"))
        w.submit(Intention("a", "send_message", {"target": "b", "text": "hello"}, w.version))

    def test_poll_exposes_busy_until_and_sender_sees_delivery(self):
        w = self.world()
        w.submit(Intention("a", "send_message", {"target": "b", "text": "secret"}, w.version))
        self.assertEqual(w.poll("a")["busy_until"], "2026-01-01T00:01:00+00:00")
        w.advance()
        perception = w.poll("a")
        self.assertIsNone(perception["busy_until"])
        self.assertTrue(any(e["kind"] == "message_delivered" for e in perception["events"]))

    def test_sender_sees_message_target_when_send_completes(self):
        w = self.world()
        w.submit(Intention("a", "send_message", {"target": "b", "text": "secret"}, w.version))
        w.advance()
        completion = next(e for e in w.poll("a")["events"] if e["kind"] == "action_completed")
        self.assertEqual(completion["payload"], {"action": "send_message", "target": "b"})

    def test_speech_completion_does_not_retarget_original_words(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "room"), ActorState("b", "far")],
                  locations=[LocationState("room", x=0, y=0, sound_radius=5),
                             LocationState("far", x=100, y=0, sound_radius=5)])
        w.submit(Intention("a", "speak", {"text": "private words", "volume": "normal"}, w.version))
        w.actors["b"].location = "room"
        w.advance()
        completion = next(e for e in w.event_log if e.kind == "action_completed")
        self.assertNotIn("b", completion.visible_to)

    def test_invalid_intention_does_not_mutate(self):
        w = self.world(); version = w.version
        with self.assertRaises(ActionRejected): w.submit(Intention("a", "apologize", {"target": "b"}, version))
        self.assertEqual(w.version, version)

    def test_inspect_item_is_offered_only_when_present_and_reports_objective_fact(self):
        w = self.world()
        w.item_locations["folder"] = "room"
        self.assertIn({"kind": "inspect", "item": "folder"}, w.affordances("a"))
        w.submit(Intention("a", "inspect", {"item": "folder"}, w.version))
        w.advance()
        event = w.event_log[-1]
        self.assertEqual(event.kind, "item_inspected")
        self.assertEqual(dict(event.payload), {"item": "folder", "location": "room", "held": False})
        # v4: the fact of an inspection is co-located visible (payload has no
        # secret content - V4-DESIGN §3).
        self.assertIn("a", event.visible_to)
        self.assertIn("b", event.visible_to)

    def test_search_current_location_lists_only_physically_present_items(self):
        w = self.world()
        w.item_locations.update({"folder": "room", "elsewhere": "other"})
        w.locations["other"] = LocationState("other")
        self.assertIn({"kind": "search"}, w.affordances("a"))
        w.submit(Intention("a", "search", {}, w.version))
        w.advance()
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

    def test_inspect_completion_is_co_located_visible_but_item_is_not_secret(self):
        # v4: co-located actors see that an inspection happened; the payload
        # carries no private content (V4-DESIGN §3).
        w = self.world()
        w.item_locations["folder"] = "room"
        w.submit(Intention("a", "inspect", {"item": "folder"}, w.version))
        w.advance()
        completion = next(event for event in w.event_log
                          if event.kind == "action_completed")
        self.assertIn("b", completion.visible_to)
        self.assertNotIn("held", dict(completion.payload))

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
        self.assertEqual(event.payload["target"], "office")
        self.assertTrue(event.payload["responded"])
        self.assertIn("b", event.visible_to)

    def test_knock_rejects_open_or_unreachable_places(self):
        w = self.world()
        with self.assertRaises(ActionRejected):
            w.submit(Intention("a", "knock", {"target": "room"}, w.version))
        w.locations["closed"] = LocationState("closed", open=False)
        with self.assertRaises(ActionRejected):
            w.submit(Intention("a", "knock", {"target": "closed"}, w.version))

    def test_closed_boundary_uses_generic_interaction_seam(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "outside"), ActorState("b", "office")],
                  locations=[LocationState("outside"), LocationState("office", open=False)],
                  routes={("outside", "office"): 60})
        option = {"kind": "interact", "target": "office", "verb": "knock", "parameters": {}}
        self.assertIn(option, w.affordances("a"))
        w.submit(Intention("a", "interact", {"target": "office", "verb": "knock", "parameters": {}},
                           w.version))
        w.advance()
        event = next(e for e in w.event_log if e.kind == "interaction")
        self.assertEqual(event.payload["target"], "office")
        self.assertEqual(event.payload["verb"], "knock")
        self.assertTrue(event.payload["responded"])
        self.assertFalse(w.locations["office"].open)

    def test_generic_interaction_validates_capability_and_parameters(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "outside")],
                  locations=[LocationState("outside"), LocationState(
                      "gate", open=False, physical_capabilities={
                          "tap": {"parameters": {"surface": "metal"}}})],
                  routes={("outside", "gate"): 60})
        w.submit(Intention("a", "interact", {"target": "gate", "verb": "tap",
                                                "parameters": {"surface": "metal"}}, w.version))
        w.advance()
        self.assertEqual(next(e for e in w.event_log if e.kind == "interaction").payload["verb"], "tap")
        with self.assertRaises(ActionRejected):
            w.submit(Intention("a", "interact", {"target": "gate", "verb": "tap",
                                                    "parameters": {"surface": "wood"}}, w.version))

    def test_location_knowledge_is_public_or_actor_private(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "room"), ActorState("b", "room")],
                  locations=[LocationState("room")],
                  public_knowledge={"room": "The office is closed after hours."},
                  private_knowledge={"room": {"a": "A custodian has a permit."}})
        self.assertEqual(w.poll("a")["knowledge"], {
            "room": {"public": "The office is closed after hours.",
                     "private": "A custodian has a permit."}})
        self.assertEqual(w.poll("b")["knowledge"], {
            "room": {"public": "The office is closed after hours."}})

    def test_scheduled_events_advance_without_plot_state(self):
        w = self.world(); w._schedule(w.now + timedelta(minutes=5), "world_event", None, {"event": "rain"}, None); w.advance()
        self.assertEqual(w.event_log[-1].kind, "world_event")
        self.assertFalse(any(name in vars(w) for name in ("story_phase", "romance", "affection", "relationship_score")))

    def test_scheduled_effects_apply_objective_state_and_replay(self):
        def make():
            return World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                         actors=[ActorState("a", "room")],
                         locations=[LocationState("room"), LocationState("vault", open=False)],
                         routes={("room", "vault"): 60},
                         document_defs={"report": {"title": "Report", "content": "x",
                                                    "reading_seconds": 5}})
        seed = make()
        w = make()
        w._schedule(w.now + timedelta(minutes=1), "world_event", None,
                    {"event": "vault_unlocked",
                     "effects": [{"op": "open_location", "id": "vault"},
                                  {"op": "add_document", "id": "report", "location": "vault"}]},
                    None)
        w.advance()
        self.assertTrue(w.locations["vault"].open)
        self.assertEqual(w.item_locations.get("report"), "vault")
        replayed = replay_world(seed, w.replayable_log())
        self.assertTrue(replayed.locations["vault"].open)
        self.assertEqual(replayed.item_locations.get("report"), "vault")

    def test_scheduled_effect_moves_and_removes_items(self):
        w = self.world()
        w.item_locations["folder"] = "room"
        w._schedule(w.now, "world_event", None,
                    {"event": "relocate",
                     "effects": [{"op": "move_item", "id": "folder", "location": "other"},
                                  {"op": "remove_item", "id": "folder"}]}, None)
        w.advance()
        self.assertNotIn("folder", w.item_locations)

    def test_world_event_multitarget_visibility(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "room"), ActorState("b", "room"), ActorState("c", "room")],
                  locations=[LocationState("room")])
        w._schedule(w.now, "world_event", None, {"event": "meeting", "target": ["a", "b"]}, None)
        w.advance()
        event = w.event_log[-1]
        self.assertEqual(event.visible_to, frozenset({"a", "b"}))
        self.assertNotIn("c", event.visible_to)

    def test_rejection_message_lists_what_is_present_here(self):
        w = self.world()
        w.item_locations["folder"] = "room"
        with self.assertRaises(ActionRejected) as ctx:
            w.submit(Intention("a", "inspect", {"item": "missing"}, w.version))
        self.assertIn("folder", str(ctx.exception))
        self.assertTrue(any("folder" in alternative for alternative in ctx.exception.alternatives))

    def test_move_rejection_explains_closure_and_open_neighbors(self):
        w = self.world()
        w.locations["office"] = LocationState("office", open=False)
        w.routes[("room", "office")] = 60
        with self.assertRaises(ActionRejected) as ctx:
            w.submit(Intention("a", "move", {"target": "office"}, w.version))
        self.assertIn("关着", str(ctx.exception))
        with self.assertRaises(ActionRejected) as ctx:
            w.submit(Intention("a", "move", {"target": "far"}, w.version))
        self.assertIn("不是一个你知道的地方", str(ctx.exception))

    def test_interact_rejection_lists_supported_verbs(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("a", "outside")],
                  locations=[LocationState("outside"), LocationState(
                      "gate", open=False, physical_capabilities={"tap": {"parameters": {}}})],
                  routes={("outside", "gate"): 60})
        with self.assertRaises(ActionRejected) as ctx:
            w.submit(Intention("a", "interact", {"target": "gate", "verb": "kick", "parameters": {}}, w.version))
        self.assertIn("tap", str(ctx.exception))

    def test_open_close_requires_controllable(self):
        w = self.world()
        self.assertNotIn({"kind": "close"}, w.affordances("a"))
        with self.assertRaises(ActionRejected) as ctx:
            w.submit(Intention("a", "close", {}, w.version))
        self.assertIn("不受你控制", str(ctx.exception))
        controllable = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                             actors=[ActorState("a", "room")],
                             locations=[LocationState("room", controllable=True)])
        self.assertIn({"kind": "close"}, controllable.affordances("a"))
        controllable.submit(Intention("a", "close", {}, controllable.version))
        controllable.advance()
        self.assertFalse(controllable.locations["room"].open)
        self.assertIn({"kind": "open"}, controllable.affordances("a"))
        controllable.submit(Intention("a", "open", {}, controllable.version))
        controllable.advance()
        self.assertTrue(controllable.locations["room"].open)

    def test_controllable_flag_survives_checkpoint_and_replay(self):
        base = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                     actors=[ActorState("a", "room")],
                     locations=[LocationState("room", controllable=True)])
        w = base.__class__.from_checkpoint(base, base.checkpoint_state())
        self.assertTrue(w.locations["room"].controllable)
        replayed = replay_world(base, w.replayable_log())
        self.assertTrue(replayed.locations["room"].controllable)

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
        w.submit(Intention("a", "move", {"target": "finish"}, w.version))
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
                  actors=[ActorState("陈默", "room")], locations=[LocationState("room")])
        ledger = Ledger({"known": "answer"})
        ledger.accept(w, "陈默", "ambiguous-obligations")
        with self.assertRaises(ActionRejected):
            ledger.query(w, "陈默", "unknown")
        self.assertEqual(ledger.queries_used, 0)
        ledger.query(w, "陈默", "known")

    def test_ledger_reward_is_emitted_only_after_seeded_objective_condition(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("陈默", "room")], locations=[LocationState("room")])
        ledger = Ledger({"known": "answer"})
        accepted = ledger.accept(w, "陈默", "ambiguous-obligations")
        self.assertEqual(ledger.status, "accepted")
        self.assertNotIn("reward_granted", accepted.payload)
        answer = ledger.query(w, "陈默", "known")
        self.assertEqual(answer.kind, "system_answer")
        self.assertEqual(ledger.status, "completed")
        reward = w.event_log[-1]
        self.assertEqual(reward.kind, "system_reward_granted")
        self.assertEqual(reward.payload["condition"], "correct objective fact query")
        self.assertEqual(reward.payload["reward"], "one narrow objective clarification")

    def test_ledger_penalty_is_an_auditable_consequence_of_voluntary_decline(self):
        w = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                  actors=[ActorState("陈默", "room")], locations=[LocationState("room")])
        ledger = Ledger({"known": "answer"})
        event = ledger.decline_offer(w, "陈默")
        self.assertEqual(ledger.status, "declined")
        self.assertEqual(event.kind, "system_penalty_applied")
        self.assertEqual(event.payload["penalty"], "the offered clarification is forfeited")
        self.assertTrue(ledger.penalty_applied)
        self.assertFalse(ledger.reward_granted)
        self.assertEqual(ledger.affordances("陈默"), [])
        with self.assertRaises(ActionRejected):
            ledger.query(w, "陈默", "known")

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
        self.assertIn("send_message 和 give 用 target", prompt)
        self.assertIn("inner", prompt)

    def test_prompt_describes_physical_interaction_limits(self):
        from harness.prompt import render_world_message
        text = render_world_message(
            {"time": "now", "location": "room", "observer": "a", "inbox": [], "events": []},
            [{"kind": "inspect", "item": "folder"}, {"kind": "search"}, {"kind": "knock", "target": "office"}],
        )
        self.assertIn("inspect（item=folder", text)
        self.assertIn("search（搜一搜这里）", text)
        self.assertIn("interact（target=office", text)

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
        self.assertIn("你细看了folder", text)
        self.assertIn("你把folder交给了b", text)

    def test_world_message_spells_out_self_move_completion(self):
        from harness.prompt import render_world_message
        text = render_world_message({"observer": "a", "time": "now", "location": "finish",
                                     "events": [{"kind": "action_completed", "actor": "a",
                                                 "payload": {"action": "move", "target": "finish"}}]}, [])
        self.assertIn("你到了finish", text)

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
        self.assertNotIn("max_output_tokens", body)

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

    def test_provider_retries_valid_json_with_empty_output_text(self):
        first = Mock(); first.__enter__ = lambda self: self; first.__exit__ = Mock(return_value=False)
        first.read.return_value = b'{"output_text":""}'
        second = Mock(); second.__enter__ = lambda self: self; second.__exit__ = Mock(return_value=False)
        second.read.return_value = b'{"output_text":"ok"}'
        with patch("harness.provider.urlopen", side_effect=[first, second]) as opened:
            result = OpenAICompatible(model="m", retries=1, retry_backoff=0,
                                      sleep=lambda _: None)([])
        self.assertEqual(result, "ok")
        self.assertEqual(opened.call_count, 2)

    def test_provider_empty_output_payload_is_bounded_diagnostic_retryable_error(self):
        responses = []
        for payload in (b'{"output":[]}', b'{}'):
            response = Mock(); response.__enter__ = lambda self: self
            response.__exit__ = Mock(return_value=False); response.read.return_value = payload
            responses.append(response)
        with patch("harness.provider.urlopen", side_effect=responses) as opened:
            with self.assertRaisesRegex(RuntimeError, "no textual output") as raised:
                OpenAICompatible(model="m", retries=1, retry_backoff=0,
                                 sleep=lambda _: None)([])
        self.assertEqual(opened.call_count, 2)
        self.assertTrue(raised.exception.retryable)
        self.assertTrue(raised.exception.retry_exhausted)
        self.assertEqual(raised.exception.attempts, 2)

    def test_provider_rejects_oversized_request_before_network_with_diagnostics(self):
        with patch("harness.provider.urlopen") as opened:
            with self.assertRaisesRegex(ValueError, r"request body .* bytes exceeds limit 100") as raised:
                OpenAICompatible(model="m", max_request_bytes=100)([
                    {"role": "user", "content": "x" * 500}
                ])
        opened.assert_not_called()
        self.assertFalse(raised.exception.retryable)
        self.assertTrue(hasattr(raised.exception, "request_bytes"))
        self.assertEqual(raised.exception.request_limit, 100)

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

    def test_provider_complete_call_budget_includes_one_interpreter_call(self):
        provider = OpenAICompatible(model="m", timeout=10, retries=1,
                                    max_retries=1, max_duration=20,
                                    sleep=lambda _: None)
        self.assertLessEqual(provider.worst_case_seconds() * 2, 60)

    def test_provider_rejects_nonpositive_concurrency(self):
        with self.assertRaises(ValueError):
            OpenAICompatible(model="m", max_concurrency=0)

    def test_provider_full_turn_budget_allows_character_retry_and_gm(self):
        provider = OpenAICompatible(model="m", timeout=10, retries=1,
                                    max_retries=1, max_duration=20,
                                    sleep=lambda _: None)
        self.assertGreater(provider.worst_case_seconds() * 3 + 5, 60)

    def test_prompt_explicitly_satisfies_provider_json_mode(self):
        state = PrivateState("a")
        prompt = build_prompt(identity="A", private_seed="fact", state=state,
                              perception={"observer": "a"}, affordances=[])
        self.assertIn("JSON", prompt)
        self.assertIn("inner", prompt)

    def test_prompt_requires_identity_not_fast_decision(self):
        state = PrivateState("a")
        prompt = build_prompt(identity="A", private_seed="fact", state=state,
                              perception={"observer": "a"}, affordances=[])
        self.assertIn("全程在角色里", prompt)
        self.assertNotIn("do not deliberate at length", prompt)


class V4PhysicsTests(unittest.TestCase):
    """V4-DESIGN §2/§3/§5 的新机制：inner、别名遥测、可见性、中断、观察模型。"""

    def _world(self):
        return World(start=datetime.fromisoformat("2026-03-16T07:00:00+08:00"),
                     actors=[ActorState("a", "宿舍", known_contacts={"b"}),
                             ActorState("b", "宿舍", known_contacts={"a"}),
                             ActorState("c", "宿舍", known_contacts=set())],
                     locations=[LocationState("宿舍"), LocationState("学生会办公室")],
                     routes={("宿舍", "学生会办公室"): 600, ("学生会办公室", "宿舍"): 600})

    def test_descriptions_ride_a_much_slower_counter_than_state(self):
        # V4-DESIGN 首验日反馈 #3：状态（knowledge/布局）每 N=20 回合刷新；
        # 物品/地点描述只在首到、observe、压缩后（M=99999）出现。
        w = World(start=datetime.fromisoformat("2026-03-16T07:00:00+08:00"),
                  actors=[ActorState("a", "宿舍")],
                  locations=[LocationState("宿舍"), LocationState("学生会办公室")],
                  routes={("宿舍", "学生会办公室"): 600, ("学生会办公室", "宿舍"): 600},
                  entity_descriptions={"宿舍": "一张床，一张桌。",
                                      "学生会办公室": "一排铁皮柜。"},
                  public_knowledge={"老地下室": "维修中，约 3 月 18 日开。"})
        w.state_refresh_rounds = 20
        w.description_refresh_rounds = 99999
        first = w.poll("a")
        self.assertTrue(first["descriptions"])
        self.assertTrue(first["knowledge"])
        second = w.poll("a")
        self.assertNotIn("descriptions", second)
        self.assertEqual(second["knowledge"], {})
        # N 到期：状态回来，描述仍然不给。
        w.actors["a"].rounds_since_observation = 20
        third = w.poll("a")
        self.assertTrue(third["knowledge"])
        self.assertNotIn("descriptions", third)
        # observe 请求把描述带回来。
        w.actors["a"].observe_request = True
        fourth = w.poll("a")
        self.assertIn("descriptions", fourth)
        # 压缩重置：notify_compaction 后下一次 poll 全量（状态+描述）。
        w.notify_compaction("a")
        fifth = w.poll("a")
        self.assertIn("descriptions", fifth)
        self.assertTrue(fifth["knowledge"])

    def test_inner_is_parsed_bounded_and_private(self):
        from harness.adapter import parse_decision
        from harness.adapter import reset_alias_telemetry
        reset_alias_telemetry()
        intention, _ = parse_decision(
            "a", '{"inner":"先想清楚再说","type":"speak","args":{"text":"喂"}}', None)
        self.assertEqual(intention.inner, "先想清楚再说")
        long_inner = "想" * 300
        intention, _ = parse_decision(
            "a", '{"inner":"' + long_inner + '","type":"wait","args":{"duration_seconds":60}}', None)
        self.assertLessEqual(len(intention.inner), 210)
        self.assertTrue(intention.inner.endswith("已截断）"))

    def test_tolerant_parsing_handles_model_slips(self):
        from harness.adapter import parse_decision
        intention, _ = parse_decision(
            "a", "{'inner':'嗯','type':'wait','args':{'duration_seconds':60,}}", None)
        self.assertEqual(intention.kind, "wait")

    def test_alias_executes_and_counts(self):
        from harness.adapter import parse_decision, alias_telemetry, reset_alias_telemetry
        reset_alias_telemetry()
        intention, _ = parse_decision("a", '{"type":"wait","args":{"seconds":60}}', None)
        self.assertEqual(intention.args["duration_seconds"], 60)
        self.assertEqual(alias_telemetry().get("wait:seconds->duration_seconds"), 1)

    def test_normal_speech_reaches_location_whisper_only_named(self):
        from harness.adapter import parse_decision
        w = self._world()
        w.submit(parse_decision("a", '{"type":"speak","args":{"text":"大家好"}}', None)[0])
        speech = next(e for e in w.event_log if e.kind == "speech")
        self.assertEqual(speech.visible_to, frozenset({"a", "b", "c"}))
        w2 = self._world()
        w2.submit(parse_decision(
            "a", '{"type":"speak","args":{"text":"只告诉你","volume":"whisper","to":["b"]}}', None)[0])
        speech = next(e for e in w2.event_log if e.kind == "speech")
        self.assertEqual(speech.visible_to, frozenset({"a", "b"}))

    def test_interrupt_suspend_resume_and_abandon(self):
        from harness.adapter import parse_decision
        w = self._world()
        w.submit(parse_decision("a", '{"type":"wait","args":{"duration_seconds":900}}', None)[0])
        w.submit(parse_decision("b", '{"type":"speak","args":{"text":"打扰一下","interrupt":["a"]}}', None)[0])
        a = w.actors["a"]
        self.assertIsNone(a.busy_until)
        self.assertEqual(a.pending["remaining_seconds"], 900)
        self.assertIn({"kind": "continue_action"}, w.affordances("a"))
        w.submit(parse_decision("a", '{"type":"continue_action"}', None)[0])
        self.assertEqual((a.busy_until - w.now).total_seconds(), 900)
        # sleep defaults to uninterruptable
        w4 = self._world()
        w4.submit(parse_decision("a", '{"type":"sleep","args":{"duration_seconds":3600}}', None)[0])
        w4.submit(parse_decision("b", '{"type":"speak","args":{"text":"醒醒","interrupt":["a"]}}', None)[0])
        self.assertIsNone(w4.actors["a"].pending)

    def test_abandon_marks_action_failed(self):
        from harness.adapter import parse_decision
        w = self._world()
        w.submit(parse_decision("a", '{"type":"wait","args":{"duration_seconds":900}}', None)[0])
        w.submit(parse_decision("b", '{"type":"speak","args":{"text":"打断","interrupt":["a"]}}', None)[0])
        w.submit(parse_decision("a", '{"type":"abandon_action"}', None)[0])
        abandoned = next(e for e in w.event_log if e.kind == "action_abandoned")
        self.assertTrue(abandoned.payload["failed"])
        self.assertIsNone(w.actors["a"].pending)

    def test_move_duration_is_map_fact_not_argument(self):
        from harness.adapter import parse_decision
        w = self._world()
        w.submit(parse_decision("a", '{"type":"move","args":{"target":"学生会办公室"}}', None)[0])
        self.assertEqual((w.actors["a"].busy_until - w.now).total_seconds(), 600)

    def test_wait_is_bounded_by_longest_wait(self):
        from harness.adapter import parse_decision
        from harness.kernel import ActionRejected
        w = self._world()
        with self.assertRaises(ActionRejected):
            w.submit(parse_decision("a", '{"type":"wait","args":{"duration_seconds":3601}}', None)[0])

    def test_message_latency_is_one_tick(self):
        from harness.adapter import parse_decision
        w = self._world()
        w.submit(parse_decision("a", '{"type":"send_message","args":{"target":"b","text":"晚上见"}}', None)[0])
        self.assertEqual((w.actors["a"].busy_until - w.now).total_seconds(), 60)

    def test_document_read_content_stays_private_but_fact_is_public(self):
        from harness.adapter import parse_decision
        w = self._world()
        w.document_defs["memo"] = {"title": "便签", "content": "秘密内容"}
        w.item_locations["memo"] = "宿舍"
        w.submit(parse_decision("b", '{"type":"read","args":{"document":"memo"}}', None)[0])
        w.advance()
        content = next(e for e in w.event_log if e.kind == "document_read")
        self.assertEqual(content.visible_to, frozenset({"b"}))
        fact = next(e for e in w.event_log if e.kind == "action_completed"
                    and e.payload.get("action") == "read")
        self.assertIn("a", fact.visible_to)

    def test_others_wait_sleep_invisible(self):
        from harness.adapter import parse_decision
        w = self._world()
        w.submit(parse_decision("a", '{"type":"wait","args":{"duration_seconds":600}}', None)[0])
        w.advance()
        b_seen = [e.kind for e in w.event_log if "b" in e.visible_to]
        self.assertNotIn("action_started", b_seen)
        self.assertNotIn("action_completed", b_seen)


if __name__ == "__main__": unittest.main()

