"""Guard the JSON-Schema action-protocol validator."""

import json
import unittest
from datetime import datetime

from harness.action_schema import SCHEMAS, validate_action_args
from harness.kernel import ActionRejected, ActorState, Intention, LocationState, World


class ActionSchemaTests(unittest.TestCase):
    def test_every_kernel_action_has_a_schema(self):
        world = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                      actors=[ActorState("a", "room")], locations=[LocationState("room")])
        # V4-AGENT-INTERFACE M1: sleep is merged into wait — the schema must
        # not declare it, and the memory tools must be declared even though
        # they never reach the world kernel (the engine consumes them).
        self.assertNotIn("sleep", SCHEMAS)
        for kind in world.ACTIONS - {"sleep"}:
            self.assertIn(kind, SCHEMAS, f"missing schema for {kind}")

    def test_valid_args_pass(self):
        cases = [
            ("wait", {"duration_seconds": 60, "inner": "等"}),
            ("speak", {"text": "hi", "volume": "normal", "inner": "打招呼"}),
            ("send_message", {"target": "b", "text": "hi", "inner": "通知"}),
            ("move", {"target": "room", "inner": "过去"}),
            ("continue_action", {"inner": "继续"}),
            ("read", {"item": "ledger", "inner": "读"}),
            ("compare", {"first": "a", "second": "b", "inner": "比对"}),
            ("system_query", {"question": "哨子在哪里？", "inner": "问"}),
        ]
        for kind, args in cases:
            self.assertIsNone(validate_action_args(kind, args), (kind, args))

    def test_wrong_key_is_described(self):
        reason = validate_action_args("read", {"document": "ledger"}) or ""
        self.assertIn("unexpected argument 'document'", reason)
        self.assertIn("inner", reason)
        self.assertIn("item", reason)

    def test_missing_required_is_described(self):
        self.assertIn("'inner'", validate_action_args("annotate", {"item": "ledger"}) or "")
        self.assertIn("'text'", validate_action_args("annotate", {"item": "ledger", "inner": "写"}) or "")
        self.assertIn("'second'", validate_action_args("compare", {"first": "a", "inner": "比"}) or "")

    def test_wrong_type_is_described(self):
        reason = validate_action_args("wait", {"duration_seconds": "60"}) or ""
        self.assertIn("'duration_seconds'", reason)
        self.assertIn("integer", reason)

    def test_no_args_action_rejects_extras(self):
        reason = validate_action_args("wait", {"place": "archive", "inner": "等", "duration_seconds": 60}) or ""
        self.assertIn("unexpected argument 'place'", reason)

    def test_runner_rejects_wrong_signature_with_schema_message(self):
        from harness.agent_state import PrivateState
        from harness.runner import Runner
        from harness.trace import Trace
        world = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                      actors=[ActorState("a", "room")], locations=[LocationState("room")],
                      document_defs={"ledger": {"title": "L", "content": "x", "reading_seconds": 2}},
                      item_locations={"ledger": "room"})

        def agent(state, perception, affordances):
            return Intention("a", "read", {"doc": "ledger"}, perception["world_version"])

        trace = Trace("v3-test", "schema-rejection")
        Runner(world, {"a": agent}, {actor: PrivateState(actor) for actor in world.actors},
               trace).run(stop_at=world.now + __import__("datetime").timedelta(seconds=60),
                          max_turns=5)
        rejected = next(turn for turn in trace.agent_turns if turn["result"] == "rejected")
        self.assertIn("unexpected argument 'doc'", rejected["error"])
        self.assertIn("'item'", rejected["error"])

    def test_provider_retries_transient_failures_beyond_old_budget(self):
        """Provider blips are common; the resilient default rides through six
        consecutive 502s instead of dying after the old five-attempt budget."""
        import os
        from unittest.mock import patch
        from urllib.error import HTTPError
        from io import BytesIO
        from harness.provider import provider_from_env
        saved = {k: os.environ.get(k) for k in
                 ("V3_PROVIDER_RETRIES", "V3_PROVIDER_MAX_BACKOFF", "V3_PROVIDER_MAX_DURATION")}
        try:
            os.environ.update({"V3_PROVIDER_RETRIES": "8",
                               "V3_PROVIDER_MAX_BACKOFF": "120",
                               "V3_PROVIDER_MAX_DURATION": "600"})
            provider = provider_from_env()
            provider.sleep = lambda _: None  # no real backoff sleeps in tests
            self.assertGreater(provider.retries, 5)
            calls = {"n": 0}

            def fake(request, timeout=0):
                calls["n"] += 1
                if calls["n"] <= 6:
                    raise HTTPError("http://test", 502, "bad", {}, BytesIO(b"upstream"))
                payload = json.dumps({"output_text": json.dumps(
                    {"kind": "wait", "args": {"duration_seconds": 60}})})
                return BytesIO(payload.encode())

            with patch("harness.provider.urlopen", side_effect=fake), \
                 patch("harness.provider.time.monotonic",
                       side_effect=[float(i) for i in range(20)]):
                out = provider([{"role": "user", "content": "x"}])
            self.assertIn("wait", out)
            self.assertEqual(calls["n"], 7)  # six blips then success
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
