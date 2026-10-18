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
carrier. Ticket 60 extends that prop contract to a location's interior detail:
a concrete prop named there must resolve to a registered entity/concept or be
written as unusable in the same sentence. Homonym collisions are printed as
non-blocking `warning:` lines, as are two ticket-61/62 silent-default traps: a
placed document whose body asserts a concrete state while naming no
`known_to` (ticket 61), and a concept whose `desc` states a status/conclusion
while `known_to` hands it to many actors (ticket 62).

Ticket 78 adds a second, separate channel — the seed *contract* gates (G1–G4),
computed by :func:`contract_gate_findings` and printed by the same command.
The name contract above asks "is this name resolvable?"; the contract gates ask
"can the world actually deliver what the seed asserts?": G1 an acting person in
a scheduled notice must be a real actor (or the sentence is rewritten as a
visible absence); G2 a role noun must be a registered name or be declared
generic in `role_prose:`; G3 every location and every item/document must be
reachable; G4 a prose-announced interaction must land on an existing affordance
class (a read wants a document, a seen/taken thing wants an item, a contacted
person wants an actor or KB contact). The two channels are kept separate so each
one's history is checkable on its own: the CLI is the pre-run gate and fails
when either reports.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.world_loader import (  # noqa: E402
    _COMPLETENESS_STATES, _CONCRETE_PROP_WORDS, load_world_pack, ref_names,
    strip_refs)
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

# Ticket 60: a location's interior detail (the paragraphs after the public
# brief, ticket 58) names the room's own equipment. The d1-am artifact
# (real-20261001T065553) walked into three props that lived only in that prose:
# 陈默 `read 扫描仪` / `read 扫描仪日志` four times in the archive, 林瑶室友
# `read 校史专用柜` / `read 专用柜登记本` in the library, and 辅导员 tried
# `take 桌上的白纸和笔` / `take 纸笔` in the archive. Every attempt is a
# wasted turn, and the room reads as broken. The vocabulary is the ticket-47
# controlled prop list plus the two names the artifact reached for; a bare
# 柜/柜子 is deliberately absent — the engine already tells actors that a
# cabinet is not something to open, and flagging every 铁皮柜/抽屉 would drown
# the gate (the same reasoning as K47c's 表格).
_LOCATION_PROP_WORDS: tuple[str, ...] = _PERSONA_PROP_WORDS + ("扫描仪", "专用柜")

# The ticket's own wording for "this prop is not usable here". The prop and one
# of these markers must sit in the same sentence (。！？；/newline/—— boundary),
# so that "不在本房间 / 坏了 / 管理员收着" reads as a statement about that prop;
# comma scope is deliberately NOT used, because natural Chinese splits a prop
# from its state across commas ("扫描仪的待机灯常绿，但机器坏了").
_UNUSABLE_PROP_RE = re.compile(
    r"不在|没有|没放|没收|坏了|坏着|送修|报修|停用|用不了|不能用|打不开|开不了|"
    r"锁|钥匙|收着|收在|不能碰|不许|禁止|不对外")
_PROP_SENTENCE_SPLIT = re.compile(r"[。！？；\n]|——")

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
            # Ticket 61 changed the runtime default: a location's brief stays
            # world-level (every aware actor holds that row), but an item or
            # document is world-public only when the seed says so. An unmarked
            # one expands to nobody's KB, so it imposes no per-actor marker
            # resolution — whoever reaches it gets the body through the
            # ticket-49 observation instead (ticket 62 narrows concepts that
            # appear only in such a body).
            return None if kind == "locations" else []
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
    findings.extend(_location_brief_findings(pack, root))
    findings.extend(_location_prop_findings(pack, root))

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


def _location_brief_findings(pack, root: Path) -> list[str]:
    """Ticket 58: a location body must separate a public brief from interior
    detail.

    The KB row every aware actor gets carries only the first paragraph of a
    location ``.md`` (its public identity/purpose line); the blank-line-
    separated paragraphs after it are the interior detail, which reaches an
    actor only through a real source (the ticket-49 arrival description, a
    note, or reading). A body written as one undivided paragraph hands every
    actor the interior detail with no source, so the lint refuses it and says
    how to split.
    """
    findings: list[str] = []
    location_ids = {str(row["id"]) for row in pack.locations}
    for path in sorted(root.glob("locations/*.md")):
        entity = path.stem
        if entity not in location_ids:
            continue
        text = path.read_text(encoding="utf-8")
        lines = [line.strip() for line in text.strip().splitlines()]
        body = [line for line in lines if not line.startswith("#")]
        paragraphs = [p.strip() for p in "\n".join(body).split("\n\n") if p.strip()]
        if len(paragraphs) >= 2:
            continue
        findings.append(
            f"{path.relative_to(root)}: 只有一段描述，无法区分可公开的地点身份与内部细节 — "
            "把第一段写成谁都能知道的身份/用途（叫什么、在哪、大致做什么），"
            "内部细节（柜子怎么码、哪页有折痕）另起一段、空行分隔；"
            "内部细节只在到达时经客观描述下发，不再进入每个角色的 KB")
    return findings


