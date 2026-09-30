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
Besides the name registry gate, this enforces the ticket-47 knowledge
contract: a puzzle entry never carries its answer in the delivered desc, a
guardrail row is reachable by the plot words its owner hears, a persona only
names props the world can produce, and inline manifest content is a name
carrier. Homonym collisions are printed as non-blocking `warning:` lines.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.world_loader import (  # noqa: E402
    _CONCRETE_PROP_WORDS, load_world_pack, ref_names)
from harness.kb import normalize  # noqa: E402

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

# ticket 47: named props a character card or a memory may promise by name.
# The objective half is world_loader's controlled prop vocabulary (the same
# list its concrete-presence gate uses); the persona half adds the register and
# roster props the v4 d1-am artifact showed actors reaching for. Kept as an
# explicit controlled list, never inferred from a 表/单 suffix pattern — a bare
# generic noun (表格) is not a "named prop", and flagging every 作息表/时间表
# would drown the gate.
_PERSONA_PROP_WORDS: tuple[str, ...] = _CONCRETE_PROP_WORDS + (
    "考勤表", "志愿报名表", "体测表", "活动签到表", "查寝表",
)
# For the advisory name-collision scan: a short personal address is a name that
# starts 小/老, ends with a known role title, or ends with a kinship suffix.
_ROLE_NAMES: tuple[str, ...] = tuple(part for part in _ROLES.split("|") if part)
_KINSHIP_TAILS = "爸妈哥姐弟妹儿女"

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
    try:
        pack = load_world_pack(root)
    except ValueError as exc:
        # The world-completeness contract (issue 35) is enforced at load time:
        # an uncovered concrete-presence claim, a bad object_presence entry, or
        # an unknown completeness state surfaces here with the remediation text.
        return [f"world pack violates the seed contract: {exc}"]
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

    # ---------- ④ ticket 47: knowledge-entry grading ----------
    # A puzzle entry states only the question/anomaly; its answer lives in the
    # document that can be read. A suppression/guardrail row must be reachable
    # by the plot words its owner hears. A persona may only name props the
    # world can produce. Inline manifest content is a name carrier like prose.
    findings.extend(_puzzle_findings(pack))
    findings.extend(_guard_findings(pack))
    findings.extend(_prop_findings(pack, root))
    findings.extend(_inline_content_findings(pack))

    # ---------- ③ dead registry entries (informational) ----------
    for note in dead_aliases(root):
        findings.append(note)
    return findings


def _contains(haystack: str, needle: str) -> bool:
    """Substring test under the KB's own normalization (的/之 and punctuation
    collapse) so "底层的报销凭证" and "底层报销凭证" compare equal."""
    text = normalize(haystack)
    return bool(text) and normalize(needle) in text


def _entity_contents(pack) -> dict[str, str]:
    """Readable bodies an actor can obtain by reading, keyed by entity id."""
    return {str(row["id"]): str(row["content"])
            for row in (*pack.items, *pack.documents)
            if isinstance(row.get("content"), str) and str(row["content"]).strip()}


def _puzzle_findings(pack) -> list[str]:
    """Ticket 47 / K1: a puzzle entry's desc is the question, never the answer.

    A concept declares ``puzzle: {reveal: <document/item id>, answer: [...]}``.
    Every answer clause must be absent from the desc/memory (or the entry leaks
    the conclusion before any read) and present in the reveal carrier's content
    (or the answer is unreachable).
    """
    findings: list[str] = []
    contents = _entity_contents(pack)
    for row in pack.manifest.get("concepts", ()) or ():
        puzzle = row.get("puzzle")
        if puzzle is None:
            continue
        cid = str(row.get("id", "?"))
        where = f"concept {cid} puzzle"
        if not isinstance(puzzle, dict):
            findings.append(f"{where}: puzzle must be a mapping")
            continue
        reveal = str(puzzle.get("reveal", ""))
        answer = puzzle.get("answer")
        if (not isinstance(answer, (list, tuple)) or not answer
                or any(not isinstance(a, str) or not a.strip() for a in answer)):
            findings.append(f"{where}: answer must be a non-empty list of clause strings")
            continue
        if reveal not in contents:
            findings.append(
                f"{where}: reveal {reveal!r} is not a document/item with readable "
                "content, so the answer can never be obtained")
            continue
        carrier = contents[reveal]
        delivered = [str(row.get("desc", ""))]
        delivered.extend(str(v) for v in (row.get("memory") or {}).values())
        for clause in answer:
            if any(_contains(text, clause) for text in delivered):
                findings.append(
                    f"{where}: 谜底泄漏 — answer {clause!r} is already in the desc/memory "
                    "delivered before any read; keep the entry to the question and put "
                    f"the answer only in {reveal!r}")
            if not _contains(carrier, clause):
                findings.append(
                    f"{where}: 谜底不可达 — answer {clause!r} is not in the content of "
                    f"{reveal!r}")
    return findings


