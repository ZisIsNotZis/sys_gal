"""Compatibility adapter: the story world lives in ``world/``, not here."""

from pathlib import Path
from .kernel import World
from .world_loader import load_world_pack


def create_world() -> World:
    return load_world_pack(Path(__file__).parents[1] / "world").build_world()


def load_story_pack():
    """Return the validated story data for callers that need non-world seed data."""
    return load_world_pack(Path(__file__).parents[1] / "world")
