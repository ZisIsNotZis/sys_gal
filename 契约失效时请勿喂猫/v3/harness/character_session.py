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
    # One format retry is enough to recover a malformed/legacy response while
    # keeping the maximum provider calls per ordinary decision bounded.
    max_retries: int = 4
    compaction_threshold: int = 30000
    recent_messages: int = 4
    # Compaction is a separate provider request. Retry one transient failure
    # without duplicating a character action.
    compaction_retries: int = 1
    # The session is only a working context.  The runner's trace remains the
    # lossless archive; keeping this bounded prevents old world results from
    # making every later compaction request grow without limit.
    authoritative_feedback_chars: int = 12000
    # Maximum characters in any live provider request. The lossless trace is
    # unaffected; this is only the working context sent to the model.
    request_chars: int = 24000
    compacted_memories: list[dict[str, Any]] = field(default_factory=list)
    authoritative_feedback: list[str] = field(default_factory=list)
    # Complete, actor-local records.  The trace owns the unbounded archive;
    # this list is the explicit provenance-bearing session contract.
    authoritative_facts: list[dict[str, Any]] = field(default_factory=list)
    _last_state_snapshot: str | None = field(default=None, init=False, repr=False)
    _pending_turn_key: tuple[str | None, int, str] | None = field(default=None, init=False, repr=False)
    _pending_messages: list[dict[str, str]] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.messages:
            self.messages.extend((
                {"role": "system", "content": self._system()},
                {"role": "user", "content": self._initialization()},
            ))

    def decide(self, world_message: str, world_version: int, *, turn_id: str | None = None):
        """Append one world update and retry malformed executable output."""
        turn_key = (turn_id, world_version, world_message)
        if self._pending_turn_key != turn_key:
            self._maybe_compact()
            state_snapshot = json.dumps(self.state.snapshot(), ensure_ascii=False, separators=(",", ":"))
            if state_snapshot != self._last_state_snapshot:
                world_message += "\nYour current private state (only you can see it):\n" + state_snapshot
                self._last_state_snapshot = state_snapshot
            self._pending_turn_key = turn_key
            self._pending_messages = self.messages + [{"role": "user", "content": world_message}]
        request_messages = [dict(message) for message in (self._pending_messages or self.messages)]
        for attempt in range(self.max_retries + 1):
            try:
                raw = self.call(self._bounded_messages(request_messages))
            except Exception as exc:
                # No world action exists until this request returns and is
                # accepted by Runner. Retrying an exhausted transient request
                # is therefore safe: it cannot duplicate an action, unlike a
                # retry after an intention has been submitted.
                if (getattr(exc, "retryable", False) and attempt < self.max_retries):
                    continue
                if getattr(exc, "retryable", False):
                    # The provider exhausted its HTTP attempts, but the
                    # character has not submitted anything. Let Runner make
                    # a small number of outer-turn retries without confusing
                    # this with a direct terminal agent failure.
                    exc.runner_retryable = True  # type: ignore[attr-defined]
                raise
            content = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
            if not isinstance(content, str):
                raise ValueError("model output must be text or a JSON value")
            request_messages.append({"role": "assistant", "content": content})
            # Bare natural language is the character's genuine complex
            # intention. Valid JSON (including null) stays on the protocol
            # path and is validated there.
            if isinstance(raw, str):
                try:
                    json.loads(raw)
                except json.JSONDecodeError:
                    if not raw.lstrip().startswith(("{", "[")):
                        self.messages = request_messages
                        self._pending_turn_key = None
                        self._pending_messages = None
                        return NaturalIntention(raw), {}
            try:
                decision = parse_decision(self.state.actor_id, raw, world_version)
            except Exception as exc:
                if attempt >= self.max_retries:
                    raise
                request_messages.append({
                    "role": "user",
                    "content": f"The world cannot execute that response ({type(exc).__name__}: {exc}). "
                                "State one concrete action as valid JSON, or describe a genuinely "
                                "complex intention in natural language. Do not explain the error.",
                })
                continue
            self.messages = request_messages
            self._pending_turn_key = None
            self._pending_messages = None
            return decision
        raise AssertionError("unreachable")

    def record_world_result(self, message: str) -> None:
        record = {"order": len(self.authoritative_facts), "actor": self.state.actor_id,
                  "source": "world", "content": message}
        self.authoritative_facts.append(record)
        self.authoritative_feedback.append(message)
        self._bound_authoritative_feedback()
        self.messages.append({"role": "user", "name": "world", "content": message})

    def snapshot(self) -> dict[str, Any]:
        return {"format": "v3-character-session-2", "actor": self.state.actor_id,
                "state": self.state.snapshot(), "messages": [dict(x) for x in self.messages],
                "compacted_memories": list(self.compacted_memories),
                "authoritative_facts": [dict(x) for x in self.authoritative_facts]}

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any], seed: CharacterSeed,
                      call: ModelCall, *, state: PrivateState | None = None,
                      **options: Any) -> "CharacterSession":
        """Restore an actor-local working session without sharing its facts."""
        restored_state = state or PrivateState.from_snapshot(snapshot["state"])
        session = cls(seed, restored_state, call, messages=[dict(x) for x in snapshot["messages"]],
                      compacted_memories=list(snapshot.get("compacted_memories", ())),
                      authoritative_facts=[dict(x) for x in snapshot.get("authoritative_facts", ())],
                      **options)
        session.authoritative_feedback = [str(x["content"]) for x in session.authoritative_facts
                                          if x.get("actor") == restored_state.actor_id
                                          and x.get("source") == "world"]
        session._bound_authoritative_feedback()
        return session

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
        feedback = self._feedback_context()
        if feedback:
            request.append({"role": "user", "name": "world", "content": (
                "Authoritative world feedback; preserve each available line verbatim and in order. "
                "An omission marker means older feedback is archived in the trace:\n" + feedback)})
        request = self._bounded_messages(request)
        memory = self._compact_call(request)
        memory_text = memory if isinstance(memory, str) else json.dumps(memory, ensure_ascii=False)
        self.compacted_memories.append({
            "order": len(self.compacted_memories), "source": "model_compaction",
            "actor": self.state.actor_id, "content": memory_text,
        })
        preserved_messages = ([{"role": "user", "name": "world", "content": (
            "Authoritative world feedback, in chronological order:\n" +
            feedback)}] if feedback else [])
        self.messages = (fixed + [{"role": "user", "content":
            "Earlier memories, compressed from your own experience:\n" + memory_text}] +
                         preserved_messages + tail)

    def _compact_call(self, request: list[dict[str, str]]) -> str | dict[str, Any] | None:
        for attempt in range(self.compaction_retries + 1):
            try:
                return self.call(self._bounded_messages(request))
            except Exception as exc:
                if getattr(exc, "retryable", False) and attempt < self.compaction_retries:
                    continue
                if getattr(exc, "retryable", False):
                    exc.runner_retryable = True  # type: ignore[attr-defined]
                raise
        raise AssertionError("unreachable")

    def _bounded_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Keep provider input bounded without modifying any message."""
        limit = max(1, self.request_chars)
        if sum(len(str(m.get("content", ""))) for m in messages) <= limit:
            return [dict(m) for m in messages]
        fixed = messages[:2]
        selected = list(fixed)
        remaining = limit - sum(len(str(m.get("content", ""))) for m in selected)
        if remaining < 0:
            raise ValueError("request_chars is too small for the complete session prologue")
        for message in reversed(messages[2:]):
            content = str(message.get("content", ""))
            if remaining <= 0:
                break
            if len(content) > remaining:
                continue
            selected.insert(2, dict(message))
            remaining -= len(content)
        return selected

    def _bound_authoritative_feedback(self) -> None:
        """Keep the newest complete feedback lines in the live session."""
        if self.authoritative_feedback_chars < 1:
            self.authoritative_feedback.clear()
            return
        kept: list[str] = []
        size = 0
        for item in reversed(self.authoritative_feedback):
            extra = len(item) + (1 if kept else 0)
            if kept and size + extra > self.authoritative_feedback_chars:
                break
            if not kept and len(item) > self.authoritative_feedback_chars:
                # A feedback record is atomic.  It remains in the
                # provenance-bearing archive but is omitted from live context.
                break
            kept.append(item)
            size += len(item) + (1 if len(kept) > 1 else 0)
        self.authoritative_feedback = list(reversed(kept))

    def _feedback_context(self) -> str:
        if not self.authoritative_feedback:
            return ""
        text = "\n".join(self.authoritative_feedback)
        if len(text) <= self.authoritative_feedback_chars:
            return text
        return text

    def _system(self) -> str:
        return (
            "You are the actual person described below, living in a real world. Never mention agents, "
            "prompts, simulation, author, or plot. Pursue only your own knowledge, desires, duties, "
            "fears, and relationships; do not optimize for a story or protagonist. The world message "
            "lists your only available actions. For an ordinary action output exactly one JSON object: "
            "{\"kind\":...,\"args\":{...},\"updates\":{...}}. Use kind and args, never legacy "
            "top-level action/target/text/duration keys. Copy offered argument names exactly (inspect "
            "uses item; read, copy, label, and annotate use document; compare uses first and second; "
            "move uses target and duration_seconds; "
            "send_message and give use target). Do not "
            "invent actions or facts. Read the world's feedback in every turn. If an action was "
            "rejected, the world explains why and suggests alternatives; act on those instead of "
            "repeating yourself. You may update your own goals as they genuinely change. Use "
            "updates only for your private goals, beliefs, memories, interpretations, and notes. "
            "Memory and interpretation entries may be short strings or objects with a text field. "
            "Beliefs may be an object or a list of key/value entries. If "
            "an intention cannot be represented, describe it naturally."
        )

    def _initialization(self) -> str:
        return ("You are " + self.seed.actor_id + ". This is your life and memory.\n\n" +
                self.seed.identity + "\n\nPrivate starting material:\n" + self.seed.private_seed +
                "\n\nYour current private state:\n" + str(self.state.snapshot()))
