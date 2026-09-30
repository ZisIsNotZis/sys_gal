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
                "lin", "text", {"target": "amani", "text": "?"}, index + 1), "submitted")
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
            monitor.note_turn("a", Intention("a", "text",
                                             {"target": "b", "text": "hi"}, index + 1), "submitted")
        restored = RepetitionMonitor()
        restored.restore(monitor.state())
        self.assertEqual(restored.notice("a"), monitor.notice("a"))

    def test_chain_shaped_text_drives_the_message_loop(self):
        # Ticket 43: the chain path wraps the calls, so the unanswered-message
        # counter must read the target from the inner text call — otherwise it
        # too was dead on the run's real path.
        monitor = RepetitionMonitor(message_threshold=4, message_stride=3)
        text = Intention("lin", "text", {"calls": [
            {"name": "text", "args": {"target": "amani", "text": "?"}}]}, 1)
        for _ in range(4):
            monitor.note_turn("lin", text, "submitted")
        notice = monitor.notice("lin")
        self.assertIsNotNone(notice)
        self.assertIn("amani", notice)

    def test_consecutive_waits_stagnate_with_a_concrete_action_and_stride(self):
        # Ticket 43: wait is no longer exempt. Consecutive waits accumulate,
        # fire once at the threshold, then on the stride — never every turn —
        # and the notice names both the elapsed simulated time and at least
        # one action the character can actually still take.
        monitor = RepetitionMonitor(stagnation_threshold=4, stagnation_stride=4)
        # Chain shape: recorded.args wraps the calls, so the duration is read
        # from the inner wait call (the live engine path).
        wait = Intention("tang", "wait", {"calls": [
            {"name": "wait", "args": {"duration_seconds": 600}}]}, 1)
        for _ in range(3):
            monitor.note_turn("tang", wait, "submitted")
        self.assertIsNone(monitor.notice("tang"))
        monitor.note_turn("tang", wait, "submitted")
        notice = monitor.notice("tang", affordances=[
            {"kind": "move", "target": "中庭"},
            {"kind": "read", "item": "草稿"},
            {"kind": "wait", "duration_seconds": 600}])
        self.assertIsNotNone(notice)
        self.assertIn("waiting in place", notice)
        self.assertIn("40 min", notice)          # 4 × 600 s of simulated time
        self.assertIn("move to 中庭", notice)     # a real executable action
        # Stride: the 5th–7th waits stay quiet; the 8th fires again.
        for _ in range(3):
            monitor.note_turn("tang", wait, "submitted")
        self.assertIsNone(monitor.notice("tang"))
        monitor.note_turn("tang", wait, "submitted")
        self.assertIsNotNone(monitor.notice(
            "tang", affordances=[{"kind": "move", "target": "中庭"}]))

    def test_consecutive_sleeps_never_stagnate(self):
        # Overnight sleep is not stagnation: it stays exempt (ticket 43).
        monitor = RepetitionMonitor(stagnation_threshold=4)
        sleep = Intention("a", "sleep", {"duration_seconds": 28800}, 1)
        for _ in range(10):
            monitor.note_turn("a", sleep, "submitted")
        self.assertIsNone(monitor.notice("a"))

    def test_a_non_wait_or_relocated_turn_restarts_the_wait_run(self):
        monitor = RepetitionMonitor(stagnation_threshold=4)
        wait = Intention("a", "wait", {"duration_seconds": 600}, 1)
        for _ in range(3):
            monitor.note_turn("a", wait, "submitted", location="room")
        # A non-wait action (even a rejected one) breaks the run.
        monitor.note_turn("a", Intention("a", "read", {"item": "台账"}, 1),
                          "rejected", location="room")
        for _ in range(3):
            monitor.note_turn("a", wait, "submitted", location="room")
        self.assertIsNone(monitor.notice("a"))
        monitor.note_turn("a", wait, "submitted", location="room")
        self.assertIsNotNone(monitor.notice("a"))
        # A change of location also breaks the run.
        for _ in range(3):
            monitor.note_turn("a", wait, "submitted", location="courtyard")
        self.assertIsNone(monitor.notice("a"))
        monitor.note_turn("a", wait, "submitted", location="courtyard")
        self.assertIsNotNone(monitor.notice(
            "a", affordances=[{"kind": "move", "target": "中庭"}]))

    def test_stagnation_state_round_trips(self):
        monitor = RepetitionMonitor(stagnation_threshold=4)
        for _ in range(4):
            monitor.note_turn("a", Intention("a", "wait",
                                              {"duration_seconds": 600}, 1), "submitted")
        restored = RepetitionMonitor(stagnation_threshold=4)
        restored.restore(monitor.state())
        self.assertEqual(
            restored.notice("a", affordances=[{"kind": "move", "target": "x"}]),
            monitor.notice("a", affordances=[{"kind": "move", "target": "x"}]))

    def test_runner_injects_notice_into_perception_at_frontier(self):
        world = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                      actors=[ActorState("a", "room"), ActorState("b", "room")],
                      locations=[LocationState("room")])

        def agent(state, perception, affordances):
            if state.actor_id == "a":
                return Intention("a", "text", {"target": "b", "text": "hello"},
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

