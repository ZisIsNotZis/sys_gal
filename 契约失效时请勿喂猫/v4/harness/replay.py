"""Reconstruct objective state from a saved trajectory without agents."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from .kernel import Event, LocationState, World, apply_world_effects
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
    if event.kind == "enter" and event.actor:
        # Discrete movement: the last enter defines where the actor stands
        # (also correct for interrupted/abandoned multi-hop moves).
        world.actors[event.actor].location = str(event.payload["location"])
    elif event.kind == "action_completed" and event.actor:
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
            from .kernel import _set_location_open
            _set_location_open(world, actor.location, True)
        elif kind == "close":
            from .kernel import _set_location_open
            _set_location_open(world, actor.location, False)
        elif kind == "give":
            item = str(payload["item"])
            target = world.actors[str(payload["target"])]
            actor.inventory.discard(item)
            target.inventory.add(item)
    elif event.kind == "message_delivered":
        target = world.actors[str(event.payload["target"])]
        target.inbox.append({"from": event.actor, "text": str(event.payload["text"]),
                             "sent_at": event.time.isoformat()})
    elif event.kind == "world_event":
        # Seeded world events may carry objective effects; replay them so the
        # reconstructed world matches the authoritative run.
        apply_world_effects(world, event.payload)
    elif event.kind == "document_copied":
        source = str(event.payload["document"])
        copy_id = str(event.payload["copy"])
        if event.actor:
            actor = world.actors[event.actor]
            material = sorted(item for item in world.copy_material_items if item in actor.inventory)
            if material:
                actor.inventory.remove(material[0])
        world.document_defs[copy_id] = {**world.document_defs[source], "copied_from": source}
        world.item_locations[copy_id] = str(event.payload["location"])
    elif event.kind == "document_labeled":
        document = str(event.payload["document"])
        world.document_defs.setdefault(document, {}).setdefault("labels", []).append(
            str(event.payload["label"]))
    elif event.kind == "document_annotated":
        document = str(event.payload["document"])
        world.document_defs.setdefault(document, {}).setdefault("annotations", []).append({
            "text": str(event.payload["annotation"]), "by": event.actor,
            "time": event.time.isoformat()})
