"""Ticket 49 — objective observation, memory emergence, and stay-read.

Ruling 2026-09-30: every entity already carries an objective description (the
Markdown body). The moment an actor actually sees one — an item in view, a
place reached, a thing held — the engine records that objective description as
a new memory row for that actor, emits an observable ``observed`` world event,
and never lets the description be lost to context compaction. Reading is no
longer a model chore: staying in view of a readable thing for its
``reading_seconds`` counts as having read it.

These tests are the pre-run gate for the failure class "objective description
was a one-shot snapshot: never entered memory, could not survive compaction".
"""

import unittest
from datetime import datetime, timedelta

from harness.kernel import (ActionRejected, ActorState, Intention, LocationState,
                            World)

START = datetime.fromisoformat("2026-03-16T07:00:00+08:00")
# Objective prose must read as fact; these are the slips that turn a
# description into a subjective inference.
SUBJECTIVE_WORDS = ("大概", "也许", "似乎", "好像", "应该", "我猜", "可能",
                    "想必", "恐怕", "应该是")

PROP = "# 旧哨子\n\n一只小小的红色哨子，漆面有几道划痕。"
LEDGER = "# 台账\n\n一本蓝色封皮的登记簿。"
PLACE = "# 实验室\n\n靠墙一排铁皮柜，窗边一张长桌。"
HALL = "# 走廊\n\n两侧全是关着的门。"
FAR = "# 库房\n\n角落里堆着落灰的纸箱。"


class _WorldMixin:
    def world(self, **overrides):
        defaults = dict(
            start=START,
            actors=[ActorState("a", "lab"), ActorState("b", "lab")],
            locations=[LocationState("lab"), LocationState("hall")],
            routes={("lab", "hall"): 60, ("hall", "lab"): 60},
            item_locations={"old_whistle": "lab", "ledger": "lab"},
            document_defs={"ledger": {"title": "台账", "content": "正文甲。",
                                      "reading_seconds": 120}},
            entity_descriptions={"lab": PLACE, "hall": HALL,
                                 "old_whistle": PROP, "ledger": LEDGER},
        )
        defaults.update(overrides)
        return World(**defaults)

    def observed_events(self, world):
        return [e for e in world.event_log if e.kind == "observed"]


class ObjectiveObservationTests(_WorldMixin, unittest.TestCase):
    def test_first_sight_records_objective_and_emits_a_private_event(self):
        world = self.world()
        packet = world.poll("a")

        # (a) every visible entity is registered once, with its objective text.
        observed = world.actors["a"].observed
        self.assertEqual(set(observed), {"lab", "old_whistle", "ledger"})
        self.assertEqual(observed["old_whistle"]["where"], "lab")
        self.assertIn("一只小小的红色哨子", observed["old_whistle"]["objective"])
        self.assertNotIn("#", observed["old_whistle"]["objective"])
        self.assertEqual(observed["lab"]["objective"].splitlines()[0],
                         "靠墙一排铁皮柜，窗边一张长桌。")

        # the observable measurement exists: one `observed` event per entity,
        # private to the actor.
        events = self.observed_events(world)
        self.assertEqual({e.payload["entity"] for e in events},
                         {"lab", "old_whistle", "ledger"})
        for event in events:
            self.assertEqual(event.visible_to, frozenset({"a"}))
            self.assertEqual(event.payload["where"], "lab")

        # the description still reaches the model through the existing channel.
        self.assertIn("old_whistle", packet["descriptions"])
        self.assertEqual(packet["descriptions"]["lab"], PLACE)

        # a co-located actor never perceives another actor's observation event.
        other = world.poll("b")
        self.assertEqual(len([e for e in other["events"]
                              if e["kind"] == "observed"]), 3)

    def test_an_entity_is_recorded_only_once(self):
        world = self.world()
        world.poll("a")
        first = len(self.observed_events(world))
        second = world.poll("a")
        self.assertEqual(len(self.observed_events(world)), first)
        self.assertNotIn("descriptions", second)

    def test_observed_survives_a_checkpoint_round_trip(self):
        world = self.world()
        world.poll("a")
        snapshot = world.checkpoint_state()
        restored = World.from_checkpoint(self.world(), snapshot)
        self.assertEqual(restored.actors["a"].observed,
                         world.actors["a"].observed)
        # resuming must not re-emit the first-sight events.
        before = len([e for e in restored.event_log if e.kind == "observed"])
        restored.poll("a")
        self.assertEqual(len([e for e in restored.event_log
                              if e.kind == "observed"]), before)

    def test_known_to_stays_awareness_only(self):
        # (g) a known_to entity elsewhere is neither observed nor described.
        world = self.world(item_locations={"old_whistle": "hall", "ledger": "lab"},
                           entity_access={"old_whistle": {"a"}})
        packet = world.poll("a")
        self.assertNotIn("old_whistle", world.actors["a"].observed)
        self.assertNotIn("old_whistle", packet["descriptions"])
        self.assertFalse(any(e.payload["entity"] == "old_whistle"
                             for e in self.observed_events(world)))


