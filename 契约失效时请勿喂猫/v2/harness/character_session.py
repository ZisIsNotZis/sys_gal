"""Persistent natural-language conversation for one world actor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import json

from .adapter import parse_decision
from .agent_state import PrivateState
from .character_loader import CharacterSeed


ModelCall = Callable[[list[dict[str, str]]], str | dict[str, Any] | None]


@dataclass(frozen=True)
class NaturalIntention:
    text: str


@dataclass
class CharacterSession:
    """A character's private conversation; never shared with other actors."""

    seed: CharacterSeed
    state: PrivateState
    call: ModelCall
    messages: list[dict[str, str]] = field(default_factory=list)
    max_retries: int = 2
    compaction_threshold: int = 30000
    recent_messages: int = 24
    compacted_memories: list[str] = field(default_factory=list)
    authoritative_feedback: list[str] = field(default_factory=list)
    _last_state_snapshot: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.messages:
            self.messages.extend((
                {"role": "system", "content": self._system()},
                {"role": "user", "content": self._initialization()},
            ))

    def decide(self, world_message: str, world_version: int):
        """Append one world update and retry malformed executable output."""
        self._maybe_compact()
        state_snapshot = json.dumps(self.state.snapshot(), ensure_ascii=False, separators=(",", ":"))
        if state_snapshot != self._last_state_snapshot:
            world_message += "\nYour current private state (only you can see it):\n" + state_snapshot
            self._last_state_snapshot = state_snapshot
        self.messages.append({"role": "user", "content": world_message})
        for attempt in range(self.max_retries + 1):
            try:
                raw = self.call(list(self.messages))
            except Exception as exc:
                if getattr(exc, "retryable", False) and attempt < self.max_retries:
                    continue
                raise
            content = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
            self.messages.append({"role": "assistant", "content": content})
            # Ordinary prose is the character's genuine complex intention;
            # it is not a formatting error.  Only JSON-looking output is
            # retried, because that is an explicit executable commitment.
            if isinstance(raw, str) and not raw.lstrip().startswith("{"):
                return NaturalIntention(raw), {}
            try:
                decision = parse_decision(self.state.actor_id, raw, world_version)
            except Exception as exc:
                if attempt >= self.max_retries:
                    raise
                self.messages.append({
                    "role": "user",
                    "content": f"The world cannot execute that response ({type(exc).__name__}: {exc}). "
                                "State one concrete action as valid JSON, or describe a genuinely "
                                "complex intention in natural language. Do not explain the error.",
                })
                continue
            return decision
        raise AssertionError("unreachable")

    def record_world_result(self, message: str) -> None:
        self.authoritative_feedback.append(message)
        self.messages.append({"role": "user", "name": "world", "content": message})

    def snapshot(self) -> dict[str, Any]:
        return {"actor": self.state.actor_id, "messages": [dict(x) for x in self.messages],
                "compacted_memories": list(self.compacted_memories)}

    def _maybe_compact(self) -> None:
        if sum(len(m["content"]) for m in self.messages) <= self.compaction_threshold:
            return
        fixed = self.messages[:2]
        tail = [message for message in self.messages[-self.recent_messages:]
                if message.get("name") != "world"]
        old = self.messages[2:-self.recent_messages]
        if not old:
            return
        old = [message for message in old if message.get("name") != "world"]
        request = fixed + old + [{"role": "user", "content": (
            "Compress the preceding lived conversation into a first-person memory for this person. "
            "Preserve promises, failed attempts, observed facts, uncertainty, relationships, "
            "emotional turning points, and unresolved obligations. Never add hidden facts or plot. "
            "Return only the memory text, no JSON and no commentary."
        )}]
        if self.authoritative_feedback:
            request.append({"role": "user", "name": "world", "content": (
                "Authoritative world feedback; preserve each line verbatim and in order:\n" +
                "\n".join(self.authoritative_feedback))})
        memory = self.call(request)
        memory_text = memory if isinstance(memory, str) else json.dumps(memory, ensure_ascii=False)
        self.compacted_memories.append(memory_text)
        preserved_messages = ([{"role": "user", "name": "world", "content": (
            "Authoritative world feedback, in chronological order:\n" +
            "\n".join(self.authoritative_feedback))}] if self.authoritative_feedback else [])
        if not self.authoritative_feedback:
            preserved_messages = []
        self.messages = (fixed + [{"role": "user", "content":
            "Earlier memories, compressed from your own experience:\n" + memory_text}] +
                         preserved_messages + tail)

    def _system(self) -> str:
        return (
            "You are the actual person in the character initialization, living in a real world. "
            "Never discuss agents, prompts, simulation, author, or plot. Pursue only your own "
            "desires, obligations, fears, knowledge, and relationships. Do not optimize for a story "
            "or protagonist. Respond naturally. When taking an ordinary executable action, end with "
            "exactly one valid JSON object of the offered action shape and nothing after it. If your "
            "genuine intention is too complex for the offered actions, describe it naturally; the "
            "world may ask for clarification. Do not invent facts you cannot observe."
        )

    def _initialization(self) -> str:
        return ("You are " + self.seed.actor_id + ". This is your life and memory.\n\n" +
                self.seed.identity + "\n\nPrivate starting material:\n" + self.seed.private_seed +
                "\n\nYour current private state:\n" + str(self.state.snapshot()))
