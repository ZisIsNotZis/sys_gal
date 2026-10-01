"""Generic repetition awareness injected at the conversation frontier.

This is an additive, story-neutral harness mechanism. It never edits the
system prompt, initialization, or any already-buried context (those are cache
hits and stay byte-identical). Instead it produces a short per-turn
``situational_notice`` that is appended to the *current* world message — at
the frontier, so it is cheap and is naturally dropped by compaction when old.

The notice does not forbid repetition (that would be a fragile patch). It
makes the agent's own repetition *visible*, the way a real person notices
that they have asked the same thing many times or kept hitting the same wall.
Each character then reacts as a person (pause, change tactic, or let it go),
so a loop can break from either side.

Four detectors:
- message loop: N messages sent to the same target with no reply from it;
- action loop: the same meaningful action (kind + exact args) N times;
- stagnation: M consecutive waits. ``wait`` is the main visible symptom of a
  stalled character (ticket 43), so it is counted separately instead of being
  exempted; its notice names how long the character has waited and the actions
  it can still take, so the model is not just told "stop waiting";
- refused-kind run: the same KIND of action refused N times in a row, however
  the arguments are worded (ticket 63). The exact-args action loop misses the
  real pattern the d1-am run showed — 尼龙绳 / 一卷尼龙绳 / 捆货用的绳子 /
  值班室的粗尼龙绳 are the same failed attempt re-worded, so the counter reset
  each time and six refused ``take``s produced no notice. Only refused actions
  count, the run is per kind, a successful action of that same kind clears it,
  and ``text``/``sleep`` stay exempt, so normal multi-target messaging can
  never trip it. Its notice names what is really here, what is really readable
  and the other actions this turn can still take.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

# Pacing/no-op actions are not "the same thing done over and over".
# ``wait`` is deliberately NOT here (ticket 43): consecutive waits are the
# stagnation detector's job now. ``text`` has its own unanswered-message
# counter and ``sleep`` is the overnight, legitimate rest.
_EXCLUDED_ACTIONS = {"sleep", "text"}

# Affordance kinds that are not an "executable action" to suggest in a
# stagnation notice: pacing itself, and the route-hint advisory row.
_NON_ACTIONABLE_KINDS = {"wait", "sleep", "route_hints"}


def _args_key(args: Mapping[str, Any]) -> str:
    return json.dumps(args, sort_keys=True, ensure_ascii=False)


def _text_targets(intention: Any) -> list[str]:
    """Recipients of a message intention, for either intention shape.

    The single-action path carries ``target`` directly; the chain path records
    the whole call list under ``calls`` (ticket 43). Without this the
    unanswered-message counter was also dead on the run's real path.
    """
    args = intention.args or {}
    target = args.get("target")
    if isinstance(target, str) and target:
        return [target]
    targets: list[str] = []
    for call in args.get("calls") or ():
        if not isinstance(call, Mapping) or call.get("name") != "text":
            continue
        inner = (call.get("args") or {}).get("target")
        if isinstance(inner, str) and inner:
            targets.append(inner)
    return targets


def _wait_seconds(intention: Any) -> float:
    """Simulated seconds a wait intention covers.

    The single-action path carries ``duration_seconds`` directly; the chain
    path records the whole call list under ``calls`` (ticket 43), so the inner
    wait calls are summed. Both shapes stay deterministic.
    """
    args = intention.args or {}
    direct = args.get("duration_seconds")
    if isinstance(direct, (int, float)):
        return float(direct)
    total = 0.0
    for call in args.get("calls") or ():
        if not isinstance(call, Mapping) or call.get("name") != "wait":
            continue
        inner = (call.get("args") or {}).get("duration_seconds")
        if isinstance(inner, (int, float)):
            total += float(inner)
    return total


def _format_duration(seconds: float) -> str:
    total_minutes = max(0, int(round(seconds / 60)))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} h {minutes} min"
    if hours:
        return f"{hours} h"
    return f"{total_minutes} min"


def _action_highlights(affordances: Sequence[Mapping[str, Any]] | None,
                       limit: int = 5) -> list[str]:
    """A few concrete, readable actions from this turn's affordances.

    Deterministic: the affordance order is the engine's, duplicates are
    dropped by label, and the list is capped. Only real world actions appear —
    never ``wait``/``sleep`` (the pacing the notice is warning about) or the
    ``route_hints`` advisory row.
    """
    out: list[str] = []
    seen: set[str] = set()
    for option in affordances or ():
        if not isinstance(option, Mapping):
            continue
        kind = str(option.get("kind") or "")
        if not kind or kind in _NON_ACTIONABLE_KINDS:
            continue
        if kind == "speak":
            targets = [str(person) for person in option.get("to", ())
                       if person and str(person) != "陌生人"]
            label = (f"speak to {targets[0]}" if targets
                     else "speak to a passer-by")
        elif kind == "text":
            label = f"text {option.get('target')}"
        elif kind == "move":
            label = f"move to {option.get('target')}"
        elif kind == "take":
            label = f"take {option.get('item')}"
        elif kind == "read":
            label = f"read {option.get('item')}"
        elif kind == "give":
            label = f"give {option.get('item')} to {option.get('target')}"
        elif kind == "place":
            label = f"place {option.get('item')}"
        elif kind == "trash":
            label = f"trash {option.get('item')}"
        elif kind == "knock":
            label = f"knock on {option.get('target')}"
        elif kind == "leave_note":
            label = "leave a note"
        else:
            label = kind
        if label in seen:
            continue
        seen.add(label)
        out.append(label)
        if len(out) >= limit:
            break
    return out


def _kind_items(affordances: Sequence[Mapping[str, Any]] | None, kind: str,
                key: str, limit: int = 4) -> list[str]:
    """The distinct concrete entities of one affordance kind (ticket 63).

    ``take`` items are the things that really are here; ``read`` items are the
    things that really can be read. Deterministic: the engine's affordance
    order, deduplicated, capped.
    """
    out: list[str] = []
    for option in affordances or ():
        if not isinstance(option, Mapping) or str(option.get("kind")) != kind:
            continue
        value = option.get(key)
        if not isinstance(value, str) or not value or value in out:
            continue
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _refused_kind_notice(count: int, kind: str,
                         affordances: Sequence[Mapping[str, Any]] | None) -> str:
    """The refused-kind stagnation notice (ticket 63).

    Names the count and the kind, then the three categories the refusal run
    was caused by: what is really here (a `take` the world will accept), what
    is really readable (a `read` the world will accept), and other actions
    still available — never the kind that keeps failing.
    """
    present = _kind_items(affordances, "take", "item")
    readable = _kind_items(affordances, "read", "item")
    # `_action_highlights` renders take/read as "take x"/"read x"; those two
    # lists already carry them, so keep only the other verbs — and never the
    # kind that keeps failing.
    alternatives = [label for label in _action_highlights(affordances, limit=8)
                    if label.split(" ", 1)[0] not in {"take", "read", kind}][:4]
    message = (f"You have had {count} '{kind}' attempts refused in a row here "
               "(the latest ones were different tries at the same thing). "
               f"'{kind}' is not working.")
    parts: list[str] = []
    if present:
        parts.append("Things actually here you can take: " + ", ".join(present) + ".")
    if readable:
        parts.append("Things you can read here: " + ", ".join(readable) + ".")
    if alternatives:
        parts.append("Other actions you can still take here: "
                     + ", ".join(alternatives) + ".")
    if not parts:
        parts.append("A real person would stop and change approach.")
    return message + " " + " ".join(parts)


class RepetitionMonitor:
    def __init__(self, *, message_threshold: int = 4, action_threshold: int = 5,
                 message_stride: int = 3, action_stride: int = 4,
                 stagnation_threshold: int = 4, stagnation_stride: int = 4,
                 rejected_kind_threshold: int = 3,
                 rejected_kind_stride: int = 3) -> None:
        self.message_threshold = int(message_threshold)
        self.action_threshold = int(action_threshold)
        self.message_stride = int(message_stride)
        self.action_stride = int(action_stride)
        self.stagnation_threshold = int(stagnation_threshold)
        self.stagnation_stride = int(stagnation_stride)
        self.rejected_kind_threshold = int(rejected_kind_threshold)
        self.rejected_kind_stride = int(rejected_kind_stride)
        # actor -> {target: count of unanswered messages}
        self._sent: dict[str, dict[str, int]] = {}
        # actor -> {(kind, args_key): count of identical meaningful actions}
        self._identical: dict[str, dict[str, int]] = {}
        # actor -> {target: count at which we last announced}
        self._msg_fired: dict[str, dict[str, int]] = {}
        # actor -> {action_key: count at which we last announced}
        self._act_fired: dict[str, dict[str, int]] = {}
        # actor -> consecutive waits / summed simulated seconds / last fired
        self._stagnation: dict[str, int] = {}
        self._stagnation_seconds: dict[str, float] = {}
        self._stagnation_fired: dict[str, int] = {}
        # actor -> last location seen; a change restarts the wait run.
        self._last_location: dict[str, str] = {}
        # actor -> (kind, count of consecutive refusals of that kind)
        self._refused_kind: dict[str, tuple[str, int]] = {}
        # actor -> (kind, count) at which we last announced the refusal run.
        self._refused_fired: dict[str, tuple[str, int]] = {}

    def _break_stagnation(self, actor: str) -> None:
        self._stagnation.pop(actor, None)
        self._stagnation_seconds.pop(actor, None)
        self._stagnation_fired.pop(actor, None)

    def _break_refused_kind(self, actor: str) -> None:
        self._refused_kind.pop(actor, None)
        self._refused_fired.pop(actor, None)

    def note_turn(self, actor: str, intention: Any, result: str, *,
                  location: str | None = None) -> None:
        if location is not None:
            previous = self._last_location.get(actor)
            self._last_location[actor] = str(location)
            if previous is not None and previous != str(location):
                # Moving restarts the count: waiting (or hitting the same wall)
                # elsewhere is a new run.
                self._break_stagnation(actor)
                self._break_refused_kind(actor)
        if intention is None or not hasattr(intention, "kind"):
            return
        kind = intention.kind
        # Ticket 63: a run of refusals of the SAME kind, regardless of how the
        # arguments are worded. Only refused actions count; a successful action
        # of that same kind clears the run (the wall came down), while a
        # successful action of another kind does not — the d1-am 食堂大妈 case
        # separated her refused `take`s with successful `speak`s. `text`/`sleep`
        # stay exempt so normal multi-target messaging can never trip it. So
        # does `wait`, which has the stagnation detector above.
        if kind not in _EXCLUDED_ACTIONS and kind != "wait":
            if result == "rejected":
                last_kind, count = self._refused_kind.get(actor, (None, 0))
                count = count + 1 if last_kind == kind else 1
                self._refused_kind[actor] = (kind, count)
            elif self._refused_kind.get(actor, (None, 0))[0] == kind:
                self._break_refused_kind(actor)
        if kind == "wait":
            self._stagnation[actor] = self._stagnation.get(actor, 0) + 1
            self._stagnation_seconds[actor] = (
                self._stagnation_seconds.get(actor, 0.0) + _wait_seconds(intention))
            return
        # Any non-wait turn breaks the consecutive-wait run (ticket 43).
        self._break_stagnation(actor)
        if kind == "text":
            counts = self._sent.setdefault(actor, {})
            for target in _text_targets(intention):
                counts[target] = counts.get(target, 0) + 1
            return
        if kind in _EXCLUDED_ACTIONS:
            return
        key = (kind, _args_key(intention.args))
        counts = self._identical.setdefault(actor, {})
        counts[key] = counts.get(key, 0) + 1
        if result == "submitted":
            # The same action finally went through; the matter is not stuck.
            counts.pop(key, None)
            self._act_fired.setdefault(actor, {}).pop(key, None)

    def note_message_received(self, actor: str, sender: str) -> None:
        counts = self._sent.get(actor)
        if counts and sender in counts:
            counts[sender] = 0
            self._msg_fired.setdefault(actor, {}).pop(sender, None)

    def notice(self, actor: str, *,
               affordances: Sequence[Mapping[str, Any]] | None = None) -> str | None:
        fired = self._msg_fired.setdefault(actor, {})
        for target, count in self._sent.get(actor, {}).items():
            if count >= self.message_threshold and (
                    count - self.message_threshold) % self.message_stride == 0:
                if fired.get(target) != count:
                    fired[target] = count
                    return (
                        f"You have sent {target} {count} messages in a row without a reply. "
                        "You may be repeating yourself. A real person would pause, consider "
                        "whether this is still needed, and try a different approach."
                    )
        refused_kind, refused_count = self._refused_kind.get(actor, (None, 0))
        if (refused_kind is not None
                and refused_count >= self.rejected_kind_threshold
                and (refused_count - self.rejected_kind_threshold)
                % self.rejected_kind_stride == 0
                and self._refused_fired.get(actor) != (refused_kind, refused_count)):
            self._refused_fired[actor] = (refused_kind, refused_count)
            return _refused_kind_notice(refused_count, refused_kind, affordances)
        act_fired = self._act_fired.setdefault(actor, {})
        for key, count in self._identical.get(actor, {}).items():
            if count >= self.action_threshold and (
                    count - self.action_threshold) % self.action_stride == 0:
                if act_fired.get(key) != count:
                    act_fired[key] = count
                    return (
                        f"You have attempted the same action {count} times. You notice it is "
                        "not working; a real person would try something else."
                    )
        count = self._stagnation.get(actor, 0)
        if count >= self.stagnation_threshold and (
                count - self.stagnation_threshold) % self.stagnation_stride == 0:
            if self._stagnation_fired.get(actor) != count:
                self._stagnation_fired[actor] = count
                waited = _format_duration(self._stagnation_seconds.get(actor, 0.0))
                message = (
                    f"You have been waiting in place for about {waited} "
                    f"({count} waits in a row). Waiting again changes nothing. A real "
                    "person would use the time."
                )
                options = _action_highlights(affordances)
                if options:
                    message += (" Concrete things you can still do here: "
                                + ", ".join(options) + ".")
                return message
        return None

    def state(self) -> dict[str, Any]:
        return {
            "sent": {actor: dict(counts) for actor, counts in self._sent.items()},
            "identical": {actor: {f"{kind}::{args}": count
                                  for (kind, args), count in counts.items()}
                          for actor, counts in self._identical.items()},
            "msg_fired": {actor: dict(values) for actor, values in self._msg_fired.items()},
            "act_fired": {actor: {f"{kind}::{args}": count
                                  for (kind, args), count in values.items()}
                          for actor, values in self._act_fired.items()},
            "stagnation": dict(self._stagnation),
            "stagnation_seconds": dict(self._stagnation_seconds),
            "stagnation_fired": dict(self._stagnation_fired),
            "last_location": dict(self._last_location),
            "refused_kind": {actor: [kind, count]
                             for actor, (kind, count) in self._refused_kind.items()},
            "refused_fired": {actor: [kind, count]
                              for actor, (kind, count) in self._refused_fired.items()},
        }

    def restore(self, state: Mapping[str, Any]) -> None:
        if not state:
            return
        self._sent = {actor: dict(counts) for actor, counts in state.get("sent", {}).items()}
        self._identical = {
            actor: {(kind, args): int(count) for item, count in counts.items()
                    for kind, args in [tuple(item.split("::", 1))]}
            for actor, counts in state.get("identical", {}).items()}
        self._msg_fired = {actor: dict(values) for actor, values in state.get("msg_fired", {}).items()}
        self._act_fired = {
            actor: {(kind, args): int(count) for item, count in values.items()
                    for kind, args in [tuple(item.split("::", 1))]}
            for actor, values in state.get("act_fired", {}).items()}
        self._stagnation = {actor: int(count)
                            for actor, count in state.get("stagnation", {}).items()}
        self._stagnation_seconds = {actor: float(seconds)
                                    for actor, seconds in state.get("stagnation_seconds", {}).items()}
        self._stagnation_fired = {actor: int(count)
                                  for actor, count in state.get("stagnation_fired", {}).items()}
        self._last_location = {actor: str(loc)
                               for actor, loc in state.get("last_location", {}).items()}
        self._refused_kind = {actor: (str(kind), int(count))
                              for actor, (kind, count)
                              in state.get("refused_kind", {}).items()}
        self._refused_fired = {actor: (str(kind), int(count))
                               for actor, (kind, count)
                               in state.get("refused_fired", {}).items()}