def _location_prop_findings(pack, root: Path) -> list[str]:
    """Ticket 60 / K60: a location interior may not promise a prop the world
    cannot produce.

    The first paragraph of a location ``.md`` is its public brief; the
    paragraphs after it are the interior detail an actor receives on arrival
    (ticket 58), so a concrete prop named there is a promise that actor will
    act on. Each such prop must resolve to a registered entity or concept, or
    the same sentence must say it cannot be used here.
    """
    declared = _declared(pack)
    pattern = re.compile("|".join(re.escape(word) for word in
                                   sorted(set(_LOCATION_PROP_WORDS),
                                          key=len, reverse=True)))
    findings: list[str] = []
    for path in sorted(root.glob("locations/*.md")):
        text = strip_refs(path.read_text(encoding="utf-8"))
        lines = [line.strip() for line in text.strip().splitlines()]
        body = [line for line in lines if not line.startswith("#")]
        paragraphs = [p.strip() for p in "\n".join(body).split("\n\n") if p.strip()]
        for paragraph in paragraphs[1:]:
            for sentence in _PROP_SENTENCE_SPLIT.split(paragraph):
                if _UNUSABLE_PROP_RE.search(sentence):
                    continue
                for token in sorted(set(pattern.findall(sentence))):
                    if _resolves(token, declared):
                        continue
                    findings.append(
                        f"{path.relative_to(root)}: 内部细节里的道具 {token!r} 没解析到注册实体/概念，"
                        "句子也没写明它用不了 — 注册它（items:/documents: 里给 location；可读给 "
                        "content，不可读给 readable: false + readable_reason），或在同一句里写明"
                        "「不在本房间 / 坏了 / 管理员收着」这类不可操作表述")
    return findings


# Ticket 61: physical-state words that, carried into every actor's KB, leak
# who handled a document and when. A placed document whose body asserts one of
# these while its `known_to` is empty is the 宿管阿姨/折痕 pattern.
_DOCUMENT_STATE_WORDS: tuple[str, ...] = (
    "折痕", "缺页", "缺角", "涂改", "破损", "磨损", "水渍", "霉斑", "虫蛀", "撕破",
)


def placed_entity_ids(pack) -> set[str]:
    """Item/document ids that exist in the opening world: placed at a location
    or held in an actor's inventory (ticket 61). A scheduled-only entity is not
    yet placed."""
    placed = {str(row["id"]) for row in (*pack.items, *pack.documents)
              if row.get("location") is not None}
    placed.update(str(item) for row in pack.actors
                  for item in row.get("inventory", ()))
    return placed


def document_state_warnings(world_root: str | Path) -> list[str]:
    """Ticket 61 (non-blocking): a placed document that asserts a concrete
    physical state but names no `known_to`.

    Before ticket 61 an unmarked placed document expanded its full body into
    every actor's KB — which is literally how 宿管阿姨 cited the 台账's 折痕
    without ever entering the archive. Now the default is the opposite: nobody
    holds it as a knowledge row, and only an actor who reaches or reads it can
    cite that state. That silence is easy to author by accident, so surface it
    for a human to confirm; add `known_to` when the state really is common
    knowledge. Returns warning lines for the non-blocking channel (never a
    finding that fails the lint).
    """
    pack = load_world_pack(Path(world_root))
    placed = placed_entity_ids(pack)
    warnings: list[str] = []
    for row in pack.documents:
        entity = str(row["id"])
        if entity not in placed or row.get("known_to"):
            continue
        text = pack.descriptions["documents"].get(entity, "")
        hit = next((word for word in _DOCUMENT_STATE_WORDS if word in text), None)
        if hit is None:
            continue
        warnings.append(
            f"documents/{entity}.md: 正文提到具体状态 {hit!r}，而 known_to 为空 — "
            "没有显式列出的知情者（旧缺省「没写 known_to = 全公开」，修复后只对到过/读到"
            "的人可见）；确认是否有意：若确实众所周知，就显式写 known_to，否则可以不管。")
    return warnings


# Ticket 62: a concept's `desc` is the identity shared with every `known_to`
# actor — "what this thing is", never its state or a conclusion drawn from a
# source. A state/conclusion word in a widely-shared desc is the ticket-61
# pattern again: `known_to` means "knows it exists" (ticket 40), but the desc
# rides out as a knowledge line, so "knows of it" reads as "knows its detail".
# The d1-am artifacts show the cost — 宿管阿姨/辅导员/食堂大妈 all carried
# `flood-route-note`'s "箭头没画完", and 食堂大妈's KB held 器材室's
# "借出时间…对不上" verbatim though she never read the 台账/导出件. The detail
# belongs to a source (reading / being shown / being told; ticket 49).
_CONCEPT_STATE_WORDS: tuple[str, ...] = (
    "未画完", "没画完", "没写完", "对不上", "签名人", "签名潦草", "墨迹深浅",
    "缺页", "缺角", "涂改", "折痕", "破损", "磨损", "水渍", "霉斑", "虫蛀",
    "撕破", "没署名", "没有署名", "没标注", "没有标注", "代笔", "责任人",
)
# A `known_to` this wide turns a leaked state into a shared conclusion.
_WIDE_KNOWN_TO = 5


