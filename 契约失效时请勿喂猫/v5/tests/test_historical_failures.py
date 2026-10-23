"""v5 的历史失败台账：M4 首次真跑之前的预门。

v5 路线图 §5 要求「每一支故事自己一份」台账，v5 此前没有。这一份的每一行都是一类**在本仓库真的发生过**的失败，指到一条会在守卫被拆掉时变红的测试。行不是对既有测试的别名：能被删掉而不变红的断言不许留在台账里。

覆盖台账（R = 本文件新增的行；E = 已由现存测试守住，只在这里点名，不重复写）
----------------------------------------------------------------------------
R00 台账形态：行必须写出类别、观察自、没有它时的后果 ........ test_r00_every_row_names_its_class_and_its_origin_and_what_breaks_without_it
R01 唯一运行工件被覆盖（轨迹丢失） ........................ test_r01_a_run_never_overwrites_an_earlier_run_directory
R02 运行没有逐回合 context.md，不能回答"他当时知道什么" .... test_r02_a_run_without_a_per_turn_context_view_is_not_evidence
R03 context.md 抬头写死"演员是脚本"（模型局被说成脚本局） .... test_r03_context_header_reports_who_actually_decided
R04 摘要按动作数猜语义，编出没发生的"把话说破" .............. test_r04_the_generated_ending_counts_speech_and_does_not_guess_what_was_said
R05 截断的工具调用让整局崩溃（而不是记成一条失败回合） ...... test_r05_a_truncated_tool_call_costs_one_turn_not_the_whole_run
R06 provider 空回复/挂死变成静默 wait 或无限等 .............. test_r06_a_provider_failure_is_bounded_and_raises_provider_error
R07 反作弊第三检抓不住"结局唯一" .......................... test_r07_the_reachability_check_catches_a_unique_ending
R08 排程效果没有处理器时被悄悄吃掉（P3：排程无后果） ........ test_r08_a_scheduled_effect_with_no_handler_is_a_loud_failure
R09 拿走别人的东西没有被在场者看见（或被告知给看不见的人） .. test_r09_taking_from_another_persons_drawer_is_seen_only_by_those_who_can_see
R10 "结局不唯一"的门槛被退回到 2（N 条路径 N-1 个结局照样过门） test_r10_the_uniqueness_threshold_scales_with_the_number_of_paths
R11 过夜之后时钟读成 32:00、日期不翻（一局过了夜，读的人看不出来） test_r11_the_clock_rolls_the_date_when_the_world_crosses_midnight

E01 引擎里出现故事名词（盲区） ............................ tests.test_m1_core.PrimitiveTests.test_engine_does_not_know_story_names；scripts/v5_lint.py check_engine_is_story_blind
E02 状态键没有渲染（改了状态但看不见） .................... tests.test_m1_core.SeedTests.test_every_state_key_has_a_renderer；scripts/v5_lint.py
E03 种子里对具名角色的祈使句（作者推动） .................. tests.test_m3_agent.AntiCheatTests.test_imperative_addressed_to_a_named_character_is_caught
E04 天意事件 / 排程替角色做决定 ........................... tests.test_m3_agent.AntiCheatTests.test_a_destiny_event_is_caught、test_scheduling_a_character_action_is_caught
E05 模型看不见别人的私密状态、也看不见状态键 .............. tests.test_m3_agent.PromptTests.test_prompt_never_carries_another_persons_private_state、test_turn_message_is_the_rendered_block_only；tests.test_m3_agent.AgentLoopTests.test_the_agent_sees_only_its_own_context
E06 拒绝不带"为什么、眼前有什么"（原地打转） .............. tests.test_m3_agent.AgentLoopTests.test_a_refusal_is_fed_back_so_the_agent_can_correct_itself；tests.test_m1_gates.Gate3ActionableRefusals
E07 读/摸留下痕迹，或读的内容被广播 ...................... tests.test_m1_gates.Gate1NoTrace；tests.test_m2_borrow_note.RecognitionTests.test_reading_gives_the_words_and_never_the_hand
E08 纸上有作者/时间/读者这类来源元数据 ................... tests.test_m1_gates.Gate2NoProvenance
E09 认字变成魔法（不用认识字迹就说出是谁的字） ............ tests.test_m2_borrow_note.RecognitionTests.test_recognition_is_knowledge_not_magic、test_only_someone_who_knows_the_hand_can_name_it
E10 叙述没人感知到的世界事件 .............................. tests.test_m1_gates.Gate4PerceptionOnly；tests.test_m2_borrow_note.StoryTests.test_no_script_ever_narrates_an_unperceived_world_event
E11 描述性指称解析失败（"桌子底下那只铁皮抽屉""手里的空白纸"） tests.test_m2_borrow_note.ReferenceTests（M3 试点已修，补的两个测试）
E12 走不到世界终点（F9） .................................. tests.test_m1_story.StoryTests.test_every_path_runs_to_the_end_of_the_world；tests.test_m2_borrow_note.StoryTests.test_four_paths_reach_four_findings
E13 重放不一致 / 篡改原子效果抓不住 ....................... tests.test_m1_replay.ReplayTests；tests.test_m2_borrow_note.ReplayTests
E14 种子里多一个不认识的字段被静默丢弃 .................... tests.test_m2_borrow_note.SchemaTests.test_an_unknown_seed_field_fails_loudly；tests.test_m3_agent.AntiCheatTests.test_unknown_field_in_a_seed_is_a_hard_error
E15 敲门后直接进门（没有等待） ............................ tests.test_m1_story.StoryTests.test_knocking_is_followed_by_waiting_not_by_instant_entry
E16 撞上引擎词汇的实体 id ................................. tests.test_m2_lint.LintTests.test_reserved_entity_ids_are_rejected

今天没有守卫、所以不记账的两类（写在报告里，不写成测试，见本包报告"未决"）
----------------------------------------------------------------------------
U01 拿走别人的东西没有任何社会后果（V5-M3-PILOT §三 第 6 行：乙拿走了借条，除了被看见没有后果）。R09 只守住"被看见"与"看见的范围"；"这是谁的东西（物权）"由 M4 制度层承担，v5 今天没有这个规则，所以不写测试。（路线图 §1 已把物权留在种子层）。
U02 旁观者无事可做 / "问一句"仍是最省力路径（V5-M3-PILOT §三 第 7、8 行）：属于种子与设计层，v5 今天没有可判据的守卫。
U03 无进展/停滞检测（v4 P1/P2、F5：重复同一被拒意图、wait 打转）：v5 还没有 runner 与半天续跑，M4 才落地，落地时在 M4 那份台账里补。
"""

