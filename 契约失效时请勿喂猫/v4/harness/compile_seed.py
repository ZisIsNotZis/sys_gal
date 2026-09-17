"""Compile the authored seed into the initial checkpoint (ticket 25).

One state-loading path: manifest + characters are the human authoring
surface; this module compiles them into a ``v4-checkpoint-2`` artifact that
the engine loads. The seed's pre-run ``history:`` section becomes the world's
history log — REAL past events that flashback replays.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def git_hash(root: str | Path | None = None) -> str:
    """Best-effort commit hash of the code that produced a checkpoint."""
    try:
        directory = Path(root) if root else Path(__file__).parents[1]
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=directory, capture_output=True, text=True,
                             timeout=10, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def build_initial_checkpoint(engine: Any, pack: Any, run_id: str,
                             root: str | Path | None = None) -> dict[str, Any]:
    """Snapshot the freshly-compiled world + engine state as the run's initial
    checkpoint (``v4-checkpoint-2``): world, history log, per-actor KB,
    sessions (system prompt at messages[0]), prompts + tools snapshots, meta.
    The engine then restores FROM this artifact — one state-loading path."""
    engine._init_kb(engine.world.now)
    checkpoint = engine.trace.checkpoint_snapshot(engine.world, engine)
    checkpoint["format"] = "v4-checkpoint-2"
    checkpoint["meta"] = {
        "git_hash": git_hash(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "compiled_from": "manifest",
        "history_count": len(engine.world.history_log),
    }
    return checkpoint
