"""Tests for the frontier repetition-awareness notice."""

import unittest
from datetime import datetime, timedelta

from harness.agent_state import PrivateState
from harness.kernel import ActorState, Intention, LocationState, World
from harness.prompt import render_world_message
from harness.repetition import RepetitionMonitor
from harness.runner import Runner
from harness.trace import Trace


class RepetitionMonitorTests(unittest.TestCase):
    def test_message_loop_notice_fires_after_threshold_and_resets_on_reply(self):
        monitor = RepetitionMonitor(message_threshold=4, message_stride=3)
        for index in range(4):
            monitor.note_turn("lin", Intention(
                "lin", "send_message", {"target": "amani", "text": "?"}, index + 1), "submitted")
        notice = monitor.notice("lin")
        self.assertIsNotNone(notice)
        self.assertIn("amani", notice)
        self.assertIn("messages in a row", notice)
        # A reply from the target resets the counter and clears the announcement.
        monitor.note_message_received("lin", "amani")
        self.assertIsNone(monitor.notice("lin"))

    def test_action_loop_notice_fires_for_identical_rejected_action_and_resets_on_success(self):
        monitor = RepetitionMonitor(action_threshold=5)
        intention = Intention("chen", "move", {"target": "old-basement",
                                               "duration_seconds": 1200}, 1)
        for index in range(5):
            monitor.note_turn("chen", intention, "rejected")
        self.assertIn("same action", monitor.notice("chen"))
        monitor.note_turn("chen", intention, "submitted")
        self.assertIsNone(monitor.notice("chen"))

    def test_state_round_trip(self):
        monitor = RepetitionMonitor()
        for index in range(4):
            monitor.note_turn("a", Intention("a", "send_message",
                                             {"target": "b", "text": "hi"}, index + 1), "submitted")
        restored = RepetitionMonitor()
        restored.restore(monitor.state())
        self.assertEqual(restored.notice("a"), monitor.notice("a"))

    def test_runner_injects_notice_into_perception_at_frontier(self):
        world = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                      actors=[ActorState("a", "room"), ActorState("b", "room")],
                      locations=[LocationState("room")])

        def agent(state, perception, affordances):
            if state.actor_id == "a":
                return Intention("a", "send_message", {"target": "b", "text": "hello"},
                                 perception["world_version"])
            return None

        states = {actor: PrivateState(actor) for actor in world.actors}
        trace = Trace("v3-test", "repetition-runner")
        Runner(world, {actor: agent for actor in world.actors}, states, trace,
               max_workers=2).run(
                   # 1 tick = 5 min per message (V4-DESIGN §3); give the
                   # window room for the repetition pattern to build.
                   stop_at=world.now + timedelta(minutes=25), max_turns=60)
        notices = [turn["perception"].get("situational_notice")
                   for turn in trace.agent_turns if turn["actor"] == "a"]
        self.assertTrue(any(notice and "messages in a row" in notice for notice in notices))

    def test_prompt_renders_notice_at_the_end(self):
        text = render_world_message(
            {"time": "now", "location": "room", "inbox": [], "events": [],
             "situational_notice": "You have sent b 4 messages in a row without a reply."},
            [{"kind": "wait", "duration_seconds": 900}])
        self.assertIn("messages in a row", text)
        # The notice is a frontier line before the action shapes.
        self.assertTrue(text.index("messages in a row") < text.index("# actions"))


if __name__ == "__main__":
    unittest.main()
