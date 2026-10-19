#!/usr/bin/env python3
"""轨迹工件：打包成紧凑形态并核对（ticket 114）。

规范形态是 `<name>.jsonl.zst`（一行一条记录 + zstd -19），进 git；原始 `.json`
仍然本地生成、可读，但不进 git——它由紧凑工件展开即可重建。规则与理由见
`runs/README.md`，实现见 `harness/pack.py`。

用法：
    python3 scripts/pack_trajectory.py pack            # 把未打包 / 改动过的工件打包
    python3 scripts/pack_trajectory.py check           # 核对（预跑门的一环）
    python3 scripts/pack_trajectory.py unpack <pack> <out.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import pack as packer  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("pack", "check", "unpack"))
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--force", action="store_true", help="pack 时重写已有的紧凑工件")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "pack":
        packed = 0
        for source in packer.sources(ROOT):
            target = packer.pack_name(source)
            stale = target.is_file() and target.stat().st_mtime < source.stat().st_mtime
            if packer.pack(source, force=args.force or stale):
                packed += 1
        print(f"打包 {packed} 件（未变化的不动）。")
        return 0
    if args.command == "check":
        problems = packer.check(ROOT, verbose=args.verbose)
        for problem in problems:
            print(f"FAIL {problem}")
        if problems:
            return 1
        total = len(list(ROOT.glob(f"runs/*{packer.SUFFIX}"))) + len(
            list(ROOT.glob(f"checkpoints/*{packer.SUFFIX}")))
        print(f"trajectory OK：{total} 件紧凑工件与原始文件逐件一致")
        return 0
    if len(args.paths) != 2:
        parser.error("unpack 需要 <pack> <out.json>")
    obj = packer.unpack(Path(args.paths[0]), Path(args.paths[1]))
    print(f"展开 {args.paths[0]} → {args.paths[1]}"
          f"（{len(json.dumps(obj, ensure_ascii=False))} 字节 JSON）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
