"""Lossless-enough trajectory capture for later novel construction."""

from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .agent_state import PrivateState
from .kernel import Intention, World


class Trace:
    def __init__(self, seed_version: str, run_id: str) -> None:
        self.seed_version = seed_version
        self.run_id = run_id
        self.agent_turns: list[dict[str, Any]] = []
        self.system_turns: list[dict[str, Any]] = []
        self.gm_turns: list[dict[str, Any]] = []
        self.outcome: dict[str, Any] | None = None
        self.sessions: dict[str, dict[str, Any]] = {}

    def record_session(self, actor: str, snapshot: dict[str, Any]) -> None:
        self.sessions[actor] = deepcopy(snapshot)

    def record_agent(self, *, state: PrivateState, perception: dict[str, Any],
                     affordances: list[dict[str, Any]], intention: Intention | None,
                     result: str, error: str | None = None,
                     version_before: int | None = None, version_after: int | None = None,
                     event_ids: list[int] | None = None) -> None:
        self.agent_turns.append({
            "actor": state.actor_id, "perception": deepcopy(perception),
            "private_state": state.snapshot(), "affordances": deepcopy(affordances),
            "intention": None if intention is None else {
                "actor": intention.actor, "kind": intention.kind,
                "args": deepcopy(dict(intention.args)), "expected_version": intention.expected_version,
            }, "result": result, "error": error,
            "version_before": version_before, "version_after": version_after,
            "event_ids": list(event_ids or []),
        })

    def record_system(self, request: dict[str, Any], result: dict[str, Any]) -> None:
        self.system_turns.append({"request": deepcopy(request), "result": deepcopy(result)})

    def record_gm(self, record: dict[str, Any]) -> None:
        """Record only the actor-scoped GM request and bounded response."""
        self.gm_turns.append(deepcopy(record))

    def finish(self, *, reason: str, world: World) -> None:
        self.outcome = {"reason": reason, "time": world.now.isoformat(), "world_version": world.version}

    def fail(self, *, reason: str, world: World, error: BaseException) -> None:
        """Record an aborted run without fabricating a world action."""
        self.outcome = {"reason": reason, "time": world.now.isoformat(),
                        "world_version": world.version,
                        "error": {"type": type(error).__name__, "message": str(error),
                                  "provider_code": getattr(error, "provider_code", None),
                                  "attempts": getattr(error, "attempts", None)}}

    def verify_complete(self, world: World, *, endpoint: str, stop_event: str) -> None:
        if world.now.isoformat() != endpoint:
            raise ValueError("trajectory did not reach the requested endpoint")
        if not any(e.kind == "world_event" and e.payload.get("event") == stop_event
                   for e in world.event_log):
            raise ValueError(f"trajectory lacks required stop event: {stop_event}")
        verify_event_log(world.replayable_log())

    def snapshot(self, world: World) -> dict[str, Any]:
        return {"format": "v2-trajectory-1", "seed_version": self.seed_version,
                "run_id": self.run_id, "agent_turns": self.agent_turns,
                "system_turns": self.system_turns, "gm_turns": self.gm_turns,
                "sessions": self.sessions, "outcome": self.outcome,
                "world_events": list(world.replayable_log()),
                "replay": {"event_count": len(world.event_log), "contiguous": [e.id for e in world.event_log] == list(range(1, len(world.event_log) + 1)),
                           "world_versions_contiguous": [e.world_version for e in world.event_log] == list(range(1, len(world.event_log) + 1)),
                "first_time": world.event_log[0].time.isoformat() if world.event_log else None,
                "last_time": world.event_log[-1].time.isoformat() if world.event_log else None,
                "last_event_id": world.event_log[-1].id if world.event_log else None}}

    def save(self, world: World, path: str | Path) -> None:
        target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.snapshot(world), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_event_log(log: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> None:
    """Reject truncated, reordered, or internally inconsistent trajectories."""
    previous_time = None
    for index, event in enumerate(log, 1):
        if event.get("id") != index or event.get("world_version") != index:
            raise ValueError(f"non-contiguous event at index {index}")
        if event.get("cause") is not None and not isinstance(event["cause"], int):
            raise ValueError(f"invalid cause on event {index}")
        if previous_time is not None and event["time"] < previous_time:
            raise ValueError(f"time moved backwards at event {index}")
        previous_time = event["time"]