def _guard_findings(pack) -> list[str]:
    """Ticket 47 / K2: a suppression/guardrail row must be reachable by the plot
    words its owner actually hears.

    A kb row carrying ``triggers: ["<plot phrase>", ...]`` declares the phrases
    that should surface it. Because :func:`harness.kb.hits` matches the whole
    query text against a key (both directions), the operative direction for a
    long plot sentence is *key is a substring of the trigger*. A guard whose
    nearest key can only be reached from the other direction is invisible.
    """
    findings: list[str] = []
    for actor, rows in (pack.manifest.get("kb", {}) or {}).items():
        for row in rows:
            triggers = row.get("triggers")
            if triggers is None:
                continue
            keys = [str(k) for k in (row.get("keys") or row.get("fields") or ())
                    if not str(k).startswith("!")]
            where = f"kb[{actor}] {sorted(keys)}"
            if (not isinstance(triggers, (list, tuple)) or not triggers
                    or any(not isinstance(t, str) or not t.strip() for t in triggers)):
                findings.append(f"{where}: triggers must be a non-empty list of plot phrases")
                continue
            if not any(normalize(k) and normalize(k) in normalize(t)
                       for k in keys for t in triggers):
                findings.append(
                    f"{where}: 抑制/守则行检索不到 — no key is a substring of any trigger "
                    f"{list(map(str, triggers))}; the row can never surface for {actor}")
    return findings


def _pattern_names(text: str) -> list[str]:
    """Controlled name-like tokens (the _PATTERNS detector), markers ignored."""
    body = re.sub(r"\[\[[^\]\[]+\]\]", "\u0002", str(text))
    tokens: list[str] = []
    for pattern in _PATTERNS:
        tokens.extend(pattern.findall(body))
    return [token for token in tokens
            if not any(char in _FUNCTION_CHARS for char in token)]


def _prop_findings(pack, root: Path) -> list[str]:
    """Ticket 47 / K47c: a named prop promised by a card or memory must land.

    Scans character cards (skipping markdown headings) and concept memories for
    the controlled prop vocabulary; each token must resolve to a registered
    entity or concept. A prop the world cannot produce is a promise the actor
    will fail to keep in play.
    """
    declared = _declared(pack)
    pattern = re.compile("|".join(re.escape(word) for word in
                                   sorted(set(_PERSONA_PROP_WORDS), key=len, reverse=True)))
    findings: list[str] = []

    def scan(where: str, text: str) -> None:
        for token in sorted(set(pattern.findall(text))):
            if not _resolves(token, declared):
                findings.append(
                    f"{where}: named prop {token!r} does not resolve to a registered "
                    "item/concept — register it or reword the promise")

    for path in sorted(root.glob("characters/*.md")):
        body = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("#"))
        scan(str(path.relative_to(root)), body)
    for concept in pack.concepts:
        for owner, memory in concept["memory"].items():
            scan(f"concept {concept['id']} memory[{owner}]", str(memory))
    return findings


def _inline_content_findings(pack) -> list[str]:
    """Ticket 47 / K47d: inline manifest `content`/`desc` is a name carrier.

    A name-like token written straight into an items/documents/locations row is
    model-visible after load (markers stripped), so it must resolve to a
    registered entity or concept just like prose — otherwise new content smuggles
    in a name neither the model nor flashback can resolve.
    """
    declared = _declared(pack)
    findings: list[str] = []
    for kind in ("items", "documents", "locations"):
        for row in getattr(pack, kind):
            for field in ("content", "desc"):
                text = row.get(field)
                if not isinstance(text, str) or not text.strip():
                    continue
                for token in sorted(set(_pattern_names(text))):
                    if _resolves(token, declared):
                        continue
                    findings.append(
                        f"{kind} {row['id']} {field}: inline name {token!r} does not "
                        "resolve to a registered entity/concept — register it or wrap "
                        "it as [[...]]")
    return findings


def _person_address(name: str) -> bool:
    return (name[0] in "小老" or name.endswith(_ROLE_NAMES)
            or name[-1] in _KINSHIP_TAILS)


def collision_warnings(world_root: str | Path) -> list[str]:
    """Ticket 47 / K47e: advisory homonym collisions (never block).

    Two registered names are confusable when a short personal address nests
    inside a longer name owned by a different entity, or when a 小<姓> form sits
    beside an actor of the same surname (the 「小陈」/陈默 clash). Returns plain
    warning lines for a human to judge; seed lint stays green.
    """
    pack = load_world_pack(Path(world_root))
    owners: dict[str, set[str]] = {}
    for kind in ("locations", "items", "documents", "actors"):
        for row in getattr(pack, kind):
            owners.setdefault(str(row["id"]), set()).add(f"{kind}:{row['id']}")
    for concept in pack.concepts:
        owners.setdefault(concept["name"], set()).add(f"concept:{concept['id']}")
        for alias in concept["aliases"]:
            owners.setdefault(alias, set()).add(f"concept:{concept['id']}")
    actor_ids = {str(row["id"]) for row in pack.actors}
    names = [name for name in owners if len(name) >= 2]
    warnings: list[str] = []
    for name in sorted(names):
        if len(name) == 2 and name[0] == "小" and name[1] in _SURNAMES:
            surname = name[1]
            others = sorted(other for other in actor_ids
                            if other != name and other.startswith(surname))
            if others:
                warnings.append(
                    f"name collision 小名 {name!r} 与同姓角色称呼 {', '.join(others)} "
                    "（不同实体，易混称，供人判断）")
    for short in sorted(names, key=lambda n: (-len(n), n)):
        if not _person_address(short):
            continue
        for long in names:
            if short == long or short not in long:
                continue
            if owners[short] & owners[long]:
                continue  # same entity/id: a 的/alias derivation, not a clash
            warnings.append(
                f"name collision {short!r} ⊂ {long!r}（{sorted(owners[short])} vs "
                f"{sorted(owners[long])}，供人判断）")
    return warnings


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
    try:
        warnings = collision_warnings(args.world)
    except ValueError:
        warnings = []
    for note in warnings:
        print(f"warning: {note}")
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
