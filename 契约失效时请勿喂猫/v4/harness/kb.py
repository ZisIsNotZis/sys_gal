"""Per-actor private notebook / KB row model (V4-AGENT-INTERFACE §3/§4/§6).

The engine owns the KB; the model sees only rendered lines. desc is opaque —
the engine never interprets memory content. Rows are located by id (unique
per actor); fields are immutable (M8): edit only changes desc. Replay
intervals are sim-minutes (tick = 1 minute, V4-ENGINE §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import itertools
import re
from typing import Any

TODO_REPLAY_MINUTES = 60
REMINDER_REPLAY_MINUTES = 30
KNOWLEDGE_REPLAY_MINUTES = 120
TODO_OPEN_LIMIT = 12

RESERVED_FIELDS = {"person", "location", "item", "todo", "reminder", "self"}
# Fields whose values participate in the mention set (M7). document joins
# because world document descriptions auto-expand into document rows (§6):
# without it they would fall into the unconditional branch.
_MENTION_FIELDS = ("person", "location", "item", "document")
_WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}
_WEEKDAY_CHAR = {v: k for k, v in _WEEKDAY.items()}
_REMINDER_RE = re.compile(r"^(\d{1,2})/(\d{1,2})\((周[一二三四五六日])\) (\d{1,2}):(\d{2})$")
# Rendering order for due lines within one turn (docs §3: 按类型排序).
_CATEGORY_ORDER = {"reminder": 0, "todo": 1, "person": 2, "location": 3, "item": 4}


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


def _interval_minutes(fields: dict[str, Any]) -> int:
    """m3: a multi-field row takes the MAX of its fields' intervals."""
    table = {"todo": TODO_REPLAY_MINUTES, "reminder": REMINDER_REPLAY_MINUTES}
    values = [table.get(key, KNOWLEDGE_REPLAY_MINUTES) for key in fields]
    return max(values) if values else KNOWLEDGE_REPLAY_MINUTES


def _main_field(fields: dict[str, Any]) -> tuple[str, Any]:
    for key in ("self", "todo", "reminder", "person", "location", "item"):
        if key in fields:
            return key, fields[key]
    for key, value in fields.items():
        return key, value
    return "id", ""


@dataclass
class _Row:
    id: str
    fields: dict[str, Any]
    desc: str
    status: str = "open"
    last_shown: datetime | None = None
    shown_seq: int = 0  # monotonic per-KB surfacing order (recall tie-break)

    def render(self) -> str:
        if self.fields.get("self") and "person" in self.fields:
            # docs §3 sample: the identity row renders as [person=<own name>]
            return f"[person={self.fields['person']}]: {self.desc}"
        key, value = _main_field(self.fields)
        if key == "reminder" and isinstance(value, datetime):
            value = format_reminder_time(value)
        if key in {"self", "todo"}:
            value = "true"
        return f"[{key}={value}]: {self.desc}"


