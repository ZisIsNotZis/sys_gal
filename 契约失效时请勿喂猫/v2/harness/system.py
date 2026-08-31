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
    """

    CASE = Case(
        "ambiguous-obligations",
        ("name the object", "name the responsible person", "name a deadline"),
        "one narrow objective clarification",
    )

    def __init__(self, facts: Mapping[str, str] | None = None) -> None:
        self.facts = dict(facts or {})
        self.status = "offered"
        self.accepted = False
        self.queries_used = 0
        self.reward_granted = False
        self.penalty_applied = False

    def affordances(self, actor_id: str) -> list[dict[str, Any]]:
        if actor_id != "chen-mo":
            return []
        if self.status == "offered":
            return [{"kind": "system_accept", "case": self.CASE.id},
                    {"kind": "system_decline", "case": self.CASE.id}]
        if self.status == "accepted" and self.queries_used < self.CASE.query_limit:
            return [{"kind": "system_query", "question": ""}]
        return []

    def accept(self, world: World, actor_id: str, case_id: str) -> Event:
        if actor_id != "chen-mo" or self.status != "offered" or case_id != self.CASE.id:
            raise ActionRejected("Ledger case is unavailable")
        self.accepted = True
        self.status = "accepted"
        return world.commit_external("system_case_accepted", actor_id, {
            "case": self.CASE.id, "terms": list(self.CASE.terms),
            "condition": "correct objective fact query",
            "reward_offer": self.CASE.reward,
        }, None)

    def decline(self, world: World, actor_id: str) -> Event:
        if actor_id != "chen-mo" or self.status != "offered":
            raise ActionRejected("Ledger offer is unavailable")
        self.status = "declined"
        self.penalty_applied = True
        return world.commit_external("system_penalty_applied", actor_id, {
            "case": self.CASE.id,
            "condition": "voluntary decline after binding offer",
            "penalty": "the offered clarification is forfeited",
        }, None)

    decline_offer = decline

    def query(self, world: World, actor_id: str, question: str) -> Event:
        if actor_id != "chen-mo" or self.status != "accepted":
            raise ActionRejected("Ledger has no accepted case")
        if self.queries_used >= self.CASE.query_limit:
            raise ActionRejected("Ledger query limit exhausted")
        if not isinstance(question, str) or not question.strip() or len(question) > 160:
            raise ActionRejected("query must be concise")
        answer = self.facts.get(question.strip())
        if answer is None:
            raise ActionRejected("question is outside the Ledger's objective fact table")
        self.queries_used += 1
        answer_event = world.commit_external("system_answer", actor_id, {
            "case": self.CASE.id, "question": question.strip(), "answer": answer,
            "condition_satisfied": True,
        }, None)
        self.status = "completed"
        self.reward_granted = True
        world.commit_external("system_reward_granted", actor_id, {
            "case": self.CASE.id,
            "condition": "correct objective fact query",
            "reward": self.CASE.reward,
            "evidence_event_id": answer_event.id,
        }, answer_event.id)
        return answer_event
