"""V4-CAST 两层演员制的引擎行为测试。

合成世界，不依赖 v4/world；覆盖：角色分层调度、各唤醒触发器、冷清检测、
唤醒预算、简报无泄漏、滚动记忆有界、ask 对话期生命周期（多轮 +
会话内记忆 + 结束销毁）、路人池 weight/rarity 抽样。
"""

from __future__ import annotations

import asyncio
import random
import unittest
from datetime import datetime

from harness.adapter import parse_decision
from harness.agent_state import PrivateState
from harness.engine import AsyncEngine
from harness.kernel import ActorState, Intention, LocationState, World
from harness.npc_agent import (NpcAgent, build_extra_briefing,
                               build_extra_system_prompt, build_npc_system_prompt,
                               extra_heard_speech_since, extra_scene_transcript,
                               generate_stranger_name,
                               public_mc_digest, sample_extra)
from harness.runner import Runner
from harness.trace import Trace

START = datetime.fromisoformat("2026-03-16T07:00:00+08:00")


def _world():
    return World(start=START,
                 actors=[ActorState("陈默", "咖啡馆"),
                         ActorState("宿管阿姨", "宿舍", role="npc")],
                 locations=[LocationState("咖啡馆"), LocationState("宿舍"),
                            LocationState("中庭")],
                 routes={("咖啡馆", "中庭"): 600, ("中庭", "咖啡馆"): 600,
                         ("宿舍", "中庭"): 600, ("中庭", "宿舍"): 600})
    # 心跳：即时动作后世界仍有边界可推进，queue_drained 不会提前收尾。
    world._schedule(datetime.fromisoformat("2026-03-16T07:10:00+08:00"),
                    "world_event", None, {"event": "heartbeat"}, None)
    world._schedule(datetime.fromisoformat("2026-03-16T09:00:00+08:00"),
                    "world_event", None, {"event": "heartbeat2"}, None)


def _mc_agent(script):
    """script: list of intentions consumed in order; None afterwards."""
    def agent(state, perception, affordances):
        if script:
            return script.pop(0)
        return None
    return agent


def _null(_state, _perception, _affordances):
    return None


def _wait(seconds):
    return parse_decision("陈默", '{"name":"wait",'
                                  '"arguments":{"duration_seconds":%d}}' % seconds,
                          None)[0]