class ActorKB:
    """One actor's private KB. Not thread-safe; owned by the engine loop."""

    def __init__(self, actor_id: str, rows: list[dict[str, Any]], now: datetime) -> None:
        self.actor_id = actor_id
        self._now = now  # last sim-time seen; refresh anchor for recall
        self._rows: dict[str, _Row] = {}
        self._overflow: list[str] = []
        self._pending_recall: list[str] = []
        self._shown_seq = itertools.count(1)
        self_rows = 0
        for row in rows:
            row_id = str(row.get("id", ""))
            if not row_id:
                raise ValueError(f"[{actor_id}] seed row without id")
            if row_id in self._rows:
                raise ValueError(f"[{actor_id}] duplicate seed row id: {row_id}")
            fields = dict(row.get("fields", {}))
            if "reminder" in fields and isinstance(fields["reminder"], str):
                when = parse_reminder_time(fields["reminder"], now)
                if when is None:
                    raise ValueError(f"[{actor_id}] seed row {row_id}: "
                                     f"unparseable reminder time: {fields['reminder']}")
                fields["reminder"] = when
            if fields.get("self"):
                self_rows += 1
            self._rows[row_id] = _Row(row_id, fields, str(row.get("desc", "")))
        if self_rows != 1:
            raise ValueError(f"[{actor_id}] exactly one self:true row is required, "
                             f"found {self_rows}")

    # ------------------------------------------------------------- mutation

    def apply_ops(self, ops: list[dict[str, Any]], now: datetime) -> tuple[list[str], dict[str, int]]:
        """Apply an update_memory patch. Partial success: valid rows apply,
        failures are returned as per-row English errors (docs §4)."""
        errors: list[str] = []
        telemetry = {"applied": 0, "rejected": 0, "tolerated_open_on_open": 0, "free_field": 0}
        seen: set[str] = set()
        for op in ops:
            row_id = str(op.get("id", ""))
            kind = str(op.get("op", ""))
            # Literal duplicate rows (two identical opens of one id) collide;
            # a lifecycle sequence open→edit→close of one id applies in order.
            if kind == "open" and row_id in seen:
                errors.append(f"[id={row_id}] duplicate row in patch")
                telemetry["rejected"] += 1
                continue
            seen.add(row_id)
            if kind not in {"open", "edit", "close"}:
                errors.append(f"[id={row_id}] unknown op: {kind or '(missing)'}")
                telemetry["rejected"] += 1
                continue
            fields = op.get("fields")
            error = self._apply_one(row_id, kind, fields, op.get("desc"), now, telemetry)
            if error:
                errors.append(error)
                telemetry["rejected"] += 1
            else:
                telemetry["applied"] += 1
        return errors, telemetry

    def _apply_one(self, row_id: str, kind: str, fields: Any, desc: Any,
                   now: datetime, telemetry: dict[str, int]) -> str | None:
        row = self._rows.get(row_id)
        if kind == "open":
            if row is not None and row.status == "open":
                # Tolerated reopen of an open row: treated as edit (docs §4).
                telemetry["tolerated_open_on_open"] += 1
                return self._edit_desc(row, desc, now, self._shown_seq)
            if row is not None and row.status == "closed":
                return self._reopen(row, desc, now, telemetry)
            # New row.
            if not isinstance(fields, dict) or not fields:
                return f"[id={row_id}] missing fields"
            if fields.get("todo") and self._open_todos() >= TODO_OPEN_LIMIT:
                return f"[id={row_id}] todo limit reached ({TODO_OPEN_LIMIT})"
            for key in fields:
                if key not in RESERVED_FIELDS:
                    telemetry["free_field"] += 1
            if "reminder" in fields:
                when = parse_reminder_time(fields["reminder"], now)
                if when is None:
                    return (f"[id={row_id}] unparseable reminder time: "
                            f"{fields['reminder']}")
                fields = {**fields, "reminder": when}
            if not isinstance(desc, str) or not desc.strip():
                return f"[id={row_id}] missing desc"
            self._rows[row_id] = _Row(row_id, dict(fields), desc)
            self._touch(self._rows[row_id], now)
            if row_id in self._overflow:
                self._overflow.remove(row_id)
            return None
        if row is None:
            return f"[id={row_id}] no match"
        if kind == "edit":
            if row.status == "closed":
                return f"[id={row_id}] wrong state: closed rows can only be reopened"
            return self._edit_desc(row, desc, now, self._shown_seq)
        # close
        if row.status == "closed":
            return f"[id={row_id}] wrong state: already closed"
        row.status = "closed"
        if row_id in self._overflow:
            self._overflow.remove(row_id)
        return None

    def _touch(self, row: _Row, now: datetime) -> None:
        """Refresh a row's last_shown and its surfacing tie-break order."""
        row.last_shown = now
        row.shown_seq = next(self._shown_seq)

    @staticmethod
    def _edit_desc(row: _Row, desc: Any, now: datetime, seq_next) -> str | None:
        if desc is None:
            return None  # a bare open/edit with no desc is a tolerated no-op
        if not isinstance(desc, str) or not desc.strip():
            return f"[id={row.id}] missing desc"
        row.desc = desc
        row.last_shown = now
        row.shown_seq = next(seq_next)
        return None

    def _reopen(self, row: _Row, desc: Any, now: datetime,
                telemetry: dict[str, int]) -> str | None:
        row.status = "open"
        row.last_shown = now  # re-archive resets last_shown (docs M8)
        row.shown_seq = next(self._shown_seq)
        if desc is not None:
            if not isinstance(desc, str) or not desc.strip():
                row.status = "closed"
                return f"[id={row.id}] missing desc"
            row.desc = desc
        return None

    def _open_todos(self) -> int:
        return sum(1 for r in self._rows.values()
                   if r.status == "open" and r.fields.get("todo"))

    def close_reminder(self, row_id: str) -> None:
        row = self._rows.get(row_id)
        if row is not None:
            row.status = "closed"
            if row_id in self._overflow:
                self._overflow.remove(row_id)

    # ------------------------------------------------------------- replay

    def _is_due(self, row: _Row, now: datetime) -> bool:
        if row.status != "open":
            return False
        if row.last_shown is None:
            return True
        return (now - row.last_shown).total_seconds() >= _interval_minutes(row.fields) * 60

    def _mention_hit(self, row: _Row, mention_set: set[str]) -> bool:
        # Entity rows (person/location/item) are mention-gated ALWAYS —
        # including turn 0: an unmentioned entity's description must not
        # surface before the entity enters the actor's perception (user
        # ruling 2026-09-08: [item=红色哨子] must not pop up unmentioned).
        # Unconditional rows (self/todo/reminder/free) flood on turn 0 and
        # replay on their interval timers; the identity anchor (self:true)
        # is always unconditional.
        if row.fields.get("self"):
            return True
        hits = [key for key in _MENTION_FIELDS
                if key in row.fields and row.fields[key] in mention_set]
        if hits:
            return True
        return not any(key in row.fields for key in _MENTION_FIELDS)

    def _category(self, row: _Row) -> tuple[int, float]:
        key, _ = _main_field(row.fields)
        order = _CATEGORY_ORDER.get(key, 5)
        ts = row.last_shown.timestamp() if row.last_shown else 0.0
        return (order, ts)

    def due_lines(self, now: datetime, mention_set: set[str], limit: int = 8) -> list[str]:
        self._now = now
        lines: list[str] = []
        rendered: set[str] = set()

        def emit(row: _Row) -> None:
            row.last_shown = now
            row.shown_seq = next(self._shown_seq)
            rendered.add(row.id)
            lines.append(row.render())

        # Explicitly recalled rows surface first (docs §4: 下一轮显式包含);
        # rows that do not fit stay queued for the next turn.
        still_pending: list[str] = []
        for row_id in self._pending_recall:
            row = self._rows.get(row_id)
            if row is None or row.status != "open":
                continue
            if len(lines) < limit:
                emit(row)
            else:
                still_pending.append(row_id)
        self._pending_recall = still_pending

        open_rows = {row.id: row for row in self._rows.values()
                     if row.status == "open" and row.id not in rendered}
        # Overflowed rows clear before newly due rows (docs §3 顺延队列先清);
        # they were already due when they overflowed, so they render
        # unconditionally in queue order.
        ordered = [open_rows[rid] for rid in self._overflow if rid in open_rows]
        in_overflow = set(self._overflow)
        candidates = [row for rid, row in open_rows.items()
                      if rid not in in_overflow
                      and self._is_due(row, now) and self._mention_hit(row, mention_set)]
        ordered.extend(sorted(candidates, key=self._category))
        for row in ordered:
            if len(lines) >= limit:
                break
            emit(row)
        # Rows that ran out of room stay queued (old queue order first, new
        # overflow appended behind them).
        self._overflow = [row.id for row in ordered if row.id not in rendered]
        return lines

    def due_reminders(self, now: datetime) -> list[dict[str, Any]]:
        out = []
        for row in self._rows.values():
            if row.status != "open" or "reminder" not in row.fields:
                continue
            when = row.fields["reminder"]
            if isinstance(when, datetime) and when <= now:
                out.append({"id": row.id, "time": when, "desc": row.desc,
                            "rendered": row.render()})
        return out

    def force_recall(self, kinds: list[str] | None, ids: list[str] | None,
                     closed: bool = False, limit: int = 8) -> list[str]:
        """recall: explicitly surface the requested kinds/ids in the next
        #knowledge block. Rows are queued (rendered again next turn even if
        not yet due) and returned immediately for the engine's use; closed
        rows only when ``closed`` is true. Ordering: oldest last_shown first."""
        kind_set = set(kinds or ())
        id_set = set(ids or ())
        if not kind_set and not id_set:
            return []
        matches = [row for row in self._rows.values()
                   if row.status == "open" or closed]
        matches = [row for row in matches
                   if (row.id in id_set) or (bool(kind_set & set(row.fields)))]
        matches.sort(key=lambda r: (r.last_shown.timestamp() if r.last_shown else -1.0,
                                    r.shown_seq))
        picked = matches[:limit]
        for row in picked:
            if row.id not in self._pending_recall:
                self._pending_recall.append(row.id)
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
        def field_value(value: Any) -> Any:
            if isinstance(value, datetime):
                return format_reminder_time(value)
            return value

        return {"actor_id": self.actor_id,
                "rows": [{"id": r.id,
                          "fields": {k: field_value(v) for k, v in r.fields.items()},
                          "desc": r.desc,
                          "status": r.status,
                          "last_shown": r.last_shown.isoformat() if r.last_shown else None,
                          "shown_seq": r.shown_seq}
                         for r in self._rows.values()],
                "overflow": list(self._overflow),
                "pending_recall": list(self._pending_recall),
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
        for row in state["rows"]:
            fields = dict(row["fields"])
            if "reminder" in fields and isinstance(fields["reminder"], str):
                fields["reminder"] = (parse_reminder_time(fields["reminder"], now)
                                      or fields["reminder"])
            last = row.get("last_shown")
            try:
                shown = datetime.fromisoformat(last) if last else None
                seq = int(row.get("shown_seq", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid kb snapshot row {row.get('id')}: {exc}") from exc
            kb._rows[str(row["id"])] = _Row(str(row["id"]), fields,
                                            str(row["desc"]), str(row.get("status", "open")),
                                            shown, seq)
        kb._overflow = [str(x) for x in state.get("overflow", ())]
        kb._pending_recall = [str(x) for x in state.get("pending_recall", ())]
        return kb
