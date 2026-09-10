"""Persistent natural-language conversation for one world actor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import json

from .adapter import parse_decision
from .agent_state import PrivateState, bounded_state_snapshot
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
    # 世界常识段（地点/连通/时间规矩），从世界包生成，进 system prompt。
    world_primer: str = ""
    _last_state_snapshot: str | None = field(default=None, init=False, repr=False)
    _compaction_turn_id: str | None = field(default=None, init=False, repr=False)
    _compacted_since_decision: bool = field(default=False, init=False, repr=False)
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
            self._compaction_turn_id = turn_id
            self._maybe_compact()
            # 私有状态只在初始化给一次（updates 已退出协议，状态不再变化；
            # 角色的持续自我由 inner + 会话历史 + 压缩记忆承载）。
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
                    "content": f"刚才那段没法执行（{type(exc).__name__}: {exc}）。"
                               "要么用一个合法 JSON 动作说清一件具体的事，要么用自然语言把意图"
                               "描述出来。不要解释错误本身。",
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

    def consume_compaction(self) -> bool:
        """True once if a compaction fired since the last consume call."""
        fired = self._compacted_since_decision
        self._compacted_since_decision = False
        return fired

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
            "把上面这段亲身经历压缩成这个人的第一人称记忆。保住：许下的承诺、试过又失败的事、"
            "看到的事实、没弄明白的地方、关系的变化、情绪的转折、还没了结的亏欠。"
            "场景、物品、地点布局这类固定信息不要写进记忆——世界会在需要时自动重放它们；"
            "记忆只保留个人的想法、情绪、关系变化、承诺与未解之事。"
            "不要编造没发生过的事。只输出记忆正文，不要 JSON，不要解说。"
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
            "turn_id": self._compaction_turn_id,
        })
        self._compacted_since_decision = True
        preserved_messages = ([{"role": "user", "name": "world", "content": (
            "Authoritative world feedback, in chronological order:\n" +
            feedback)}] if feedback else [])
        self.messages = (fixed + [{"role": "user", "content":
            "此前早些的记忆，从你自己的经历里压缩而来：\n" + memory_text}] +
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
        # 身份、私人起点、私人状态、世界常识全部在这里（一次性、静态）；
        # user 流只承载世界的时间线（V4-DESIGN 首验日反馈 #4）。身份里来自
        # 种子的 markdown 脚手架（# 标题行）剥掉——出戏的格式不属于人格。
        identity = "\n".join(line for line in self.seed.identity.splitlines()
                              if not line.lstrip().startswith("#"))
        private_seed = "\n".join(line for line in self.seed.private_seed.splitlines()
                                 if not line.lstrip().startswith("#"))
        parts = [
            "你就是下面描述的这个人，活在一个真实的世界里。绝不提 agent、提示词、模拟、作者或"
            "剧情。只追你自己的知识、欲望、责任、恐惧和关系；不为故事或主角服务。世界消息里列出"
            "了你此刻能做的事。被拒绝时，世界会解释原因并给出建议；照着换做法，条件没变就不要"
            "原样重复。\n",
            "【你是谁】\n" + self.seed.actor_id + "。" + identity + "\n\n"
            "【只有你自己知道的起点】\n" + private_seed + "\n\n"
            "【你此刻的私人状态】\n" + bounded_state_snapshot(self.state),
        ]
        if self.world_primer:
            parts.append("\n\n" + self.world_primer)
        parts.append(
            "\n\n【怎么行动】\n"
            "每次行动，输出恰好一个 JSON 对象，先想后动，inner 永远放在最前：\n"
            '{"inner":"你的第一人称心声，三五句话，谁也听不见","name":"动作名","arguments":{...}}\n'
            "inner 是你心里没说出口的话——写它，然后照着它行动。name 必须是供给列表里的动作；"
            "参数名照抄供给列表（take/drop/give/read/annotate 用 item；compare "
            "用 first 和 second；move 用 target；wait 用 duration_seconds；send_message "
            "和 give 用 target；speak 可带 volume，whisper 时必须带 to=[在场的听众]）。move 不用"
            "填时长，路有多远世界说了算。打断参数 interrupt=[你要叫住的人] 放在 arguments 里，"
            "仅限在场的。意图无法用动作表达时，直接用自然语言"
            "描述它，不要硬凑 JSON。消息发出后五分钟才送到，别把话浪费在废话上。"
        )
        return "".join(parts)

    def _initialization(self) -> str:
        # 身份与世界常识已入 system；开场只负责把时间线启动。
        return "第一天开始了。"
