"""M5：同一套世界、同一套检查，在第二支故事上跑一遍。

人的答案把《末班车》的模型首轮报告放在下一个里程碑旁边（`docs/V5-ROADMAP.md` §3）：
"这套机制能让模型自己走出它的路"要在一块第二个世界上再成立一次，才算阶梯上的结论。
这一份测的是**同一份回路**（`stories/agent_loop.py`）接到第二个种子上仍然成立的五件事：

1. 每个动作都由模型决定：一条模型局里没有 `[脚本]` 的动作；
2. 每个动作都留下它当时拿到的上下文，`context_used` 为真；
3. 上下文里没有状态键、没有别人的私密信念——第二支故事的提示不是靠"这次记得"；
4. `context.md` 的抬头是算出来的，不是写死的：把决定者翻成脚本，抬头必须跟着变；
5. 结局由这支故事自己的摘要拼出，回路不认识"末班车"这三个字。

花的钱是零：MockProvider 走同一条回路。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401
from engine.agent import Decision, MockProvider
from engine.prompt import system_prompt
from engine.seed import load
from stories.common import context_view
from stories.s1_last_bus import agent_run
from stories.s1_last_bus.scenario import DEFAULT_SEED, summary
from stories.s2_borrow_note.agent_run import play_agents as s2_play_agents

STATE_KEYS = ("locked", "portable", "closed", "marks", "hand", "opens", "accepts")


def _run(turns_each: int = 2, decisions: int = 6):
    script = [Decision(verb="examine", args={}) for _ in range(decisions)]
    return agent_run.play_agents("mock/second-story", turns_each=turns_each,
                                 provider=MockProvider(script=list(script)))


class SecondStoryAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outcome = _run()
        cls.turns = [i for i in cls.outcome.items if i["kind"] == "turn"]

    # ---- 1. 没有脚本动作 ------------------------------------------------
    def test_every_action_in_a_model_run_is_decided_by_the_model(self):
        self.assertEqual(len(self.turns), 6)
        self.assertEqual({i["decided_by"] for i in self.turns}, {"agent"})

    # ---- 2. 上下文逐回合留下 -------------------------------------------
    def test_every_action_carries_the_context_it_was_given(self):
        for item in self.turns:
            self.assertTrue(item["context_used"], item)
            self.assertIn("glance", item["context"])
            self.assertIn("time", item["context"]["glance"])
            self.assertIn("recent", item["context"])
            self.assertTrue(item["raw"], "模型给的原始工具调用必须留下")

    # ---- 3. 第二支故事的提示仍然不泄漏 ---------------------------------
    def test_the_second_storys_prompt_carries_no_state_keys_and_no_others_private_state(self):
        world = load(DEFAULT_SEED)
        text = system_prompt(world, "jia")
        for key in STATE_KEYS:
            self.assertNotIn(key, text)
        # 乙的私密信念与司机的心事都不在甲的系统提示里
        self.assertNotIn("药是按点吃的", text)
        self.assertNotIn("落到你手上的东西你得有个交代", text)
        # 而甲自己的身份在
        self.assertIn("做一份和表格打交道的差事", text)

    # ---- 4. 抬头是算出来的 ---------------------------------------------
    def test_the_context_header_reports_who_actually_decided_on_the_second_story(self):
        view = context_view(self.outcome)
        self.assertIn("全部由模型决定", view)
        self.assertNotIn("演员是脚本", view)
        # 负向对照：把决定者翻成脚本，同一份视图必须改口，而不是一直说"模型"
        flipped = _run()
        for item in flipped.items:
            if item["kind"] == "turn":
                item["decided_by"] = "script"
        self.assertIn("演员是脚本", context_view(flipped))
        self.assertNotIn("全部由模型决定", context_view(flipped))

    # ---- 5. 结局属于这支故事，回路不认识它 -----------------------------
    def test_the_ending_comes_from_the_story_not_from_the_loop(self):
        self.assertEqual(self.outcome.summary, summary(self.outcome))
        self.assertIn("结局", self.outcome.summary)
        # 同一份回路接到《借条》上得出的仍是《借条》的摘要形状
        other = s2_play_agents("mock/second-story", turns_each=1,
                               order=("jia",), provider=MockProvider(
                                   script=[Decision(verb="examine", args={})]))
        self.assertNotEqual(set(other.summary), set(self.outcome.summary))


class SecondStoryArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="v5-second-story-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_second_story_run_writes_the_same_four_artifacts(self):
        run = _run(turns_each=1, decisions=3)
        out = agent_run.write_artifacts(run, "mock")
        # 目录由 HERE 算，测试里改到临时目录再写一次
        shutil.rmtree(out, ignore_errors=True)
        import unittest.mock as mock
        with mock.patch.object(agent_run, "HERE", self.tmp):
            out = agent_run.write_artifacts(run, "mock")
        written = sorted(p.name for p in out.iterdir())
        self.assertEqual(written, ["context.md", "events.jsonl", "run.json", "transcript.md"])
        self.assertIn("《末班车》模型试点轨迹", (out / "transcript.md").read_text(encoding="utf-8"))
        self.assertIn("全部由模型决定", (out / "context.md").read_text(encoding="utf-8"))
        # 同一秒、同一个 pid 再写一次：不许覆盖上一份
        with mock.patch.object(agent_run, "HERE", self.tmp):
            with self.assertRaises(FileExistsError):
                agent_run.write_artifacts(run, "mock")


if __name__ == "__main__":
    unittest.main()
