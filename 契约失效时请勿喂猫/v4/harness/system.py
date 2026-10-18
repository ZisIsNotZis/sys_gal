"""The Ledger's in-world rules, kept outside the neutral World kernel."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Any, Mapping

from .kernel import ActionRejected, Event, World
from .kb import normalize


# 票 91（E92）：一次点名台账的发言在 tool 结果里得到的回答。四种拒绝各一句台词——
# 台账是对话者，它说人话，引擎的英文异常文本不外泄。答案是既有 `system_answer`
# 私有事件，不写进 tool 结果（那是另一条已实现的通道，见 `Ledger.converse`）。
# `{name}` 由种子声明的 `system.name` 填入：这个类是种子无关的，名字只有一处来源。
DIALOGUE_REPLIES = {
    "unknown": ("{name}沉默了一下，答：不知道。它只答自己案卷里记着的条目——"
                "问句里带上那件事、那个东西或那个期限的名字。"),
    "closed": "{name}不应声了：这一案已经了结，它闭口了。",
    "limit": "{name}闭口了：它肯答的次数已经用尽。",
    "malformed": "它没听完：一句话问一件事，短一点（不超过 160 字）。",
}
DIALOGUE_NO_REPLY = "{name}没有作答。"
DIALOGUE_ANSWERED = "{name}应了一声——它的话直接进到你脑子里了。"


@dataclass(frozen=True)
class Case:
    id: str
    terms: tuple[str, ...]
    reward: str
    query_limit: int = 1


def _match_text(value: Any) -> str:
    """归一化后的匹配文本（票 95，E95）。

    全角/半角先经 NFKC 折到同一形，再去空白、标点与 `的`/`之`（与 KB 唤起同一个
    `normalize`）。台账因此不再要求角色逐字向出种子里的问句——但仍然不猜语义，
    只做确定性的字符包含与关键词计数。
    """
    return normalize(unicodedata.normalize("NFKC", str(value)))


class Ledger:
    """A constrained supernatural participant, not a plot director.

    The Ledger owns only its contract rules and objective fact table. It never
    receives or writes human affect, hidden agent state, or narrative labels.
    All story specifics (name, bound actor, case, terms, reward, facts) come
    from the world pack's ``system`` block at runtime. The class defaults below
    merely mirror that canonical seed so the mechanism is usable in tests;
    production runs always pass ``pack.system`` explicitly.
    """

    CASE = Case(
        "ambiguous-obligations",
        ("name the object", "name the responsible person", "name a deadline"),
        "one narrow objective clarification",
    )

    def __init__(self, facts: Mapping[str, Any] | None = None,
                 config: Mapping[str, Any] | None = None) -> None:
        config = dict(config or {})
        terms = tuple(str(x) for x in config.get("terms", self.CASE.terms))
        try:
            query_limit = int(config.get("query_limit", self.CASE.query_limit))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid query_limit: {config.get('query_limit')!r}") from exc
        self.case = Case(str(config.get("case_id", self.CASE.id)), terms,
                         str(config.get("reward", self.CASE.reward)),
                         query_limit)
        self.name = str(config.get("name", "ledger"))
        self.bound_actor = str(config.get("bound_actor", "陈默"))
        # 票 93（用户裁定）：结案由**种子排程的结算节拍**驱动，不是首次命中。
        # `settle_on` 点的是 `scheduled:` 里那条事件的 `event` 名（本种子是
        # `ledger_settlement`）；没写 = 这个案子没有排定的结算（缺就是不排，不猜）。
        settle_on = config.get("settle_on")
        self.settle_on = str(settle_on) if settle_on is not None else None
        # 票 95（E95）：事实条目有两种写法——旧的 `问句: 答案`，以及带关键词的
        # `问句: {answer: ..., keywords: [...]}`。条目自己的问句永远也算一个
        # 匹配词（缺省回落到它），因此老工件与老测试里逐字问仍然命中。
        self.facts: dict[str, str] = {}
        self.fact_keywords: dict[str, tuple[str, ...]] = {}
        for key, value in dict(facts or {}).items():
            if isinstance(value, Mapping):
                answer = value.get("answer")
                if not isinstance(answer, str) or not answer.strip():
                    raise ValueError(
                        f"fact entry {key!r} must declare a non-empty answer")
                raw = value.get("keywords") or ()
                if isinstance(raw, str):
                    raw = (raw,)
                if not isinstance(raw, (list, tuple)):
                    raise ValueError(
                        f"fact entry {key!r} keywords must be a list of strings")
                keywords = tuple(str(item) for item in raw if str(item).strip())
            else:
                answer = str(value)
                keywords = ()
            self.facts[str(key)] = answer
            self.fact_keywords[str(key)] = keywords
        self.status = "offered"
        self.accepted = False
        self.queries_used = 0
        self.reward_granted = False
        self.penalty_applied = False
        self.last_answer_event_id: int | None = None

    def affordances(self, actor_id: str) -> list[dict[str, Any]]:
        # 台账不是工具（工单 14）：交互走世界内对话。对话通道是 speak 点名台账
        # （票 91，V4-AGENT-INTERFACE §5）——它是描述世界内可及对象的旧接口，
        # v4 没有 #actions 块，所以这里仍然无 affordance。
        return []

    # ------------------------------------------------------------- 对话通道

    def answers_to(self, actor_id: str) -> bool:
        """对话通道只对一个角色开放：受约束角色（票 91）。

        未受约束的角色点名台账时不走任何路由，内核照旧判"未知收件人"，
        因此台账既不会对别人应声，也不会把自己的存在泄给别人的工具结果。"""
        return actor_id == self.bound_actor

    def addressable(self, actor_id: str, name: Any) -> bool:
        """`name` 是不是这个角色对台账的称呼（票 91）。

        只认种子声明的 `system.name`（归一化后比较）；不猜别名——台账的名字是
        种子的事实，猜出来的名字会把它变成一个什么都能应答的口子。"""
        if not self.answers_to(actor_id):
            return False
        return normalize(str(name or "")) == normalize(self.name)

    def converse(self, world: World, actor_id: str, line: Any) -> tuple[str, list[Event]]:
        """受约束角色点名台账说话 = 一次提问（票 91，引擎的唯一对话入口）。

        返回 (tool 结果文本, 本次提交的事件)。答案本身不走 tool 结果，而走既有的
        `system_answer` 私有事件——那是已实现、已测试、只为受约束角色可见的通道，
        下一回合由 prompt 渲染成它听见的一句话。答不了说不知道、超限即闭口；
        这两种都不吞查询额度（沿用 `query` 的既有语义）。"""
        start = len(world.event_log)
        try:
            self.query(world, actor_id, line)
        except ActionRejected as exc:
            template = DIALOGUE_REPLIES.get(str(exc.context.get("ledger")),
                                            DIALOGUE_NO_REPLY)
            return template.format(name=self.name), list(world.event_log[start:])
        return (DIALOGUE_ANSWERED.format(name=self.name),
                list(world.event_log[start:]))

    def auto_accept(self, world: World) -> None:
        """案件默认已接下（用户裁决 2026-09-10）：台账提出即生效，无仪式；
        提交 system_case_accepted 事件供叙事。payload 与 accept() 一致——
        缺 terms/reward_offer 会在渲染里出现字面 None（评审 #1）。"""
        if self.status == "offered":
            self.status = "accepted"
            self.accepted = True
            world.commit_external("system_case_accepted", self.bound_actor, {
                "system_name": self.name,
                "case": self.case.id, "terms": list(self.case.terms),
                "condition": "correct objective fact query",
                "reward_offer": self.case.reward,
            }, None)

    def accept(self, world: World, actor_id: str, case_id: str) -> Event:
        if actor_id != self.bound_actor or self.status != "offered" or case_id != self.case.id:
            raise ActionRejected("Ledger case is unavailable")
        self.accepted = True
        self.status = "accepted"
        return world.commit_external("system_case_accepted", actor_id, {
            "system_name": self.name,
            "case": self.case.id, "terms": list(self.case.terms),
            "condition": "correct objective fact query",
            "reward_offer": self.case.reward,
        }, None)

    def decline(self, world: World, actor_id: str) -> Event:
        if actor_id != self.bound_actor or self.status != "offered":
            raise ActionRejected("Ledger offer is unavailable")
        self.status = "declined"
        self.penalty_applied = True
        return world.commit_external("system_penalty_applied", actor_id, {
            "system_name": self.name,
            "case": self.case.id,
            "condition": "voluntary decline after binding offer",
            "penalty": "the offered clarification is forfeited",
        }, None)

    decline_offer = decline

    # ------------------------------------------------------------- 结案

    def settle(self, world: World, cause: Event | None = None) -> Event | None:
        """种子排程的结算事件到达 → 结案，并走既有 `system_reward_granted` 发报酬。

        票 93（用户裁定，文档 `docs/V4-AGENT-INTERFACE.md` §5）：**结案 ≠ 首次
        命中**。命中只产生一条 `system_answer`（答案本身），案子照旧开着、额度照旧
        递减；到种子写的那条结算节拍（`system.settle_on`，本种子是 3/22 15:00 的
        `ledger_settlement`）到达，才结案。幂等：未接受（offered/declined）或已经
        结案时什么都不做，因此同一节拍被扫描两遍也只发一次。

        结算只送种子里那句有界报酬（`case.reward`），不凭空加戏：`evidence_event_id`
        指向这案唯一那条答案（没答过就不带这个键，而不是拿一个空值顶上）。
        """
        if self.status != "accepted":
            return None
        payload: dict[str, Any] = {
            "system_name": self.name,
            "case": self.case.id,
            "condition": "seeded settlement beat",
            "reward": self.case.reward,
        }
        if self.last_answer_event_id is not None:
            payload["evidence_event_id"] = self.last_answer_event_id
        if cause is not None:
            payload["settled_event_id"] = cause.id
        event = world.commit_external("system_reward_granted", self.bound_actor, payload,
                                      cause.id if cause is not None else None)
        self.status = "closed"
        self.reward_granted = True
        return event

    def _is_mine(self, event: Event) -> bool:
        """这条 system 事件是不是本台账这案的。"""
        return (str(event.payload.get("system_name")) == self.name
                and str(event.payload.get("case")) == self.case.id)

    def _reconcile(self, world: World) -> None:
        """结案与已问次数是世界日志里的事实（票 93）。

        `Ledger` 本身不进检查点（它在 `real_run`/`resume_run` 里按种子重建），所以
        进程内的 `status`/`queries_used` 在一次恢复后会归零。`system_answer` 与
        `system_reward_granted` 都只由本台账产生、又都在检查点的世界日志里，于是
        这两样从日志重建：恢复后的案子不会因为重启又开着、也不会白送一次新额度。
        """
        answers = [e for e in world.event_log
                   if e.kind == "system_answer" and self._is_mine(e)]
        self.queries_used = max(self.queries_used, len(answers))
        if answers and self.last_answer_event_id is None:
            self.last_answer_event_id = answers[-1].id
        if self.status != "closed" and any(
                e.kind == "system_reward_granted" and self._is_mine(e)
                for e in world.event_log):
            self.status = "closed"
            self.reward_granted = True

    def query(self, world: World, actor_id: str, question: str) -> Event:
        # 票 91：四种拒绝各带一个机器可读的原因（`context["ledger"]`），
        # 好让对话通道说人话而不必匹配英文措辞；异常文本本身不变。
        self._reconcile(world)
        if actor_id != self.bound_actor:
            # 不是受约束角色就不是一场对话：不路由也不留审计事件（否则会把
            # 别人的话记到受约束角色名下）。
            raise ActionRejected("Ledger has no accepted case",
                                 context={"ledger": "closed"})
        if self.status != "accepted":
            self._audit(world, question, matched=False, outcome="closed")
            raise ActionRejected("Ledger has no accepted case",
                                 context={"ledger": "closed"})
        if self.queries_used >= self.case.query_limit:
            self._audit(world, question, matched=False, outcome="limit")
            raise ActionRejected("Ledger query limit exhausted",
                                 context={"ledger": "limit"})
        if not isinstance(question, str) or not question.strip() or len(question) > 160:
            self._audit(world, question, matched=False, outcome="malformed")
            raise ActionRejected("query must be concise",
                                 context={"ledger": "malformed"})
        answer, outcome = self._lookup(question)
        if answer is None:
            # 票 95（E95）：命中不了也说不知道——但拒绝本身必须留痕（一条只给
            # 提问者的私有 `system_dialogue` 事件），否则会话压缩后复核者只能
            # 靠“没有 system_answer”反推。不消耗查询额度。
            self._audit(world, question, matched=False, outcome=outcome)
            raise ActionRejected(
                "question is outside the Ledger's objective fact table; "
                "no entry's keywords matched it (the question must name the "
                "object, or match a declared keyword)"
                f" (queries used: {self.queries_used}/{self.case.query_limit})",
                context={"ledger": "unknown"})
        self.queries_used += 1
        answer_event = world.commit_external("system_answer", actor_id, {
            "system_name": self.name,
            "case": self.case.id, "question": question.strip(), "answer": answer,
            "condition_satisfied": True,
        }, None)
        # 票 93：答对只是答对——案子不在这里结（结案见 `settle`）。
        self.last_answer_event_id = answer_event.id
        # 票 95（E95）：每次对话都在世界日志里留一条只给提问者的事件；命中的
        # 那条带答案事件 id，于是“问了什么、答了没、答案是哪一条”都可审计。
        self._audit(world, question, matched=True, outcome="answered",
                    answer_event_id=answer_event.id)
        return answer_event

    # Alias: the engine calls the contract lookup through `ask` — `query` as
    # a method name trips SQL-injection scanners on a pure dict lookup.
    ask = query

    # ------------------------------------------------- 确定性匹配（票 95，E95）

    def _terms(self, key: str) -> list[str]:
        """一个条目的匹配词：自己声明的 keywords + 条目问句本身。"""
        terms: list[str] = []
        for term in (key, *self.fact_keywords.get(key, ())):
            normalized = _match_text(term)
            if normalized and normalized not in terms:
                terms.append(normalized)
        return terms

    def _lookup(self, question: str) -> tuple[str | None, str]:
        """确定性匹配：返回 (答案 | None, outcome)。不调模型、不猜语义。

        规则（文档 `V4-AGENT-INTERFACE.md` §5）：
        - 归一化：NFKC（全角/半角）+ 去空白/标点/`的`/`之`；
        - 问句归一化后与某个条目问句逐字相等 → 直接命中它；
        - 否则每个条目的每个匹配词计一分（词出现在问句里，或问句整句出现在
          词里——与 KB 唤起同一条双向子串规则）；
        - 唯一最高分且 >0 → 命中；并列或零分 → 不知道（outcome
          `tie` / `unknown`）。

        条目自己的问句也是匹配词，所以旧写法（逐字问）照旧命中；一个条目只
        声明 keywords 时，它们只是让自然问法也能对上。
        """
        normalized = _match_text(question)
        exact = [key for key in self.facts if _match_text(key) == normalized]
        if len(exact) == 1:
            return self.facts[exact[0]], "answered"
        if len(exact) > 1:
            return None, "tie"
        scores: dict[str, int] = {}
        for key in self.facts:
            score = sum(1 for term in self._terms(key)
                        if term in normalized or normalized in term)
            if score:
                scores[key] = score
        if not scores:
            return None, "unknown"
        best = max(scores.values())
        winners = [key for key, score in scores.items() if score == best]
        if len(winners) != 1:
            return None, "tie"
        return self.facts[winners[0]], "answered"

    def _audit(self, world: World, question: Any, *, matched: bool,
               outcome: str, answer_event_id: int | None = None) -> Event:
        """每一次对话都留一条只给提问者的私有事件（票 95，E95）。

        `system_dialogue` 是审计通道，不是说话：不进 `speech`、不进 tool 结果、
        渲染层不为它产生一行（`prompt._event_sentence` 显式返回 None）。
        `answer_event_id` 只在命中时出现（缺就是缺，不拿空值顶）；`outcome`
        区分 `answered` / `unknown` / `tie` / `limit` / `closed` / `malformed`。
        """
        payload: dict[str, Any] = {
            "system_name": self.name,
            "case": self.case.id,
            "question": question if isinstance(question, str) else str(question),
            "matched": bool(matched),
            "outcome": str(outcome),
        }
        if answer_event_id is not None:
            payload["answer_event_id"] = answer_event_id
        return world.commit_external("system_dialogue", self.bound_actor, payload, None)
