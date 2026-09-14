"""Per-actor private notebook: key-set rows and one text matcher.

A row is ``{keys: frozenset[str], desc, status}`` (V4-AGENT-INTERFACE §3/§6).
The key set is the row's identity *and* its match mechanism:

- text keys are mention needles — the row surfaces when any needle appears in
  what the actor is currently reading/saying/hearing (``any(k in q)``);
- directive keys (``!`` prefix) carry engine semantics instead of matching:
  ``!always`` = unconditional interval bringup, ``!at=<M/D(周X) HH:MM>`` =
  scheduled bringup + force-interrupt.

There are no ids and no ``person/location/item`` match types: ``recall``,
``flashback`` and ambient replay all call the same :func:`hits`. Keys are
immutable; changing them means close + open.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import itertools
import re
from typing import Any

ALWAYS_REPLAY_MINUTES = 60
SCHEDULED_REPLAY_MINUTES = 30
KNOWLEDGE_REPLAY_MINUTES = 120
ALWAYS_OPEN_LIMIT = 12

# Backwards-compatible names used by older call sites/tests.
TODO_REPLAY_MINUTES = ALWAYS_REPLAY_MINUTES
REMINDER_REPLAY_MINUTES = SCHEDULED_REPLAY_MINUTES
TODO_OPEN_LIMIT = ALWAYS_OPEN_LIMIT

ALWAYS_KEY = "!always"
CONTACT_KEY = "!contact"
_AT_PREFIX = "!at="
_DIRECTIVE = "!"
_MIN_KEY_CHARS = 2
_KNOWN_DIRECTIVES = frozenset({ALWAYS_KEY, CONTACT_KEY})

_WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}
_WEEKDAY_CHAR = {v: k for k, v in _WEEKDAY.items()}
_REMINDER_RE = re.compile(r"^(\d{1,2})/(\d{1,2})\((周[一二三四五六日])\) (\d{1,2}):(\d{2})$")

# Characters neutral to matching: Chinese particles, whitespace, and the
# punctuation that separates names in prose. Removing them on both sides makes
# 「陈默的爸爸」/「陈默爸爸」 and 「老家属院地下室」/「老家属院的地下室」 equivalent
# without asking the model to write globs.
_NEUTRAL = str.maketrans("", "", "的之\x00 \t\r\n，。、；：！？（）【】《》"
                                "\u201c\u201d\u2018\u2019…—－-·／/")


def normalize(text: Any) -> str:
    return str(text).translate(_NEUTRAL)


def key_id(keys: Any) -> str:
    """Canonical string form of a key set (checkpoints, kernel job handles)."""
    return "|".join(sorted(str(k) for k in keys))


def parse_reminder_time(value: Any, now: datetime) -> datetime | None:
    """Strict reminder parsing (m7): 'M/D(周X) HH:MM' or ISO datetime.

    Returns None when unparseable or when the named weekday contradicts the
    date. A naive result inherits ``now``'s tzinfo.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    parsed: datetime | None = None
    match = _REMINDER_RE.match(text)
    if match:
        month, day, weekday, hour, minute = match.groups()
        try:
            candidate = datetime(now.year, int(month), int(day), int(hour), int(minute))
        except ValueError:
            return None
        if candidate.weekday() != _WEEKDAY[weekday[-1]]:
            return None
        parsed = candidate
    else:
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None and now.tzinfo is not None:
        parsed = parsed.replace(tzinfo=now.tzinfo)
    return parsed


def format_reminder_time(when: datetime) -> str:
    return (f"{when.month}/{when.day}(周{_WEEKDAY_CHAR[when.weekday()]}) "
            f"{when.hour:02d}:{when.minute:02d}")


def render_key(key: str, at: datetime | None) -> str:
    if at is not None and key.startswith(_AT_PREFIX):
        return f"{_AT_PREFIX}{format_reminder_time(at)}"
    return key


def hits(keys: Any, queries: Any) -> bool:
    """One matcher for replay, recall and flashback (V4-AGENT-INTERFACE §3).

    True when any text key is a substring of any query, or vice versa (the
    reverse direction lets a short query such as 「2013年台风」 reach the longer
    key 「2013年台风夜」). Directive keys are not needles.
    """
    needles = [normalize(k) for k in keys if not str(k).startswith(_DIRECTIVE)]
    if not needles:
        return False
    for query in queries:
        text = normalize(query)
        if not text:
            continue
        for needle in needles:
            if needle and (needle in text or text in needle):
                return True
    return False


