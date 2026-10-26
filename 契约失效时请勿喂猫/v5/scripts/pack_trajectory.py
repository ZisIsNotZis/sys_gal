#!/usr/bin/env python3
"""轨迹工件：把一次运行压成一份紧凑工件，并核对（v4 ticket 114 → v5 M5）。

一次运行在 `stories/<story>/runs/` 留下四件原始材料：

| 路 | 名字 | 回答什么 |
| --- | --- | --- |
| 脚本局 | `<v>.md` / `<v>.context.md` / `<v>.events.json` / `<v>.json` | 发生了什么、**他当时知道什么**、事件账、摘要 |
| 模型局 | `agent-*/transcript.md` / `context.md` / `events.jsonl` / `run.json` | 同上 |

它们是证据，不是缓存：报告与票据里的每条读数都指回这里。四件里的一份（逐回合的
`context.md`）回答"他知道什么才做了那件事"——少了它，这一局就不是证据。

一件工件的规范形态是 `runs/<story>-<路>.jsonl.zst`（一行一条记录 + `zstd -19`），
进 git；原始四件留在本地，由紧凑形态展开即可逐字节重建。打包**不裁剪任何内容**：
压缩靠的是同一段事实在视图、事件账、摘要里各写一遍以及 `indent` 的空格，不是删。
规则与理由见 `runs/README.md`。

用法（在 `v5/` 目录下）：

    python3 scripts/pack_trajectory.py pack                 # 把未打包 / 变过的工件打包
    python3 scripts/pack_trajectory.py check                # 核对（预跑门的一环）
    python3 scripts/pack_trajectory.py unpack runs/<story>-<路>.jsonl.zst [<out_dir>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORIES = ROOT / "stories"
RUNS = ROOT / "runs"
SUFFIX = ".jsonl.zst"
FORMAT = "v5-run-pack-1"


def zstd() -> str:
    binary = shutil.which("zstd")
    if not binary:
        raise SystemExit("需要 zstd（apt install zstd）：紧凑工件靠它把冗余压掉")
    return binary


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def role_of(name: str) -> str:
    """四件原始材料各自的角色（按名字判，不按目录判：两种局共用同一份判据）。"""
    if name == "context.md" or name.endswith(".context.md"):
        return "context"
    if name == "events.jsonl" or name.endswith(".events.json"):
        return "events"
    if name == "run.json" or name.endswith(".json"):
        return "run"
    return "transcript"


@dataclass(frozen=True)
class Unit:
    """一次运行的全部原始材料：故事 + 路 + 它们所在的目录。"""

    story: str
    name: str
    home: Path
    files: tuple[Path, ...]
    where: str  # 目录相对 v5 根（写进工件，展开时据此回家）

    @property
    def tag(self) -> str:
        return f"{self.story}/{self.name}"

    def has_context(self) -> bool:
        return any(role_of(path.name) == "context" for path in self.files)


def units(stories_root: Path = STORIES) -> dict[tuple[str, str], Unit]:
    """所有故事的所有路。脚本局按名字前缀分组（`a.md`/`a.json`/…），模型局即一个目录。"""
    found: dict[tuple[str, str], Unit] = {}
    if not stories_root.is_dir():
        return found

    def where(path: Path) -> str:
        try:
            return path.relative_to(stories_root.parent).as_posix()
        except ValueError:
            return path.as_posix()

    for story_dir in sorted(path for path in stories_root.iterdir() if path.is_dir()):
        runs = story_dir / "runs"
        if not runs.is_dir():
            continue
        bundles: dict[str, list[Path]] = {}
        for entry in sorted(runs.iterdir()):
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            if entry.is_dir():
                files = tuple(sorted(f for f in entry.iterdir()
                                     if f.is_file() and not f.name.startswith(".")))
                if files:
                    found[(story_dir.name, entry.name)] = Unit(story_dir.name, entry.name, entry,
                                                              files, where(entry))
                continue
            bundles.setdefault(entry.name.split(".")[0], []).append(entry)
        for base, files in bundles.items():
            found[(story_dir.name, base)] = Unit(story_dir.name, base, runs,
                                                 tuple(sorted(files)), where(runs))
    return found


def pack_path(story: str, unit: str, packs_root: Path = RUNS) -> Path:
    return packs_root / f"{story}-{unit}{SUFFIX}"


def body_of(unit: Unit) -> bytes:
    """一行一条记录：先一条 meta（这次运行有哪四件、各多少字节、摘要），再逐件全文。"""
    members = []
    texts: list[tuple[str, str]] = []
    for path in unit.files:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise SystemExit(f"{path} 不是 UTF-8 文本，紧凑工件只收文本工件")
        members.append({"name": path.name, "role": role_of(path.name),
                        "bytes": len(raw), "sha256": digest(raw)})
        texts.append((path.name, text))
    records = [{"type": "pack", "format": FORMAT, "story": unit.story, "unit": unit.name,
                "dir": unit.where, "files": members}]
    records += [{"type": "file", "name": name, "text": text} for name, text in texts]
    return ("\n".join(json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                      for record in records) + "\n").encode("utf-8")


def decompress(pack: Path) -> bytes:
    return subprocess.run([zstd(), "-d", "-q", "-c", str(pack)],
                          capture_output=True, check=True).stdout


def read_records(pack: Path) -> list[dict]:
    raw = decompress(pack).decode("utf-8")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def unpacked(pack: Path) -> tuple[dict, dict[str, bytes]]:
    """读出 meta 与逐件全文（展开出来的字节就是要写回磁盘的字节）。"""
    records = read_records(pack)
    meta = records[0]
    files = {record["name"]: record["text"].encode("utf-8")
             for record in records[1:] if record.get("type") == "file"}
    return meta, files


def pack_problems(pack: Path) -> list[str]:
    """只核对工件自身：记录完整、逐件摘要对得上、里面有一份 context。"""
    try:
        meta, files = unpacked(pack)
    except (subprocess.CalledProcessError, ValueError, KeyError, IndexError) as error:
        return [f"读不出（{type(error).__name__}）"]
    if meta.get("format") != FORMAT:
        return [f"格式不是 {FORMAT}：{meta.get('format')!r}"]
    problems: list[str] = []
    members = {entry["name"]: entry for entry in meta.get("files") or []}
    for name, entry in sorted(members.items()):
        if name not in files:
            problems.append(f"缺件：{name}")
        elif digest(files[name]) != entry["sha256"]:
            problems.append(f"记录与全文不一致：{name}")
    for name in sorted(set(files) - set(members)):
        problems.append(f"多出记录：{name}")
    if not any(role_of(name) == "context" for name in members):
        problems.append("不是证据（包里没有 context.md）")
    return problems


def pack_unit(unit: Unit, *, force: bool = False,
              packs_root: Path = RUNS) -> tuple[Path, int, int] | None:
    """写 `runs/<story>-<路>.jsonl.zst`；对得上且不过期时不写，返回 None。"""
    target = pack_path(unit.story, unit.name, packs_root)
    body = body_of(unit)
    if not force and target.is_file():
        stale = any(target.stat().st_mtime < path.stat().st_mtime for path in unit.files)
        try:
            intact = decompress(target) == body
        except (subprocess.CalledProcessError, OSError):
            intact = False
        if not stale and intact:
            return None
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([zstd(), "-19", "-q", "-f", "-o", str(target)],
                            input=body, capture_output=True)
    if result.returncode != 0:
        raise SystemExit(f"zstd failed for {unit.tag}：{result.stderr.decode()[:200]}")
    return target, len(body), sum(path.stat().st_size for path in unit.files)


def compare(tag: str, unit: Unit, pack: Path) -> list[str]:
    """原始四件与紧凑工件逐件比：件名要对得上，字节要一样。"""
    problems: list[str] = []
    try:
        meta, restored = unpacked(pack)
    except (subprocess.CalledProcessError, ValueError, KeyError, IndexError):
        return [f"读不出：{tag} 的 {pack.name}"]
    stored = {entry["name"] for entry in meta.get("files") or []}
    present = {path.name for path in unit.files}
    gone = sorted(stored - present)
    extra = sorted(present - stored)
    if gone:
        why = "——没有 context.md 的一局不是证据" if any(role_of(n) == "context" for n in gone) else ""
        problems.append(f"原始工件缺件：{tag} 少了 {', '.join(gone)}（工件里存着，本地不在了）{why}")
    if extra:
        problems.append(f"未打包：{tag} 的 {', '.join(extra)} 不在工件里")
    for path in sorted(unit.files, key=lambda p: p.name):
        if path.name in restored and digest(path.read_bytes()) != digest(restored[path.name]):
            problems.append(f"展开不一致：{tag} 的 {path.name}")
    return problems


def check(stories_root: Path = STORIES, packs_root: Path = RUNS, *,
          verbose: bool = False) -> list[str]:
    """三种坏各自点名：未打包、工件过期、展开与原文不一致（另加"缺 context"）。"""
    problems: list[str] = []
    found = units(stories_root)
    packs = sorted(packs_root.glob(f"*{SUFFIX}")) if packs_root.is_dir() else []
    covered: set[str] = set()
    for (story, name), unit in sorted(found.items()):
        covered.add(f"{story}-{name}")
        if not unit.has_context():
            problems.append(f"不是证据：{unit.tag} 没有 context.md（回答不了他知道什么才做了那件事）")
        target = pack_path(story, name, packs_root)
        if not target.is_file():
            problems.append(f"未打包：{unit.tag}（{len(unit.files)} 件原始工件只在本地）")
            continue
        newer = [path.name for path in unit.files if target.stat().st_mtime < path.stat().st_mtime]
        if newer:
            problems.append(f"紧凑工件过期：{unit.tag} 的 {target.name}"
                            f"（原始文件更新过：{', '.join(sorted(newer))}）")
        problems += compare(unit.tag, unit, target)
    for target in packs:
        if target.name.removesuffix(SUFFIX) in covered:
            continue
        own = pack_problems(target)
        problems += [f"{problem}：{target.name}（原始文件不在本地，只核对工件自身）"
                     for problem in own]
        if not own and verbose:
            print(f"note: {target.name} 只有紧凑形态（原始文件不在了），工件自身一致")
    return problems


def unpack(pack: Path, out_dir: Path | None = None, *, root: Path = ROOT) -> tuple[Path, int]:
    """把工件展开成可读的原始四件，并自校验（逐件摘要）。"""
    problems = pack_problems(pack)
    if problems:
        raise SystemExit("；".join(f"{problem}：{pack.name}" for problem in problems))
    meta, files = unpacked(pack)
    target_dir = out_dir if out_dir is not None else root / meta["dir"]
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = pack.stat().st_mtime
    for name, raw in sorted(files.items()):
        target = target_dir / name
        target.write_bytes(raw)
        if digest(target.read_bytes()) != digest(raw):
            raise SystemExit(f"展开后校验失败：{target}")
        # 展开出来的四件不晚于工件本身：它们是工件生出来的，不是跑出来的。
        os.utime(target, (stamp, stamp))
    return target_dir, len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("pack", "check", "unpack"))
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--force", action="store_true", help="pack 时重写内容没变的工件")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "pack":
        written = skipped = raw_bytes = packed_bytes = 0
        for _key, unit in sorted(units().items()):
            result = pack_unit(unit, force=args.force)
            if result is None:
                skipped += 1
                continue
            target, body, raw = result
            written += 1
            raw_bytes += raw
            packed_bytes += target.stat().st_size
            print(f"打包 {unit.tag} → {target.relative_to(ROOT)}"
                  f"（{len(unit.files)} 件 {raw} → {target.stat().st_size} 字节）")
        print(f"打包 {written} 件、跳过 {skipped} 件（对得上且不过期）"
              + (f"；{raw_bytes} → {packed_bytes} 字节" if written else ""))
        return 0

    if args.command == "check":
        problems = check(verbose=args.verbose)
        for problem in problems:
            print(f"FAIL {problem}")
        if problems:
            return 1
        total = len(list(RUNS.glob(f"*{SUFFIX}"))) if RUNS.is_dir() else 0
        print(f"trajectory OK：{total} 件紧凑工件（{len(units())} 条路）各自对得上")
        return 0

    if len(args.paths) not in (1, 2):
        parser.error("unpack 需要 <pack> [<out_dir>]")
    out_dir = Path(args.paths[1]) if len(args.paths) == 2 else None
    target_dir, count = unpack(Path(args.paths[0]), out_dir)
    print(f"展开 {args.paths[0]} → {target_dir}（{count} 件，逐件摘要一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
