"""V4 protocol plumbing (ticket 12): static TOOLS, native tool-call provider
path, and the v4 session/agent contract (V4-AGENT-INTERFACE §0/§1/§2/§4)."""

from __future__ import annotations

import io
import json
import unittest
from unittest import mock

from harness.action_schema import SCHEMAS, SPEAK_TOOLS, TOOLS, validate_action_args
from harness.agent_state import PrivateState
from harness.character_loader import load_story_characters
from harness.natural_agent import SYSTEM_PROMPT_V4, V4Session, make_persistent_agent_v4
from pathlib import Path


def _chat_response(message: dict) -> bytes:
    return json.dumps({"choices": [{"message": message}]}).encode()


class _FakeResponse(io.BytesIO):
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class ToolsTests(unittest.TestCase):
    def test_tools_cover_the_doc_table_without_sleep(self):
        names = {tool["function"]["name"] for tool in TOOLS}
        expected = {"update_memory", "recall", "flashback", "wait", "speak",
                    "text", "move", "read", "take", "place", "give", "knock",
                    "leave_note", "trash",
                    "continue_action", "abandon_action"}
        self.assertEqual(names, expected)
        self.assertNotIn("sleep", SCHEMAS)  # M1: sleep merged into wait
        # Static full declaration, cache-safe: every tool carries a Chinese
        # description and its schema as parameters.
        for tool in TOOLS:
            self.assertTrue(tool["function"]["description"])
            self.assertIs(tool["function"]["parameters"], SCHEMAS[tool["function"]["name"]])

    def test_memory_tool_arg_validation(self):
        rows_err = validate_action_args("update_memory", {})
        self.assertIsNotNone(rows_err)
        self.assertIn("needs the 'rows' argument", rows_err or "")
        keys_err = validate_action_args("update_memory", {"rows": [{"op": "open"}]})
        self.assertIsNotNone(keys_err)
        self.assertIn("needs the 'keys' argument", keys_err or "")
        self.assertIsNone(validate_action_args(
            "update_memory", {"rows": [{"keys": ["草稿", "!always"], "op": "open",
                                        "desc": "弄清是谁放的"}]}))
        self.assertIsNone(validate_action_args("recall", {"keys": ["草稿"]}))
        self.assertIsNotNone(validate_action_args("recall", {}))
        entity_err = validate_action_args("flashback", {})
        self.assertIsNotNone(entity_err)
        self.assertIn("needs the 'entity' argument", entity_err or "")

    def test_contact_nickname_resolves_to_formal_id(self):
        """T3/T4 end to end: 妈妈 must reach 陈默妈 through the contact row,
        and an uncontactable name must be rejected with the addressable list."""
        from datetime import datetime, timezone
        from harness.kernel import (ActorState, ActionRejected, LocationState,
                                    World, Intention)

        def fresh():
            start = datetime(2026, 3, 16, 7, 0, tzinfo=timezone.utc)
            world = World(start=start,
                          actors=[ActorState("陈默", "男生宿舍"),
                                  ActorState("陈默妈", "陈默家")],
                          locations=[LocationState("男生宿舍"),
                                     LocationState("陈默家")])
            world.actors["陈默"].known_contacts = {"陈默妈"}
            world.actors["陈默"].contact_aliases = {"妈妈": "陈默妈", "我妈": "陈默妈"}
            return world

        # nickname -> formal id, exact name -> itself
        for nickname in ("妈妈", "我妈", "陈默妈"):
            world = fresh()
            world.submit(Intention("陈默", "text",
                                   {"target": nickname, "text": "在吗"},
                                   world.version))
            world.advance()
            sent = [e for e in world.event_log if e.kind == "message_sent"]
            self.assertTrue(sent, f"text({nickname!r}) must send")
            self.assertEqual(sent[0].payload["target"], "陈默妈")
        # uncontactable names are rejected with the addressable list
        for stranger in ("林瑶", "爸"):
            with self.assertRaises(ActionRejected) as ctx:
                fresh().submit(Intention("陈默", "text",
                                         {"target": stranger, "text": "hi"},
                                         None) if False else
                               Intention("陈默", "text",
                                         {"target": stranger, "text": "hi"},
                                         fresh().version))
            self.assertIn("available", str(ctx.exception))

    def test_memory_tool_descriptions_match_the_key_set_schema(self):
        """Guard a real miss: the schemas moved to key sets while the
        descriptions still advertised fields:/item:/kinds, which is what made
        the model write `item:2013年台风台账` as a key in a live run."""
        from harness.action_schema import _TOOL_DESCRIPTIONS
        for name in ("update_memory", "recall"):
            desc = _TOOL_DESCRIPTIONS[name]
            for banned in ("fields", "kinds"):
                self.assertNotIn(banned, desc, f"{name} description still mentions {banned!r}")
        self.assertIn("keys", _TOOL_DESCRIPTIONS["update_memory"])
        self.assertIn("keys", _TOOL_DESCRIPTIONS["recall"])

    def test_trace_records_the_offered_tool_list(self):
        from datetime import datetime
        from harness.kernel import ActorState, LocationState, World
        from harness.trace import Trace
        world = World(start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                      actors=[ActorState("a", "room")], locations=[LocationState("room")])
        trace = Trace("v3", "tool-list")
        trace.record_tools(["wait", "speak"])
        snapshot = trace.snapshot(world)
        self.assertEqual(snapshot["tools"], ["wait", "speak"])
        restored = Trace("v3", "other")
        restored.restore_from_snapshot(snapshot)
        self.assertEqual(restored.tools, ["wait", "speak"])

    def test_speak_only_tools_for_extras(self):
        self.assertEqual([tool["function"]["name"] for tool in SPEAK_TOOLS], ["speak"])


