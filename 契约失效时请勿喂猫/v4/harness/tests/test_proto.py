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
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ToolsTests(unittest.TestCase):
    def test_tools_cover_the_doc_table_without_sleep(self):
        names = {tool["function"]["name"] for tool in TOOLS}
        expected = {"think", "update_memory", "recall", "flashback", "wait", "speak",
                    "send_message", "move", "read", "copy", "label", "annotate",
                    "compare", "take", "drop", "give", "inspect", "search", "knock",
                    "interact", "open", "close", "observe", "ask_stranger",
                    "continue_action", "abandon_action"}
        self.assertEqual(names, expected)
        self.assertNotIn("sleep", SCHEMAS)  # M1: sleep merged into wait
        # Static full declaration, cache-safe: every tool carries a Chinese
        # description and its schema as parameters.
        for tool in TOOLS:
            self.assertTrue(tool["function"]["description"])
            self.assertIs(tool["function"]["parameters"], SCHEMAS[tool["function"]["name"]])

    def test_memory_tool_arg_validation(self):
        self.assertIsNone(validate_action_args("think", {"inner": "心里的话"}))
        self.assertIn("non-empty", validate_action_args("think", {"inner": ""}))
        self.assertIn("needs the 'rows' argument", validate_action_args("update_memory", {}))
        self.assertIn("needs the 'fields' argument",
                      validate_action_args("update_memory", {"rows": [{"id": "x"}]}))
        self.assertIsNone(validate_action_args(
            "update_memory", {"rows": [{"fields": {"todo": True}, "id": "x", "op": "open"}]}))
        self.assertIsNone(validate_action_args("recall", {"closed": True, "limit": 5}))
        self.assertIn("needs the 'entity' argument", validate_action_args("flashback", {}))

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

    def test_chat_with_tools_retries_when_no_tool_calls(self):
        provider = self._provider(retries=1)
        attempts = []

        def fake_urlopen(request, timeout=None):
            attempts.append(1)
            if len(attempts) == 1:
                return _FakeResponse(_chat_response({"content": "只是散文"}))
            return _FakeResponse(_chat_response({
                "content": "", "tool_calls": [
                    {"id": "c", "type": "function",
                     "function": {"name": "observe", "arguments": "{}"}}]}))

        with mock.patch("harness.provider.urlopen", fake_urlopen):
            message = provider.chat_with_tools([{"role": "user", "content": "hi"}], TOOLS)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "observe")


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
                                         "arguments": json.dumps({"inner": "先想想"})}},
                           {"id": "t2", "type": "function",
                            "function": {"name": "speak",
                                         "arguments": "not json"}}]})
        agent = make_persistent_agent_v4(seed, provider)
        calls = agent("9/16(周三) 7:00 @半坡咖啡馆\n...", PrivateState("陈默"))
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
        agent.deliver_tool_results([
            {"tool_call_id": "t1", "ok": True, "text": "ok"},
            {"tool_call_id": "t2", "ok": False, "text": "speak: unparseable arguments"},
        ])
        self.assertEqual([m["role"] for m in session_messages(agent)][2:],
                         ["assistant", "tool", "tool"])
        self.assertEqual(session_messages(agent)[3]["tool_call_id"], "t1")
        self.assertEqual(session_messages(agent)[3]["content"], "ok")
        self.assertEqual(session_messages(agent)[4]["tool_call_id"], "t2")
        self.assertIn("unparseable", session_messages(agent)[4]["content"])
        # Structurally parsed calls; malformed arguments carry parse_error.
        self.assertEqual(calls[0], {"name": "think", "arguments": {"inner": "先想想"},
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
