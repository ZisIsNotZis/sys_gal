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

from harness.world_loader import load_world_pack, ref_names  # noqa: E402

# Surname table for 姓+身份 patterns (李阿姨, 方老师, 郑大爷, ...).
_SURNAMES = ("王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘"
             "于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹"
             "薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤")
_ROLES = ("大爷|大妈|阿姨|大叔|大姐|师傅|老板|老板娘|代表|社长|编辑|记者|馆员|干事|管理员"
          "|秘书|同学|学长|学姐|老师|校工|店主|摊主|主任|主席|辅导员")
_PLACE_TAILS = ("家属院|地下室|器材室|后厨|广播站|糕点铺|县城|合作社|校园社|研究社|编辑部|坊")

# Prose particles/pronouns: a "name" match containing one of these is almost
# always an over-greedy capture ("会催的妈", "都是我妈") rather than a name.
_FUNCTION_CHARS = frozenset("的了是我你他她它都也会要有这那个们很就还只把被从和对与后前上中很")

# Order matters only for readability; resolution uses substring containment.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"[{_SURNAMES}](?:{_ROLES})"),
    re.compile(rf"[小老][{_SURNAMES}]"),
    re.compile(r"阿[\u4e00-\u9fff]"),
    # Kinship suffix with a name in front (陈默爸). {2,3} skips bare "爸爸"/"妈妈".
    re.compile(r"[\u4e00-\u9fff]{2,3}(?:爸|妈|哥|姐|弟|妹)"),
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


def _kb_keys(pack) -> tuple[dict[str, set[str]], set[str]]:
    """(actor -> keys its rows carry, generic names resolvable by everyone).

    `kind: generic` concepts are registry-only by design — they define a name
    without giving anyone a row, so they resolve universally.
    """
    keys = {actor: {str(k) for row in rows for k in row["keys"]}
            for actor, rows in pack.kb.items()}
    generic = {c["name"] for c in pack.concepts if c["kind"] == "generic"}
    generic.update(a for c in pack.concepts if c["kind"] == "generic"
                   for a in c["aliases"])
    return keys, generic


def _scope_holders(pack, source: str) -> list[str] | None:
    """Which actors receive a given authored text (T5 裁决 scope rules).

    None means "everyone" (world-level text: manifest notices, system facts,
    extra knowledge notes)."""
    name = Path(source).name
    if source.startswith("characters/"):
        stem = name[:-3] if name.endswith(".md") else name
        return [stem] if stem in pack.kb else []
    if source.startswith(("locations/", "items/", "documents/")):
        kind = source.split("/")[0]
        entity = name[:-3] if name.endswith(".md") else name
        rows = {str(r["id"]): r for r in getattr(pack, kind)}
        if entity not in rows:
            return []
        known_to = rows[entity].get("known_to")
        if known_to is None:
            return None  # public visible layer: every actor holds this row
        return [str(a) for a in known_to if str(a) in pack.kb]
    if source == "manifest.yml":
        return None  # checked separately, per structured scope
    return None


def lint(world_root: str | Path) -> list[str]:
    """Two complementary gates (T5 裁决) — neither is sufficient alone:

    ① every [[name]] marker must resolve in the KB keys of *each* actor who
       receives that text;
    ② every unmarked name-like token must resolve somewhere in the registry
       (otherwise the author probably forgot to mark it).
    """
    root = Path(world_root)
    pack = load_world_pack(root)
    declared = _declared(pack)
    kb_keys, universal = _kb_keys(pack)
    # Public figures (cast members) are common knowledge as *people*: a place
    # description may name the person who works there without every reader
    # having met them. Resolving their formal name ≠ knowing them personally.
    public_figures = {str(r["id"]) for r in pack.actors}
    findings: list[str] = []

    sources: list[tuple[str, str]] = []
    for pattern in _PROSE_GLOBS:
        for path in sorted(root.glob(pattern)):
            sources.append((str(path.relative_to(root)),
                            path.read_text(encoding="utf-8")))
    # A file defines the thing it is *about*: its own title always resolves for
    # every reader (the document/location is the definition of the term).
    self_defining: dict[str, set[str]] = {}
    for source, text in sources:
        title = text.splitlines()[0].lstrip("# ").strip() if text else ""
        self_defining[source] = {title} if title else set()

    # ① marked references, scoped per recipient
    checked_markers = 0
    for source, text in sources:
        holders = _scope_holders(pack, source)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name in ref_names(line):
                checked_markers += 1
                def resolves_for(a: str) -> bool:
                    return (name in universal or name in public_figures
                            or name in self_defining.get(source, set())
                            or _resolves(name, kb_keys.get(a, set())))
                if holders is None:
                    missing = [a for a in kb_keys if not resolves_for(a)]
                else:
                    missing = [a for a in holders if not resolves_for(a)]
                if missing:
                    findings.append(
                        f"{source}:{line_no}: [[{name}]] does not resolve for "
                        f"{', '.join(missing)} — add a contact row or concept "
                        f"alias for them")

    # ② unmarked name-like tokens (whole registry, as before)
    seen: set[tuple[str, str]] = set()
    for source, text in sources:
        for line_no, line in enumerate(text.splitlines(), start=1):
            for regex in _PATTERNS:
                for match in regex.finditer(line):
                    candidate = match.group(0)
                    if _resolves(candidate, declared):
                        continue
                    if any(char in _FUNCTION_CHARS for char in candidate):
                        continue
                    key = (candidate, source)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        f"{source}:{line_no}: unmarked name-like token "
                        f"{candidate!r} — mark it [[name]] and make sure it "
                        f"resolves for everyone who reads this text")

    # structured manifest scopes: notices → target; facts → everyone
    manifest = pack.manifest
    for row in manifest.get("scheduled", ()):
        notice = str(row.get("notice", ""))
        targets = row.get("target")
        holders = ([targets] if isinstance(targets, str)
                   else list(targets) if isinstance(targets, list) else None)
        if holders is None:
            holders = list(kb_keys)
        for name in ref_names(notice):
            missing = [a for a in holders
                       if a in kb_keys and not (name in universal
                                                or name in public_figures
                                                or _resolves(name, kb_keys[a]))]
            if missing:
                findings.append(
                    f"manifest scheduled {row.get('event')}: [[{name}]] does not "
                    f"resolve for {', '.join(missing)}")
    for name in ref_names(str(pack.manifest.get("system", {}).get("facts", {}))):
        missing = [a for a, keys in kb_keys.items()
                   if not (name in universal or name in public_figures
                           or _resolves(name, keys))]
        if missing:
            findings.append(
                f"manifest system.facts: [[{name}]] does not resolve for "
                f"{', '.join(missing)}")
    if checked_markers == 0:
        findings.append("no [[name]] markers found anywhere — run "
                        "scripts/mark_seed.py; unmarked references cannot be "
                        "scope-checked")
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
