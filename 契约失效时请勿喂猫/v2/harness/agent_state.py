"""Private character state; never attached to the objective World."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PrivateState:
    actor_id: str
    goals: tuple[str, ...] = ()
    beliefs: dict[str, float] = field(default_factory=dict)
    memories: list[dict[str, Any]] = field(default_factory=list)
    interpretations: list[dict[str, Any]] = field(default_factory=list)
    private_notes: list[str] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "goals": list(self.goals),
            "beliefs": dict(self.beliefs),
            "memories": [dict(x) for x in self.memories],
            "interpretations": [dict(x) for x in self.interpretations],
            "private_notes": list(self.private_notes),
        }