def concept_state_warnings(world_root: str | Path) -> list[str]:
    """Ticket 62 (non-blocking): a concept whose `desc` states a status or a
    conclusion while its `known_to` hands that line to many actors.

    The fix has two halves that must both hold: write only the identity into
    `desc`, and let whoever reads / is shown / is told the source obtain the
    state (ticket 49). This warns when only the first half is missing — a
    state word still sits in a desc delivered to at least `_WIDE_KNOWN_TO`
    actors — so a human confirms whether the conclusion is really shared.
    Returns warning lines for the non-blocking channel (never a finding).
    """
    pack = load_world_pack(Path(world_root))
    warnings: list[str] = []
    for concept in pack.concepts:
        hit = next((word for word in _CONCEPT_STATE_WORDS if word in concept["desc"]), None)
        if hit is None or len(concept["known_to"]) < _WIDE_KNOWN_TO:
            continue
        warnings.append(
            f"concept {concept['id']}: desc 含状态/结论词 {hit!r} 而 known_to 列了 "
            f"{len(concept['known_to'])} 人 — 这等于把结论发给多人：desc 只写「这是什么」，"
            "细节应由读到/被展示/被告知获得（ticket 49）；确认这份结论确实众知，否则收窄。")
    return warnings


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


def contact_symmetry_warnings(world_root: str | Path) -> list[str]:
    """Ticket 66: advisory one-way address books (never block).

    If A can message B, B's address book should carry A, or the one-way must
    be intended. The kernel lets B reply only to a contact (or a co-located
    person), so an unrecorded sender leaves B able to receive but unable to
    answer the artifact's 宿管阿姨/下棋大爷 exchange. This lists each A→B
    without B→A so the author can fix the seed or say why it is one-way;
    remote actors (no campus presence/comms) are exempt.
    """
    try:
        pack = load_world_pack(Path(world_root))
    except ValueError:
        return []
    pairs = {(str(actor), str(row["of"]))
             for actor, rows in pack.contacts.items() for row in rows}
    remote = {str(row["id"]) for row in pack.actors if row.get("remote")}
    one_way = sorted((a, b) for a, b in pairs
                     if (b, a) not in pairs and a not in remote and b not in remote)
    if not one_way:
        return []
    listed = "、".join(f"{a}→{b}" for a, b in one_way)
    return [f"contact asymmetry (ticket 66): {listed}"
            "（A 能给 B 发消息而 B 的通讯录里没有 A；若非有意单向，补一条 contact "
            "或在 B 的行里说明为何单向）"]


# ---------------------------------------------------------------------------
# Ticket 78: 种子契约四门（G1 施动者绑定 / G2 角色名词 / G3 可达性 / G4 动作覆盖）
#
# 上面那套契约问“这个名字能不能解析”；四门问“世界能不能兑现作者写的事”。
# 四门只读种子，不改世界包，也不替作者做决定：每条违规给出所在行与两条合法改法。
# 名字解析契约与四门分成两条通道（main() 同时跑、都判失败），因为二者的历史
# 各自可核：前者防“提到一个不存在的东西”，后者防“写下一件世界做不到的事”。
# ---------------------------------------------------------------------------

# G1/G2 的角色类名词（后缀表）。一个作者写下的“谁在做什么”，若这个“谁”不是一个
# 真实演员，世界就无法让这件事发生（G1）；若它连注册名都不是，读到它的人也没有任何
# 可解析的东西（G2）。词表是受控的，不做逐名词 NLP：
# 只收“以职务/身份指人”的词，亲属称谓（爷爷/儿子）和泛称（同学/老人）不收——
# 后者会把大半篇散文都点成违规，把门变成噪音。
_ROLE_NOUNS: tuple[str, ...] = (
    "值班干事", "干事", "值班员", "值班人", "值班学生", "值班同学", "宿管阿姨",
    "宿管助理", "值班宿管助理", "食堂大妈", "老板娘", "店员", "兼职店员",
    "管理员", "馆员", "学生馆员", "编辑", "记者", "代表", "老师", "师傅",
    "保安", "科员", "主任", "负责人", "班长", "辅导员", "主席", "学姐",
    "学长", "阿姨", "大爷", "大妈", "大叔", "大姐",
)
# 施动线索：角色词之后、同一个分句里出现这些动词，才算“某人在做某事”。
_AGENT_VERBS: tuple[str, ...] = (
    "把", "说", "按", "递", "交", "送", "打", "来", "去", "走", "叫", "问",
    "拿", "摊", "核", "签", "通", "拒", "收", "进", "出", "站", "坐", "带",
    "拦", "催", "翻", "贴", "挂", "查", "看", "喊", "跑", "举", "搬", "抬",
    "念", "写", "听", "返岗", "值班", "当班", "盘点", "答应", "通知", "报备",
    "解释", "交代",
)
# G1 的第三条合法路：可观测缺席写法——种子不声称有人在场执行，而是说清这个人不在。
_ABSENCE_FORMS: tuple[str, ...] = (
    "请假", "不在", "缺席", "没来", "未到", "没到", "离校", "外出", "下班",
    "回老家", "未见", "已离",
)
# “不代表你已到场”里的“代表”是动词：前面的否定/助动词把它从人名挡回动词。
_VERB_PREFIX_CHARS = frozenset("不没未别可能要想敢需用来代被让给")
# 引号内是某个已建模角色说的话（转述），不是世界的客观陈述：G1 只看引号外。
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"|“[^”]*”|「[^」]*」|‘[^’]*’")
_CLAUSE_BREAK_RE = re.compile(r"[。，；！？：\n]|——")
_ROLE_PROSE_KEY = "role_prose"