from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import library  # noqa: F401,E402  规则与渲染在导入时登记
import anti_cheat  # noqa: E402
from engine import agent as agent_module  # noqa: E402
from engine.agent import ChatProvider, Decision, DecisionParseError, MockProvider, ProviderError  # noqa: E402
from engine.core import Entity, World  # noqa: E402
from engine.events import EventLog  # noqa: E402
from engine.rules import drain, submit  # noqa: E402
from engine.seed import load  # noqa: E402
from library import EFFECTS  # noqa: E402
from stories.common import context_view  # noqa: E402
from stories.s2_borrow_note import agent_run  # noqa: E402
from stories.s2_borrow_note.agent_run import play_agents, write_artifacts  # noqa: E402
from stories.s2_borrow_note.scenario import DEFAULT_SEED, play  # noqa: E402


def _one_agent_run(order=("jia",), turns_each=1, decisions=None):
    provider = MockProvider(decisions or [Decision("wait", {})])
    return play_agents("mock", turns_each=turns_each, provider=provider, order=order)


class _Response:
    """urllib 返回值的替身：只要 read() 与 with。"""

    def __init__(self, payload):
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class HistoricalFailureLedger(unittest.TestCase):
    def test_r00_every_row_names_its_class_and_its_origin_and_what_breaks_without_it(self):
        """【R00 台账形态】行必须写出类别、观察自哪里、没有它时今天会怎样。

        观察自：v4 台账（v4/harness/tests/test_historical_failures.py）的体例；本文件即为 v5 的对应物，形态由这条自检固定。
        没有它时：一行可以退化成"调用某个已经绿的测试"的别名——写得像守卫，拆掉却不变红，台账就成了装饰。
        """
        rows = [name for name in dir(type(self))
                if name.startswith("test_r") and not name.startswith("test_r00")]
        self.assertGreaterEqual(len(rows), 3, "台账至少要三行")
        for name in rows:
            doc = getattr(type(self), name).__doc__ or ""
            self.assertIn("【", doc, f"{name} 没有写出失败类别")
            self.assertIn("观察自：", doc, f"{name} 没有写出观察自哪里")
            self.assertIn("没有它时：", doc, f"{name} 没有写出没有守卫时的后果")

    def test_r01_a_run_never_overwrites_an_earlier_run_directory(self):
        """【R01 唯一运行工件】一次运行一个目录，绝不覆盖上一次的轨迹。

        观察自：AGENTS.md § v5 gate（"every provider run must land in a unique runs/agent-<time>-<pid>-<tag>/ directory (never overwrite one)"）与 § run analysis protocol；v4 的 113/114 号票就是轨迹被覆盖后整次验收无法复核。
        没有它时：同名 tag 的第二次运行会写进上一次的目录，旧轨迹被悄悄替换，报告里的引用变成指向别人。
        """
        run = _one_agent_run()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(agent_run, "HERE", Path(tmp)), \
                 mock.patch.object(agent_run.time, "strftime", return_value="20260101T000000"), \
                 mock.patch.object(agent_run.os, "getpid", return_value=4242):
                first = write_artifacts(run, "same")
                sentinel = first / "transcript.md"
                sentinel.write_text("上一次运行的轨迹，不许被覆盖", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    write_artifacts(run, "same")
                self.assertEqual(sentinel.read_text(encoding="utf-8"),
                                 "上一次运行的轨迹，不许被覆盖")
                self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    def test_r02_a_run_without_a_per_turn_context_view_is_not_evidence(self):
        """【R02 context.md 缺席或残缺】一次运行必须有逐回合的上下文视图，含模型给出的原始工具调用。

        观察自：AGENTS.md § v5 gate（"A run without context.md cannot answer 'what did he know when he did that', so it is not evidence"）与 § run analysis protocol。
        没有它时：轨迹只剩动作和结局，读的人无法回答"他当时知道什么"，一次模型运行就无法审，等于没跑。
        """
        run = _one_agent_run(order=("jia", "yi"), turns_each=2,
                             decisions=[Decision("wait", {}), Decision("examine", {"target": "借条"}),
                                        Decision("wait", {}), Decision("wait", {})])
        turns = [item for item in run.items if item["kind"] == "turn"]
        self.assertEqual(len(turns), 4)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(agent_run, "HERE", Path(tmp)):
                out = write_artifacts(run, "ctx")
            names = {path.name for path in out.iterdir()}
            self.assertEqual(names, {"transcript.md", "context.md", "events.jsonl", "run.json"})
            view = (out / "context.md").read_text(encoding="utf-8")
        self.assertEqual(view.count("\n## `["), len(turns), "每个动作一节")
        for item in turns:
            self.assertIn(item["raw"], view, f"第 {item['step']} 步的原始工具调用没进 context.md")

    def test_r03_context_header_reports_who_actually_decided(self):
        """【R03 视图抬头写死】context.md 的抬头必须由这一局的真实决定者生成，模型局不许自称脚本局。

        观察自：v5/docs/V5-M3-PILOT.md §三 第 5 行（模型局的 context.md 抬头写着"演员是脚本，不读上下文"，两份工件保留原样当证据）。
        没有它时：读者会按错误的抬头读上下文——模型局的每一回合都被当成"他没读上文"，主体性是零的证据反而被台账自己抹掉。
        """
        agent_view = context_view(_one_agent_run())
        self.assertIn("全部由模型决定", agent_view)
        self.assertNotIn("演员是脚本", agent_view)
        script_view = context_view(play("a"))
        self.assertIn("演员是脚本", script_view)
        self.assertNotIn("全部由模型决定", script_view)

    def test_r04_the_generated_ending_counts_speech_and_does_not_guess_what_was_said(self):
        """【R04 摘要猜语义】自动生成的结局句只许说事实（几次动作、读到了什么），不许替角色补情节。

        观察自：v5/docs/V5-M3-PILOT.md §三 第 4 行（"有人开口"被写成"把话说破"，根因是摘要按动作数猜语义）。
        没有它时：一句"说破""摊牌"就把没发生的对抗写进结局，报告与轨迹从此互相矛盾，读的人会按摘要而不是轨迹判断这一局。
        """
        provider = MockProvider([Decision("speak", {"text": "借条先别改"})])
        run = play_agents("mock", turns_each=1, provider=provider, order=("jia",))
        ending = run.summary["结局"]
        self.assertEqual(run.summary["有人当场说话"], 1)
        self.assertIn("当场开口 1 次", ending)
        for guessed in ("说破", "摊牌", "坦白", "吵", "逼"):
            self.assertNotIn(guessed, ending, f"结局句替角色补了情节：{ending}")

    def test_r05_a_truncated_tool_call_costs_one_turn_not_the_whole_run(self):
        """【R05 截断即崩局】一次坏掉的工具调用只算一回合的失败，整局继续跑。

        观察自：v5/docs/V5-M3-PILOT.md §三 第 3 行（一次工具调用被 max_tokens 截断，整局崩溃；处置是上移到 700 并把解析失败记成一条失败回合继续跑）。
        没有它时：一次截断就丢掉整局已经发生过的回合，花掉的机器时间与轨迹一起作废；而且崩溃没有工件，事后无法判断坏在哪一回合。
        """
        class TruncatingOnce:
            def __init__(self):
                self.calls = 0

            def decide(self, messages, tools):
                self.calls += 1
                if self.calls == 1:
                    raise DecisionParseError('{"function": {"name": "write", "arguments": "{\\"text\\": \\"今借到现')
                return Decision("wait", {}, raw='{"name": "wait", "arguments": {}}')

        provider = TruncatingOnce()
        run = play_agents("mock", turns_each=2, provider=provider, order=("jia",))
        turns = [item for item in run.items if item["kind"] == "turn"]
        self.assertEqual(len(turns), 2)
        self.assertFalse(turns[0]["ok"])
        self.assertEqual(turns[0]["reason"], "模型的工具调用无法解析")
        self.assertEqual(turns[0]["decided_by"], "agent")
        self.assertTrue(turns[1]["ok"])

    def test_r06_a_provider_failure_is_bounded_and_raises_provider_error(self):
        """【R06 provider 失败被静默吞掉】空回复与挂死连接都必须变成有界的 ProviderError，不许降级成 wait、也不许无限等。

        观察自：AGENTS.md § run analysis protocol（"A provider failure whose retry budget is exhausted is terminal ... must be checkpointed as a failed trace"）；v4 台账 F1（provider 502/瞬时重试逃逸成 agent_failure）与 E3（content-only 回复被丢，角色永久沉默）。
        没有它时：模型什么都不说时世界被一个假 wait 推着走，轨迹看起来正常、其实是它自己编的；挂死的连接则把整局钉在原地，等不到失败也等不到结果。
        """
        stalls: list[float | None] = []

        def stalled(request, timeout=None):
            stalls.append(timeout)
            raise TimeoutError("挂死的连接")

        provider = ChatProvider(model="m", base_url="http://127.0.0.1:9/v1", api_key="k",
                                timeout=3, retries=2)
        with mock.patch("urllib.request.urlopen", stalled), \
             mock.patch.object(agent_module.time, "sleep", return_value=None):
            with self.assertRaises(ProviderError):
                provider.decide([{"role": "user", "content": "hi"}], [])
        self.assertEqual(len(stalls), 2, "重试次数是有界的")
        self.assertEqual(stalls[0], 3, "每次请求都带墙钟上限")

        def silent(request, timeout=None):
            return _Response({"choices": [{"message": {"content": "我想想。", "tool_calls": []}}]})

        quiet = ChatProvider(model="m", base_url="http://127.0.0.1:9/v1", api_key="k",
                             timeout=3, retries=1)
        with mock.patch("urllib.request.urlopen", silent), \
             mock.patch.object(agent_module.time, "sleep", return_value=None):
            with self.assertRaises(ProviderError):
                quiet.decide([{"role": "user", "content": "hi"}], [])

    def test_r07_the_reachability_check_catches_a_unique_ending(self):
        """【R07 反作弊第三检抓不住错】"结局不唯一"这条检查本身必须能被反例打红。

        观察自：AGENTS.md § v5 gate（anti_cheat 覆盖"endings that are not unique"）与 v4 台账的体例（检查器测量期望轨迹，反向夹具证明它抓得住错）；v5 此前只测了祈使句与天意两条，第三检没有反例夹具。
        没有它时：只写一条路径、或两条路径走到同一个结局的故事都能过门，"结局不唯一"变成一句没人验证的断言。
        """
        def scenario_with(endings: dict[str, str]):
            module = types.SimpleNamespace()
            module.SCRIPTS = {variant: [] for variant in endings}
            module.play = lambda variant: types.SimpleNamespace(variant=variant)
            module.summary = lambda run: {"结局": endings[run.variant]}
            return module

        same = scenario_with({"a": "谁也没改", "b": "谁也没改"})
        with mock.patch.object(anti_cheat.importlib, "import_module", return_value=same):
            problems, _notes = anti_cheat.check_reachability("probe", False)
        self.assertTrue(problems)
        self.assertTrue(any("结局" in problem for problem in problems), problems)

        single = scenario_with({"a": "谁也没改"})
        with mock.patch.object(anti_cheat.importlib, "import_module", return_value=single):
            problems, _notes = anti_cheat.check_reachability("probe", False)
        self.assertTrue(any("只写了一条路径" in problem for problem in problems), problems)

    def test_r08_a_scheduled_effect_with_no_handler_is_a_loud_failure(self):
        """【R08 排程被悄悄吃掉】到点的世界效果没有处理器时必须当场炸，不许当成"什么也没发生"。

        观察自：v4 台账 P3（scheduled events with no consequence）；v5 engine/rules.py drain 的注释与 KeyError 就是这条的守卫。
        没有它时：一个拼错的排程效果会被无声消费，世界里"该发生的事"从来没发生，也没有任何事件说明它被跳过了。
        """
        world = World(start=0)
        world.add(Entity(id="p", kind="place", name="屋"))
        log = EventLog()
        world.schedule_effect(10, {"kind": "谁也没实现的效果", "place": "p"})
        world.clock = 10
        with self.assertRaises(KeyError) as ctx:
            drain(world, log, EFFECTS)
        self.assertIn("谁也没实现的效果", str(ctx.exception))
        self.assertEqual(len(log), 0, "失败的排程不许留下一条'已经发生'的事件")

    def test_r09_taking_from_another_persons_drawer_is_seen_only_by_those_who_can_see(self):
        """【R09 拿走没被看见 / 看见被广播】从一个不属于自己的抽屉里拿走东西，必须只落进看得见的人的记忆。

        观察自：v5/docs/V5-M3-PILOT.md §三 第 6 行（乙直接拉开甲的抽屉把借条拿走，除了被看见没有任何后果）——那一行的"被看见"这一半今天有守卫，"物权后果"那一半是 M4 制度层，见本文件头 U01。
        没有它时：拿东西要么是无声的（世界没有见证人，事后无从追究），要么被广播给看不见的人（隔着关上的门也知道谁拿走了什么）。
        """
        world = load(DEFAULT_SEED)
        log = EventLog()
        submit(world, log, "jia", "unlock", {"target": "抽屉"})
        submit(world, log, "jia", "open", {"target": "抽屉"})
        self.assertTrue(submit(world, log, "bing", "move", {"target": "楼道"}).ok)
        world.set_state("room", "door", "closed")
        receipt = submit(world, log, "jia", "take", {"target": "借条"})
        self.assertTrue(receipt.ok, receipt.reason)
        seen = " ".join(text for _at, text in world.memory["yi"])
        unseen = " ".join(text for _at, text in world.memory["bing"])
        self.assertIn("拿起了借条", seen)
        self.assertNotIn("拿起了", unseen)

    def test_r10_the_uniqueness_threshold_scales_with_the_number_of_paths(self):
        """【R10 结局门槛退回 2】路径多于结局时必须拒绝，门槛跟路径数走、不是常量 2。

        观察自：commit 6063e1c 的复审（把 scripts/anti_cheat.py 的 len(distinct) < len(variants) 改回 len(distinct) < 2，133 条测试全绿）——旧门槛只抓得住"所有路径同一个结局"，抓不住"三条路径两个结局"。
        没有它时：第三检可以被悄悄退回 2 而无人变红；一条故事写四条路径只走到两个结局，仍然过门，"结局"回到作者的断言。
        """
        def scenario_with(endings: dict[str, str]):
            module = types.SimpleNamespace()
            module.SCRIPTS = {variant: [] for variant in endings}
            module.play = lambda variant: types.SimpleNamespace(variant=variant)
            module.summary = lambda run: {"结局": endings[run.variant]}
            return module

        def check(endings: dict[str, str]) -> list[str]:
            module = scenario_with(endings)
            with mock.patch.object(anti_cheat.importlib, "import_module", return_value=module):
                problems, _notes = anti_cheat.check_reachability("probe", False)
            return problems

        # 三条路径只走到两个结局：门槛若写死 2 就放行，按路径数比就拒绝。
        two_of_three = check({"a": "谁也没改", "b": "谁也没改", "c": "借条到了乙手里"})
        self.assertTrue(any("3 条路径只走到 2 个结局" in problem for problem in two_of_three), two_of_three)

        # 对照：三条路径三个结局必须放行，否则上面那条只是被一个永远拒绝的检查满足。
        self.assertEqual(check({"a": "谁也没改", "b": "借条到了乙手里", "c": "门开着"}), [])


    def test_r11_the_clock_rolls_the_date_when_the_world_crosses_midnight(self):
        """【R11 过夜之后日期不翻】世界时钟过了午夜，轨迹上必须读出"第二天早上"，不是 32:00。

        观察自：2026-10-23 的复核——`半日一局` 的《夜市》路 e 在 1920 分钟（18:30 收摊、次日开门）处
        把时间印成 `32:00`，日期停在前一天，于是"这一局真的过了夜"在轨迹上看不出来，只写在测试的断言里。
        没有它时：一条真的跨了夜的路径，读者只能从 `32:00` 这个数字猜；任何"过了半天/过了夜"的说法
        都退回成开发者口头的解释，而不是工件上看得见的事实。
        """
        from engine.surface import clock_label
        # 有日期就翻日：1920 = 次日 08:00
        self.assertEqual(clock_label(1920, "2026-04-02"), "2026-04-03 08:00")
        self.assertEqual(clock_label(1920 + 2, "2026-04-02"), "2026-04-03 08:02")
        # 没有日期就没有日可翻，仍然是那个难看的数——两读并存，说明翻日是日期做的
        self.assertEqual(clock_label(1920), "32:00")
        # 真的过夜那一局的故事视图里，次日的两个事件都带着次日的日期
        from stories.s3_night_market.scenario import play
        from stories.common import transcript
        view = transcript(play("e"), "《夜市》路 e")
        self.assertIn("2026-04-03 08:00", view)
        self.assertNotIn("32:00", view)


if __name__ == "__main__":
    unittest.main()
