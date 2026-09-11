"""V4-CAST 两层演员制的引擎行为测试。

合成世界，不依赖 v4/world；覆盖：角色分层调度、各唤醒触发器、冷清检测、
唤醒预算、简报无泄漏、滚动记忆有界、ask_stranger 对话期生命周期（多轮 +
会话内记忆 + 结束销毁）、路人池 weight/rarity 抽样。
"""

from __future__ import annotations

import random
import unittest
from datetime import datetime

from harness.adapter import parse_decision
from harness.agent_state import PrivateState
from harness.kernel import ActorState, LocationState, World
from harness.npc_agent import (NpcAgent, build_npc_system_prompt,
                               generate_stranger_name, public_mc_digest,
                               sample_extra)
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

    def test_ask_stranger_spawns_answers_and_destroys_on_departure(self):
        asked = []
        answers = ["登记本在值班台抽屉里。"]

        def stub(messages):
            asked.append(messages)
            text = answers.pop(0) if answers else "这个我真不知道。"
            return '{"name":"speak","arguments":{"text":"%s"}}' % text

        ask = parse_decision("陈默", '{"name":"ask",'
                                    '"arguments":{"question":"晚安归登记本在哪？"}}', None)[0]
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