# G4：需要交互才能兑现的概念（受控词表 + 号码）。正文提到它，就等于向角色承诺了
# 一次动作；而引擎的动作目标只有既有几类：read 的目标是文书（kernel.py:728），
# “看见/拿”的对象是 items（描述走知觉），去的地方是可达 locations（G3），联系的
# 对象是 actors 或 KB 联系人行。词表因此必须落到这几类上，不许自创新的概念类别。
_INTERACTION_KINDS: dict[str, tuple[str, ...]] = {
    "read": ("公告栏", "布告栏", "通告栏", "告示栏", "黑板报", "排班表", "值班表", "价目表"),
    "examine": ("热水壶", "饮水机", "关东煮", "冰柜", "货架", "柜台", "储物柜",
                "信箱", "售货机", "例汤", "菜牌", "菜谱"),
    "call": ("电话", "内线", "热线", "总机", "分机"),
}
# 一个“打电话”的提法只有在同一分句里带拨打/报备线索时才算承诺了一条通信路径；
# 否则“妈妈来电话”这类叙述会被整篇误点。
_CALL_CUES: tuple[str, ...] = ("拨", "打", "致电", "报备", "热线", "号码", "总机", "分机")
_PHONE_NUMBER_RE = re.compile(r"(?<![\d\-])\d{5,}(?![\d\-])")
# G3 第二臂：正文要角色“去”的地方。引擎的 move 目标只能是注册地点，所以这类
# 提法必须落到一个有路由的 location 上；一个只有概念（kind: place）却没有 location
# 与路的地方，角色永远走不到（票 78：后街糕点铺）。
_DESTINATION_CUES: tuple[str, ...] = ("去", "回", "前往", "走去", "赶往", "走进", "直奔")
_INTERACTION_LABELS: dict[str, str] = {
    "read": "读",
    "examine": "看见/拿",
    "call": "联系",
}
_INTERACTION_FIXES: dict[str, str] = {
    "read": ("read 的目标只能是文书：把它登记成 documents: 条目（给 title/content/"
             "location，正文就是张贴或写在上面的内容），或者把这句话改成不承诺可读"),
    "examine": ("能被看见/拿取的东西必须是 items: 条目（带 location 与 known_to；"
                "描述走知觉与 observed），或者把这句话改成不承诺可以查看/取用"),
    "call": ("要联系的对象必须是 actors: 里的角色，或在某角色的 KB 里有一条联系人行"
             "（contacts:），否则角色拨打时世界没有可回应的对方"),
}


class _Authored(NamedTuple):
    """一段模型会看到的作者正文，以及它所属的行。行上的 `role_prose:` 就是
    “这些角色词在本行是泛称集合”的声明。

    用 NamedTuple 而不是 dataclass：测试按既有习惯以 importlib 在没有登记
    sys.modules 的模块里执行本文件，py3.14 的 dataclass 会因此取不到模块字典。"""

    source: str
    label: str
    section: str
    key: str
    text: str
    generic: tuple[str, ...] = ()


def _generic_declaration(row: object) -> tuple[str, ...]:
    """行上的 `role_prose:` 声明：本行的角色词是泛称集合，不是具体某人。"""
    if not isinstance(row, dict):
        return ()
    raw = row.get(_ROLE_PROSE_KEY)
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(token).strip() for token in raw if str(token).strip())


def _authored_texts(pack, root: Path) -> list[_Authored]:
    """作者正文的单一口径：排程通知、概念 desc/memory、kb 行、item/document 正文、
    地点 rules 与 extras 注记，以及 characters|items|documents|locations|
    organizations 的 .md 正文。G2 与 G4 共用这一份语料，两门就不会各扫一套。"""
    manifest = pack.manifest
    rows: dict[str, dict[str, object]] = {}
    for section in ("locations", "actors", "items", "documents"):
        for row in manifest.get(section, ()) or ():
            rows.setdefault(str(row.get("id")), row)
    texts: list[_Authored] = []

    def add(source: str, label: str, section: str, key: object, text: object,
            row: object = None) -> None:
        body = str(text)
        if not body.strip():
            return
        texts.append(_Authored(source, label, section, str(key), body,
                               _generic_declaration(row)))

    for row in manifest.get("scheduled", ()) or ():
        add("manifest.yml", f"scheduled {row.get('event')}", "scheduled",
            row.get("event"), row.get("notice", ""), row)
    for row in manifest.get("concepts", ()) or ():
        label = f"concept {row.get('id')}"
        add("manifest.yml", f"{label} desc", "concepts", row.get("id"),
            row.get("desc", ""), row)
        for owner, memory in (row.get("memory") or {}).items():
            add("manifest.yml", f"{label} memory[{owner}]", "concepts",
                row.get("id"), memory, row)
    for actor, kb_rows in (manifest.get("kb") or {}).items():
        for index, row in enumerate(kb_rows or (), 1):
            keys = sorted(str(key) for key in (row.get("keys") or ()))
            add("manifest.yml", f"kb[{actor}] {keys}", "kb", f"{actor}#{index}",
                row.get("desc", ""), row)
    for section in ("items", "documents"):
        for row in manifest.get(section, ()) or ():
            entity = str(row.get("id"))
            for field in ("content", "desc"):
                add("manifest.yml", f"{section[:-1]} {entity} {field}", section,
                    entity, row.get(field, ""), row)
    for row in manifest.get("locations", ()) or ():
        place = str(row.get("id"))
        for index, rule in enumerate(row.get("rules", ()) or ()):
            add("manifest.yml", f"location {place} rules[{index}]", "locations",
                place, rule, row)
        for extra in row.get("extras", ()) or ():
            # fragment 本身就是“这个地点常出现的陌生人”的声明，不扫；注记扫。
            add("manifest.yml", f"location {place} extras knowledge_notes",
                "locations", place, extra.get("knowledge_notes", ""), row)
    for pattern in ("characters/*.md", "items/*.md", "documents/*.md",
                    "locations/*.md", "organizations/*.md"):
        for path in sorted(root.glob(pattern)):
            relative = str(path.relative_to(root))
            add(relative, relative, "", path.stem,
                path.read_text(encoding="utf-8"), rows.get(path.stem))
    return texts


