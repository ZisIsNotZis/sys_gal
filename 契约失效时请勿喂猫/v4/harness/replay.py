"""Reconstruct objective state from a saved trajectory without agents."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from .kernel import ActorState, Event, LocationState, World, apply_world_effects
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
    elif event.kind in {"extra_arrived", "extra_removed"}:
        # E84: a conversation-scoped stranger is a real actor between its
        # arrival and its departure, so replay must rebuild its span — a
        # despawned extra's take is a real take (the item left its location),
        # and the departure is what puts it back down.
        name = str(event.actor)
        if event.kind == "extra_arrived":
            world.actors[name] = ActorState(name, str(event.payload["location"]),
                                            role="extra")
            world._cursor[name] = len(world.event_log)
        else:
            world.actors.pop(name, None)
            world._cursor.pop(name, None)
    elif event.kind == "item_dropped":
        # E84: an item an extra was carrying comes back to the
        # extra's last location instead of vanishing with it.
        item = str(event.payload["item"])
        holder = world.actors.get(str(event.actor))
        if holder is not None:
            holder.inventory.discard(item)
        world.item_locations[item] = str(event.payload["location"])
    elif event.kind == "action_completed" and event.actor:
        payload = event.payload
        # E84: mirror the kernel's completion-time guard — an event whose
        # actor is already gone (a despawned extra, two takes of one item) stands
        # as a fact and mutates nothing, instead of crashing the rebuild.
        actor = world.actors.get(event.actor)
        if actor is None:
            return
        kind = payload.get("action")
        if kind == "move":
            actor.location = str(payload["target"])
        elif kind == "take":
            item = str(payload["item"]); actor.inventory.add(item); world.item_locations.pop(item, None)
        elif kind == "drop":
            item = str(payload["item"]); actor.inventory.discard(item); world.item_locations[item] = actor.location
        elif kind == "place" and str(payload["item"]) in world.persistent_notes:
            # 票 101（E105）：放下一张字条 = 它又变成“留在这里的纸”。
            note = world.persistent_notes[str(payload["item"])]
            actor.inventory.discard(str(payload["item"]))
            note["location"] = actor.location
        elif kind == "open":
            from .kernel import _set_location_open
            _set_location_open(world, actor.location, True)
        elif kind == "close":
            from .kernel import _set_location_open
            _set_location_open(world, actor.location, False)
        elif kind == "give":
            item = str(payload["item"])
            target = world.actors[str(payload["target"])]
            note = world.persistent_notes.get(item)
            if note is not None:
                # 票 101（E105）：递字条与递物品同一条持有关系（背包），位置随之更新。
                actor.inventory.discard(item)
                target.inventory.add(item)
                note["location"] = target.location
            else:
                actor.inventory.discard(item)
                target.inventory.add(item)
    elif event.kind == "message_delivered":
        target = world.actors[str(event.payload["target"])]
        target.inbox.append({"from": event.actor, "text": str(event.payload["text"]),
                             "sent_at": event.time.isoformat()})
    elif event.kind == "note_left" and event.actor:
        # Notes remain in the room until a single enterer receives and burns
        # them; replay applies the recorded note_read events in event order.
        # Ticket 88: a persistent note is the other kind — it is rebuilt under
        # the id the event carries and never burns; the read events that follow
        # therefore do not remove it.
        payload = event.payload or {}
        location_id = str(payload.get("location")
                          or world.actors[event.actor].location)
        if payload.get("persist"):
            note_id = str(payload["note"])
            world.persistent_notes[note_id] = {
                "id": note_id, "author": event.actor, "location": location_id,
                "text": str(payload.get("text", "")),
                "left_at": event.time.isoformat()}
            sheet = str(payload.get("on") or "")
            if sheet and sheet not in world.document_defs:
                # 票 101（E105b）：这张纸被写成了这份文稿；票 113（112 §E1）：
                # 一沓纸写一张只少一张，剩 ≥1 张时纸本身还是原来那张（位置与
                # 持有关系都不变），拿走最后一张时这沓就空了。
                writer = world.actors.get(str(event.actor))
                left = int(payload.get("count_left", 0))
                if left > 0:
                    world.item_counts[sheet] = left
                else:
                    world.item_counts.pop(sheet, None)
                    for actor in world.actors.values():
                        actor.inventory.discard(sheet)
                    world.item_locations.pop(sheet, None)
                if writer is not None:
                    writer.inventory.add(note_id)
        else:
            world.locations[location_id].notes.append(
                {"author": event.actor, "text": str(payload.get("text", "")),
                 "left_at": event.time.isoformat()})
    elif event.kind == "note_read":
        location = world.locations[str(event.payload["location"])]
        for index, note in enumerate(location.notes):
            left_at = event.payload.get("left_at")
            if (note.get("author") == event.payload.get("author")
                    and note.get("text") == event.payload.get("text")
                    and (left_at is None or note.get("left_at") == left_at)):
                location.notes.pop(index)
                break
    elif event.kind == "item_trashed":
        # Ticket 88: a destroyed persistent note must not survive a replay. A
        # trashed ordinary item is not rebuilt here — that gap predates this
        # change and is out of its scope.
        item = str((event.payload or {}).get("item") or "")
        world.persistent_notes.pop(item, None)
    elif event.kind == "world_event":
        # Seeded world events may carry objective effects; replay them so the
        # reconstructed world matches the authoritative run.
        apply_world_effects(world, event.payload)
    elif event.kind == "document_annotated":
        document = str(event.payload["document"])
        world.document_defs.setdefault(document, {}).setdefault("annotations", []).append({
            "text": str(event.payload["annotation"]), "by": event.actor,
            "time": event.time.isoformat()})
