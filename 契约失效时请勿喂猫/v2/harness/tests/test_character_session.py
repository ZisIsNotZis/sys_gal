import unittest
from harness.character_loader import CharacterSeed
from harness.character_session import CharacterSession
from harness.agent_state import PrivateState


class CharacterSessionTests(unittest.TestCase):
    def seed(self):
        return CharacterSeed("a", "A is cautious.", "A remembers B.")

    def test_static_initialization_is_sent_once_and_transcript_continues(self):
        calls = []
        def model(messages):
            calls.append(messages)
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        session.decide("The sun rises.", 0)
        session.record_world_result("One minute passes.")
        session.decide("A bird lands nearby.", 1)
        self.assertEqual([m["role"] for m in calls[0]], ["system", "user", "user"])
        self.assertEqual(len(calls[1]), 6)
        self.assertEqual(calls[1][0], calls[0][0])
        self.assertEqual(calls[1][-1]["content"], "A bird lands nearby.")

    def test_world_result_is_retained_for_the_next_decision(self):
        calls = []
        def model(messages):
            calls.append(messages)
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        session.decide("The room is quiet.", 0)
        session.record_world_result(
            "The world accepted your move. It is in progress and will complete at 12:15."
        )
        session.decide("Your move to archive completed successfully. You are now at archive.", 1)
        self.assertIn("accepted your move", calls[1][-2]["content"])
        self.assertIn("completed successfully", calls[1][-1]["content"])

    def test_invalid_json_is_reported_to_same_character_then_retried(self):
        calls = []
        outputs = ['{"kind":"wait","args":}', '{"kind":"wait","args":{"duration_seconds":60}}']
        def model(messages):
            calls.append(messages)
            return outputs.pop(0)
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, _ = session.decide("The room is quiet.", 0)
        self.assertEqual(decision.kind, "wait")
        self.assertEqual(len(calls), 2)
        self.assertIn("cannot execute", calls[1][-1]["content"])

    def test_retryable_provider_failure_retries_same_turn_without_duplicate_update(self):
        calls = []
        attempts = [0]
        def model(messages):
            calls.append([dict(message) for message in messages])
            if attempts[0] == 0:
                attempts[0] += 1
                error = RuntimeError("upstream response did not reach a terminal state")
                error.retryable = True
                raise error
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, _ = session.decide("The room is quiet.", 0)
        self.assertEqual(decision.kind, "wait")
        self.assertEqual(len(calls), 2)
        self.assertEqual([m["content"] for m in calls[0]], [m["content"] for m in calls[1]])

    def test_natural_language_is_not_retried_as_format_error(self):
        calls = []
        def model(messages):
            calls.append(messages)
            return "I call Qiao and tell him I have not found the ledger."
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        from harness.character_session import NaturalIntention
        decision, _ = session.decide("The ledger is missing.", 0)
        self.assertIsInstance(decision, NaturalIntention)
        self.assertEqual(len(calls), 1)

    def test_natural_language_can_be_translated_by_explicit_gm(self):
        from harness.natural_agent import make_persistent_agent
        from harness.kernel import Intention
        seed = self.seed()
        def model(messages):
            return "I wait quietly."
        def gm(text, perception, affordances):
            return {"kind":"wait", "args":{"duration_seconds":60}}
        agent = make_persistent_agent(seed, model, gm)
        decision, updates = agent(PrivateState("a"), {"world_version":0,"time":"now","location":"room","events":[],"inbox":[]}, [{"kind":"wait","duration_seconds":60}])
        self.assertIsInstance(decision, Intention)
        self.assertEqual(decision.kind, "wait")

    def test_gm_resolution_is_auditable_and_malformed_output_is_bounded(self):
        from harness.natural_agent import make_persistent_agent
        seed = self.seed()
        def model(messages):
            return "I try to search the closed archive for the ledger."
        def gm(text, perception, affordances):
            return {"not_an_action": "invented plot"}
        agent = make_persistent_agent(seed, model, gm)
        decision, updates = agent(
            PrivateState("a"),
            {"world_version": 4, "time": "now", "location": "room",
             "events": [], "inbox": [], "private_notes": ["must not leak"]},
            [{"kind": "wait", "duration_seconds": 60}],
        )
        self.assertIsNone(decision)
        self.assertEqual(updates, {})
        audit = agent.drain_gm_records()
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["actor"], "a")
        self.assertEqual(audit[0]["original_prose"], "I try to search the closed archive for the ledger.")
        self.assertEqual(audit[0]["perception"], {
            "world_version": 4, "time": "now", "location": "room",
            "events": [], "inbox": [], "private_notes": ["must not leak"]})
        self.assertEqual(audit[0]["affordances"], [{"kind": "wait", "duration_seconds": 60}])
        self.assertEqual(audit[0]["result"], {"not_an_action": "invented plot"})
        self.assertIn("ValueError", audit[0]["error"])

    def test_gm_cannot_select_an_action_outside_visible_affordances(self):
        from harness.natural_agent import make_persistent_agent
        agent = make_persistent_agent(
            self.seed(), lambda messages: "I search the archive.",
            lambda text, perception, affordances: {
                "kind": "inspect", "args": {"target": "archive"},
            })
        decision, updates = agent(
            PrivateState("a"), {"world_version": 0, "time": "now", "location": "room",
                                 "events": [], "inbox": []},
            [{"kind": "wait", "duration_seconds": 60}],
        )
        self.assertIsNone(decision)
        self.assertEqual(updates, {})
        self.assertIn("not offered", agent.drain_gm_records()[0]["error"])

    def test_gm_tuple_escape_hatch_cannot_return_fabricated_intention(self):
        from harness.natural_agent import make_persistent_agent
        from harness.kernel import Intention
        agent = make_persistent_agent(
            self.seed(), lambda messages: "I search the archive.",
            lambda text, perception, affordances: (
                Intention("a", "wait", {"duration_seconds": 60}, 0),
                {"private_notes": ["untrusted"]},
                "extra",
            ))
        decision, updates = agent(
            PrivateState("a"), {"world_version": 0, "time": "now", "location": "room",
                                 "events": [], "inbox": []},
            [{"kind": "wait", "duration_seconds": 60}],
        )
        self.assertIsNone(decision)
        self.assertEqual(updates, {})
        audit = agent.drain_gm_records()[0]
        self.assertIn("ValueError", audit["error"])

    def test_world_updates_are_natural_language(self):
        from harness.prompt import render_world_message
        text = render_world_message({"time":"now", "location":"room", "inbox":[], "events":[]},
                                    [{"kind":"wait", "duration_seconds":900}])
        self.assertIn("The time is now", text)
        self.assertIn("wait", text)
        self.assertNotIn('"time"', text)

    def test_compaction_keeps_initialization_and_recent_turns(self):
        calls = []
        def model(messages):
            calls.append(messages)
            if any("Compress the preceding" in m["content"] for m in messages):
                return "I remember that the ledger was missing and I promised to ask Qiao."
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model,
                                   compaction_threshold=180, recent_messages=4)
        for i in range(8):
            session.decide("A long world update number " + str(i) + " happened.", i)
            session.record_world_result("The action completed after a long interval.")
        self.assertTrue(session.compacted_memories)
        self.assertEqual(session.messages[0]["role"], "system")
        self.assertIn("Earlier memories", session.messages[2]["content"])
        # Authoritative feedback is retained verbatim for continuity; the
        # bounded transcript still keeps only the fixed prologue, one memory,
        # the feedback block, and the recent window.
        self.assertLess(sum(len(m["content"]) for m in session.messages), 2000)

    def test_compaction_keeps_authoritative_feedback_in_order_without_duplicate_turns(self):
        calls = []
        def model(messages):
            calls.append([dict(message) for message in messages])
            if any("Compress the preceding" in message["content"] for message in messages):
                return "I remember the open commitment and the failed move."
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model,
                                   compaction_threshold=260, recent_messages=4)
        feedback = ["AUTHORITATIVE RESULT [%d]: event %d remains recorded." % (i, i)
                    for i in range(1, 9)]
        for index, result in enumerate(feedback):
            session.decide("World update " + str(index) + " happened.", index)
            session.record_world_result(result)
        session.decide("A new event wakes you.", 3)
        requests = [messages for messages in calls
                    if any("Compress the preceding" in m["content"] for m in messages)]
        self.assertTrue(requests)
        request_text = "\n".join(m["content"] for m in requests[-1])
        for result in feedback:
            self.assertIn(result, request_text)
        current_text = "\n".join(m["content"] for m in session.messages)
        self.assertIn("Earlier memories", current_text)
        self.assertIn("A new event wakes you.", current_text)
        for result in feedback:
            self.assertEqual(current_text.count(result), 1)

    def test_private_updates_are_visible_to_the_character_on_the_next_turn(self):
        calls = []
        def model(messages):
            calls.append([dict(message) for message in messages])
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        state = PrivateState("a")
        session = CharacterSession(self.seed(), state, model)
        session.decide("The room is quiet.", 0)
        state.private_notes.append("remember the unresolved promise")
        session.decide("The door remains closed.", 1)
        self.assertIn("remember the unresolved promise", calls[-1][-1]["content"])

    def test_compaction_does_not_send_private_state_to_gm(self):
        from harness.natural_agent import make_persistent_agent
        gm_inputs = []
        def model(messages):
            if any("Compress the preceding" in m["content"] for m in messages):
                return "The person remembers the unresolved promise."
            return "I describe a complex action."
        def gm(text, perception, affordances):
            gm_inputs.append((text, perception, affordances))
            return None
        agent = make_persistent_agent(self.seed(), model, gm)
        state = PrivateState("a", private_notes=["secret private note"])
        perception = {"world_version": 0, "time": "now", "location": "room",
                      "events": [], "inbox": []}
        for index in range(8):
            agent(state, {**perception, "world_version": index},
                  [{"kind": "wait", "duration_seconds": 60}])
            agent.session().record_world_result("AUTHORITATIVE RESULT [" + str(index) + "]")
        agent(state, {**perception, "world_version": 9},
              [{"kind": "wait", "duration_seconds": 60}])
        self.assertTrue(gm_inputs)
        for _, gm_perception, _ in gm_inputs:
            self.assertNotIn("secret private note", str(gm_perception))
