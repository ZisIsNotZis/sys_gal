"""Small provider-neutral adapter for independent character model calls."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .adapter import parse_decision
from .agent_state import PrivateState
from .character_loader import CharacterSeed
from .kernel import Intention
from .prompt import build_prompt


ModelCall = Callable[[str], str | dict[str, Any] | None]


def make_model_agent(seed: CharacterSeed, call: ModelCall):
    """Return a Runner-compatible agent bound to exactly one character seed."""
    def agent(state: PrivateState, perception: dict[str, Any],
              affordances: list[dict[str, Any]]) -> tuple[Intention | None, dict[str, Any]]:
        prompt = build_prompt(identity=seed.identity, private_seed=seed.private_seed,
                              state=state, perception=perception, affordances=affordances)
        return parse_decision(state.actor_id, call(prompt), perception["world_version"])
    return agent
