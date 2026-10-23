"""P4/P5 的检查点：把一个世界与到此为止的账本冻结成一个文件，再从它续跑。

检查点存的是**状态**，不是剧本位置：世界（实体、状态、包含、时钟、排程、心智、旗标）
加事件账本的前缀。续跑 = 从检查点还原世界与账本，再让同一份脚本/演员往下走；
续跑后的账本仍是同一本账（id 连续，前缀逐字节相同），所以"整本账从种子重放"
与"检查点续跑"必须是同一个世界——这就是续跑因果连续的定义。

文件格式 `v5-checkpoint-1`（UTF-8 JSON，一个对象）：

    {
      "format": "v5-checkpoint-1",
      "label": "checkpoint",            # 人读的断点名字，不参与还原
      "clock": 1361,                    # 人读的时间；权威值是 world.clock
      "event_count": 24,                # 账本里已有几条 = 最后一个事件 id
      "events": [ ...Event.to_json()...],   # 账本前缀，id 必须 1..event_count 连续
      "digest": "<sha256>",             # world.digest()；读回后必须一致
      "world": {
        "clock": 1361, "date": "…", "seq": 57,
        "entities": [{id, kind, name, prose, identity, aliases}],
        "state":  {eid: {键: 值}},
        "parent": {eid: 父 eid},
        "schedule": [[when, seq, effect]],
        "memory": {eid: [[at, 文本]]},
        "knowledge": {eid: [eid]},
        "beliefs": {eid: [[about, says]]},
        "hand_readers": {eid: {字形: eid}},
        "flags": {键: 值}
      }
    }

`seq` 必须存：它决定同一时刻两条排程的先后，而 `World.digest()` 看不见它。
`world.entities` 也必须按插入顺序存：同一场地里“先投递给谁”由实体顺序决定，
顺序变了世界仍是同一个 digest，账本却不是同一本字节（这是续跑门抓到的真事）。
引擎没有“版本号”字段：世界的一致性由逐事件的 `digest_after` 负责，事件的身份由
ordinal（`EventLog.next_id()` = 已有条数 + 1）负责；检查点断言用这两样。

命名：一个检查点写进 `<目录>/<run_id>.<label>.checkpoint-<两位序号>.json`。
`run_id` 缺省是 `checkpoint-<UTC 时间>-<pid>-<纳秒>`，序号从 01 起取该目录下第一个
空位，写入用 `os.link`（目标已存在即失败），所以**绝不覆盖任何既有工件**；同一个
`run_id` 的多次检查点因此是一条序列，而不是互相覆盖。写盘是"临时文件 → 硬链接到
正式名 → 删临时文件"，中途被杀不会留下半个检查点。
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import Entity, World
from .events import EventLog

FORMAT = "v5-checkpoint-1"

#: 读回时必须齐全的顶层字段。
REQUIRED = ("format", "label", "clock", "event_count", "events", "digest", "world")

#: 世界快照必须齐全的字段，与世界对象的可变字段一一对应。
WORLD_FIELDS = ("clock", "date", "seq", "entities", "state", "parent", "schedule",
                "memory", "knowledge", "beliefs", "hand_readers", "flags")


class CheckpointError(ValueError):
    pass


# ---- 世界与账本 ⇄ 普通数据

def snapshot_world(world: World) -> dict[str, Any]:
    """世界 → 可 JSON 的字典。字段与世界对象的可变字段一一对应，不派生新值。"""
    return {
        "clock": world.clock,
        "date": world.date,
        "seq": world.seq,
        # 顺序即插入顺序，不能排序：同一场地里"谁先被投递到"由它决定，
        # 而 digest 看不见这个差别（还原后世界同一个 digest，账本却不同字节）。
        "entities": [
            {"id": ent.id, "kind": ent.kind, "name": ent.name, "prose": ent.prose,
             "identity": ent.identity, "aliases": list(ent.aliases)}
            for _eid, ent in world.entities.items()
        ],
        "state": {eid: dict(row) for eid, row in sorted(world.state.items())},
        "parent": dict(sorted(world.parent.items())),
        # 顺序即入账顺序，不能排序：同刻排程的先后由 seq 决定，但列表本身要原样回来。
        "schedule": [[when, seq, dict(effect)] for when, seq, effect in world.schedule],
        "memory": {eid: [list(row) for row in rows]
                   for eid, rows in sorted(world.memory.items())},
        "knowledge": {eid: list(items) for eid, items in sorted(world.knowledge.items())},
        "beliefs": {eid: [list(row) for row in rows]
                    for eid, rows in sorted(world.beliefs.items())},
        "hand_readers": {eid: dict(sorted(readers.items()))
                         for eid, readers in sorted(world.hand_readers.items())},
        "flags": dict(sorted(world.flags.items())),
    }


def restore_world(snap: dict[str, Any]) -> World:
    """字典 → 世界。不经过种子：检查点自带全部可变状态。"""
    missing = [key for key in WORLD_FIELDS if key not in snap]
    if missing:
        raise CheckpointError(f"检查点缺少世界字段：{missing}")
    world = World(start=int(snap["clock"]), date=str(snap["date"]))
    for row in snap["entities"]:
        world.add(Entity(id=row["id"], kind=row["kind"], name=row["name"],
                         prose=row.get("prose", ""),
                         identity=row.get("identity", ""),
                         aliases=tuple(row.get("aliases", ()))))
    # add() 会把状态与心智置空，实体建好之后再整体覆盖，避免两处默认值打架。
    world.state = {eid: dict(row) for eid, row in snap["state"].items()}
    world.parent = dict(snap["parent"])
    world.clock = int(snap["clock"])
    world.seq = int(snap["seq"])
    world.schedule = [[int(when), int(seq), dict(effect)]
                      for when, seq, effect in snap["schedule"]]
    world.memory = {eid: [list(row) for row in rows]
                    for eid, rows in snap["memory"].items()}
    world.knowledge = {eid: list(items) for eid, items in snap["knowledge"].items()}
    world.beliefs = {eid: [list(row) for row in rows]
                     for eid, rows in snap["beliefs"].items()}
    world.hand_readers = {eid: dict(readers) for eid, readers in snap["hand_readers"].items()}
    world.flags = dict(snap["flags"])
    return world


def snapshot(world: World, log: EventLog, *, label: str = "") -> dict[str, Any]:
    """世界 + 账本前缀 → 一个检查点载荷。`digest` 是读回时的自校验。"""
    return {
        "format": FORMAT,
        "label": label,
        "clock": world.clock,
        "event_count": len(log),
        "events": log.to_json(),
        "digest": world.digest(),
        "world": snapshot_world(world),
    }


# ---- 读写

def validate(payload: Any) -> dict[str, Any]:
    """格式、连续性与自校验。任何一项不合就拒绝，不做猜测。"""
    if not isinstance(payload, dict):
        raise CheckpointError("检查点不是一个 JSON 对象")
    missing = [key for key in REQUIRED if key not in payload]
    if missing:
        raise CheckpointError(f"检查点缺少字段：{missing}")
    if payload["format"] != FORMAT:
        raise CheckpointError(f"检查点格式不认识：{payload['format']!r}（要 {FORMAT!r}）")
    rows = payload["events"]
    if not isinstance(rows, list):
        raise CheckpointError("events 不是一个列表")
    if int(payload["event_count"]) != len(rows):
        raise CheckpointError(
            f"event_count={payload['event_count']} 与账本条数 {len(rows)} 不一致")
    ids = [row.get("id") for row in rows]
    if ids != list(range(1, len(rows) + 1)):
        raise CheckpointError(f"账本 id 不连续：{ids[:5]}…（要求 1..{len(rows)}）")
    return payload


def restore(payload: dict[str, Any]) -> tuple[World, EventLog]:
    """检查点 → （世界，账本）。账本的下一个 id 自动接在旧 id 之后。"""
    validate(payload)
    world = restore_world(payload["world"])
    if world.digest() != payload["digest"]:
        raise CheckpointError("还原后的世界与检查点记录的 digest 不一致")
    return world, EventLog.from_json(payload["events"])


def new_run_id(prefix: str = "checkpoint") -> str:
    """抗碰撞、可做文件名的运行标识（与 v4 的形状一致：时间 + pid + 纳秒）。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{prefix}-{stamp}-{os.getpid()}-{time.time_ns() % 1_000_000_000:09d}"


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in text) or "checkpoint"


