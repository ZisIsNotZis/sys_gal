"""Load public identity and private starting material without cross-leaks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CharacterSeed:
    actor_id: str
    identity: str
    private_seed: str
    goals: str = ""
    metadata: dict[str, str] | None = None
    # V4-CAST §3: the fifth section (## 导演笔记) is stripped from the
    # persona prompt and carried here for the director briefing only.
    director_notes: str = ""


def load_character(path: str | Path, actor_id: str | None = None) -> CharacterSeed:
    text = Path(path).read_text(encoding="utf-8")
    marker = "## Private starting state"
    if marker in text:
        public, private = text.split(marker, 1)
        private = private.split("## ", 1)[0].strip()
    else:
        public, private = text, ""
    if not public.strip():
        raise ValueError(f"character file has no public identity: {path}")
    goals = ""
    if "## Goals and fears" in public:
        goals = public.split("## Goals and fears", 1)[1].split("## ", 1)[0].strip()
    director_notes = ""
    if "## 导演笔记" in text:
        director_notes = text.split("## 导演笔记", 1)[1].split("## ", 1)[0].strip()
    return CharacterSeed(actor_id or Path(path).stem, public.strip(), private, goals,
                         director_notes=director_notes)


def load_characters(directory: str | Path) -> dict[str, CharacterSeed]:
    result = {}
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"character directory does not exist: {directory}")
    for path in sorted(directory.glob("*.md")):
        seed = load_character(path)
        if seed.actor_id in result:
            raise ValueError(f"duplicate character id: {seed.actor_id}")
        result[seed.actor_id] = seed
    return result


def load_story_characters(world_root: str | Path) -> dict[str, CharacterSeed]:
    """Load the character directory belonging to this world pack."""
    return load_characters(Path(world_root) / "characters")