class ReadFallbackTests(_WorldMixin, unittest.TestCase):
    def test_read_of_a_seen_prop_returns_its_objective_description(self):
        # (d) a thing the actor has seen but that carries no readable body:
        # the rejection must state the real situation AND hand back the
        # system-layer objective description, never a guess.
        world = self.world()
        world.poll("a")
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("a", "read", {"item": "old_whistle"},
                                   world.version))
        message = str(caught.exception)
        self.assertEqual(caught.exception.context["reason"],
                         "present_without_body")
        objective = world.actors["a"].observed["old_whistle"]["objective"]
        self.assertIn(objective, message)
        self.assertIn("看见过", message)
        for word in SUBJECTIVE_WORDS:
            self.assertNotIn(word, message, f"subjective wording: {word}")

    def test_read_of_a_seen_prop_now_elsewhere_returns_its_objective(self):
        world = self.world(entity_access={"old_whistle": {"a"}})
        world.poll("a")
        world.actors["a"].location = "hall"
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("a", "read", {"item": "old_whistle"},
                                   world.version))
        message = str(caught.exception)
        self.assertEqual(caught.exception.context["reason"],
                         "known_not_readable_not_here")
        objective = world.actors["a"].observed["old_whistle"]["objective"]
        self.assertIn(objective, message)
        for word in SUBJECTIVE_WORDS:
            self.assertNotIn(word, message, f"subjective wording: {word}")

    def test_read_of_an_unknown_thing_does_not_invent_a_description(self):
        # Nothing was seen: no objective text may be fabricated.
        world = self.world(entity_descriptions={}, item_locations={},
                           document_defs={})
        with self.assertRaises(ActionRejected) as caught:
            world.submit(Intention("a", "read", {"item": "ghost"},
                                   world.version))
        self.assertNotIn("看见过", str(caught.exception))


class StayReadTests(_WorldMixin, unittest.TestCase):
    def _auto_reads(self, world, actor="a"):
        return [e for e in world.event_log
                if e.kind == "document_read" and e.actor == actor
                and e.payload.get("auto")]

    def test_staying_for_reading_seconds_counts_as_having_read(self):
        # (e) full dwell → one auto document_read, delivered to the reader.
        world = self.world()
        world.poll("a")                                   # dwell starts
        world.advance(until=START + timedelta(seconds=120))
        packet = world.poll("a")
        auto = [e for e in packet["events"]
                if e["kind"] == "document_read" and e["payload"].get("auto")]
        self.assertEqual(len(auto), 1)
        self.assertEqual(auto[0]["payload"]["document"], "ledger")
        self.assertEqual(auto[0]["payload"]["content"], "正文甲。")
        self.assertEqual(len(self._auto_reads(world)), 1)
        # only once.
        world.poll("a")
        self.assertEqual(len(self._auto_reads(world)), 1)

    def test_leaving_before_reading_seconds_resets_the_clock(self):
        # (e) the timer is a continuous-stay timer: leaving voids it.
        world = self.world()
        world.poll("a")                                   # dwell starts at t0
        world.submit(Intention("a", "move", {"target": "hall"}, world.version))
        world.advance()                                   # at hall, t0+60
        world.poll("a")
        world.submit(Intention("a", "move", {"target": "lab"}, world.version))
        world.advance()                                   # back at t0+120
        world.poll("a")                                   # dwell restarts
        world.advance(until=START + timedelta(seconds=180))
        world.poll("a")                                   # 60s < 120s
        self.assertEqual(self._auto_reads(world), [])

    def test_auto_read_false_requires_reading_on_purpose(self):
        # (f) manifest-level opt-out for story-critical documents.
        world = self.world(document_defs={
            "ledger": {"title": "台账", "content": "正文甲。",
                       "reading_seconds": 120, "auto_read": False}})
        world.poll("a")
        world.advance(until=START + timedelta(seconds=120))
        world.poll("a")
        self.assertEqual(self._auto_reads(world), [])
        # the active read still works and is not marked auto.
        world.submit(Intention("a", "read", {"item": "ledger"}, world.version))
        world.advance()
        reads = [e for e in world.event_log if e.kind == "document_read"]
        self.assertEqual(len(reads), 1)
        self.assertNotIn("auto", reads[0].payload)

    def test_an_active_read_stops_a_later_auto_read(self):
        world = self.world()
        world.poll("a")
        world.submit(Intention("a", "read", {"item": "ledger"}, world.version))
        world.advance()
        world.advance(until=START + timedelta(seconds=300))
        world.poll("a")
        self.assertEqual(self._auto_reads(world), [])

    def test_auto_read_body_reaches_the_reader_alone(self):
        # Ticket 49: stay-read has no tool call, so its body must arrive
        # through the document_read private delivery — and nothing else.
        from harness.prompt import render_world_message
        world = self.world()
        world.poll("a")
        world.advance(until=START + timedelta(seconds=120))
        reader = render_world_message(world.poll("a"), [], knowledge_lines=[])
        self.assertIn("正文甲。", reader)
        other = world.poll("b")
        self.assertFalse(any(e["kind"] == "document_read" for e in other["events"]))
        self.assertNotIn("正文甲。", render_world_message(other, [], knowledge_lines=[]))


if __name__ == "__main__":
    unittest.main()