def resolve_name(query: Any, candidates: Any) -> tuple[str | None, str | None]:
    """Resolve a name-bearing argument against a candidate set (T4 裁决).

    Same normalization as :func:`hits`; **exact-first** so a call that works
    today (``text {target: 陈默}``) never becomes ambiguous just because other
    candidates contain it as a substring. Returns ``(resolved, note)``:

    - exact hit                     -> (name, None)
    - one fuzzy hit                 -> (name, warning line teaching the form)
    - several fuzzy hits            -> (None, ambiguity listing candidates)
    - no hit                        -> (None, rejection listing what's available)

    The caller turns ``note`` into a rejection or appends it to the tool result.
    """
    text = normalize(query)
    if not text:
        return None, "empty name"
    names = [str(c) for c in candidates if str(c).strip()]
    for name in names:
        if normalize(name) == text:
            return name, None
    fuzzy = [name for name in names
             if hits([name], [text]) or hits([text], [name])]
    if len(fuzzy) == 1:
        return fuzzy[0], (f"resolved '{query}' to '{fuzzy[0]}' by fuzzy match — "
                          f"use the exact name next time")
    if len(fuzzy) > 1:
        listed = " / ".join(sorted(fuzzy)[:6])
        return None, f"ambiguous name '{query}': {listed}"
    available = " / ".join(sorted(names)[:8]) if names else "(none)"
    return None, f"unknown name '{query}'; available: {available}"


def matched_span(keys: Any, queries: Any) -> int:
    """Longest text key matching any query — replay priority ('highest match')."""
    needles = [normalize(k) for k in keys if not str(k).startswith(_DIRECTIVE)]
    best = 0
    for query in queries:
        text = normalize(query)
        if not text:
            continue
        for needle in needles:
            if needle and (needle in text or text in needle):
                best = max(best, len(needle))
    return best


def _row_keys(entry: dict[str, Any], *, legacy: bool = False) -> list[str]:
    """Normalize a row into a key list.

    The current shape is ``keys: [...]``. The legacy ``fields`` mapping is read
    only when ``legacy=True`` — i.e. when restoring a pre-migration checkpoint;
    seeds and ``update_memory`` must speak the key-set model and nothing else.
    """
    if "keys" in entry:
        return [str(k).strip() for k in entry["keys"]]
    if not legacy:
        return []
    keys: list[str] = []
    for name, value in (entry.get("fields") or {}).items():
        if isinstance(value, bool):
            if name == "todo" and value:
                keys.append(ALWAYS_KEY)
            continue
        if name == "reminder":
            if isinstance(value, str) and value.strip():
                keys.append(f"{_AT_PREFIX}{value.strip()}")
            continue
        if name == "self":
            continue
        if isinstance(value, str) and value.strip():
            keys.append(value.strip())
    return keys


def _validate_keys(keys: list[str], *, where: str, now: datetime,
                   actor_id: str | None = None) -> str | None:
    if not keys:
        return f"{where}: needs at least one key"
    for key in keys:
        if not key:
            return f"{where}: empty key"
        if key.startswith(_DIRECTIVE):
            if key.startswith(_AT_PREFIX):
                if parse_reminder_time(key[len(_AT_PREFIX):], now) is None:
                    return f"{where}: unparseable scheduled key: {key}"
            elif key not in _KNOWN_DIRECTIVES:
                return f"{where}: unknown directive key: {key}"
        elif len(key) < _MIN_KEY_CHARS and key != actor_id:
            # Short keys match too much; the actor's own identity key is the
            # one legitimate exception (its name may be one character).
            return f"{where}: key too short (min {_MIN_KEY_CHARS} chars): {key!r}"
    return None


@dataclass
class _Row:
    keys: frozenset[str]
    desc: str
    status: str = "open"
    last_shown: datetime | None = None
    shown_seq: int = 0
    at: datetime | None = None
    # Key order as authored: the first text key is the row's label when
    # rendered (concept name first, then aliases). Identity is still the set.
    order: tuple[str, ...] = ()

    @property
    def text_keys(self) -> frozenset[str]:
        return frozenset(k for k in self.keys if not k.startswith(_DIRECTIVE))

    @property
    def always(self) -> bool:
        return ALWAYS_KEY in self.keys

    def render(self) -> str:
        """`[<directives> <label> +N]: desc`. The key set is the row's handle,
        but listing six aliases on every line is noise: the label is the first
        key as authored (concept name for registry rows) and `+N` counts the
        rest. Any single key still addresses the row (fuzzy locate)."""
        ordered = list(self.order) or sorted(self.keys)
        directives = [render_key(k, self.at) for k in ordered if k.startswith(_DIRECTIVE)]
        texts = [k for k in ordered if not k.startswith(_DIRECTIVE)]
        label = directives + texts[:1]
        if len(texts) > 1:
            label.append(f"+{len(texts) - 1}")
        return f"[{' '.join(label) or key_id(self.keys)}]: {self.desc}"