def _blank_quotes(text: str) -> str:
    """引号里的话是某个角色的转述，不是世界的客观陈述。"""
    return _QUOTED_RE.sub(lambda match: "\u0001" * len(match.group(0)), text)


def _mask_names(text: str, names: set[str] | frozenset[str]) -> str:
    """把已解析的名字整段吃掉，只剩没被任何名字覆盖的文本。"""
    body = text
    for name in sorted(names, key=len, reverse=True):
        if len(name) >= 2:
            body = body.replace(name, "\u0002" * len(name))
    return body


def _clause_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """包含 [start, end) 的分句边界。"""
    left = 0
    for match in _CLAUSE_BREAK_RE.finditer(text[:start]):
        left = match.end()
    right = len(text)
    for match in _CLAUSE_BREAK_RE.finditer(text, end):
        right = match.start()
        break
    return left, right


def _role_hits(body: str) -> list[tuple[int, str]]:
    """角色词的位置与词本身，长词优先（值班干事吃掉底下的干事）。"""
    hits: list[tuple[int, str]] = []
    for token in _ROLE_NOUNS:
        start = body.find(token)
        while start >= 0:
            hits.append((start, token))
            start = body.find(token, start + len(token))
    hits.sort(key=lambda hit: (hit[0], -len(hit[1])))
    kept: list[tuple[int, str]] = []
    for position, token in hits:
        if kept and position < kept[-1][0] + len(kept[-1][1]):
            continue
        kept.append((position, token))
    return kept


def bare_role_tokens(text: str, declared: set[str]) -> list[str]:
    """G2：正文里既没注册、也不被任何注册名覆盖的角色类名词。

    否定/助动词前面的“代表/负责”是动词（“不代表你已到场”），不是人在做事。"""
    body = _mask_names(strip_refs(text), declared)
    tokens: list[str] = []
    for position, token in _role_hits(body):
        if position and body[position - 1] in _VERB_PREFIX_CHARS:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _acting_role_tokens(text: str, bound: set[str]) -> list[str]:
    """G1：在排程通知里“做某事”的角色类名词。

    只把真实演员从正文里抹掉，其余角色词都保留——注册成概念并不等于世界有人能兑现
    它（这正是 G1 比 G2 严的地方）。"""
    body = _mask_names(_blank_quotes(strip_refs(text)), bound)
    tokens: list[str] = []
    for position, token in _role_hits(body):
        end = position + len(token)
        left, right = _clause_bounds(body, position, end)
        clause = body[left:right]
        if any(form in clause for form in _ABSENCE_FORMS):
            continue  # 可观测缺席写法：不声称有人在场执行
        if position and body[position - 1] in _VERB_PREFIX_CHARS:
            continue  # “不代表你已到场”里的“代表”是动词
        if not any(verb in body[end:right] for verb in _AGENT_VERBS):
            continue
        tokens.append(token)
    return tokens


def _bound_agents(pack) -> set[str]:
    """一条排程能兑现的施动者：真实演员。

    地点 extras 的 fragment 不算——“这个地点常出现的陌生人”由引擎按需临时邀请，
    没有在场保证、没有库存、也不会把一个结果留在现场，承担不了广播里的一件事。
    票 77b 已裁定这条编码：事件宿主是既有 `actors:` 行（V4-CAST §1 NPC 层），
    不新增原语。"""
    return {str(actor["id"]) for actor in pack.actors}


def schedule_agent_findings(pack, root: Path) -> list[str]:
    """G1 施动者绑定：排程通知里“某人做某事”的人必须是一个真实演员。

    排程通知是世界的客观陈述、广播给所有人；它一旦说“值班干事把审计包摊开核对”，
    世界就得真有这个人做得成这件事。把名字注册成概念不算（概念没有双手），地点
    extras 也不算（见 :func:`_bound_agents`）。合法的两条路是绑定既有 actor，
    或把这件事写成可观测的缺席。
    """
    findings: list[str] = []
    rows = _manifest_rows(root)
    declared = _declared(pack)
    bound = _bound_agents(pack)
    for row in pack.manifest.get("scheduled", ()) or ():
        event = str(row.get("event"))
        notice = str(row.get("notice", ""))
        if not notice.strip():
            continue
        for token in sorted(set(_acting_role_tokens(notice, bound))):
            findings.append(
                f"G1 {_row_line(rows, 'scheduled', event, token, declared)}: "
                f"scheduled {event}: 施动者 {token!r} 没绑定任何演员 —— "
                f"排程通知是客观陈述，{token} 做的事必须有人真的能做："
                f"① 把这句的主语换成 actors: 里的真实角色（事件宿主就是既有 actor，"
                f"票 77b）；② 或改用可观测缺席写法（{token}不在/请假/没来），"
                "不声称有人在场执行；地点 extras 不算绑定（临时邀请的陌生人，"
                "没有在场保证、库存与留痕）")
    return findings