def _write_new(target: Path, blob: str) -> Path:
    """写入一个**尚不存在**的目标：临时文件 → os.link（已存在则失败）→ 删临时文件。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(blob)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)      # 目标已存在 → FileExistsError，绝不覆盖
    finally:
        temporary.unlink(missing_ok=True)
    return target


def save(path: str | Path, payload: dict[str, Any]) -> Path:
    """把载荷写到 `path`；`path` 已存在就失败（既有工件绝不覆盖）。"""
    target = Path(path)
    validate(payload)
    blob = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    return _write_new(target, blob)


def save_new(directory: str | Path, world: World, log: EventLog, *,
             label: str = "checkpoint", run_id: str | None = None) -> Path:
    """取该目录下第一个空位写一个检查点，返回实际路径（同一 run_id 的序列号递增）。"""
    base = Path(directory)
    name = run_id or new_run_id()
    payload = snapshot(world, log, label=label)
    for ordinal in range(1, 10000):
        target = base / f"{name}.{_slug(label)}.checkpoint-{ordinal:02d}.json"
        try:
            return save(target, payload)
        except FileExistsError:
            continue
    raise CheckpointError(f"{base} 下 {name} 的检查点序号已经用尽")


def load(path: str | Path) -> dict[str, Any]:
    """读一个检查点并校验；失败一律 CheckpointError，不返回半个状态。"""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise CheckpointError(f"读不到检查点：{exc}") from exc
    except json.JSONDecodeError as exc:
        raise CheckpointError(f"检查点不是合法 JSON：{exc}") from exc
    return validate(payload)


def last_event_id(payload: dict[str, Any]) -> int:
    return int(payload["event_count"])