def _make_row(keys: list[str], desc: str, now: datetime) -> _Row:
    order = tuple(dict.fromkeys(keys))
    unique = frozenset(order)
    at = None
    for key in unique:
        if key.startswith(_AT_PREFIX):
            at = parse_reminder_time(key[len(_AT_PREFIX):], now)
    return _Row(unique, desc, at=at, order=order)


class ActorKB:
    """One actor's private KB. Not thread-safe; owned by the engine loop."""

    def __init__(self, actor_id: str, rows: list[dict[str, Any]], now: datetime) -> None:
        self.actor_id = actor_id
        self._now = now
        self._rows: dict[frozenset[str], _Row] = {}
        self._overflow: list[frozenset[str]] = []
        self._pending_recall: list[frozenset[str]] = []
        self._shown_seq = itertools.count(1)
        for entry in rows:
            keys = _row_keys(entry)
            error = _validate_keys(keys, where=f"[{key_id(keys) or '?'}]", now=now,
                                   actor_id=actor_id)
            if error:
                raise ValueError(f"[{actor_id}] seed row {error}")
            row = _make_row(keys, str(entry.get("desc", "")), now)
            if row.keys in self._rows:
                raise ValueError(f"[{actor_id}] duplicate key set: {key_id(row.keys)}")
            self._rows[row.keys] = row
        # Identity anchor (M2 without a magic key): every actor keeps one row
        # keyed by their own name, so the model always has an "I am X" line.
        if not any(actor_id in row.keys for row in self._rows.values()):
            raise ValueError(f"[{actor_id}] no identity row keyed by {actor_id!r}")

    # ------------------------------------------------------------- helpers

    def row_keys(self) -> list[frozenset[str]]:
        return list(self._rows.keys())

    def has_identity(self) -> bool:
        return any(self.actor_id in row.keys for row in self._rows.values())

    def scheduled_rows(self) -> list[_Row]:
        return [row for row in self._rows.values()
                if row.status == "open" and row.at is not None]

    def _open_always(self) -> int:
        return sum(1 for row in self._rows.values()
                   if row.status == "open" and row.always)

    def _locate(self, target: frozenset[str]) -> tuple[_Row | None, str | None, list[str]]:
        """Exact key set, then a unique superset; ambiguity lists candidates."""
        row = self._rows.get(target)
        if row is not None:
            return row, None, []
        candidates = [r for r in self._rows.values()
                      if r.status == "open" and target <= r.keys]
        if len(candidates) == 1:
            return candidates[0], (f"matched by unique subset: "
                                   f"the row's keys are [{sorted(candidates[0].keys)}]"), []
        if len(candidates) > 1:
            listed = " / ".join(str(sorted(r.keys)) for r in candidates[:5])
            return None, None, [f"[{sorted(target)}] is ambiguous; you might mean: {listed}"]
        return None, None, [f"[{sorted(target)}] no match"]

    # ------------------------------------------------------------- mutation

    def apply_ops(self, ops: list[dict[str, Any]], now: datetime
                  ) -> tuple[list[str], dict[str, int], list[str]]:
        """Apply an update_memory patch. Partial success: valid rows apply,
        failures are per-row English errors. Returns (errors, telemetry,
        warnings) — warnings report a fuzzy-but-unique key-set match."""
        errors: list[str] = []
        warnings: list[str] = []
        telemetry = {"applied": 0, "rejected": 0, "tolerated_open_on_open": 0,
                     "fuzzy_match": 0, "always_rejected": 0}
        for op in ops:
            kind = str(op.get("op", ""))
            keys = _row_keys(op)
            if kind not in {"open", "edit", "close"}:
                errors.append(f"[{sorted(keys)}] unknown op: {kind or '(missing)'}")
                telemetry["rejected"] += 1
                continue
            error = _validate_keys(keys, where=f"[{sorted(keys)}]", now=now)
            if error:
                errors.append(error)
                telemetry["rejected"] += 1
                continue
            target = frozenset(keys)
            desc = op.get("desc")
            if kind == "open":
                existing = self._rows.get(target)
                if existing is not None and existing.status == "open":
                    telemetry["tolerated_open_on_open"] += 1
                    self._write_desc(existing, desc, now, errors)
                    telemetry["applied"] += 1
                    continue
                if existing is not None:
                    existing.status = "open"
                    existing.last_shown = now
                    existing.shown_seq = next(self._shown_seq)
                    self._write_desc(existing, desc, now, errors)
                    telemetry["applied"] += 1
                    continue
                if ALWAYS_KEY in target and self._open_always() >= ALWAYS_OPEN_LIMIT:
                    errors.append(f"[{sorted(keys)}] always-bringup limit reached "
                                  f"({ALWAYS_OPEN_LIMIT})")
                    telemetry["rejected"] += 1
                    continue
                if not isinstance(desc, str) or not desc.strip():
                    errors.append(f"[{sorted(keys)}] missing desc")
                    telemetry["rejected"] += 1
                    continue
                self._rows[target] = _make_row(keys, desc, now)
                self._touch(self._rows[target], now)
                if target in self._overflow:
                    self._overflow.remove(target)
                telemetry["applied"] += 1
                continue
            row, warning, locate_errors = self._locate(target)
            if row is None:
                errors.extend(locate_errors)
                telemetry["rejected"] += 1
                continue
            if warning:
                warnings.append(warning)
                telemetry["fuzzy_match"] += 1
            if kind == "edit":
                if row.status == "closed":
                    errors.append(f"[{sorted(keys)}] wrong state: closed rows can "
                                  f"only be reopened")
                    telemetry["rejected"] += 1
                    continue
                self._write_desc(row, desc, now, errors)
                telemetry["applied"] += 1
                continue
            # close
            if row.status == "closed":
                errors.append(f"[{sorted(keys)}] wrong state: already closed")
                telemetry["rejected"] += 1
                continue
            if self.actor_id in row.keys:
                errors.append(f"[{sorted(keys)}] cannot close your identity row")
                telemetry["always_rejected"] += 1
                continue
            row.status = "closed"
            if row.keys in self._overflow:
                self._overflow.remove(row.keys)
            telemetry["applied"] += 1
        return errors, telemetry, warnings

    def _write_desc(self, row: _Row, desc: Any, now: datetime,
                    errors: list[str]) -> None:
        if desc is None:
            return  # bare open/edit is a tolerated no-op
        if not isinstance(desc, str) or not desc.strip():
            errors.append(f"[{sorted(row.keys)}] missing desc")
            return
        row.desc = desc
        self._touch(row, now)

    def _touch(self, row: _Row, now: datetime) -> None:
        row.last_shown = now
        row.shown_seq = next(self._shown_seq)

    # ------------------------------------------------------------- replay

    def _interval_minutes(self, row: _Row) -> int:
        if row.always:
            return ALWAYS_REPLAY_MINUTES
        if row.at is not None:
            return SCHEDULED_REPLAY_MINUTES
        return KNOWLEDGE_REPLAY_MINUTES

    def _is_due(self, row: _Row, now: datetime) -> bool:
        if row.status != "open":
            return False
        if row.last_shown is None:
            return True
        return (now - row.last_shown).total_seconds() >= self._interval_minutes(row) * 60

    def due_lines(self, now: datetime, haystack: Any, limit: int = 8) -> list[str]:
        """Rows to inject this turn: explicit recalls, then due directives
        (``!always`` unconditional, ``!at`` on schedule), then mention hits in
        longest-match order. Overflow queue drains before newly due rows."""
        self._now = now
        queries = list(haystack) if isinstance(haystack, (list, tuple, set)) else [haystack]
        lines: list[str] = []
        rendered: set[frozenset[str]] = set()

        def emit(row: _Row) -> None:
            row.last_shown = now
            row.shown_seq = next(self._shown_seq)
            rendered.add(row.keys)
            lines.append(row.render())

        still_pending: list[frozenset[str]] = []
        for keys in self._pending_recall:
            row = self._rows.get(keys)
            if row is None or row.status != "open":
                continue
            if len(lines) < limit:
                emit(row)
            else:
                still_pending.append(keys)
        self._pending_recall = still_pending

        open_rows = [row for row in self._rows.values()
                     if row.status == "open" and row.keys not in rendered]
        by_keys = {row.keys: row for row in open_rows}
        ordered: list[_Row] = [by_keys[k] for k in self._overflow if k in by_keys]
        in_overflow = set(self._overflow)

        def rank(row: _Row) -> tuple[int, int, float, int]:
            priority = 0 if row.always else 1 if row.at is not None else 2
            span = matched_span(row.keys, queries) if priority == 2 else 0
            ts = row.last_shown.timestamp() if row.last_shown else -1.0
            return (priority, -span, ts, row.shown_seq)

        candidates = [row for row in open_rows
                      if row.keys not in in_overflow and self._is_due(row, now)
                      and (row.always or row.at is not None or hits(row.keys, queries))]
        ordered.extend(sorted(candidates, key=rank))
        for row in ordered:
            if len(lines) >= limit:
                break
            emit(row)
        self._overflow = [row.keys for row in ordered if row.keys not in rendered]
        return lines

    def due_reminders(self, now: datetime) -> list[dict[str, Any]]:
        out = []
        for row in self._rows.values():
            if row.status != "open" or row.at is None:
                continue
            if row.at <= now:
                out.append({"id": key_id(row.keys), "time": row.at, "desc": row.desc,
                            "rendered": format_reminder_time(row.at)})
        return out

    def close_scheduled(self, row_id: str) -> None:
        for row in self._rows.values():
            if key_id(row.keys) == row_id:
                row.status = "closed"
                if row.keys in self._overflow:
                    self._overflow.remove(row.keys)
                return

    def match_rows(self, queries: Any, limit: int | None = None) -> list[str]:
        """flashback: every row (open or closed) whose keys match the query,
        longest match first — the actor's own past, not a log lookup."""
        query_list = list(queries) if isinstance(queries, (list, tuple, set)) else [queries]
        matches = [row for row in self._rows.values() if hits(row.keys, query_list)]
        matches.sort(key=lambda row: (-matched_span(row.keys, query_list),
                                      row.last_shown.timestamp() if row.last_shown else -1.0,
                                      row.shown_seq))
        return [row.render() for row in (matches[:limit] if limit else matches)]

    def force_recall(self, keys: list[str] | None, closed: bool = False,
                     limit: int = 8) -> list[str]:
        """recall: explicitly surface rows selected by keyword. Accepts text
        keys and directive keys (``!always`` lists every obligation)."""
        wanted = [str(k).strip() for k in (keys or []) if str(k).strip()]
        if not wanted:
            return []
        matches = [row for row in self._rows.values()
                   if (row.status == "open" or closed)
                   and (hits(row.keys, wanted)
                        or any(w == k for w in wanted for k in row.keys))]
        matches.sort(key=lambda row: (row.last_shown.timestamp() if row.last_shown else -1.0,
                                      row.shown_seq))
        picked = matches[:limit]
        for row in picked:
            if row.keys not in self._pending_recall:
                self._pending_recall.append(row.keys)
        return [row.render() for row in picked]

    def on_compaction(self) -> None:
        """compaction: all last_shown reset (closed rows excluded, docs §3)."""
        for row in self._rows.values():
            if row.status == "open":
                row.last_shown = None
        self._overflow = []
        self._pending_recall = []

    # -------------------------------------------------------------- persist

    def snapshot(self) -> dict[str, Any]:
        return {"actor_id": self.actor_id,
                "rows": [{"keys": list(row.order) or sorted(row.keys),
                          "desc": row.desc,
                          "status": row.status,
                          "last_shown": row.last_shown.isoformat() if row.last_shown else None,
                          "shown_seq": row.shown_seq}
                         for row in self._rows.values()],
                "overflow": [sorted(row.keys) for row in self._rows.values()
                             if row.keys in self._overflow],
                "pending_recall": [sorted(keys) for keys in self._pending_recall],
                "shown_seq": next(self._shown_seq)}

    @classmethod
    def from_snapshot(cls, state: dict[str, Any], now: datetime) -> "ActorKB":
        kb = cls.__new__(cls)
        kb.actor_id = str(state["actor_id"])
        kb._now = now
        try:
            kb._shown_seq = itertools.count(int(state.get("shown_seq", 1)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid kb snapshot shown_seq: {exc}") from exc
        kb._rows = {}
        kb._overflow = []
        kb._pending_recall = []
        for entry in state["rows"]:
            keys = _row_keys(entry, legacy=True)
            if not keys:
                continue  # pre-migration row with no derivable key
            row = _make_row(keys, str(entry.get("desc", "")), now)
            # A legacy checkpoint can collapse distinct rows onto one key set
            # (e.g. two `todo: true` rows); keep the first and skip the rest
            # rather than failing the resume.
            if row.keys in kb._rows:
                continue
            last = entry.get("last_shown")
            try:
                row.last_shown = datetime.fromisoformat(last) if last else None
                row.shown_seq = int(entry.get("shown_seq", 0))
                row.status = str(entry.get("status", "open"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid kb snapshot row {key_id(row.keys)}: {exc}") from exc
            kb._rows[row.keys] = row
        kb._overflow = [frozenset(k) for k in state.get("overflow", ())
                        if frozenset(k) in kb._rows]
        kb._pending_recall = [frozenset(k) for k in state.get("pending_recall", ())
                              if frozenset(k) in kb._rows]
        return kb
