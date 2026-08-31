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

    def test_two_malformed_json_responses_are_retried_before_failure(self):
        calls = []
        def model(messages):
            calls.append(messages)
            return '{"kind":"wait","args":{"duration_seconds":60}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        with self.assertRaises(Exception):
            session.decide("The room is quiet.", 0)
        self.assertEqual(len(calls), 5)

    def test_many_transient_provider_failures_use_the_session_bound(self):
        calls = []
        def model(messages):
            calls.append(messages)
            if len(calls) <= 4:
                error = RuntimeError("upstream empty response")
                error.retryable = True
                raise error
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, _ = session.decide("The room is quiet.", 0)
        self.assertEqual(decision.kind, "wait")
        self.assertEqual(len(calls), 5)

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

    def test_exhausted_provider_failure_is_retried_before_any_action_exists(self):
        calls = []
        attempts = [0]
        def model(messages):
            calls.append(messages)
            if attempts[0] == 0:
                attempts[0] += 1
                error = RuntimeError("provider HTTP 502 after bounded retries")
                error.retryable = True
                error.retry_exhausted = True
                raise error
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, _ = session.decide("The room is quiet.", 0)
        self.assertEqual(decision.kind, "wait")
        self.assertEqual(len(calls), 2)

    def test_malformed_private_update_does_not_block_physical_action(self):
        def model(messages):
            return '{"kind":"wait","args":{"duration_seconds":60},"updates":{"mystery":true}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, updates = session.decide("The room is quiet.", 0)
        self.assertEqual(decision.kind, "wait")
        self.assertEqual(updates, {"mystery": True})

    def test_string_memory_update_is_accepted_for_natural_character_output(self):
        def model(messages):
            return '{"kind":"wait","args":{"duration_seconds":60},"updates":{"memories":["I remember this room."]}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, updates = session.decide("The room is quiet.", 0)
        self.assertEqual(decision.kind, "wait")
        self.assertEqual(updates["memories"], ["I remember this room."])

    def test_belief_key_value_list_is_accepted(self):
        def model(messages):
            return '{"kind":"wait","args":{"duration_seconds":60},"updates":{"beliefs":[{"key":"door","value":"closed"}]}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        _, updates = session.decide("The room is quiet.", 0)
        self.assertEqual(updates["beliefs"], [{"key": "door", "value": "closed"}])

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

    def test_valid_json_null_is_handled_as_no_action(self):
        calls = []
        def model(messages):
            calls.append(messages)
            return "null"
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, updates = session.decide("The room is quiet.", 0)
        self.assertIsNone(decision)
        self.assertEqual(updates, {})
        self.assertEqual(len(calls), 1)

    def test_valid_non_object_json_is_retried_as_protocol_error(self):
        outputs = ["[]", '{"kind":"wait","args":{"duration_seconds":60}}']
        def model(messages):
            return outputs.pop(0)
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, _ = session.decide("The room is quiet.", 0)
        self.assertEqual(decision.kind, "wait")

    def test_json_object_with_empty_message_is_left_for_engine_rejection(self):
        def model(messages):
            return '{"kind":"send_message","args":{"target":"b","text":""}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, _ = session.decide("The room is quiet.", 0)
        self.assertEqual(decision.kind, "send_message")

    def test_legacy_action_shape_is_reported_and_retried(self):
        calls = []
        outputs = ['{"action":"wait","duration":60}',
                   '{"kind":"wait","args":{"duration_seconds":60}}']
        def model(messages):
            calls.append(messages)
            return outputs.pop(0)
        session = CharacterSession(self.seed(), PrivateState("a"), model)
        decision, _ = session.decide("The room is quiet.", 0)
        self.assertEqual(decision.kind, "wait")
        self.assertEqual(len(calls), 2)
        self.assertIn("cannot execute", calls[1][-1]["content"])

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

    def test_gm_provider_failure_is_not_silently_converted_to_no_action(self):
        from harness.natural_agent import make_persistent_agent
        def failed_gm(text, perception, affordances):
            error = RuntimeError("upstream unavailable")
            error.retryable = True
            raise error
        agent = make_persistent_agent(self.seed(), lambda messages: "I search the archive.", failed_gm)
        with self.assertRaisesRegex(RuntimeError, "upstream unavailable"):
            agent(PrivateState("a"), {"world_version": 0, "time": "now",
                                      "location": "room", "events": [], "inbox": []},
                 [{"kind": "wait", "duration_seconds": 60}])
        self.assertEqual(len(agent.drain_gm_records()), 1)

    def test_gm_retries_terminal_transient_provider_failure(self):
        from harness.natural_agent import make_persistent_agent, make_provider_gm
        calls = [0]
        def model(messages):
            return "I wait quietly."
        def provider(text_and_prompt):
            calls[0] += 1
            if calls[0] == 1:
                error = RuntimeError("provider HTTP 502 after bounded retries")
                error.retryable = True
                error.retry_exhausted = True
                raise error
            return {"kind": "wait", "args": {"duration_seconds": 60}}
        agent = make_persistent_agent(self.seed(), model, make_provider_gm(provider))
        decision, _ = agent(PrivateState("a"),
                            {"world_version": 0, "time": "now", "location": "room",
                             "events": [], "inbox": []},
                            [{"kind": "wait", "duration_seconds": 60}])
        self.assertEqual(decision.kind, "wait")
        self.assertEqual(calls[0], 2)

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
        # bounded transcript still keeps only the fixed prologue (including the
        # feedback-guidance line), one memory, the feedback block, and the
        # recent window. The bound tracks the prologue size.
        self.assertLess(sum(len(m["content"]) for m in session.messages), 2400)

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

    def test_long_feedback_history_stays_bounded_and_keeps_latest_results(self):
        def model(messages):
            if any("Compress the preceding" in m["content"] for m in messages):
                return "I remember the relevant obligations."
            return '{"kind":"wait","args":{"duration_seconds":60}}'

        session = CharacterSession(self.seed(), PrivateState("a"), model,
                                   compaction_threshold=300, recent_messages=2,
                                   authoritative_feedback_chars=120)
        for index in range(40):
            session.record_world_result("result %02d: " % index + "x" * 30)
        session.decide("A final update arrives.", 40)

        self.assertLessEqual(sum(len(item) for item in session.authoritative_feedback), 120)
        self.assertIn("result 39", "\n".join(session.authoritative_feedback))
        self.assertNotIn("result 00", "\n".join(session.authoritative_feedback))
        self.assertLessEqual(sum(len(m["content"]) for m in session.messages), 2200)

    def test_compaction_retries_a_terminal_upstream_failure(self):
        calls = []
        failed = [False]
        def model(messages):
            calls.append(messages)
            if any("Compress the preceding" in m["content"] for m in messages):
                if not failed[0]:
                    failed[0] = True
                    error = RuntimeError("provider HTTP 502 after bounded retries")
                    error.retryable = True
                    error.retry_exhausted = True
                    raise error
                return "I remember the unresolved promise."
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model,
                                   compaction_threshold=180, recent_messages=4,
                                   compaction_retries=1)
        for i in range(8):
            session.decide("A long world update number " + str(i) + " happened.", i)
            session.record_world_result("The action completed after a long interval.")
        self.assertTrue(failed[0])
        self.assertTrue(session.compacted_memories)

    def test_30k_history_compacts_and_every_provider_request_is_bounded(self):
        calls = []
        def model(messages):
            calls.append([dict(message) for message in messages])
            if any("Compress the preceding" in m["content"] for m in messages):
                return "I retain the unresolved obligation."
            return '{"kind":"wait","args":{"duration_seconds":60}}'

        session = CharacterSession(self.seed(), PrivateState("a"), model,
                                   compaction_threshold=30000, request_chars=2000,
                                   recent_messages=4)
        for index in range(80):
            session.decide("A lived event %d: %s" % (index, "details " * 60), index)
            session.record_world_result("The world completed event %d." % index)
        session.decide("The final observed event arrives.", 80)

        self.assertTrue(session.compacted_memories)
        self.assertGreater(len(calls), 80)
        self.assertTrue(all(sum(len(m["content"]) for m in request) <= 2000
                            for request in calls))

    def test_retry_does_not_duplicate_turn_or_world_message_in_transcript(self):
        calls = []
        failed = [True]
        def model(messages):
            calls.append([dict(message) for message in messages])
            if failed[0]:
                failed[0] = False
                error = RuntimeError("temporary upstream failure")
                error.retryable = True
                raise error
            return '{"kind":"wait","args":{"duration_seconds":60}}'

        session = CharacterSession(self.seed(), PrivateState("a"), model)
        session.decide("The room is quiet.", 0)
        session.record_world_result("The move completed at noon.")
        session.decide("A bird lands nearby.", 1)

        contents = [m["content"] for m in session.messages]
        self.assertEqual(contents.count("A bird lands nearby."), 1)
        self.assertEqual(contents.count("The move completed at noon."), 1)
        self.assertEqual(len(calls), 3)

    def test_same_turn_retry_commits_one_observation_and_one_assistant_response(self):
        calls = []
        attempts = [0]
        def model(messages):
            calls.append([dict(message) for message in messages])
            if attempts[0] == 0:
                attempts[0] += 1
                error = RuntimeError("outer transient failure")
                error.retryable = True
                raise error
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model, max_retries=0)
        with self.assertRaises(RuntimeError):
            session.decide("One observation.", 7, turn_id="turn-7")
        session.decide("One observation.", 7, turn_id="turn-7")
        contents = [message["content"] for message in session.messages]
        self.assertEqual(sum("One observation." in content for content in contents), 1)
        self.assertEqual(contents.count('{"kind":"wait","args":{"duration_seconds":60}}'), 1)
        self.assertEqual([m["content"] for m in calls[0]], [m["content"] for m in calls[1]])

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

    def test_bounding_omits_oversized_records_without_slicing_json_or_feedback(self):
        calls = []
        def model(messages):
            calls.append([dict(m) for m in messages])
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a"), model, request_chars=2000)
        assistant_json = '{"kind":"wait","args":{"duration_seconds":60},"padding":"' + "x" * 2500 + '"}'
        session.messages.append({"role": "assistant", "content": assistant_json})
        feedback = "WORLD FEEDBACK BEGIN {\"event\":\"complete\"} END " + "y" * 3000
        session.record_world_result(feedback)
        session.decide("A short observation.", 0)
        request = calls[-1]
        contents = [m["content"] for m in request]
        self.assertNotIn(assistant_json, contents)
        self.assertNotIn(feedback, contents)
        self.assertTrue(all(content not in assistant_json for content in contents))
        self.assertTrue(all(content not in feedback for content in contents))
        self.assertLessEqual(sum(len(m["content"]) for m in request), 2000)

    def test_too_small_request_limit_fails_before_sending_incomplete_prologue(self):
        calls = []
        session = CharacterSession(self.seed(), PrivateState("a"),
                                   lambda messages: calls.append(messages), request_chars=1)
        with self.assertRaisesRegex(ValueError, "session prologue"):
            session.decide("observation", 0)
        self.assertEqual(calls, [])

    def test_authoritative_contract_is_ordered_private_and_restorable(self):
        def model(messages):
            if any("Compress the preceding" in m["content"] for m in messages):
                return "I remember the obligation."
            return '{"kind":"wait","args":{"duration_seconds":60}}'
        session = CharacterSession(self.seed(), PrivateState("a", private_notes=["secret"]), model,
                                   compaction_threshold=180, recent_messages=2)
        for index in range(5):
            session.record_world_result("RESULT %d" % index)
            session.decide("Observation %d" % index, index)
        snapshot = session.snapshot()
        self.assertEqual([x["order"] for x in snapshot["authoritative_facts"]], list(range(5)))
        self.assertTrue(all(x["actor"] == "a" and x["source"] == "world"
                            for x in snapshot["authoritative_facts"]))
        restored = CharacterSession.from_snapshot(snapshot, self.seed(), model)
        self.assertEqual(restored.snapshot()["authoritative_facts"], snapshot["authoritative_facts"])
        self.assertEqual(restored.state.snapshot(), snapshot["state"])
        self.assertIn("RESULT 4", "\n".join(restored.authoritative_feedback))

    def test_sessions_for_each_actor_do_not_share_authoritative_or_private_facts(self):
        seen = {}
        def model_for(actor):
            def model(messages):
                seen[actor] = "\n".join(m["content"] for m in messages)
                return '{"kind":"wait","args":{"duration_seconds":60}}'
            return model
        sessions = [CharacterSession(CharacterSeed(actor, actor, "private-" + actor),
                                     PrivateState(actor, private_notes=["private-" + actor]),
                                     model_for(actor), request_chars=2000)
                    for actor in ("a", "b", "c")]
        for session in sessions:
            session.record_world_result("FACT-" + session.state.actor_id)
            session.decide("observation", 0)
        for actor in ("a", "b", "c"):
            self.assertIn("FACT-" + actor, seen[actor])
            for other in ("a", "b", "c"):
                if other != actor:
                    self.assertNotIn("FACT-" + other, seen[actor])
                    self.assertNotIn("private-" + other, seen[actor])
