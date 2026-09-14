#!/usr/bin/env python3
"""Seed name lint: no named thing may exist only in prose.

The v4 day run failed because 陈默 reasoned about 红色哨子/老街坊 from a
description while neither name was registered anywhere the engine could reach,
so flashback returned nothing. The registry that fixes this is
``world/manifest.yml`` (actors/locations/items/documents plus the ``concepts:``
section). This lint is the inverse gate: every name-like token in authored
prose must resolve to a registered entity or concept (an existing entity id, a
concept name, or a concept alias). There is no separate whitelist — a generic
place like 校门口 becomes a ``kind: generic`` concept so everything follows one
system.

Usage:
    python3 scripts/seed_lint.py [world_dir] [--verbose]

Exit code 0 when the seed is self-consistent, 1 with a report otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.world_loader import load_world_pack  # noqa: E402

# Surname table for 姓+身份 patterns (李阿姨, 方老师, 郑大爷, ...).
_SURNAMES = ("王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘"
             "于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹"
             "薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤")
_ROLES = ("大爷|大妈|阿姨|大叔|大姐|师傅|老板|老板娘|代表|社长|编辑|记者|馆员|干事|管理员"
          "|秘书|同学|学长|学姐|老师|校工|店主|摊主|主任|主席|辅导员")
_PLACE_TAILS = ("家属院|地下室|器材室|后厨|广播站|糕点铺|县城|合作社|校园社|研究社|编辑部|坊")

# Order matters only for readability; resolution uses substring containment.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"[{_SURNAMES}](?:{_ROLES})"),
    re.compile(rf"[小老][{_SURNAMES}]"),
    re.compile(rf"[\u4e00-\u9fff]{{1,4}}(?:{_PLACE_TAILS})"),
    re.compile(r"(?:蓝色兔子(?:贴纸|雨伞|登记)|红色(?:哨子|保温杯)|催(?:稿|办)单|抽水泵|"
               r"登记本|抄件|保温杯|糖罐子|老照片|旧记录|校报草稿|审计包)"),
    re.compile(r"(?:台风|纪念活动|无障碍|审计|值班表)"),
)

# Authored prose the lint scans; generated runs/traces are excluded.
_PROSE_GLOBS = ("characters/*.md", "items/*.md", "documents/*.md",
                "locations/*.md", "organizations/*.md", "manifest.yml")
# The lint looks at the manifest's authored prose fields, not the kb rows it
# generates (those are derived from the same names and would only echo them).


def _declared(pack) -> set[str]:
    names: set[str] = set()
    for row in (*pack.locations, *pack.items, *pack.documents, *pack.actors):
        names.add(str(row["id"]))
    for concept in pack.concepts:
        names.add(concept["name"])
        names.update(concept["aliases"])
    names.update(pack.lexicon)
    return names


def _resolves(candidate: str, declared: set[str]) -> bool:
    return any(candidate in name or name in candidate for name in declared)


def _manifest_prose(pack) -> str:
    """Authored prose inside the manifest: notices, extra knowledge notes,
    system facts, and hand-written kb descs (not the concept expansion)."""
    manifest = pack.manifest
    parts: list[str] = []
    for row in manifest.get("scheduled", ()):
        parts.append(str(row.get("notice", "")))
        parts.append(str(row.get("event", "")))
    for row in manifest.get("locations", ()):
        for extra in row.get("extras", ()) or ():
            parts.append(str(extra.get("fragment", "")))
            parts.append(str(extra.get("knowledge_notes", "")))
    for key, value in (manifest.get("system", {}).get("facts", {}) or {}).items():
        parts.append(str(key))
        parts.append(str(value))
    for rows in (manifest.get("kb", {}) or {}).values():
        for row in rows:
            parts.append(str(row.get("desc", "")))
    return "\n".join(parts)


def lint(world_root: str | Path) -> list[str]:
    root = Path(world_root)
    pack = load_world_pack(root)
    declared = _declared(pack)
    findings: list[str] = []

    sources: list[tuple[str, str]] = []
    for pattern in _PROSE_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.name == "manifest.yml":
                # Scan the raw manifest so line numbers are real; every declared
                # name in it resolves, so only genuinely unregistered prose fails.
                sources.append((str(path.relative_to(root)),
                                path.read_text(encoding="utf-8")))
            else:
                sources.append((str(path.relative_to(root)),
                                path.read_text(encoding="utf-8")))

    seen: set[tuple[str, str]] = set()
    for source, text in sources:
        for line_no, line in enumerate(text.splitlines(), start=1):
            for regex in _PATTERNS:
                for match in regex.finditer(line):
                    candidate = match.group(0)
                    if _resolves(candidate, declared):
                        continue
                    key = (candidate, source)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        f"{source}:{line_no}: unregistered name {candidate!r} "
                        f"— register it in concepts: (or reword)")
    # Dead registry entries are informational, not failures.
    return findings


def dead_aliases(world_root: str | Path) -> list[str]:
    root = Path(world_root)
    text = "\n".join(path.read_text(encoding="utf-8")
                     for pattern in _PROSE_GLOBS
                     for path in root.glob(pattern)) + _manifest_prose(load_world_pack(root))
    out = []
    for concept in load_world_pack(root).concepts:
        for alias in concept["aliases"]:
            if alias not in text:
                out.append(f"concept {concept['id']}: alias {alias!r} never appears")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("world", nargs="?", default=str(Path(__file__).resolve().parents[1] / "world"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    findings = lint(args.world)
    if args.verbose:
        for note in dead_aliases(args.world):
            print(f"note: {note}")
    if findings:
        print(f"seed lint FAILED ({len(findings)} unregistered name(s)):")
        for finding in findings:
            print("  " + finding)
        return 1
    print("seed lint OK: every named thing resolves to an entity or concept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
