"""Adapter from persistent character sessions to the neutral Runner."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .character_loader import CharacterSeed
from .character_session import CharacterSession, ModelCall, NaturalIntention
from .agent_state import PrivateState


GMCall = Any


def make_provider_gm(call: ModelCall, *, max_retries: int = 1):
    """Create a narrow interpreter for prose that cannot be executed directly."""
    def gm(text: str, perception: dict, affordances: list[dict]):
        prompt = [{"role": "system", "content": (
            "You are a neutral world interpreter. Convert the person's natural-language "
            "intention into exactly one concrete action from the offered actions. Do not invent "
            "facts, dialogue, relationships, or plot. If it cannot be safely resolved, return "
            "null. Output valid JSON only."
        )}, {"role": "user", "content": (
            f"Person's intention:\n{text}\n\nVisible world:\n{perception}\n\n"
            f"Offered actions:\n{affordances}\n\nReturn {{\"kind\":...,\"args\":...}} or null."
        )}]
        for attempt in range(max_retries + 1):
            try:
                return call(prompt)
            except Exception as exc:
                # Interpretation has no world side effect until its result is
                # validated and submitted by Runner, so a bounded retry is
                # safe even when the provider exhausted its own HTTP retries.
                if getattr(exc, "retryable", False) and attempt < max_retries:
                    continue
                if getattr(exc, "retryable", False):
                    exc.runner_retryable = True  # type: ignore[attr-defined]
                raise
    return gm


def make_persistent_agent(seed: CharacterSeed, call: ModelCall, gm: GMCall = None,
                          session: CharacterSession | None = None,
                          world_primer: str = ""):
    # ``session`` lets a resume path inject a restored conversation so history
    # survives a checkpoint/restart; otherwise one is created from the seed.
    session: CharacterSession | None = session
    gm_records: list[dict[str, Any]] = []

    def agent(state: PrivateState, perception: dict, affordances: list[dict]):
        nonlocal session
        if session is None:
            session = CharacterSession(seed, state, call, world_primer=world_primer)
        from .prompt import render_world_message
        message = render_world_message(perception, affordances)
        decision, updates = session.decide(message, perception["world_version"],
                                            turn_id=perception.get("_turn_id"))
        if isinstance(decision, NaturalIntention):
            if gm is None:
                raise ValueError("character expressed a natural-language intention but no GM is bound")
            record: dict[str, Any] = {"actor": state.actor_id, "original_prose": decision.text,
                                      "perception": deepcopy(perception),
                                      "affordances": deepcopy(affordances),
                                      "result": None, "error": None}
            try:
                interpreted = gm(decision.text, deepcopy(perception), deepcopy(affordances))
                record["result"] = deepcopy(interpreted)
                if isinstance(interpreted, tuple):
                    if len(interpreted) != 2:
                        raise ValueError("GM result must be an (intention, updates) pair")
                    intention, updates = interpreted
                    if intention is not None and intention.kind not in {
                            str(option.get("kind")) for option in affordances}:
                        raise ValueError("GM selected an action that was not offered by the world")
                    resolved = (intention, updates)
                else:
                    from .adapter import parse_decision
                    resolved = parse_decision(state.actor_id, interpreted, perception["world_version"])
                    intention, updates = resolved
                    offered_kinds = {str(option.get("kind")) for option in affordances}
                    if intention is not None and intention.kind not in offered_kinds:
                        raise ValueError("GM selected an action that was not offered by the world")
                gm_records.append(record)
                return resolved
            except Exception as exc:
                # A GM is an interpreter, not an authority. An invalid result
                # means no action; it must not become an opaque engine failure.
                record["error"] = f"{type(exc).__name__}: {exc}"
                gm_records.append(record)
                # An upstream outage is different from an invalid
                # interpretation. Do not turn an infrastructure failure into
                # an in-world decision to do nothing.
                if getattr(exc, "retryable", False):
                    raise
                return None, {}
        return decision, updates

    agent.session = lambda: session  # type: ignore[attr-defined]
    agent.record_world_result = lambda message: session and session.record_world_result(message)  # type: ignore[attr-defined]
    agent.consume_compaction = (lambda: session.consume_compaction() if session else False)  # type: ignore[attr-defined]
    agent.session_snapshot = lambda: session.snapshot() if session else None  # type: ignore[attr-defined]
    def drain_gm_records() -> list[dict[str, Any]]:
        records = list(gm_records)
        gm_records.clear()
        return records
    agent.drain_gm_records = drain_gm_records  # type: ignore[attr-defined]
    return agent
