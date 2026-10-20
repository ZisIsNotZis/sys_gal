"""M3：模型接入、工具表、反作弊检查。

这一层不花钱也能测：MockProvider 走同一条回路，证明"模型决定 → 世界裁 → 拒绝回灌"是通的。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import library  # noqa: F401
import anti_cheat
from engine.agent import Decision, MockProvider, agent_turn, ChatProvider
from engine.events import EventLog
from engine.prompt import system_prompt, tool_specs, turn_message
from engine.rules import REGISTRY
from engine.seed import build, load
from stories.s2_borrow_note.agent_run import play_agents
from stories.s2_borrow_note.scenario import DEFAULT_SEED


class ToolTableTests(unittest.TestCase):
    def test_every_library_verb_is_offered_and_nothing_else(self):
        names = {t["function"]["name"] for t in tool_specs()}
        self.assertEqual(names, set(REGISTRY))

    def test_every_tool_says_what_it_does(self):
        for tool in tool_specs():
            self.assertTrue(tool["function"]["description"].strip(), tool)

    def test_required_arguments_come_from_the_library(self):
        by_name = {t["function"]["name"]: t for t in tool_specs()}
        self.assertEqual(by_name["write"]["function"]["parameters"]["required"],
                         ["target", "text"])
        self.assertIn("with", by_name["write"]["function"]["parameters"]["properties"])
        self.assertEqual(by_name["place"]["function"]["parameters"]["required"],
                         ["target", "to"])
        self.assertEqual(by_name["wait"]["function"]["parameters"]["required"], [])


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.world = load(DEFAULT_SEED)

    def test_prompt_carries_the_characters_own_identity(self):
        text = system_prompt(self.world, "yi")
        self.assertIn("手头紧", text)
        self.assertIn("你能做的事只有这些", text)

    def test_prompt_never_carries_another_persons_private_state(self):
        text = system_prompt(self.world, "jia")
        self.assertNotIn("药是按点吃的", text)
        self.assertNotIn("谁都认得", text)

    def test_turn_message_is_the_rendered_block_only(self):
        text = turn_message(self.world, "jia")
        self.assertIn("【此刻】", text)
        self.assertNotIn("marks", text)
        self.assertNotIn("state", text)


class AgentLoopTests(unittest.TestCase):
    def test_a_refusal_is_fed_back_so_the_agent_can_correct_itself(self):
        world = load(DEFAULT_SEED)
        log = EventLog()
        history: dict[str, list[dict]] = {}
        provider = MockProvider([Decision("read", {"target": "借条"})])
        turn = agent_turn(world, log, "jia", provider, history)
        self.assertFalse(turn.receipt.ok)          # 抽屉锁着，借条看不见
        self.assertTrue(any(m["role"] == "tool" and "没成" in m["content"]
                            for m in history["jia"]))

    def test_an_agent_run_marks_every_action_as_the_agents_own(self):
        provider = MockProvider([
            Decision("unlock", {"target": "抽屉"}),
            Decision("open", {"target": "抽屉"}),
            Decision("take", {"target": "借条"}),
            Decision("place", {"target": "借条", "to": "出租屋"}),
        ])
        run = play_agents("mock", turns_each=1, provider=provider,
                          order=("jia",))
        turns = [i for i in run.items if i["kind"] == "turn"]
        self.assertEqual(len(turns), 1)            # turns_each=1 × 一个角色
        self.assertTrue(all(i["decided_by"] == "agent" and i["context_used"]
                            for i in turns))
        self.assertTrue(all(i["raw"] for i in turns))

    def test_the_agent_sees_only_its_own_context(self):
        provider = MockProvider([Decision("examine", {"target": "借条"})])
        run = play_agents("mock", turns_each=1, provider=provider, order=("jia",))
        turn = [i for i in run.items if i["kind"] == "turn"][0]
        self.assertIn("【眼前】", turn["prompt"]["turn"])
        self.assertNotIn("药是按点吃的", turn["prompt"]["system"])

    def test_provider_without_key_fails_loudly(self):
        provider = ChatProvider(model="x", base_url="http://127.0.0.1:9/v1", api_key="",
                                timeout=1, retries=1)
        with self.assertRaises(Exception):
            provider.decide([{"role": "user", "content": "hi"}], [])


class AntiCheatTests(unittest.TestCase):
    def test_imperative_addressed_to_a_named_character_is_caught(self):
        seed = {"start_clock": 0,
                "people": [{"id": "a", "name": "甲", "identity": "让乙把借条交出来。"},
                           {"id": "b", "name": "乙"}]}
        problems = anti_cheat.check_imperatives(seed, "probe")
        self.assertTrue(problems)

    def test_a_destiny_event_is_caught(self):
        seed = {"start_clock": 0,
                "places": [{"id": "p", "name": "屋"}],
                "schedule": [{"at": 10, "effect": {"kind": "fate", "place": "p"}}]}
        problems = anti_cheat.check_destiny(seed, "probe")
        self.assertTrue(any("没有对应的制度或物理" in p for p in problems))

    def test_scheduling_a_character_action_is_caught(self):
        seed = {"start_clock": 0,
                "places": [{"id": "p", "name": "屋"}],
                "schedule": [{"at": 10, "effect": {"kind": "arrive", "place": "p",
                                                   "actor": "甲"}}]}
        problems = anti_cheat.check_destiny(seed, "probe")
        self.assertTrue(any("替角色做决定" in p for p in problems))

    def test_unknown_field_in_a_seed_is_a_hard_error(self):
        with self.assertRaises(ValueError):
            build({"start_clock": 0, "people": [{"id": "a", "name": "甲", "mood": "紧张"}]})


if __name__ == "__main__":
    unittest.main()
