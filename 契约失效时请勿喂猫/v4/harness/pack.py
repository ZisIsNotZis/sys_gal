"""轨迹工件的紧凑形态（ticket 114）：一行一条记录的 jsonl，再用 zstd 压紧。

一局运行的 `.json` 是冗余的：同一段事件、同一段描述在 `world_events`、
`agent_turns.perception`、`agent_turns.affordances`、`checkpoint.trace` 里各出现
一次，再叠上 `indent=2` 的空格。实测（D1 全天工件）：17 MB → zstd -19 后 0.52 MB；
23 MB 的检查点 → 0.85 MB，去掉内嵌的那份 `trace`（与当天轨迹逐字相同）→ 0.29 MB。

所以"文件太大所以不记录"是错的：**记录全部，换紧凑形态**。
规范形态 `<name>.jsonl.zst` 一行一条记录，不裁剪任何角色看到或说出的内容，
只去掉逐字重复的那一份（检查点内嵌的 trace 由同一次运行的轨迹承担）。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterator

SUFFIX = ".jsonl.zst"
BIG = ("agent_turns", "system_turns", "gm_turns", "sessions", "knowledge",
       "world_events")
# 检查点里内嵌的 trace 与同一次运行的轨迹逐字相同，pack 时不存，unpack 时从轨迹补回。
CHECKPOINT_DUPLICATE = "trace"


def zstd() -> str:
    binary = shutil.which("zstd")
    if not binary:
        raise SystemExit("需要 zstd（apt install zstd）：紧凑工件靠它把冗余压掉")
    return binary


def pack_name(source: Path) -> Path:
    return source.with_name(source.stem + SUFFIX)


def source_name(pack_path: Path) -> Path:
    return pack_path.with_name(pack_path.name.removesuffix(SUFFIX) + ".json")


def records_of(name: str, obj: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """把一件工件摊成一行一条记录。顺序即重建顺序。"""
    if obj.get("format") == "v4-checkpoint-2":
        omitted = [CHECKPOINT_DUPLICATE] if CHECKPOINT_DUPLICATE in obj else []
        yield {"type": "meta", "kind": "checkpoint", "name": name, "omitted": omitted}
        for key, value in obj.items():
            if key in omitted:
                continue
            yield {"type": "part", "key": key, "data": value}
        return
    scalars = {key: value for key, value in obj.items() if key not in BIG}
    # 旧工件没有 `knowledge` 一栏：记下哪些段落真的存在，展开时才不会凭空多出来。
    yield {"type": "meta", "kind": "trajectory", "name": name, "data": scalars,
           "sections": [key for key in BIG if key in obj]}
    for turn in obj.get("agent_turns", ()):
        yield {"type": "agent_turn", "data": turn}
    for turn in obj.get("system_turns", ()):
        yield {"type": "system_turn", "data": turn}
    for turn in obj.get("gm_turns", ()):
        yield {"type": "gm_turn", "data": turn}
    for actor, session in (obj.get("sessions") or {}).items():
        yield {"type": "session", "actor": actor, "data": session}
    for actor, rows in (obj.get("knowledge") or {}).items():
        yield {"type": "knowledge", "actor": actor, "data": rows}
    for event in obj.get("world_events", ()):
        yield {"type": "event", "data": event}


def object_of(lines: list[dict[str, Any]]) -> dict[str, Any]:
    """从记录重建工件。检查点缺的那个部件由调用方补（见 `unpack`）。"""
    meta = lines[0]
    if meta.get("kind") == "checkpoint":
        return {line["key"]: line["data"] for line in lines[1:]}
    out: dict[str, Any] = dict(meta.get("data") or {})
    turns = {"agent_turn": "agent_turns", "system_turn": "system_turns",
             "gm_turn": "gm_turns"}
    sections = meta.get("sections") or list(BIG)
    for key in BIG:
        if key in sections:
            out[key] = [] if key in turns.values() or key == "world_events" else {}
    for line in lines[1:]:
        kind = line["type"]
        if kind in turns:
            out[turns[kind]].append(line["data"])
        elif kind == "session":
            out["sessions"][line["actor"]] = line["data"]
        elif kind == "knowledge":
            out["knowledge"][line["actor"]] = line["data"]
        elif kind == "event":
            out["world_events"].append(line["data"])
    return out


def read_lines(path: Path) -> list[dict[str, Any]]:
    raw = subprocess.run([zstd(), "-d", "-q", "-c", str(path)],
                         capture_output=True, check=True).stdout
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def pack(source: Path, *, force: bool = False) -> Path | None:
    """写 `<name>.jsonl.zst`。已有且非 force 时跳过。"""
    target = pack_name(source)
    if target.is_file() and not force:
        return None
    obj = json.loads(source.read_text(encoding="utf-8"))
    body = "\n".join(json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                     for record in records_of(source.name, obj)) + "\n"
    result = subprocess.run([zstd(), "-19", "-q", "-f", "-o", str(target)],
                            input=body.encode("utf-8"), capture_output=True)
    if result.returncode != 0:
        raise SystemExit(f"zstd failed for {source}: {result.stderr.decode()[:200]}")
    return target


def unpack(pack_path: Path, out_path: Path, *, trajectory: Path | None = None) -> dict[str, Any]:
    lines = read_lines(pack_path)
    obj = object_of(lines)
    omitted = lines[0].get("omitted") or []
    if omitted:
        sibling = trajectory or source_name(pack_path)
        if CHECKPOINT_DUPLICATE in omitted:
            # 内嵌的 trace 与同一次运行的轨迹逐字相同：从轨迹补回，不重复存。
            obj[CHECKPOINT_DUPLICATE] = (json.loads(sibling.read_text(encoding="utf-8"))
                                         if sibling.is_file() else None)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return obj


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def sources(root: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in ("runs/*.json", "checkpoints/*.json"):
        found.extend(sorted(root.glob(pattern)))
    return found


def check(root: Path, *, verbose: bool = False) -> list[str]:
    """每个 `.json` 都要有对得上的紧凑工件；展开必须与原文一致，且不能过期。"""
    problems: list[str] = []
    for source in sources(root):
        target = pack_name(source)
        if not target.is_file():
            problems.append(f"未打包：{source.relative_to(root)}")
            continue
        if target.stat().st_mtime < source.stat().st_mtime:
            problems.append(f"紧凑工件过期（原文件更新过）：{target.relative_to(root)}")
        original = json.loads(source.read_text(encoding="utf-8"))
        lines = read_lines(target)
        rebuilt = object_of(lines)
        if original.get("format") == "v4-checkpoint-2":
            # 存的是除内嵌 trace 之外的每一栏；trace 由同一次运行的轨迹承担。
            for key, value in rebuilt.items():
                if digest(value) != digest(original.get(key)):
                    problems.append(f"展开不一致：{target.relative_to(root)} 的 {key}")
                    break
            missing = set(original) - set(rebuilt) - {CHECKPOINT_DUPLICATE}
            if missing:
                problems.append(f"漏存：{target.relative_to(root)} 缺 {sorted(missing)}")
        elif digest(rebuilt) != digest(original):
            problems.append(f"展开不一致：{target.relative_to(root)}")
    for pack_path in (sorted(root.glob("runs/*" + SUFFIX))
                      + sorted(root.glob("checkpoints/*" + SUFFIX))):
        if not source_name(pack_path).is_file() and verbose:
            print(f"note: {pack_path.relative_to(root)} 只有紧凑形态（原始文件不在了）")
    return problems
