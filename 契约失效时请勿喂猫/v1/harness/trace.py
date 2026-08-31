"""Serializable trace capture for harness and agent trajectory analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .kernel import Event, Intention, WorldHarness
from .vn import project_vn


@dataclass
class TraceRecorder:
    """Captures agent inputs/outputs alongside the authoritative world log."""

    source_version: str
    run_id: str
    agent_trajectory: list[dict[str, Any]] = field(default_factory=list)
    judge_trajectory: list[dict[str, Any]] = field(default_factory=list)
    run_outcome: dict[str, Any] | None = None

    def record_agent_turn(
        self,
        *,
        actor: str,
        perception: Mapping[str, Any],
        affordances: list[Mapping[str, Any]],
        intention: Intention | None,
        result: str,
        error: str | None = None,
        committed_event_ids: list[int] | None = None,
        world_version_after: int | None = None,
    ) -> None:
        entry = {
            "actor": actor,
            "world_version": perception.get("world_version"),
            "time": perception.get("time"),
            "perception": deepcopy(dict(perception)),
            "affordances": deepcopy([dict(option) for option in affordances]),
            "intention": None if intention is None else {
                "actor": intention.actor,
                "kind": intention.kind,
                "args": deepcopy(dict(intention.args)),
                "expected_version": intention.expected_version,
            },
            "result": result,
            "error": error,
        }
        if committed_event_ids is not None:
            entry["committed_event_ids"] = list(committed_event_ids)
        if world_version_after is not None:
            entry["world_version_after"] = world_version_after
        self.agent_trajectory.append(entry)

    def record_judge_turn(self, *, request: Mapping[str, Any], response: Mapping[str, Any], result: str) -> None:
        self.judge_trajectory.append({
            "request": deepcopy(dict(request)),
            "response": deepcopy(dict(response)),
            "result": result,
        })

    def finish(self, *, outcome: str, reason: str, time: str) -> None:
        self.run_outcome = {"outcome": outcome, "reason": reason, "time": time}

    def snapshot(self, world: WorldHarness) -> dict[str, Any]:
        world_log = list(world.replayable_log())
        projection = project_vn(world_log)
        return {
            "trace_format": "harness-trace-v2",
            "source_version": self.source_version,
            "run_id": self.run_id,
            "agent_trajectory": self.agent_trajectory,
            "judge_trajectory": self.judge_trajectory,
            "run_outcome": self.run_outcome,
            "world_trajectory": world_log,
            "replay": {
                "event_count": len(world_log),
                "first_event_id": world_log[0]["id"] if world_log else None,
                "last_event_id": world_log[-1]["id"] if world_log else None,
                "contiguous_event_ids": [e["id"] for e in world_log] == list(range(1, len(world_log) + 1)),
                "projection_format": projection["format"],
            },
            "vn_projection": projection,
            "final_state": {
                "time": world.now.isoformat(),
                "story_phase": world.story_phase,
                "terminal_reason": world.terminal_reason,
                "actor_resolutions": dict(world.actor_resolutions),
                "world_version": world.version,
                "actors": {
                    actor_id: {
                        "location": actor.location,
                        "inventory": sorted(actor.inventory),
                        "sleeping": actor.sleeping,
                        "inbox": list(actor.inbox),
                        "beliefs": dict(actor.beliefs),
                        "relationships": dict(actor.relationships),
                    }
                    for actor_id, actor in sorted(world.actors.items())
                },
                "item_locations": dict(sorted(world.item_locations.items())),
                "ledger": {
                    "case": world.ledger_case,
                    "choice": world.ledger_choice,
                    "reward": world.ledger_reward,
                },
            },
        }

    def save(self, world: WorldHarness, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.snapshot(world), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
