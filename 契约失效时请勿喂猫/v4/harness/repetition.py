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

Two detectors:
- message loop: N messages sent to the same target with no reply from it;
- action loop: the same meaningful action (kind + exact args) N times.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

# Pacing/no-op actions are not "the same thing done over and over".
_EXCLUDED_ACTIONS = {"wait", "sleep", "send_message"}


def _args_key(args: Mapping[str, Any]) -> str:
    return json.dumps(args, sort_keys=True, ensure_ascii=False)


class RepetitionMonitor:
    def __init__(self, *, message_threshold: int = 4, action_threshold: int = 5,
                 message_stride: int = 3, action_stride: int = 4) -> None:
        self.message_threshold = int(message_threshold)
        self.action_threshold = int(action_threshold)
        self.message_stride = int(message_stride)
        self.action_stride = int(action_stride)
        # actor -> {target: count of unanswered messages}
        self._sent: dict[str, dict[str, int]] = {}
        # actor -> {(kind, args_key): count of identical meaningful actions}
        self._identical: dict[str, dict[str, int]] = {}
        # actor -> {target: count at which we last announced}
        self._msg_fired: dict[str, dict[str, int]] = {}
        # actor -> {action_key: count at which we last announced}
        self._act_fired: dict[str, dict[str, int]] = {}

    def note_turn(self, actor: str, intention: Any, result: str) -> None:
        if intention is None or not hasattr(intention, "kind"):
            return
        kind = intention.kind
        if kind == "send_message":
            target = intention.args.get("target")
            if isinstance(target, str) and target:
                counts = self._sent.setdefault(actor, {})
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

    def notice(self, actor: str) -> str | None:
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