class ChatWithToolsTests(unittest.TestCase):
    def _provider(self, retries=0):
        from harness.provider import OpenAICompatible
        return OpenAICompatible(base_url="http://gw/v1", model="m",
                                timeout=1, retries=retries, max_concurrency=1,
                                retry_backoff=0.0)

    def test_chat_with_tools_parses_tool_calls(self):
        provider = self._provider()
        seen = {}

        def fake_urlopen(request, timeout=None):
            seen["body"] = json.loads(request.data.decode())
            return _FakeResponse(_chat_response({
                "content": "",
                "tool_calls": [
                    {"id": "call-1", "type": "function",
                     "function": {"name": "speak",
                                  "arguments": json.dumps({"text": "早"}, ensure_ascii=False)}},
                ],
            }))

        with mock.patch("harness.provider.urlopen", fake_urlopen):
            message = provider.chat_with_tools(
                [{"role": "user", "content": "hi"}], TOOLS)
        self.assertEqual(seen["body"]["tool_choice"], "auto")
        self.assertEqual(seen["body"]["tools"], TOOLS)
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "speak")

    def test_chat_with_tools_accepts_text_only_reply(self):
        # T1 文本即说话: a text-only reply is a valid decision (words are
        # spoken, the turn idles) — no retry.
        provider = self._provider(retries=1)
        attempts = []

        def fake_urlopen(request, timeout=None):
            attempts.append(1)
            return _FakeResponse(_chat_response({"content": "只是散文"}))

        with mock.patch("harness.provider.urlopen", fake_urlopen):
            message = provider.chat_with_tools([{"role": "user", "content": "hi"}], TOOLS)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(message["content"], "只是散文")
        self.assertEqual(message.get("tool_calls"), [])

    def test_chat_with_tools_retries_when_neither_text_nor_calls(self):
        # A truly unusable shape (no content AND no calls) still retries.
        provider = self._provider(retries=1)
        attempts = []

        def fake_urlopen(request, timeout=None):
            attempts.append(1)
            if len(attempts) == 1:
                return _FakeResponse(_chat_response({"content": ""}))
            return _FakeResponse(_chat_response({
                "content": "", "tool_calls": [
                    {"id": "c", "type": "function",
                     "function": {"name": "wait", "arguments": "{}"}}]}))

        with mock.patch("harness.provider.urlopen", fake_urlopen):
            message = provider.chat_with_tools([{"role": "user", "content": "hi"}], TOOLS)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "wait")


