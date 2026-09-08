"""Persona-and-notice tests: a repetitive loop breaks from either side.

The seed personas now carry social brakes (Amani does not repeat herself;
Lin would rather pause than pester someone who already said no). The runner's
frontier ``situational_notice`` makes an agent's own repetition visible. These
tests start *already inside* a loop and verify the mechanism lets a persona
break it from the asker's side, the answerer's side, or both.

This validates the harness->agent contract (notice delivered, personas that
honor it change behavior). Real-model behavior is a provider probe concern;
these are deterministic gates.
"""

import unittest
from datetime import datetime, timedelta

from harness.agent_state import PrivateState
from harness.character_loader import load_story_characters
from harness.kernel import ActorState, Intention, LocationState, World
from harness.repetition import RepetitionMonitor
from harness.runner import Runner
from harness.seed import load_story_pack
from harness.trace import Trace


def _small_world() -> World:
    return World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                 actors=[ActorState("a", "room"), ActorState("b", "room")],
                 locations=[LocationState("room")])


class PersonaLoopTests(unittest.TestCase):
    def test_seed_personas_include_social_brakes(self):
        # v4 slice: the brakes now live in the Chinese personas (V4-DESIGN §4):
        # 林瑶宁可停下来也不追着要答案；唐小岚知道她的消息是筹码，要拿捏分寸。
        pack = load_story_pack()
        seeds = load_story_characters(pack.root)
        # 中文 markdown 有硬换行，断言前先去掉空白。
        lin = "".join((seeds["林瑶"].identity + seeds["林瑶"].private_seed).split())
        self.assertIn("宁可停下来", lin)
        tang = "".join((seeds["唐小岚"].identity + seeds["唐小岚"].private_seed).split())
        # 唐小岚的刹车：不熟的人压低声音凑近，她会起鸡皮疙瘩（whisper 可疑常识）。
        self.assertIn("鸡皮疙瘩", tang)

    def test_asker_persona_breaks_loop_when_repetition_is_visible(self):
        # Start already inside the loop: a has sent four unanswered messages.
        world = _small_world()
        monitor = RepetitionMonitor()
        for index in range(4):
            monitor.note_turn("a", Intention(
                "a", "send_message", {"target": "b", "text": "same ask"}, index + 1), "submitted")
        states = {actor: PrivateState(actor) for actor in world.actors}

        def a_agent(state, perception, affordances):
            notice = perception.get("situational_notice") or ""
            if "messages in a row" in notice:
                return None  # Lin's pride: pause rather than pester
            return Intention("a", "send_message", {"target": "b", "text": "same ask"},
                             perception["world_version"])

        def b_agent(state, perception, affordances):
            return None

        trace = Trace("v3-test", "persona-asker")
        runner = Runner(world, {"a": a_agent, "b": b_agent}, states, trace, max_workers=2,
                        repetition=monitor)
        runner.run(stop_at=world.now + timedelta(minutes=1), max_turns=30)
        a_turns = [turn for turn in trace.agent_turns if turn["actor"] == "a"]
        self.assertTrue(a_turns)
        # The loop is visible from the very first turn a polls.
        self.assertIn("messages in a row",
                      a_turns[0]["perception"].get("situational_notice", ""))
        # A persona that honors the notice never repeats the ask.
        self.assertFalse(any(turn.get("intention")
                             and turn["intention"]["kind"] == "send_message"
                             for turn in a_turns))
        delivered_to_b = [event for event in world.event_log
                          if event.kind == "message_delivered"
                          and event.payload.get("target") == "b"]
        self.assertEqual(len(delivered_to_b), 0)

    def test_answerer_persona_stops_after_first_clear_answer(self):
        # Amani: answers once, clearly; further identical asks go unanswered,
        # so the loop breaks from the answerer's side even if the asker persists.
        world = _small_world()
        states = {actor: PrivateState(actor) for actor in world.actors}
        answered = {"count": 0}

        def a_agent(state, perception, affordances):
            return Intention("a", "send_message", {"target": "b", "text": "do you know?"},
                             perception["world_version"])

        def b_agent(state, perception, affordances):
            if perception.get("inbox"):
                if answered["count"] == 0:
                    answered["count"] += 1
                    return Intention("b", "send_message",
                                     {"target": "a", "text": "I already told you: I don't know."},
                                     perception["world_version"])
                return None  # will not repeat herself
            return None

        trace = Trace("v3-test", "persona-answerer")
        Runner(world, {"a": a_agent, "b": b_agent}, states, trace, max_workers=2).run(
            # 1 tick = 5 minutes per message (V4-DESIGN §3); give the window
            # room for a's repeated asks and b's single reply to land.
            stop_at=world.now + timedelta(minutes=25), max_turns=40)
        from_b = [event for event in world.event_log
                  if event.kind == "message_delivered" and event.actor == "b"]
        from_a = [event for event in world.event_log
                  if event.kind == "message_delivered" and event.actor == "a"]
        self.assertEqual(len(from_b), 1)          # answered exactly once
        self.assertGreaterEqual(len(from_a), 2)   # a kept asking regardless
        # b never replied to the repeated asks (loop broken on b's side).


if __name__ == "__main__":
    unittest.main()