def role_prose_findings(pack, root: Path) -> list[str]:
    """G2 角色名词扫描：正文里的角色类名词要么是注册名，要么在本行声明为泛称。"""
    declared = _declared(pack)
    rows = _manifest_rows(root)
    findings: list[str] = []
    for text in _authored_texts(pack, root):
        for token in bare_role_tokens(text.text, declared):
            if any(token in generic or generic in token for generic in text.generic):
                continue
            findings.append(
                f"G2 {_text_line(root, rows, text, token, declared)}: {text.label}: 角色类名词 "
                f"{token!r} 既没注册，也没声明是泛称 —— 二选一："
                f"① 注册成概念并在正文里写成 [[{token}]]"
                f"（kind: person 是具体某人，kind: generic 是“谁都可以”的泛称）；"
                f"② 在本行的 {_ROLE_PROSE_KEY}: 里声明它是泛称集合"
                f"（{_ROLE_PROSE_KEY}: [{token}]），表示这个人不是具体某人")
    return findings


def _route_graph(pack) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {str(row["id"]): set() for row in pack.locations}
    for row in pack.routes:
        graph.setdefault(str(row["from"]), set()).add(str(row["to"]))
    return graph


def _walk_from(graph: dict[str, set[str]], start: str) -> set[str]:
    seen = {start}
    pending = [start]
    while pending:
        for neighbour in graph.get(pending.pop(), ()):
            if neighbour not in seen:
                seen.add(neighbour)
                pending.append(neighbour)
    return seen


def _mc_reachability(pack) -> dict[str, set[str]]:
    """每个 MC 从自己出发点按路由图能走到的地点集合。"""
    graph = _route_graph(pack)
    starts = sorted({str(row["location"]) for row in pack.actors
                     if str(row.get("role", "mc")) == "mc"})
    starts = starts or sorted({str(row["location"]) for row in pack.actors})
    return {start: _walk_from(graph, start) for start in starts}


def _reachable_locations(pack) -> set[str]:
    reachable: set[str] = set()
    for seen in _mc_reachability(pack).values():
        reachable |= seen
    return reachable


