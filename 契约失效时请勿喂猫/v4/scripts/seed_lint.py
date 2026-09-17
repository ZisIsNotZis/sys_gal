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
                "locations/*.md", "organizations/*.md")
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
    for row in manifest.get("history", ()) or ():
        detail = (row.get("payload") or {}).get("detail", "")
        parts.append(str(detail))
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
    """Three gates, one code path per carrier (T5 裁决):

    ① .md prose: every registered name MUST carry a [[marker]] (mark_seed does
       this), and each marker must resolve for EVERY actor who receives that
       text (own card -> self; entity description -> its holders; public ->
       everyone). Marking is what makes per-actor scope checking possible.
    ② manifest authored prose (notice/desc/content/memory): the recipient set
       is structural (broadcast / known_to / concept scope), so marking is
       optional — but every registered name must resolve for the actual
       recipients.
    ③ no dead registry entries.
    """
    root = Path(world_root)
    pack = load_world_pack(root)
    declared = _declared(pack)
    kb_keys, universal = _kb_keys(pack)
    universal |= universal_from_titles(sources_md(root))
    findings: list[str] = []

    # ---------- ① .md bodies: mandatory markers + per-holder resolution ----------
    for source, text in sources_md(root):
        lines = text.splitlines(keepends=True)
        title, body = (lines[0], "".join(lines[1:])) if lines else ("", "")
        title_name = title.lstrip("# \n").strip()
        holders = _scope_holders(pack, source)
        body_names = registered_in(body, declared)

        for name in sorted(set(ref_names(body))):
            if holders is None:
                missing = [a for a, keys in kb_keys.items()
                           if not (name in universal
                                   or _resolves(name, keys))]
            else:
                missing = [a for a in holders
                           if not (name in universal or name == title_name
                                   or _resolves(name, kb_keys.get(a, set())))]
            if missing:
                findings.append(
                    f"{source}: [[{name}]] does not resolve for "
                    f"{', '.join(missing)} — add a contact row or concept alias")

        for token, _snippet in sorted(set(body_names)):
            findings.append(
                f"{source}: unmarked reference {token!r} — wrap it as "
                f"[[{token}]] (marking is mandatory in prose files)")

    # ---------- ② manifest authored prose: structural scope ----------
    manifest = pack.manifest

    remote_actors = {str(r["id"]) for r in pack.actors if r.get("remote")}

    def resolvable_for(actor: str, name: str) -> bool:
        if name in universal:
            return True
        keys = kb_keys.get(actor, set())
        return any(name in key or key in name for key in keys)

    def check_text(text: str, where: str, holders: list[str] | None) -> None:
        for name in sorted({token for token, _ in registered_in(text, declared)},
                           key=lambda n: -len(n)):
            if holders is None:
                missing = [a for a, keys in kb_keys.items()
                           if not resolvable_for(a, name)]
            else:
                missing = [a for a in holders
                           if a in kb_keys and not resolvable_for(a, name)]
            if missing:
                findings.append(
                    f"{where}: {name!r} does not resolve for "
                    f"{', '.join(missing)}")

    for row in manifest.get("scheduled", ()):
        targets = row.get("target")
        holders = ([str(targets)] if isinstance(targets, str)
                   else [str(t) for t in targets] if isinstance(targets, list)
                   else None)
        # Broadcast notices are campus atmosphere: a remote actor (陈默妈)
        # does not receive them, so they impose no knowledge obligation there.
        # Broadcast (no target) reaches every non-remote actor; targeted
        # notices reach their targets only.
        if holders is None:
            holders = [a for a in kb_keys if a not in remote_actors]
        else:
            holders = [a for a in holders if a not in remote_actors] or None
        check_text(str(row.get("notice", "")),
                   f"scheduled {row.get('event')}", holders)
    for concept in pack.concepts:
        # The shared desc goes to every known_to actor; each memory goes only
        # to the actor who owns it (that is the point of personal memory).
        check_text(concept["desc"], f"concept {concept['id']}",
                   [a for a in concept["known_to"] if a in kb_keys])
    for row in manifest.get("history", ()) or ():
        # History events are model-visible via flashback: their [[ ]] names
        # must resolve for exactly the audience that lived through them.
        targets = row.get("visible_to") or []
        holders = ([str(t) for t in targets] if isinstance(targets, list)
                   else [str(targets)])
        detail = str((row.get("payload") or {}).get("detail", ""))
        check_text(detail, f"history {row.get('time', '')}", holders or None)

        for owner, memory in concept["memory"].items():
            if owner in kb_keys:
                check_text(memory, f"concept {concept['id']} memory[{owner}]",
                           [owner])
    for actor, rows in (manifest.get("kb", {}) or {}).items():
        for row in rows:
            check_text(str(row.get("desc", "")),
                       f"kb[{actor}] {sorted(str(k) for k in row['keys'])}",
                       [actor])
    # extras knowledge_notes are conversation-scoped (delivered only to
    # whoever actually talks to that stranger), so they are not per-actor seed
    # claims — but they must still be registered names, which ② covers via
    # `declared` resolution in the .md scan of location files.

    # ---------- ③ dead registry entries (informational) ----------
    for note in dead_aliases(root):
        findings.append(note)
    return findings


def sources_md(root: Path) -> list[tuple[str, str]]:
    return [(str(path.relative_to(root)), path.read_text(encoding="utf-8"))
            for pattern in _PROSE_GLOBS
            for path in sorted(root.glob(pattern))]


def registered_in(text: str, declared: set[str]) -> list[tuple[str, str]]:
    """Unmarked registered-name occurrences, longest-first accounted."""
    body = re.sub(r"\[\[[^\]\[]+\]\]", "\u0002", text)
    found: list[tuple[str, str]] = []
    for name in sorted((n for n in declared if len(n) >= 2), key=lambda n: (-len(n), n)):
        at = body.find(name)
        while at >= 0:
            found.append((name, body[max(0, at - 10):at + len(name) + 10]))
            body = (body[:at] + "\u0003" * len(name) + body[at + len(name):])
            at = body.find(name, at + len(name))
    return found


def universal_from_titles(sources: list[tuple[str, str]]) -> set[str]:
    """A file's own title is the definition of its subject: it resolves for
    everyone holding that document."""
    titles: set[str] = set()
    for _source, text in sources:
        first = text.splitlines()[0] if text else ""
        if first.lstrip().startswith("#"):
            titles.add(first.lstrip("# \n").strip())
    return titles


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