class _FakeProvider:
    """Records chat_with_tools calls; returns a canned assistant message."""

    def __init__(self, message):
        self.message = message
        self.calls = []

    def chat_with_tools(self, messages, tools):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        return dict(self.message)

    def __call__(self, messages):
        return "第一人称记忆摘要。"


def session_messages(agent):
    return agent.session_obj.messages


class V4SessionTests(unittest.TestCase):
    def _seed(self):
        seeds = load_story_characters(Path("world"))
        return seeds["陈默"]

    def test_agent_contract_system_verbatim_and_tool_acks(self):
        seed = self._seed()
        provider = _FakeProvider({
            "content": "",
            "tool_calls": [{"id": "t1", "type": "function",
                            "function": {"name": "think",
                                         "arguments": json.dumps({})}},
                           {"id": "t2", "type": "function",
                            "function": {"name": "speak",
                                         "arguments": "not json"}}]})
        agent = make_persistent_agent_v4(seed, provider)
        decision = agent("9/16(周三) 7:00 @半坡咖啡馆\n...", PrivateState("陈默"))
        assert isinstance(decision, dict)
        calls = decision["calls"]
        request_messages = provider.calls[0]["messages"]
        # System prompt is the session's verbatim first message (doc §1).
        self.assertEqual(request_messages[0]["role"], "system")
        self.assertEqual(request_messages[0]["content"], SYSTEM_PROMPT_V4)
        # World message appended as user.
        self.assertEqual(request_messages[1]["role"], "user")
        self.assertIn("@半坡咖啡馆", request_messages[1]["content"])
        # After the reply: assistant message only — the engine reports each
        # call's result via deliver_tool_results (docs §3 tool-result rule).
        self.assertEqual([m["role"] for m in session_messages(agent)][2:],
                         ["assistant"])
        getattr(agent, "deliver_tool_results")([
            {"tool_call_id": "t1", "ok": True, "text": "ok"},
            {"tool_call_id": "t2", "ok": False, "text": "speak: unparseable arguments"},
        ])
        # Ticket 23: a chain's n results COALESCE into one tool message —
        # strict gateways reject tool-follows-tool, and the history is
        # re-sent forever. The assistant message keeps only the first call
        # so call/result counts match; every result text survives, keyed by
        # call name.
        self.assertEqual([m["role"] for m in session_messages(agent)][2:],
                         ["assistant", "tool"])
        assistant_msg = session_messages(agent)[2]
        self.assertEqual([c["id"] for c in assistant_msg["tool_calls"]], ["t1"])
        merged = session_messages(agent)[3]
        self.assertEqual(merged["tool_call_id"], "t1")
        self.assertIn("[think] ok", merged["content"])
        self.assertIn("[speak] speak: unparseable", merged["content"])
        # Structurally parsed calls; malformed arguments carry parse_error.
        self.assertEqual(calls[0], {"name": "think", "arguments": {},
                                    "tool_call_id": "t1"})
        self.assertEqual(calls[1]["name"], "speak")
        self.assertEqual(calls[1]["arguments"], {})
        self.assertIn("parse_error", calls[1])

    def test_compaction_fires_at_threshold_and_flags_once(self):
        seed = self._seed()
        provider = _FakeProvider({"content": "", "tool_calls": [
            {"id": "c", "type": "function",
             "function": {"name": "wait", "arguments": "{}"}}]})
        session = V4Session("陈默", provider, compaction_threshold=100, recent_messages=1)
        filler = "x" * 60
        session.decide(filler)
        self.assertFalse(session.consume_compaction())
        session.decide(filler)  # crosses the threshold on append
        self.assertTrue(session.consume_compaction())
        self.assertFalse(session.consume_compaction())
        # The system prompt survives compaction; the memory-fold line is in.
        self.assertEqual(session.messages[0]["role"], "system")
        self.assertTrue(any("压缩而来" in str(m.get("content")) for m in session.messages))

    def test_snapshot_roundtrip(self):
        seed = self._seed()
        provider = _FakeProvider({"content": "", "tool_calls": []})
        session = V4Session("陈默", provider)
        session.decide("9/16(周三) 7:00")
        restored = V4Session.from_snapshot(session.snapshot(), provider)
        self.assertEqual(restored.messages, session.messages)


if __name__ == "__main__":
    unittest.main()
