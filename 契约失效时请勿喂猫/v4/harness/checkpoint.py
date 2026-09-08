"""Validated, atomic JSON checkpoint file access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class CheckpointError(ValueError):
    pass


def save_checkpoint(path: str | Path, snapshot: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def load_checkpoint(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("format") != "v3-checkpoint-1":
            raise CheckpointError("unsupported checkpoint format")
        for key in ("world", "runner", "states", "sessions"):
            if key not in value:
                raise CheckpointError(f"checkpoint missing {key}")
        return value
    except CheckpointError:
        raise
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise CheckpointError(f"invalid checkpoint: {exc}") from exc
