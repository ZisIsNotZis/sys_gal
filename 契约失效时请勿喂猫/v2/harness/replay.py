"""Reconstruct objective state from a saved trajectory without agents."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from .kernel import Event, LocationState, World
from .trace import verify_event_log


def replay_world(initial: World, log: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> World:
    """Apply recorded objective consequences to a fresh initial world.

    This is intentionally not a second rules engine: it only replays event
    consequences already accepted by the authoritative kernel.
    """
    verify_event_log(log)
    world = deepcopy(initial)
    world.event_log.clear()
    world._queue.clear()
    world.now = initial.now
    world.version = 0
    for row in log:
        event = Event(int(row["id"]), datetime.fromisoformat(row["time"]), str(row["kind"]),
                      row.get("actor"), dict(row.get("payload", {})), row.get("cause"),
                      frozenset(row.get("visible_to", [])), int(row["world_version"]))
        _apply_consequence(world, event)
        world.event_log.append(event)
        world.now = event.time
        world.version = event.world_version
    return world


def _apply_consequence(world: World, event: Event) -> None:
    if event.kind == "action_completed" and event.actor:
        payload = event.payload
        actor = world.actors[event.actor]
        kind = payload.get("action")
        if kind == "move":
            actor.location = str(payload["target"])
        elif kind == "take":
            item = str(payload["item"]); actor.inventory.add(item); world.item_locations.pop(item, None)
        elif kind == "drop":
            item = str(payload["item"]); actor.inventory.discard(item); world.item_locations[item] = actor.location
        elif kind == "open":
            old = world.locations[actor.location]
            world.locations[actor.location] = LocationState(old.id, True, old.x, old.y, old.sound_radius, old.sound_loss)
        elif kind == "close":
            old = world.locations[actor.location]
            world.locations[actor.location] = LocationState(old.id, False, old.x, old.y, old.sound_radius, old.sound_loss)
    elif event.kind == "message_delivered":
        target = world.actors[str(event.payload["target"])]
        target.inbox.append({"from": event.actor, "text": str(event.payload["text"]),
                             "sent_at": event.time.isoformat()})