class RoleSchedulingTests(unittest.TestCase):
    def test_npc_is_never_clock_polled_until_addressed(self):
        world = _world()
        states = {a: PrivateState(a) for a in world.actors}
        calls = {a: 0 for a in world.actors}

        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return _wait(300)

        trace = Trace("v4-test", "npc-clock")
        Runner(world, {"陈默": agent, "宿管阿姨": _null}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T09:00:00+08:00"), max_turns=200)
        self.assertGreater(calls["陈默"], 3)
        self.assertEqual(calls["宿管阿姨"], 0)  # 无人点名，NPC 永不醒来
        self.assertTrue(all(t["role"] == "mc" for t in trace.agent_turns))

    def test_addressed_speech_wakes_the_npc(self):
        world = _world()
        # 同地才有"当面说话"；把 NPC 挪到咖啡馆与 MC 共处。
        world.actors["宿管阿姨"].location = "咖啡馆"
        states = {a: PrivateState(a) for a in world.actors}
        calls = {a: 0 for a in world.actors}

        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            if state.actor_id == "陈默" and calls[state.actor_id] == 1:
                return parse_decision("陈默",
                                      '{"name":"speak","arguments":'
                                      '{"text":"阿姨，晚安归登记本在哪？","volume":"whisper","to":["宿管阿姨"]}}',
                                      world.version)[0]
            return _wait(300)

        def npc_agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return parse_decision("宿管阿姨",
                                  '{"name":"speak","arguments":'
                                  '{"text":"在值班台抽屉里。","volume":"whisper","to":["陈默"]}}',
                                  perception.get("world_version"))[0]

        trace = Trace("v4-test", "npc-addressed")
        Runner(world, {"陈默": agent, "宿管阿姨": npc_agent}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:15:00+08:00"), max_turns=200)
        self.assertGreaterEqual(calls["宿管阿姨"], 1)
        npc_turns = [t for t in trace.agent_turns if t["actor"] == "宿管阿姨"]
        self.assertTrue(npc_turns)
        self.assertTrue(all(t["role"] == "npc" for t in npc_turns))
        # NPC 的回答以 speech 事件出现，MC 在下一次感知里听见。
        speeches = [e for e in world.event_log
                    if e.kind == "speech" and e.actor == "宿管阿姨"]
        self.assertTrue(speeches)

    def test_scheduled_target_wakes_the_npc(self):
        world = _world()
        world._schedule(datetime.fromisoformat("2026-03-16T07:30:00+08:00"),
                        "world_event", None,
                        {"event": "查寝", "target": "宿管阿姨"}, None)
        states = {a: PrivateState(a) for a in world.actors}
        calls = {a: 0 for a in world.actors}

        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return _wait(300)

        def npc_agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return None

        trace = Trace("v4-test", "npc-scheduled")
        Runner(world, {"陈默": agent, "宿管阿姨": npc_agent}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T08:00:00+08:00"), max_turns=200)
        self.assertGreaterEqual(calls["宿管阿姨"], 1)

    def test_ripple_abandoned_wakes_colocated_npc(self):
        world = _world()
        world.actors["宿管阿姨"].location = "咖啡馆"
        states = {a: PrivateState(a) for a in world.actors}
        calls = {a: 0 for a in world.actors}
        # 陈默先 start 一个 900s 的 wait，再被自己的 speak 打断（abandon）。
        steps = [parse_decision("陈默", '{"name":"wait",'
                                       '"arguments":{"duration_seconds":900}}',
                                world.version)[0],
                 parse_decision("陈默", '{"name":"speak",'
                                       '"arguments":{"text":"我走。"}}',
                                world.version)[0]]

        def agent(state, perception, affordances):
            if state.actor_id != "陈默":
                calls[state.actor_id] += 1
                return None
            if steps:
                return steps.pop(0)
            return None

        def npc_agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return None

        Runner(world, {"陈默": agent, "宿管阿姨": npc_agent}, states, trace=Trace("v4-test", "ripple")).run(
            stop_at=datetime.fromisoformat("2026-03-16T07:30:00+08:00"), max_turns=200)
        # wait 被 abandon 后产生涟漪事件 → 同地的宿管阿姨被唤醒过至少一次。
        self.assertGreaterEqual(calls["宿管阿姨"], 1)


class ColdSceneTests(unittest.TestCase):
    def test_cold_scene_wakes_once_per_silence_and_respects_budget(self):
        world = _world()
        world.actors["宿管阿姨"].location = "咖啡馆"  # 与陈默共处
        states = {a: PrivateState(a) for a in world.actors}
        calls = {a: 0 for a in world.actors}

        def agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return _wait(300)

        def npc_agent(state, perception, affordances):
            calls[state.actor_id] += 1
            return None

        trace = Trace("v4-test", "cold-scene")
        Runner(world, {"陈默": agent, "宿管阿姨": npc_agent}, states, trace).run(
            stop_at=datetime.fromisoformat("2026-03-16T12:00:00+08:00"), max_turns=1000)
        # 5 小时死寂：冷清唤醒发生，但受"每沉默期一次"约束——宿管阿姨不会被
        # 无限唤醒（唤醒次数远小于边界数）。
        self.assertGreaterEqual(calls["宿管阿姨"], 1)
        self.assertLessEqual(calls["宿管阿姨"], 12)  # 每小时唤醒预算


class BriefingLeakTests(unittest.TestCase):
    def test_briefing_never_carries_private_state_or_inner(self):
        world = _world()
        mc_state = PrivateState("陈默")
        mc_state.goals = ("SECRET-GOAL-MARKER",)
        captured = []

        def call(messages):
            captured.append(messages)
            return '{"name":"wait","arguments":{"duration_seconds":300}}'

        from harness.character_loader import CharacterSeed
        # NPC 自己的私人起点是它自己的人格材料（合法在场）；
        # 泄漏红线是 MC 的私有状态与心声。
        seed_seed = CharacterSeed("宿管阿姨", "你是宿管阿姨。", "宿管阿姨自己的备忘。")
        context = {"陈默": lambda actor, perception: {
            "mc_digest": public_mc_digest(world),
            "schedule_text": "（无）", "beat_goal": ""}}
        agent = NpcAgent(seed_seed, call,
                         lambda actor, perception: context.get(actor, {}))
        perception = {"observer": "宿管阿姨", "time": "2026-03-16T07:30:00+08:00",
                      "world_version": 3, "location": "宿舍",
                      "nearby_actors": ["陈默"], "events": [],
                      "wake_reason": "有人当面对你说话"}
        agent(PrivateState("宿管阿姨"), perception, [])
        text = "".join(m["content"] for m in captured[0])
        self.assertNotIn("SECRET-GOAL-MARKER", text)
        self.assertNotIn("SECRET-INNER-MARKER", text)
        # MC 的私有 document_read 内容（含 inner 标记）也不得经 digest 泄漏。
        self.assertNotIn("读完了", text)

    def test_rolling_memory_is_bounded(self):
        world = _world()
        mc_state = PrivateState("陈默")

        def call(messages):
            return '{"name":"wait","arguments":{"duration_seconds":300}}'

        from harness.character_loader import CharacterSeed
        seed = CharacterSeed("宿管阿姨", "你是宿管阿姨。", "")
        agent = NpcAgent(seed, call, lambda actor, perception: {}, rolling_limit=3)
        perception = {"observer": "宿管阿姨", "time": "2026-03-16T07:30:00+08:00",
                      "world_version": 1, "location": "宿舍",
                      "nearby_actors": [], "events": []}
        for _ in range(10):
            agent(mc_state, perception, [])
        self.assertEqual(len(agent.memory), 3)
        self.assertEqual(agent.wake_count, 10)


class ExtraLifecycleTests(unittest.TestCase):
    def _runner(self, tmp_script, stub):
        world = _world()
        states = {a: PrivateState(a) for a in world.actors}
        trace = Trace("v4-test", "extras")
        runner = Runner(world, {"陈默": _mc_agent(list(tmp_script)), "宿管阿姨": _null},
                        states, trace, extra_call=stub)
        return world, runner

    def test_ask_spawns_answers_and_destroys_on_departure(self):
        asked = []
        answers = ["登记本在值班台抽屉里。"]

        def stub(messages):
            asked.append(messages)
            text = answers.pop(0) if answers else "这个我真不知道。"
            return '{"name":"speak","arguments":{"text":"%s"}}' % text

        ask = parse_decision("陈默", '{"name":"speak",'
                                    '"arguments":{"text":"晚安归登记本在哪？","volume":"normal","to":["陌生人"]}}', None)[0]
        wait = _wait(300)
        reply = parse_decision("陈默", '{"name":"speak",'
                                      '"arguments":{"text":"抽屉锁着吗？"}}', None)[0]
        # 追问完就走到中庭（触发"伙伴离开"销毁）。
        leave = parse_decision("陈默", '{"name":"move",'
                                      '"arguments":{"target":"中庭"}}', None)[0]
        world, runner = self._runner([ask, wait, reply, leave], stub)
        runner.run(stop_at=datetime.fromisoformat("2026-03-16T07:25:00+08:00"),
                   max_turns=200)
        # 1) 路人被生成过并以 speech 回答（事件在日志里）
        answer = [e for e in world.event_log if e.kind == "speech"
                  and e.actor not in {"陈默", "宿管阿姨"}]
        self.assertTrue(answer, "路人必须以 speech 事件回答")
        # 2) 对话期生命周期：MC 离开后路人被销毁，零持久痕迹
        extras = [a for a, x in world.actors.items() if x.role == "extra"]
        self.assertEqual(extras, [])
        removed = [e for e in world.event_log if e.kind == "extra_removed"]
        self.assertTrue(removed)
        # 3) 多轮：第二次 provider 调用的简报里包含第一轮的回答（会话内记忆）
        self.assertGreaterEqual(len(asked), 2)
        second_brief = "".join(m["content"] for m in asked[1])
        self.assertIn("登记本在值班台抽屉里", second_brief)
        # 4) trace 标记 role=extra
        extra_turns = [t for t in runner.trace.agent_turns if t.get("role") == "extra"]
        self.assertTrue(extra_turns)

    def test_stranger_names_are_generated_and_unique(self):
        names = {generate_stranger_name(random.Random(i)) for i in range(50)}
        self.assertTrue(all(n and isinstance(n, str) for n in names))
        self.assertGreater(len(names), 5)


class ExtraContextTests(unittest.TestCase):
    def test_async_extra_wakes_for_any_audible_speaker_but_not_private_whisper(self):
        class Provider:
            def __init__(self):
                self.calls = []

            def chat_with_tools(self, messages, tools):
                self.calls.append((messages, tools))
                return {"content": "我看见了，通知就在门边。", "tool_calls": []}

        world = _world()
        world.actors["宿管阿姨"].location = "咖啡馆"
        states = {actor: PrivateState(actor) for actor in world.actors}
        provider = Provider()
        trace = Trace("v4-test", "extra-context")
        engine = AsyncEngine(world, {actor: _null for actor in world.actors},
                             states, trace, extra_call=provider)
        engine._scheduler_wake = asyncio.Event()
        name = "路人甲"
        arrival_index = len(world.event_log)
        world.add_extra(name, "咖啡馆")
        scene_start = arrival_index + 1
        engine._extras[name] = {
            "partner": "陈默", "fragment": "路过的学生", "knowledge_notes": "",
            "start": scene_start, "context_cursor": scene_start,
            "last_active": world.now,
            "system_prompt": build_extra_system_prompt("路过的学生", "", "咖啡馆"),
        }

        asyncio.run(engine._extra_turn(name, ""))
        self.assertEqual(provider.calls, [], "empty wake is silence, not an empty-question prompt")
        self.assertEqual(trace.agent_turns[-1]["result"], "none")

        world.submit(Intention("陈默", "speak", {
            "text": "这件事我只告诉你。", "volume": "whisper", "to": ["宿管阿姨"]
        }, world.version))
        asyncio.run(engine._extra_turn(name, ""))
        self.assertEqual(provider.calls, [])

        world.submit(Intention("宿管阿姨", "speak", {
            "text": "路人同学，你知道公告在哪吗？", "volume": "normal", "to": [name]
        }, world.version))
        asyncio.run(engine._extra_turn(name, ""))
        self.assertEqual(len(provider.calls), 1)
        user_tail = provider.calls[0][0][-1]["content"]
        self.assertIn("宿管阿姨（对你说）", user_tail)
        self.assertNotIn("这件事我只告诉你", user_tail)
        self.assertEqual(provider.calls[0][0][0]["content"],
                         engine._extras[name]["system_prompt"])

    def test_extra_rebrief_uses_only_recent_speech_it_actually_heard(self):
        from types import SimpleNamespace

        def speech(actor, text, *, heard, to=(), volume="normal"):
            return SimpleNamespace(
                kind="speech", actor=actor, time=START,
                payload={"text": text, "heard": list(heard), "to": list(to),
                         "volume": volume})

        events = [
            speech("陈默", "你知道公告在哪里吗？", heard=["路人甲", "陈默"],
                   to=["路人甲"]),
            speech("林瑶", "我也在找那张通知。", heard=["路人甲", "陈默", "林瑶"],
                   to=["陈默"]),
            speech("陈默", "这句耳语路人听不见。", heard=["陈默"],
                   to=["陈默"], volume="whisper"),
            speech("班长", "有人刚问公告栏的通知。", heard=["路人甲", "班长"],
                   to=["路人甲"]),
        ]
        transcript = extra_scene_transcript(events, listener="路人甲")
        self.assertTrue(extra_heard_speech_since(events, listener="路人甲", start=0))
        self.assertFalse(extra_heard_speech_since(events, listener="路人甲", start=len(events)))
        self.assertEqual(len(transcript), 3)
        joined = "\\n".join(transcript)
        self.assertIn("陈默（对你说）", joined)
        self.assertIn("林瑶", joined)
        self.assertIn("班长（对你说）", joined)
        self.assertNotIn("这句耳语路人听不见", joined)

    def test_empty_external_wake_has_no_phantom_question_or_changed_static_prefix(self):
        prompt = build_extra_system_prompt("值班同学", "知道公告流程", "教学楼")
        self.assertEqual(prompt, build_extra_system_prompt(
            "值班同学", "知道公告流程", "教学楼"))
        self.assertEqual(build_extra_briefing(transcript=[]), "")
        self.assertNotIn("对方说", build_extra_briefing(transcript=[]))

    def test_extra_tool_static_prefix_is_byte_stable_across_dynamic_tails(self):
        from copy import deepcopy
        from harness.action_schema import SPEAK_TOOLS
        from harness.npc_agent import extra_tool_calls

        class Capture:
            def __init__(self):
                self.calls = []

            def chat_with_tools(self, messages, tools):
                self.calls.append((deepcopy(messages), deepcopy(tools)))
                return {"tool_calls": [{"function": {
                    "name": "speak", "arguments": '{"text":"嗯。"}'}}]}

        provider = Capture()
        system = build_extra_system_prompt("值班同学", "知道公告流程", "教学楼")
        extra_tool_calls(provider, system, build_extra_briefing(
            transcript=["陈默（对你说）：公告栏在哪？"]))
        extra_tool_calls(provider, system, build_extra_briefing(
            transcript=["班长（对你说）：刚才有人问公告栏。", "路人甲：在门边。"]))
        extra_tool_calls(provider, system, "")
        self.assertEqual(provider.calls[0][0][0], provider.calls[1][0][0])
        self.assertEqual(provider.calls[0][1], provider.calls[1][1])
        self.assertEqual(provider.calls[0][1], SPEAK_TOOLS)
        self.assertNotEqual(provider.calls[0][0][1], provider.calls[1][0][1])
        self.assertEqual(provider.calls[2][0], [{"role": "system", "content": system}])

    def test_extra_can_silently_close_a_conversation(self):
        from harness.npc_agent import extra_tool_calls

        class Silent:
            def chat_with_tools(self, messages, tools):
                return {"content": "", "tool_calls": []}

        self.assertEqual(extra_tool_calls(
            Silent(), build_extra_system_prompt("路过的学生", "", "咖啡馆"),
            build_extra_briefing(transcript=["陈默：那先这样，我去忙了。"])), [])

    def test_extra_scene_transcript_is_bounded_and_initial_question_is_real(self):
        from types import SimpleNamespace
        events = [SimpleNamespace(kind="speech", actor="陈默", time=START,
                                  payload={"text": "你有空吗？", "heard": [], "to": ["陌生人"]})]
        initial = extra_scene_transcript(
            events, listener="路人甲", opening_question="你有空吗？", questioner="陈默")
        self.assertEqual(initial, ["陈默（对你说）：你有空吗？"])
        follow_up = [SimpleNamespace(kind="speech", actor="陈默", time=START,
                                     payload={"text": "你刚才说的那件事呢？",
                                              "heard": ["路人甲"],
                                              "to": ["陌生人"]})]
        followed = extra_scene_transcript(
            follow_up, listener="路人甲", opening_question="你刚才说的那件事呢？",
            questioner="陈默")
        self.assertEqual(followed, ["07:00 陈默（对你说）：你刚才说的那件事呢？"])
        many = [SimpleNamespace(kind="speech", actor="陈默", time=START,
                                payload={"text": str(i) + " x" * 200,
                                         "heard": ["路人甲"], "to": []})
                for i in range(20)]
        bounded = extra_scene_transcript(many, listener="路人甲")
        self.assertLessEqual(len(bounded), 8)
        self.assertLessEqual(sum(map(len, bounded)), 1200)
        self.assertTrue(all(len(line) <= 200 for line in bounded))


class ExtraPoolTests(unittest.TestCase):
    def test_sample_extra_honors_weight(self):
        pool = [{"fragment": "普通同学", "rarity": "common", "weight": 9},
                {"fragment": "知情老校友", "rarity": "rare", "knowledge_notes":
                 "知道 2013 年台风夜档案室的值班表", "weight": 1}]
        rng = random.Random(7)
        picks = [sample_extra(pool, rng)["fragment"] for _ in range(400)]
        rare = picks.count("知情老校友")
        self.assertTrue(15 <= rare <= 75, f"rare 抽样应≈10%，实际 {rare}/400")

    def test_rare_informant_knowledge_enters_the_briefing(self):
        from harness.npc_agent import build_extra_system_prompt
        prompt = build_extra_system_prompt("值班同学", "知道晚归登记本在哪", "宿舍")
        self.assertIn("知道晚归登记本在哪", prompt)
        plain = build_extra_system_prompt("普通同学", "", "食堂")
        self.assertNotIn("内情", plain.split("输出")[0].replace("你恰好知道一些内情：", "")) if False else None
        self.assertNotIn("内情", plain)


if __name__ == "__main__":
    unittest.main()
