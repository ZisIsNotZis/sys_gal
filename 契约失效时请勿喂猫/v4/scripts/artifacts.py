#!/usr/bin/env python3
"""轨迹工件的持久化：声明、复制、验证（ticket 113 = 一次证据丢失的修复）。

为什么需要它：`v4/runs/` 与 `v4/checkpoints/` 里的轨迹动辄几十 MB，所以它们被
`.gitignore` 挡在 git 外面。被挡住之后它们仍然只是**一个本地文件**——一次
`git clean -xdf`、一次误删、一次换机器，就没有了。D1 第三次验收（2026-10-18）
的整份轨迹与 d1-pm 的检查点就是这样丢的：报告和票据还在引用它们，可文件已经
不在磁盘上，任何结论都无法再复核（`AGENTS.md` 要求每次运行后人工复盘完整
轨迹）。

做法（对应 policy 的“太大就声明，不要静默忽略”）：
- `v4/artifacts.tsv` 是**声明**：路径、字节数、sha256、第二处持久位置。
- `archive` 把新工件复制到第二处持久位置（默认另一块盘），并登记进 tsv。
- `check` 逐条核对 tsv：文件在不在、字节数对不对、sha256 对不对；不在或对不上
  就是缺失，退出码非零。声明里写了却没有，等于没有。

用法：
    python3 scripts/artifacts.py archive      # 复制未归档的工件并登记
    python3 scripts/artifacts.py check        # 核对（预跑门的一环）
    python3 scripts/artifacts.py check --strict   # 还有未归档工件也算失败

第二处持久位置：`$V4_ARTIFACT_ARCHIVE`，默认 `/home/z/hf/vibe-artifacts/v4`。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = Path(os.environ.get("V4_ARTIFACT_ARCHIVE",
                                      "/home/z/hf/vibe-artifacts/v4"))
MANIFEST = ROOT / "artifacts.tsv"
HEADER = "path\tsize\tsha256\tarchive_path"
# 只登记这些类别：整份轨迹与检查点是“声称过的证据”，它们丢了结论就没了。
PATTERNS = ("runs/*.json", "checkpoints/*.json")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(path: Path | None = None) -> list[dict[str, str]]:
    path = path or MANIFEST
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("path\t"):
            continue
        cells = line.split("\t")
        if len(cells) != 4:
            raise SystemExit(f"artifacts.tsv 行格式不对（应为 4 列）：{line!r}")
        rows.append(dict(zip(("path", "size", "sha256", "archive_path"), cells)))
    return rows


def write_manifest(rows: list[dict[str, str]], path: Path | None = None) -> None:
    path = path or MANIFEST
    lines = ["# 轨迹工件的声明（ticket 113）：路径 / 字节数 / sha256 / 第二处持久位置。",
             "# 由 scripts/artifacts.py archive 追加，check 核对。手改无效——重新 archive。",
             HEADER]
    for row in sorted(rows, key=lambda item: item["path"]):
        lines.append("\t".join(row[key] for key in ("path", "size", "sha256",
                                                   "archive_path")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def candidates() -> list[Path]:
    found: list[Path] = []
    for pattern in PATTERNS:
        found.extend(sorted(ROOT.glob(pattern)))
    return [path for path in found if path.is_file()]


def archive(archive_dir: Path) -> list[str]:
    """把未登记的工件复制到 `archive_dir`，返回新登记的行数说明。"""
    rows = read_manifest()
    known = {row["path"] for row in rows}
    archive_dir.mkdir(parents=True, exist_ok=True)
    added: list[str] = []
    for path in candidates():
        relative = str(path.relative_to(ROOT))
        if relative in known:
            continue
        target = archive_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or sha256_of(target) != sha256_of(path):
            shutil.copy2(path, target)
        rows.append({"path": relative, "size": str(path.stat().st_size),
                     "sha256": sha256_of(path), "archive_path": str(target)})
        added.append(f"{relative} → {target}")
    if added:
        write_manifest(rows)
    return added


def check(archive_dir: Path, *, strict: bool = False) -> tuple[list[str], list[str]]:
    """核对 tsv 每一条。返回 (问题, 未归档的本地工件)。"""
    problems: list[str] = []
    rows = read_manifest()
    if not rows:
        problems.append("artifacts.tsv 没有任何声明——轨迹工件只能靠本地文件活着")
    seen: set[str] = set()
    for row in rows:
        local = ROOT / row["path"]
        archived = Path(row["archive_path"])
        copies = [path for path in (local, archived) if path.is_file()]
        if not copies:
            problems.append(f"缺失：{row['path']}（本地与 {row['archive_path']} 都没有）")
            continue
        for copy in copies:
            size = copy.stat().st_size
            if str(size) != row["size"]:
                problems.append(f"字节数不符：{copy} 是 {size}，声明 {row['size']}")
            elif sha256_of(copy) != row["sha256"]:
                problems.append(f"sha256 不符：{copy}")
        seen.add(row["path"])
    unarchived = [str(path.relative_to(ROOT)) for path in candidates()
                  if str(path.relative_to(ROOT)) not in seen]
    if strict and unarchived:
        problems.extend(f"未归档：{name}" for name in unarchived)
    return problems, unarchived


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("archive", "check"))
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--strict", action="store_true",
                        help="check 时，未归档的本地工件也算失败")
    args = parser.parse_args(argv)
    if args.command == "archive":
        added = archive(args.archive_dir)
        print(f"归档 {len(added)} 件 → {args.archive_dir}" if added
              else "没有新的工件需要归档。")
        for line in added:
            print(f"  {line}")
        return 0
    problems, unarchived = check(args.archive_dir, strict=args.strict)
    if unarchived:
        print(f"未归档的本地工件 {len(unarchived)} 件（`archive` 可补）："
              + "、".join(unarchived[:5]) + ("…" if len(unarchived) > 5 else ""))
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    print(f"artifacts OK：{len(read_manifest())} 件声明全部核对通过"
          f"（第二处位置 {args.archive_dir}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
