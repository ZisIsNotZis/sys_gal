"""Load a complete, story-owned world pack into neutral engine state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping
import math

import yaml

from .kernel import ActorState, LocationState, World


class DescriptionCatalog(Mapping[str, str]):
    """A read-only Markdown index; file contents are read only on lookup."""

    def __init__(self, directory: Path) -> None:
        self._paths = {path.stem: path for path in sorted(directory.glob("*.md"))} \
            if directory.is_dir() else {}

    def __getitem__(self, key: str) -> str:
        try:
            return self._paths[key].read_text(encoding="utf-8").strip()
        except KeyError:
            raise KeyError(key) from None

    def __iter__(self) -> Iterator[str]:
        return iter(self._paths)

    def __len__(self) -> int:
        return len(self._paths)


class DescriptionStore(Mapping[str, str]):
    """A merged actor-visible description store with lazy Markdown reads."""

    def __init__(self, catalogs: Mapping[str, DescriptionCatalog]) -> None:
        self._catalogs = dict(catalogs)
        self._owners = {entity_id: catalog for catalog in self._catalogs.values()
                        for entity_id in catalog}

    def __getitem__(self, key: str) -> str:
        try:
            return self._owners[key][key]
        except KeyError:
            raise KeyError(key) from None

    def __iter__(self) -> Iterator[str]:
        return iter(self._owners)

    def __len__(self) -> int:
        return len(self._owners)


@dataclass(frozen=True)
class WorldPack:
    root: Path
    manifest: dict[str, Any]
    descriptions: dict[str, DescriptionCatalog]
    locations: tuple[dict[str, Any], ...]
    actors: tuple[dict[str, Any], ...]
    items: tuple[dict[str, Any], ...]
    documents: tuple[dict[str, Any], ...]
    routes: tuple[dict[str, Any], ...]
    barriers: tuple[dict[str, Any], ...]
    scheduled: tuple[dict[str, Any], ...]
    system: dict[str, Any]

    def build_world(self) -> World:
        locations = [LocationState(
            str(row["id"]), bool(row.get("open", True)), float(row.get("x", 0)),
            float(row.get("y", 0)), float(row.get("sound_radius", 0)),
            float(row.get("sound_loss", 0)),
            {str(verb): dict(spec or {}) for verb, spec in row.get("physical_capabilities", {}).items()},
            bool(row.get("controllable", False)),
            tuple(dict(x) for x in row.get("extras", ())))
            for row in self.locations]
        actors = [ActorState(str(row["id"]), str(row["location"]),
                             set(row.get("inventory", ())),
                             known_contacts=set(row.get("known_contacts", ())),
                             role=str(row.get("role", "mc")))
                  for row in self.actors]
        item_locations = {str(row["id"]): str(row["location"])
                          for row in self.items if row.get("location") is not None}
        inventory_items = {str(item) for row in self.actors for item in row.get("inventory", ())}
        item_locations = {item: location for item, location in item_locations.items()
                          if item not in inventory_items}
        document_defs = {str(row["id"]): {
            "title": str(row.get("title", row["id"])),
            "content": str(row.get("content", "")),
            "reading_seconds": int(row.get("reading_seconds", 30)),
            **({"labels": list(row["labels"])} if "labels" in row else {}),
        } for row in self.documents}
        for row in self.documents:
            if row.get("location") is not None and str(row["id"]) not in inventory_items:
                item_locations[str(row["id"])] = str(row["location"])
        routes = {(str(row["from"]), str(row["to"])): int(row["duration_seconds"])
                  for row in self.routes}
        barriers = {(str(row["from"]), str(row["to"])): float(row["loss"])
                    for row in self.barriers}
        world = World(
            start=datetime.fromisoformat(str(self.manifest["clock"]["start"])),
            actors=actors, locations=locations, item_locations=item_locations,
            routes=routes, sound_barriers=barriers, scheduled=self.scheduled,
            document_defs=document_defs,
            copy_material_items=set(self.manifest.get("copy_material_items", ())),
            entity_descriptions=DescriptionStore({name: self.descriptions[name] for name in
                                                   ("locations", "items", "documents")}),
            entity_access={str(row["id"]): row.get("known_to", ()) for row in self.items + self.documents
                           if row.get("known_to")},
            public_knowledge=self.manifest.get("public_knowledge", {}),
            private_knowledge=self.manifest.get("private_knowledge", {}),
            longest_wait_seconds=int(self.manifest.get("engine", {}).get("idle_wait_seconds", 3600)),
        )
        engine_cfg = self.manifest.get("engine", {})
        world.state_refresh_rounds = int(engine_cfg.get("state_refresh_rounds", 20))
        world.description_refresh_rounds = int(engine_cfg.get("description_refresh_rounds", 99999))
        return world


def load_world_pack(root: str | Path) -> WorldPack:
    root = Path(root)
    manifest_path = root / "manifest.yml"
    if not manifest_path.is_file():
        raise ValueError(f"world pack has no manifest: {manifest_path}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("world manifest must declare schema_version: 1")
    for required in ("clock", "locations", "actors", "items", "documents", "routes", "barriers", "scheduled"):
        if required not in manifest or not isinstance(manifest[required], list if required not in {"clock"} else dict):
            raise ValueError(f"manifest field {required!r} has the wrong shape")
    descriptions = _load_descriptions(root)
    fields = {name: tuple(dict(row) for row in manifest[name]) for name in
              ("locations", "actors", "items", "documents", "routes", "barriers", "scheduled")}
    _validate(fields, manifest)
    _validate_descriptions(fields, descriptions)
    return WorldPack(root, manifest, descriptions, **fields, system=dict(manifest.get("system", {})))


def _load_descriptions(root: Path) -> dict[str, DescriptionCatalog]:
    result: dict[str, DescriptionCatalog] = {}
    for category in ("locations", "items", "documents", "organizations", "characters", "institutions"):
        directory = root / category
        result[category] = DescriptionCatalog(directory)
    return result


def _validate(fields: dict[str, tuple[dict[str, Any], ...]], manifest: dict[str, Any]) -> None:
    def unique(rows: tuple[dict[str, Any], ...], field: str, category: str) -> set[str]:
        ids = [str(row.get(field, "")) for row in rows]
        if any(not value for value in ids) or len(set(ids)) != len(ids):
            raise ValueError(f"{category} must contain unique non-empty {field}")
        return set(ids)

    locations = unique(fields["locations"], "id", "locations")
    actors = unique(fields["actors"], "id", "actors")
    items = unique(fields["items"], "id", "items")
    documents = unique(fields["documents"], "id", "documents")
    if not documents.isdisjoint(locations):
        raise ValueError("document ids must not shadow locations")
    if not isinstance(manifest["clock"].get("start"), str) or not isinstance(manifest["clock"].get("stop"), str):
        raise ValueError("clock.start and clock.stop must be ISO timestamps")
    start = datetime.fromisoformat(manifest["clock"]["start"])
    stop = datetime.fromisoformat(manifest["clock"]["stop"])
    if stop < start:
        raise ValueError("clock.stop must not precede clock.start")
    for row in fields["locations"]:
        for key in ("x", "y", "sound_radius", "sound_loss"):
            value = float(row.get(key, 0))
            if not math.isfinite(value) or value < 0 and key != "x" and key != "y":
                raise ValueError(f"location {row['id']} has invalid {key}")
        capabilities = row.get("physical_capabilities", {})
        if not isinstance(capabilities, dict):
            raise ValueError("physical_capabilities must be a mapping")
        for verb, spec in capabilities.items():
            if not isinstance(verb, str) or not verb or not isinstance(spec, dict):
                raise ValueError("physical capability must have a verb and mapping")
            if "parameters" in spec and not isinstance(spec["parameters"], dict):
                raise ValueError("physical capability parameters must be a mapping")
    for row in fields["actors"]:
        if row.get("location") not in locations:
            raise ValueError(f"actor {row['id']} has unknown location")
        if "known_contacts" in row and not isinstance(row["known_contacts"], list):
            raise ValueError("known_contacts must be a list")
        if any(contact not in actors or contact == row["id"]
               for contact in row.get("known_contacts", ())):
            raise ValueError(f"actor {row['id']} has an invalid known contact")
        for item in row.get("inventory", ()):
            if item not in items and item not in documents:
                raise ValueError(f"actor {row['id']} has unknown inventory item {item}")
    for row in fields["items"] + fields["documents"]:
        if row.get("location") is not None and row["location"] not in locations:
            raise ValueError(f"entity {row['id']} has unknown location")
        if "known_to" in row and not isinstance(row["known_to"], list):
            raise ValueError("known_to must be a list")
        if any(actor not in actors for actor in row.get("known_to", ())):
            raise ValueError(f"entity {row['id']} has unknown actor in known_to")
    for field_name in ("public_knowledge", "private_knowledge"):
        value = manifest.get(field_name, {})
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a mapping")
    for entity, owners in manifest.get("private_knowledge", {}).items():
        if not isinstance(owners, dict) or any(actor not in actors for actor in owners):
            raise ValueError(f"private knowledge {entity} has invalid actor")
    for row in fields["routes"]:
        if row.get("from") not in locations or row.get("to") not in locations:
            raise ValueError("route references an unknown location")
        if not isinstance(row.get("duration_seconds"), int) or row["duration_seconds"] <= 0:
            raise ValueError("route duration must be a positive integer")
    for row in fields["barriers"]:
        if row.get("from") not in locations or row.get("to") not in locations:
            raise ValueError("barrier references an unknown location")
        if float(row.get("loss", -1)) < 0:
            raise ValueError("barrier loss must be non-negative")
    route_keys = [(row.get("from"), row.get("to")) for row in fields["routes"]]
    barrier_keys = [(row.get("from"), row.get("to")) for row in fields["barriers"]]
    if len(route_keys) != len(set(route_keys)):
        raise ValueError("routes must not contain duplicate endpoints")
    if len(barrier_keys) != len(set(barrier_keys)):
        raise ValueError("barriers must not contain duplicate endpoints")
    for row in fields["scheduled"]:
        when = datetime.fromisoformat(str(row["time"]))
        if when < start or when > stop:
            raise ValueError("scheduled event is outside the world clock")
        target = row.get("target")
        targets = target if isinstance(target, list) else [target] if target is not None else []
        for entry in targets:
            if str(entry) not in actors:
                raise ValueError("scheduled event references an unknown actor")
        for effect in row.get("effects", ()):
            if not isinstance(effect, dict):
                raise ValueError("scheduled effects must be mappings")
            op = str(effect.get("op", ""))
            if op in {"open_location", "close_location"}:
                if str(effect.get("id")) not in locations:
                    raise ValueError(f"scheduled effect {op} references an unknown location")
            elif op in {"add_item", "add_document", "move_item", "remove_item"}:
                entity = str(effect.get("id"))
                if entity not in (items | documents):
                    raise ValueError(f"scheduled effect {op} references an unknown item or document")
                if op == "add_document" and entity not in documents:
                    raise ValueError(f"scheduled effect add_document references a non-document: {entity}")
                if op in {"add_item", "add_document", "move_item"}:
                    if str(effect.get("location")) not in locations:
                        raise ValueError(f"scheduled effect {op} references an unknown location")
            else:
                raise ValueError(f"scheduled effect has unknown op: {op or '<missing>'}")
    defined = items | documents
    for item in manifest.get("copy_material_items", ()):
        if item not in defined:
            raise ValueError(f"unknown copy material item {item}")
    if actors & items or actors & documents or items & documents:
        raise ValueError("actor, item, and document ids must be disjoint")


def _validate_descriptions(fields: dict[str, tuple[dict[str, Any], ...]],
                           descriptions: dict[str, DescriptionCatalog]) -> None:
    """Require a lazy Markdown description for every static visible entity."""
    required = {
        "locations": {str(row["id"]) for row in fields["locations"]},
        "items": {str(row["id"]) for row in fields["items"]},
        "documents": {str(row["id"]) for row in fields["documents"]},
    }
    for category, entity_ids in required.items():
        missing = sorted(entity_ids - set(descriptions[category]))
        if missing:
            raise ValueError(f"{category} missing Markdown descriptions: {', '.join(missing)}")


def world_primer(pack: WorldPack) -> str:
    """世界常识段（V4-DESIGN 首验日反馈 #4）：从世界包自动生成的中文常识，
    进入每个角色的 system prompt。静态事实（地点/连通/时间规矩/分寸），
    不含任何会变化的状态。"""
    lines: list[str] = ["【这个世界】"]
    for row in pack.locations:
        place = str(row["id"])
        catalog = pack.descriptions["locations"].get(place, "")
        first = next((ln.strip() for ln in catalog.splitlines()
                      if ln.strip() and not ln.strip().startswith("#")), "")
        lines.append(f"- {place}：{first}")
    lines.append("【走路】")
    seen_pairs: set[frozenset[str]] = set()
    for row in pack.routes:
        pair = frozenset((str(row["from"]), str(row["to"])))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        minutes = int(row["duration_seconds"]) // 60
        lines.append(f"- {row['from']} ↔ {row['to']}：步行约 {minutes} 分钟")
    lines.append("【时间的规矩】")
    lines.append("- 一条消息从发出到送到要 5 分钟；说话当场就能听见，所以当面说话最省时间。")
    lines.append("- 时间是你唯一的花费：一次等待就是真的一段人生，把它花在值得的人和事上。")
    lines.append("【分寸】")
    lines.append("- 陌生人凑近耳语会显得可疑；耳语（whisper）只对亲近的人用。")
    lines.append("- 初到一处你会看清四周；之后世界只把变化告诉你。想重新细看，可以 observe。")
    lines.append("- 店里、路上总有别人。想打听什么，可以用 ask_stranger 随手问一个在场的人；勤快多问，偶尔会遇上恰好知情的人。")
    lines.append("- 心声（inner）只属于你，谁也听不见。")
    return "\n".join(lines)
