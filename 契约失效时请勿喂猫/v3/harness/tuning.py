"""Wall-time speed-tuning knobs shared by run scripts.

The world and engine stay generic; these are environment-driven experiment
knobs that let a run trade simulated-time granularity and arc length against
provider wall time. They are deliberately not part of the canonical seed, so
a production run can stay faithful while a fast probe or a short-arc demo can
override them.

- ``V3_IDLE_WAIT_SECONDS``: the longest idle wait offered to agents. Larger
  values cut the number of idle agent turns per simulated day (the dominant
  wall-time driver in past runs, ~55% of turns) at the cost of reacting more
  slowly to events. Default 3600 (one simulated hour).
- ``V3_CLOCK_STOP``: an ISO timestamp that overrides the seeded world end.
  Ending earlier reaches a reasonable climax (e.g. after
  ``storm_records_available`` or ``review_meeting``) inside a small wall
  budget instead of waiting out the full eleven-day fair arc.
- ``OPENAI_MODEL`` / ``OPENAI_MAX_CONCURRENCY``: provider-side speed (faster
  model, more parallel agents). The provider already sends ``thinking: none``.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any


def idle_wait_seconds(default: int = 3600) -> int:
    value = os.environ.get("V3_IDLE_WAIT_SECONDS", str(default))
    try:
        seconds = int(value)
    except ValueError:
        raise ValueError("V3_IDLE_WAIT_SECONDS must be an integer") from None
    if seconds <= 0:
        raise ValueError("V3_IDLE_WAIT_SECONDS must be positive")
    return seconds


def clock_stop(default: str) -> datetime:
    value = os.environ.get("V3_CLOCK_STOP", default)
    return datetime.fromisoformat(value)


def effective_clock_stop(world: Any, default: str) -> datetime:
    """Return the effective arc end, inserting a ``world_stops`` marker when
    ``V3_CLOCK_STOP`` shortens the seeded clock so the completion gate still
    has an objective stop event at the chosen endpoint."""
    if "V3_CLOCK_STOP" not in os.environ:
        return datetime.fromisoformat(default)
    stop = clock_stop(default)
    world._schedule(stop, "world_event", None,
                    {"event": "world_stops", "notice": "The observed arc ends here."},
                    None)
    return stop


def apply_idle_wait(world: Any) -> None:
    """Apply the env override to a built world (a no-op without the env var)."""
    if "V3_IDLE_WAIT_SECONDS" in os.environ:
        world.longest_wait_seconds = idle_wait_seconds()
