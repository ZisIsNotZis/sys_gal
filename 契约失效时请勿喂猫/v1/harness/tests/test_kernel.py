from datetime import datetime, timedelta
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[2]))

from harness.kernel import ActionRejected, Intention
from harness.seed import create_v1_world


START = datetime.fromisoformat("2026-03-16T07:00:00+08:00")


class KernelTests(unittest.TestCase):
    def test_private_message_metadata_is_not_visible_to_roommate(self):
        world = create_v1_world()
        world.submit(Intention("chen-mo", "send_message", {"target": "lin-yao", "text": "secret"}))
        packet = world.poll_perception("gao-rui")
        self.assertFalse(any(event["kind"] == "action_started" and "secret" in str(event) for event in packet["events"]))
        self.assertFalse(any(event["kind"] == "message_sent" for event in packet["events"]))
        world.advance()
        packet = world.poll_perception("gao-rui")
        self.assertFalse(any(event["kind"] == "action_completed" and "secret" in str(event) for event in packet["events"]))
        self.assertFalse(any(event["kind"] == "action_completed" and "lin-yao" in str(event) for event in packet["events"]))

    def test_zero_duration_action_drains_all_events_at_current_timestamp(self):
        world = create_v1_world()
        world._schedule(START, "world_event", None, {"event": "same-time"}, cause=None)
        world.submit(Intention("chen-mo", "open"))
        self.assertEqual(world.next_event_time(), START + timedelta(minutes=20))
        self.assertFalse(world.has_pending_events is False)
        self.assertTrue(world.locations["dorm-3-room-417"].open)
        self.assertEqual([event.kind for event in world.event_log[-2:]], ["world_event", "action_completed"])

    def test_closed_destination_rejects_movement(self):
        world = create_v1_world()
        with self.assertRaises(ActionRejected):
            world.submit(Intention("chen-mo", "move", {"target": "community-partnerships-office", "duration_seconds": 1080}))

    def test_speech_takes_time_and_is_visible_only_to_people_in_the_room(self):
        world = create_v1_world()
        world.submit(Intention("chen-mo", "speak", {"text": "Gao, are you awake?"}))
        speech = world.event_log[-1]
        self.assertEqual(speech.kind, "speech")
        self.assertEqual(speech.visible_to, frozenset({"chen-mo", "gao-rui", "three-legged-cat"}))
        self.assertEqual(world.now, START)
        world.advance()
        self.assertEqual(world.now, START + timedelta(seconds=3))


    def test_message_is_delivered_after_fixed_delay_and_only_recipient_sees_it(self):
        world = create_v1_world()
        world.submit(Intention("chen-mo", "send_message", {"target": "lin-yao", "text": "Can we talk?"}))
        world.advance()
        self.assertEqual(world.now, START + timedelta(seconds=5))
        self.assertEqual(world.actors["lin-yao"].inbox, [{
            "from": "chen-mo", "text": "Can we talk?", "sent_at": (START + timedelta(seconds=5)).isoformat()
        }])
        packet = world.poll_perception("lin-yao")
        self.assertEqual(packet["inbox"][0]["text"], "Can we talk?")
        self.assertTrue(any(event["kind"] == "message_delivered" for event in packet["events"]))
        self.assertEqual(packet["events"][-1]["payload"]["target"], "lin-yao")


    def test_stale_intention_and_invalid_action_do_not_mutate_world(self):
        world = create_v1_world()
        before = (world.version, len(world.event_log), world.now)
        with self.assertRaises(ActionRejected):
            world.submit(Intention("chen-mo", "teleport", expected_version=world.version))
        with self.assertRaises(ActionRejected):
            world.submit(Intention("chen-mo", "wait", {"duration_seconds": 1}, expected_version=99))
        self.assertEqual((world.version, len(world.event_log), world.now), before)


    def test_affordances_do_not_offer_unreachable_items_or_routes(self):
        world = create_v1_world()
        options = world.affordances("chen-mo")
        self.assertEqual({option.get("item") for option in options if option["kind"] == "take"}, set())
        self.assertEqual(
            {option.get("target") for option in options if option["kind"] == "move"},
            {"greenhouse-courtyard", "community-partnerships-office", "student-union-room"},
        )


    def test_perception_is_private_and_does_not_leak_system_or_distant_events(self):
        world = create_v1_world()
        event = world._commit("system", "chen-mo", {"case": "three-way-ambiguity"}, cause=None)
        self.assertEqual(event.visible_to, frozenset({"chen-mo"}))
        chen_packet = world.poll_perception("chen-mo")
        gao_packet = world.poll_perception("gao-rui")
        self.assertTrue(any(item["kind"] == "system" for item in chen_packet["events"]))
        self.assertFalse(any(item["kind"] == "system" for item in gao_packet["events"]))

    def test_until_processes_all_events_through_boundary(self):
        world = create_v1_world()
        world.submit(Intention("chen-mo", "send_message", {"target": "lin-yao", "text": "one"}))
        world.submit(Intention("gao-rui", "send_message", {"target": "chen-mo", "text": "two"}))
        world.advance(until=START + timedelta(seconds=5))
        self.assertEqual(world.now, START + timedelta(seconds=5))
        self.assertEqual(len(world.actors["chen-mo"].inbox), 1)
        self.assertEqual(len(world.actors["lin-yao"].inbox), 1)

    def test_story_terminal_requires_explicit_phase_reason_and_all_major_actors(self):
        world = create_v1_world()
        world.advance(until=datetime.fromisoformat("2026-03-27T21:30:00+08:00"))
        self.assertEqual(world.story_phase, "ending")
        self.assertIsNone(world.terminal_reason)
        self.assertFalse(any(event.kind == "story_terminal" for event in world.event_log))
        self.assertTrue(getattr(world, "_pending_terminal_reason", None))

    def test_until_records_explicit_clock_advance_when_no_event_exists(self):
        world = create_v1_world()
        world._queue.clear()
        target = START + timedelta(minutes=5)
        world.advance(until=target)
        self.assertEqual(world.now, target)
        self.assertEqual(world.event_log[-1].kind, "time_advanced")
        self.assertEqual(world.event_log[-1].payload["to"], target.isoformat())


    def test_same_seed_slice_has_replayable_log_shape(self):
        first = create_v1_world()
        second = create_v1_world()
        intent = Intention("chen-mo", "speak", {"text": "Hello."})
        first.submit(intent)
        second.submit(intent)
        first.advance()
        second.advance()
        self.assertEqual(first.replayable_log(), second.replayable_log())

    def test_belief_update_requires_visible_evidence_and_is_private(self):
        world = create_v1_world()
        speech = world._commit("speech", "chen-mo", {"text": "I saw the form."}, cause=None)
        world.submit(Intention("chen-mo", "update_belief", {
            "proposition": "the form is outdated", "confidence": 0.8,
            "evidence_event_id": speech.id,
        }))
        packet = world.poll_perception("chen-mo")
        self.assertEqual(packet["beliefs"]["the form is outdated"], 0.8)
        self.assertNotIn("the form is outdated", world.poll_perception("gao-rui")["beliefs"])

    def test_mental_update_cannot_cite_private_or_unknown_evidence(self):
        world = create_v1_world()
        private = world._commit("system", "chen-mo", {"secret": True}, cause=None)
        with self.assertRaises(ActionRejected):
            world.submit(Intention("gao-rui", "update_belief", {
                "proposition": "secret", "confidence": 1.0, "evidence_event_id": private.id,
            }))
        with self.assertRaises(ActionRejected):
            world.submit(Intention("chen-mo", "update_relationship", {
                "target": "gao-rui", "delta": 2, "evidence_event_id": 9999,
            }))

    def test_relationship_update_is_bounded_and_recorded(self):
        world = create_v1_world()
        evidence = world._commit("speech", "gao-rui", {"text": "I was wrong."}, cause=None)
        world.submit(Intention("chen-mo", "update_relationship", {
            "target": "gao-rui", "delta": -3, "evidence_event_id": evidence.id,
        }))
        self.assertEqual(world.actors["chen-mo"].relationships["gao-rui"], -3)
        event = next(event for event in reversed(world.event_log) if event.kind == "update_relationship")
        self.assertEqual(event.kind, "update_relationship")
        self.assertEqual(event.payload["evidence_event_id"], evidence.id)


if __name__ == "__main__":
    unittest.main()
