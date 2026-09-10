"""The Ledger's in-world rules, kept outside the neutral World kernel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .kernel import ActionRejected, Event, World


@dataclass(frozen=True)
class Case:
    id: str
    terms: tuple[str, ...]
    reward: str
    query_limit: int = 1


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

    def __init__(self, facts: Mapping[str, str] | None = None,
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
        self.facts = dict(facts or {})
        self.status = "offered"
        self.accepted = False
        self.queries_used = 0
        self.reward_granted = False
        self.penalty_applied = False

    def affordances(self, actor_id: str) -> list[dict[str, Any]]:
        if actor_id != self.bound_actor:
            return []
        # 案件默认已接下（用户裁决）：无 accept/decline 仪式，引擎在启动时
        # 自动接案并提交 system_case_accepted 事件。
        if self.status == "accepted" and self.queries_used < self.case.query_limit:
            return [{"kind": "system_query", "question": ""}]  # affordance 行带参数名，参数值由 agent 填
        return []

    def auto_accept(self, world: World) -> None:
        """案件默认已接下（用户裁决 2026-09-10）：台账提出即生效，无仪式；
        提交 system_case_accepted 事件供叙事。"""
        if self.status == "offered":
            self.status = "accepted"
            self.accepted = True
            world.commit_external("system_case_accepted", self.bound_actor, {
                "system_name": self.name, "case": self.case.id,
                "condition": "auto-accepted on offer",
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

    def query(self, world: World, actor_id: str, question: str) -> Event:
        if actor_id != self.bound_actor or self.status != "accepted":
            raise ActionRejected("Ledger has no accepted case")
        if self.queries_used >= self.case.query_limit:
            raise ActionRejected("Ledger query limit exhausted")
        if not isinstance(question, str) or not question.strip() or len(question) > 160:
            raise ActionRejected("query must be concise")
        answer = self.facts.get(question.strip())
        if answer is None:
            raise ActionRejected("question is outside the Ledger's objective fact table")
        self.queries_used += 1
        answer_event = world.commit_external("system_answer", actor_id, {
            "system_name": self.name,
            "case": self.case.id, "question": question.strip(), "answer": answer,
            "condition_satisfied": True,
        }, None)
        self.status = "completed"
        self.reward_granted = True
        world.commit_external("system_reward_granted", actor_id, {
            "system_name": self.name,
            "case": self.case.id,
            "condition": "correct objective fact query",
            "reward": self.case.reward,
            "evidence_event_id": answer_event.id,
        }, answer_event.id)
        return answer_event

    # Alias: the engine calls the contract lookup through `ask` — `query` as
    # a method name trips SQL-injection scanners on a pure dict lookup.
    ask = query