def _entity_paths(pack) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(实体 -> 出现过的地点, 实体 -> 携带它的角色)。开局位置、背包与排程投放
    都算“出现过的地点”，所以一个今天才被放进档案室的册子也有路径。"""
    places: dict[str, set[str]] = {}
    carriers: dict[str, set[str]] = {}
    location_ids = {str(row["id"]) for row in pack.locations}
    for kind in ("items", "documents"):
        for row in getattr(pack, kind):
            entity = str(row["id"])
            places.setdefault(entity, set())
            carriers.setdefault(entity, set())
            if row.get("location") is not None:
                places[entity].add(str(row["location"]))
    for row in pack.actors:
        for item in row.get("inventory", ()):
            carriers.setdefault(str(item), set()).add(str(row["id"]))
    for row in pack.scheduled:
        for effect in row.get("effects", ()) or ():
            if not isinstance(effect, dict):
                continue
            place = str(effect.get("location"))
            if (str(effect.get("op", "")) in {"add_item", "add_document", "move_item"}
                    and place in location_ids):
                places.setdefault(str(effect.get("id")), set()).add(place)
    return places, carriers


def _has_a_path(entity: str, places: dict[str, set[str]], carriers: dict[str, set[str]],
                reachable: set[str], actor_places: dict[str, str]) -> bool:
    if any(place in reachable for place in places.get(entity, ())):
        return True
    return any(actor_places.get(actor) in reachable
               for actor in carriers.get(entity, ()))


def destination_findings(pack, root: Path) -> list[str]:
    """G3 第二臂：正文要角色“去”的地方必须是一个注册 location（有路由）。

    引擎的 move 目标只能是 locations（G3 第一臂保证它可达）。一个地方若只作为
    `kind: place` 的概念存在——后街糕点铺——角色会被常驻任务派去，却得到一个
    “不是一个你知道的地方”的拒绝，而且没有任何人能指路（票 78 报告 §2.4-2）。
    远程地点（remote: true）是种子显式声明的“只通电话”，不算漏。"""
    places = {concept["name"] for concept in pack.concepts if concept["kind"] == "place"}
    places.update(alias for concept in pack.concepts if concept["kind"] == "place"
                  for alias in concept["aliases"])
    location_ids = {str(row["id"]) for row in pack.locations}
    places -= location_ids
    if not places:
        return []
    findings: list[str] = []
    declared = _declared(pack)
    rows = _manifest_rows(root)
    for text in _authored_texts(pack, root):
        body = strip_refs(text.text)
        for name in sorted(places, key=len, reverse=True):
            for cue in _DESTINATION_CUES:
                start = body.find(cue + name)
                if start < 0:
                    continue
                findings.append(
                    f"G3 {_text_line(root, rows, text, name, declared)}: {text.label}: "
                    f"正文派角色去 {name!r}，但它只是一个 kind: place 的概念，"
                    "不是注册地点、也没有路由 —— 要么把它注册成 locations: 行并加"
                    "双向 routes，要么把这句话改成不需要走过去（电话/托人带话），"
                    "或删掉这条派工")
                break
    return findings


def reachability_findings(pack, root: Path) -> list[str]:
    """G3 可达性：每个注册地点、每件注册物件都得有一条走得通的获取/读取路径。

    远程地点（`remote: true`，只通电话/消息）本身就是“走不到”，由种子显式声明，
    故不按步行判；但放在那里的物件没有路径，照样要报。"""
    findings: list[str] = []
    per_mc = _mc_reachability(pack)
    reachable = _reachable_locations(pack)
    for row in pack.locations:
        place = str(row["id"])
        if row.get("remote"):
            continue
        lost = [start for start, seen in per_mc.items() if place not in seen]
        if lost:
            findings.append(
                f"G3 location {place}: 路由图上从 MC 出发点 {'、'.join(lost)} 都走不到 —— "
                f"加一条双向 routes: `- {{from: 已有地点, to: {place}, "
                "duration_seconds: N}}` 与反向，或把它声明成 remote: true"
                "（仅电话/消息可达），或从种子里删掉")
    places, carriers = _entity_paths(pack)
    actor_places = {str(row["id"]): str(row["location"]) for row in pack.actors}
    for kind in ("items", "documents"):
        for row in getattr(pack, kind):
            entity = str(row["id"])
            if row.get("completeness") in _COMPLETENESS_STATES:
                continue  # expectation/belief/missing：作者已声明它此刻不在手上
            if _has_a_path(entity, places, carriers, reachable, actor_places):
                continue
            where = sorted(places.get(entity, ())) or sorted(carriers.get(entity, ()))
            findings.append(
                f"G3 {kind[:-1]} {entity}: 没有任何走得通的获取/读取路径"
                f"（出现在 {where or '无处'}）—— 放在可达地点、放进可达角色的 "
                "inventory、用 scheduled 的 add_item/add_document 投放到可达地点，"
                "或在该行声明 completeness: expectation/belief/missing")
    findings.extend(destination_findings(pack, root))
    return findings


def _contact_targets(pack) -> set[str]:
    """正文可以要求角色去“联系”的对象：actors 的名字，以及每个角色 KB 里那条
    联系人行的对方与别名（contacts:，加载时展开成 !contact 行）。"""
    targets = {str(row["id"]) for row in pack.actors}
    for rows in pack.contacts.values():
        for row in rows:
            targets.add(str(row["of"]))
            targets.update(str(alias) for alias in row.get("as", ()))
    return targets


def _interaction_mentions(text: str) -> list[tuple[str, str, str]]:
    """(交互类别, 概念词, 所在分句) —— 正文向角色承诺的交互。

    ``read``/``examine`` 按受控词表匹配；“打电话”只有同一分句里带拨打/报备线索
    才算承诺了一条通信路径（否则“妈妈来电话”这类叙述会被整篇误点），号码按字面
    取出。"""
    body = strip_refs(text)
    mentions: list[tuple[str, str, str]] = []
    for kind, nouns in _INTERACTION_KINDS.items():
        for noun in nouns:
            for match in re.finditer(re.escape(noun), body):
                left, right = _clause_bounds(body, match.start(), match.end())
                clause = body[left:right]
                if kind == "call" and not any(cue in clause for cue in _CALL_CUES):
                    continue
                mentions.append((kind, noun, clause))
                break
    for number in _PHONE_NUMBER_RE.findall(body):
        position = body.find(number)
        left, right = _clause_bounds(body, position, position + len(number))
        mentions.append(("call", number, body[left:right]))
    return mentions


def interaction_findings(pack, root: Path) -> list[str]:
    """G4 动作覆盖：正文要角色去交互的东西，必须落在既有的动作目标类上。

    引擎只有几类目标，正文不能凭空多要一类：``read`` 的目标是文书
    （:meth:`harness.kernel.World._available_readables`，即 documents 与带 content
    的 items），被看见/拿取的东西必须是 items（描述走知觉与 observed），去的地方是
    可达 locations（G3 判），联系的对象是 actors 或 KB 联系人行。正文提到一个“需要
    交互”的东西却不属于任何既有类别，就是角色会反复追问路人、世界答不出来的那一族。
    匹配用整名（不吃子串）：一锅关东煮不是“一碗关东煮”，货架也不是货架上的货。"""
    findings: list[str] = []
    reachable = _reachable_locations(pack)
    places, carriers = _entity_paths(pack)
    actor_places = {str(row["id"]): str(row["location"]) for row in pack.actors}

    def reachable_names(names: set[str]) -> set[str]:
        return {name for name in names
                if _has_a_path(name, places, carriers, reachable, actor_places)}

    declared = _declared(pack)
    readable = reachable_names(
        {str(row["id"]) for row in pack.documents}
        | {str(row["id"]) for row in pack.items
           if str(row.get("content", "")).strip() and row.get("readable") is not False})
    examinable = reachable_names({str(row["id"]) for row in pack.items})
    contacts = _contact_targets(pack)

    rows = _manifest_rows(root)
    for text in _authored_texts(pack, root):
        for kind, token, clause in _interaction_mentions(text.text):
            if kind == "read" and token in readable:
                continue
            if kind == "examine" and token in examinable:
                continue
            if kind == "call" and any(target in clause for target in contacts):
                continue
            findings.append(
                f"G4 {_text_line(root, rows, text, token, declared)}: {text.label}: 正文提到 "
                f"{token!r}，等于要求角色去「{_INTERACTION_LABELS[kind]}」它，"
                f"但它不属于任何一种既有动作目标 —— {_INTERACTION_FIXES[kind]}")
    return findings


def contract_gate_findings(world_root: str | Path) -> list[str]:
    """Ticket 78 的四门：G1 施动者绑定 / G2 角色名词 / G3 可达性 / G4 动作覆盖。

    与 :func:`lint` 分开成一条通道：`lint` 判“名字是否可解析”，四门判“世界能不能
    兑现作者写下的事”。CLI 同时跑两条通道并都判失败——预跑门禁因此一条命令生效。"""
    root = Path(world_root)
    try:
        pack = load_world_pack(root)
    except ValueError as exc:
        return [f"world pack violates the seed contract: {exc}"]
    findings: list[str] = []
    findings.extend(schedule_agent_findings(pack, root))
    findings.extend(role_prose_findings(pack, root))
    findings.extend(reachability_findings(pack, root))
    findings.extend(interaction_findings(pack, root))
    return findings


# --- 违规坐标：只为把违规指到行上，不参与任何判定 -------------------------------
_TOP_LEVEL_KEY_RE = re.compile(r"^([a-z_]+):\s*$")
_ROW_ANCHOR_RE = re.compile(r"^- (?:id|event):\s*(?P<value>.+?)\s*$")
_KB_ANCHOR_RE = re.compile(r"^  (\S+):\s*$")
_ANCHOR_SECTIONS = frozenset({"locations", "actors", "items", "documents",
                              "scheduled", "concepts", "kb"})


class _ManifestRow(NamedTuple):
    """manifest.yml 的一行及其所属的行首：只为把违规指到行上，不参与判定。"""

    section: str
    key: str
    row_start: int
    line_number: int
    line: str


def _manifest_rows(root: Path) -> list[_ManifestRow]:
    path = root / "manifest.yml"
    if not path.is_file():
        return []
    rows: list[_ManifestRow] = []
    current: tuple[str, str, int] | None = None
    section = ""
    kb_actor = ""
    kb_index = 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        top = _TOP_LEVEL_KEY_RE.match(line)
        if top:
            section = top.group(1)
            current = None
            continue
        anchor = _ROW_ANCHOR_RE.match(line)
        key = anchor.group("value").strip("'\"") if anchor else ""
        if not anchor and section == "kb":
            kb = _KB_ANCHOR_RE.match(line)
            if kb:
                kb_actor = kb.group(1)
                kb_index = 0
                current = ("kb", f"{kb_actor}#0", number)
                rows.append(_ManifestRow(*current, number, line))
                continue
            if line.startswith("  - "):
                kb_index += 1
                current = ("kb", f"{kb_actor}#{kb_index}", number)
                rows.append(_ManifestRow(*current, number, line))
                continue
        if anchor and section in _ANCHOR_SECTIONS:
            current = (section, key, number)
            rows.append(_ManifestRow(*current, number, line))
            continue
        if current is not None:
            rows.append(_ManifestRow(*current, number, line))
    return rows


def _row_line(rows: list[_ManifestRow], section: str, key: str, needle: str,
              declared: set[str]) -> str:
    """某个 manifest 行里出现 needle 的行号（找不到就回到该行的行首）。

    kb 的一个角色下面有多行，所以先按行首分组：命中在哪一组的哪一行就说哪一行。
    注册名先抹掉——“下棋大爷”坐在 known_to 里不算正文提到了“大爷”。"""
    spans: dict[int, list[_ManifestRow]] = {}
    for row in rows:
        if row.section == section and row.key == key:
            spans.setdefault(row.row_start, []).append(row)
    for group in spans.values():
        for row in group:
            if needle in _mask_names(strip_refs(row.line), declared):
                return f"manifest.yml:{row.line_number}"
    if spans:
        return f"manifest.yml:{next(iter(spans))}"
    return "manifest.yml"


def _text_line(root: Path, rows: list[_ManifestRow], text: _Authored,
               needle: str, declared: set[str]) -> str:
    """一段作者正文在源文件里的行号：manifest 按所属行定位，.md 按“没被注册名
    覆盖的那一处”定位（标题里的名字不算——它是定义，不是正文提到的人）。"""
    if text.source == "manifest.yml":
        return _row_line(rows, text.section, text.key, needle, declared)
    path = root / text.source
    if path.is_file():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if needle in _mask_names(strip_refs(line), declared):
                return f"{text.source}:{number}"
    return text.source


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
    contract = contract_gate_findings(args.world)
    try:
        warnings = collision_warnings(args.world)
    except ValueError:
        warnings = []
    try:
        warnings.extend(document_state_warnings(args.world))
    except ValueError:
        pass
    try:
        warnings.extend(concept_state_warnings(args.world))
    except ValueError:
        pass
    try:
        warnings.extend(contact_symmetry_warnings(args.world))
    except ValueError:
        pass
    for note in warnings:
        print(f"warning: {note}")
    if args.verbose:
        for note in dead_aliases(args.world):
            print(f"note: {note}")
    if findings:
        print(f"seed lint FAILED ({len(findings)} unregistered name(s)):")
        for finding in findings:
            print("  " + finding)
    if contract:
        print(f"seed contract FAILED ({len(contract)} violation(s), G1-G4):")
        for finding in contract:
            print("  " + finding)
    if findings or contract:
        return 1
    print("seed lint OK: every named thing resolves to an entity or concept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
