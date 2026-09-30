"""OpenAI-compatible Responses API provider using only the standard library."""

from __future__ import annotations

import json
from http.client import HTTPResponse
from typing import Any, Callable
import os
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# Ticket 54: response bodies are read one recv-chunk at a time so the call's
# wall-clock deadline can be re-checked between chunks — urlopen's socket
# timeout only bounds a single recv.
_RESPONSE_CHUNK_BYTES = 65536


class _ResponseBudgetExceeded(Exception):
    """The call's wall-clock budget ran out mid-response (ticket 54)."""

    def __init__(self, *, attempts: int, elapsed: float, budget: float) -> None:
        super().__init__(f"response budget exceeded on attempt {attempts} "
                         f"after {elapsed:.1f}s of {budget:.1f}s")
        self.attempts = attempts
        self.elapsed = elapsed
        self.budget = budget


def _read_response_body(response: Any, *, deadline: float, started: float,
                        budget: float, attempts: int) -> bytes:
    """Read a body without ever outliving the call's budget.

    ``urlopen(timeout=...)`` bounds one socket operation, not the request: an
    upstream that dribbles a body (or holds the connection open) keeps a
    plain ``read()`` blocked forever — that is the 11:32 freeze of ticket 54.
    Real HTTP responses are read one recv-chunk at a time with the deadline
    re-checked between chunks; a non-HTTP file-like object (test doubles, for
    which ``read1`` is meaningless) keeps the single-shot read."""
    if not isinstance(response, HTTPResponse):
        return response.read()
    chunks: list[bytes] = []
    while True:
        if time.monotonic() >= deadline:
            raise _ResponseBudgetExceeded(attempts=attempts,
                                          elapsed=time.monotonic() - started,
                                          budget=budget)
        chunk = response.read1(_RESPONSE_CHUNK_BYTES)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _thinking_param(model: str) -> Any:
    """Per-provider reasoning switch (V4-DESIGN §1 reasoning matrix).

    OpenAI-style Responses endpoints accept the string "none"; volc/* expects
    an ``openapi.Thinking`` object. Send the shape each upstream parses, or
    nothing when a channel rejects the field outright (V3_THINKING_PARAM
    override, raw JSON or empty string to omit)."""
    override = os.environ.get("V3_THINKING_PARAM")
    if override is not None:
        return json.loads(override) if override.strip() else None
    if model.startswith("volc/"):
        return {"type": "disabled"}
    return "none"


def _chat_messages_to_responses_input(messages: list[dict]) -> list[dict]:
    """Translate V4Session's persisted chat-style history to Responses items."""
    converted: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("provider conversation messages must be objects")
        role = message.get("role")
        content = message.get("content", "")
        if role == "tool":
            call_id = message.get("tool_call_id")
            if not isinstance(call_id, str) or not call_id:
                raise ValueError("tool history message is missing tool_call_id")
            converted.append({"type": "function_call_output", "call_id": call_id,
                              "output": "" if content is None else str(content)})
            continue
        if role not in {"system", "developer", "user", "assistant"}:
            raise ValueError(f"unsupported Responses history role: {role!r}")
        if role == "assistant" and "tool_calls" in message:
            calls = message["tool_calls"]
            if not isinstance(calls, list):
                raise ValueError("assistant tool_calls history must be a list")
            if content not in (None, ""):
                if not isinstance(content, str):
                    raise ValueError("assistant history content must be text")
                converted.append({"role": "assistant", "content": content})
            for call in calls:
                function = call.get("function") if isinstance(call, dict) else None
                call_id = call.get("id") if isinstance(call, dict) else None
                name = function.get("name") if isinstance(function, dict) else None
                arguments = function.get("arguments") if isinstance(function, dict) else None
                if not isinstance(call_id, str) or not call_id:
                    raise ValueError("assistant tool call is missing id")
                if not isinstance(name, str) or not name:
                    raise ValueError("assistant tool call is missing function name")
                if isinstance(arguments, dict):
                    arguments = json.dumps(arguments, ensure_ascii=False)
                if not isinstance(arguments, str):
                    raise ValueError("assistant tool call is missing function arguments")
                converted.append({"type": "function_call", "call_id": call_id,
                                  "name": name, "arguments": arguments})
            continue
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise ValueError(f"{role} history content must be text")
        converted.append({"role": role, "content": content})
    return converted


def _chat_tools_to_responses_tools(tools: list[dict]) -> list[dict]:
    """Flatten Chat Completions function declarations for the Responses API."""
    converted = []
    for tool in tools:
        function = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(function, dict):
            raise ValueError("chat tool definition is missing function")
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("chat tool definition is missing function name")
        response_tool = {"type": "function", "name": name}
        for key in ("description", "parameters", "strict"):
            if key in function:
                response_tool[key] = function[key]
        converted.append(response_tool)
    return converted


def _extract_responses_tool_message(result: dict) -> dict | None:
    """Normalize Responses message/function_call output to V4Session's shape."""
    output = result.get("output")
    text = ""
    calls = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                if item.get("role", "assistant") != "assistant":
                    return None
                content = item.get("content", [])
                if not isinstance(content, list):
                    return None
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "output_text":
                        part_text = part.get("text")
                        if not isinstance(part_text, str):
                            return None
                        text += part_text
            elif item.get("type") == "function_call":
                call_id = item.get("call_id")
                name = item.get("name")
                arguments = item.get("arguments")
                if not isinstance(call_id, str) or not call_id:
                    return None
                if not isinstance(name, str) or not name:
                    return None
                if isinstance(arguments, dict):
                    arguments = json.dumps(arguments, ensure_ascii=False)
                if not isinstance(arguments, str):
                    return None
                calls.append({"id": call_id, "type": "function",
                              "function": {"name": name, "arguments": arguments}})
    elif output is not None:
        return None
    if not text and isinstance(result.get("output_text"), str):
        text = result["output_text"]
    if not text.strip() and not calls:
        return None
    return {"role": "assistant", "content": text, "tool_calls": calls}


def _fill_inner_from_reasoning(message: dict) -> None:
    """Use an open-source model's ``reasoning_content`` as the inner monologue.

    Ticket 38: when a chat tool call omits ``inner`` but the message carries
    its reasoning, that reasoning IS the private monologue — adopt it so a
    model that reasons outside the call still populates the inner channel.
    """
    reasoning = message.get("reasoning_content")
    if not isinstance(reasoning, str) or not reasoning.strip():
        return
    for call in message.get("tool_calls") or []:
        function = call.get("function") if isinstance(call, dict) else None
        if not isinstance(function, dict):
            continue
        raw = function.get("arguments")
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(args, dict):
            continue
        inner = args.get("inner")
        if isinstance(inner, str) and inner.strip():
            continue
        args["inner"] = reasoning
        function["arguments"] = json.dumps(args, ensure_ascii=False)


class OpenAICompatible:
    def __init__(self, *, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, timeout: int = 12,
                 retries: int = 3, retry_backoff: float = 0.5,
                 max_retries: int = 6, max_backoff: float = 8.0,
                 max_duration: float | None = None,
                 max_concurrency: int | None = None,
                 max_request_bytes: int = 1_000_000,
                 retry_jitter: float = 0.0,
                 sleep=time.sleep) -> None:
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "http://localhost:20128/v1")).rstrip("/")
        self.model = model or os.environ.get("OPENAI_MODEL", "")
        # This gateway model is Responses-only even when the general provider
        # setting selects the legacy chat-completions protocol.
        self.responses_only = self.model == "github_copilot/gpt-6-luna"
        # responses（默认）| chat：本地 llama-server 走 chat completions。
        self.api_style = os.environ.get("V3_PROVIDER_API", "responses")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout = timeout
        self.retries = retries
        self.retry_backoff = retry_backoff
        # A caller may request a large retry count, but an outage must never
        # turn into an unbounded wall-clock stall.
        self.max_retries = max_retries
        self.max_backoff = max_backoff
        self.max_duration = max_duration
        if max_request_bytes <= 0:
            raise ValueError("max_request_bytes must be positive")
        self.max_request_bytes = max_request_bytes
        if retry_jitter < 0:
            raise ValueError("retry_jitter must be non-negative")
        self.retry_jitter = retry_jitter
        self.sleep = sleep
        configured_concurrency = (max_concurrency if max_concurrency is not None else
                                  int(os.environ.get("OPENAI_MAX_CONCURRENCY", "2")))
        if configured_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        self.max_concurrency = configured_concurrency
        self._slots = threading.BoundedSemaphore(configured_concurrency)
        if retries < 0 or max_retries < 0 or retry_backoff < 0 or max_backoff < 0 or (max_duration is not None and max_duration <= 0):
            raise ValueError("retry counts and backoff values must be non-negative")
        if not self.model:
            raise ValueError("OPENAI_MODEL is required")

    def __call__(self, messages) -> str:
        # The conversation is owned by the character session.  Do not force
        # JSON response mode: natural language is a deliberate escape hatch
        # for intentions requiring world interpretation.
        # Session-local names are useful to the harness but are not accepted
        # by compatible Responses endpoints. GPT-6 Luna keeps native function
        # call/result pairs during compaction; legacy channels retain the
        # historical flattening behavior below.
        if self.responses_only:
            body = {"model": self.model,
                    "input": _chat_messages_to_responses_input(messages)}
            url_path = "/responses"
        else:
            api_messages = []
            for message in messages:
                role = message.get("role")
                content = message.get("content", "")
                if role == "tool":
                    api_messages.append({"role": "user",
                                         "content": f"[工具结果] {content}"})
                else:
                    api_messages.append({"role": role, "content": content})
            # Responses for configured OpenAI-style channels; Chat Completions
            # for local llama-server (its /v1/responses parser is picky about
            # bare role/content items — chat is its battle-tested path).
            if self.api_style == "chat":
                body = {"model": self.model, "messages": api_messages}
                url_path = "/chat/completions"
            else:
                body = {"model": self.model, "input": api_messages,
                        "thinking": _thinking_param(self.model)}
                url_path = "/responses"
        request_data = json.dumps(body, ensure_ascii=False).encode()
        if len(request_data) > self.max_request_bytes:
            error = ValueError(
                f"provider request body {len(request_data)} bytes exceeds limit "
                f"{self.max_request_bytes}")
            error.request_bytes = len(request_data)  # type: ignore[attr-defined]
            error.request_limit = self.max_request_bytes  # type: ignore[attr-defined]
            error.retryable = False  # type: ignore[attr-defined]
            raise error
        return self._run_request(request_data, url_path, self._extract_text)

    def _run_request(self, request_data: bytes, url_path: str,
                     extract: Callable[[dict], Any | None]) -> Any:
        """One provider round-trip under the shared concurrency/retry/backoff
        machinery; ``extract`` pulls the payload out of a decoded response and
        returns None to schedule a retry (same semantics as the legacy
        no-textual-output path)."""
        request = Request(self.base_url + url_path,
                          data=request_data,
                          headers={"Content-Type": "application/json",
                                   "Authorization": f"Bearer {self.api_key}"}, method="POST")
        retry_limit = min(self.retries, self.max_retries)
        started = time.monotonic()
        budget = self._call_budget_seconds()
        deadline = started + budget
        acquired = False
        try:
            acquired = self._slots.acquire(timeout=budget)
            if not acquired:
                error = RuntimeError("provider concurrency wait exceeded retry deadline")
                error.attempts = 0  # type: ignore[attr-defined]
                error.retryable = True  # type: ignore[attr-defined]
                error.retry_exhausted = True  # type: ignore[attr-defined]
                raise error
            for attempt in range(retry_limit + 1):
                now = time.monotonic()
                if now >= deadline:
                    raise self._deadline_error(attempt, now - started, budget)
                # Ticket 54: never let one socket wait outlive what is left of
                # the call's budget.
                attempt_timeout = min(self.timeout, deadline - now)
                try:
                    with urlopen(request, timeout=attempt_timeout) as response:
                        raw_response = _read_response_body(
                            response, deadline=deadline, started=started,
                            budget=budget, attempts=attempt + 1)
                    try:
                        result = json.loads(raw_response.decode())
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        error = RuntimeError(
                            f"provider invalid JSON response on attempt {attempt + 1}: "
                            f"{str(exc)[:200]}")
                        error.attempts = attempt + 1  # type: ignore[attr-defined]
                        error.retryable = True  # type: ignore[attr-defined]
                        error.retry_exhausted = attempt >= retry_limit  # type: ignore[attr-defined]
                        raise error from exc
                    if not isinstance(result, dict):
                        error = RuntimeError(
                            f"provider response must be a JSON object, got "
                            f"{type(result).__name__}")
                        error.attempts = attempt + 1  # type: ignore[attr-defined]
                        error.retryable = True  # type: ignore[attr-defined]
                        error.retry_exhausted = attempt >= retry_limit  # type: ignore[attr-defined]
                        raise error
                    content = extract(result)
                    if content is None:
                        if attempt >= retry_limit:
                            error = RuntimeError(
                                f"provider response contained no textual output after "
                                f"{attempt + 1} attempts (status={result.get('status')})")
                            error.attempts = attempt + 1  # type: ignore[attr-defined]
                            error.retryable = True  # type: ignore[attr-defined]
                            error.retry_exhausted = True  # type: ignore[attr-defined]
                            raise error
                        delay = min(self.retry_backoff * (2 ** attempt), self.max_backoff)
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise self._deadline_error(attempt + 1,
                                                       time.monotonic() - started, budget)
                        delay = min(delay, remaining)
                        self.sleep(delay)
                        continue
                    break
                except _ResponseBudgetExceeded as exc:
                    error = RuntimeError(
                        f"provider request budget exhausted on attempt {exc.attempts} "
                        f"({exc.elapsed:.1f}s of {exc.budget:.1f}s budget): the "
                        f"response never finished — upstream trickled or held "
                        f"the connection")
                    error.attempts = exc.attempts  # type: ignore[attr-defined]
                    error.retryable = True  # type: ignore[attr-defined]
                    error.retry_exhausted = True  # type: ignore[attr-defined]
                    raise error from exc
                except HTTPError as exc:
                    detail = exc.read().decode(errors="replace")[:800]
                    if exc.code not in {408, 409, 425, 429} and not 500 <= exc.code <= 599:
                        raise RuntimeError(f"provider HTTP {exc.code}: {detail}") from exc
                    if attempt >= retry_limit:
                        error = RuntimeError(f"provider HTTP {exc.code} after {attempt + 1} attempts: {detail}")
                        error.provider_code = exc.code  # type: ignore[attr-defined]
                        error.attempts = attempt + 1  # type: ignore[attr-defined]
                        error.retryable = True  # type: ignore[attr-defined]
                        error.retry_exhausted = True  # type: ignore[attr-defined]
                        raise error from exc
                    delay = min(self.retry_backoff * (2 ** attempt), self.max_backoff)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        continue
                    delay = min(delay, remaining)
                    self.sleep(delay)
                except (URLError, TimeoutError) as exc:
                    if attempt >= retry_limit:
                        reason = getattr(exc, "reason", str(exc))
                        error = RuntimeError(f"provider connection error after {attempt + 1} attempts: {reason}")
                        error.attempts = attempt + 1  # type: ignore[attr-defined]
                        error.retryable = True  # type: ignore[attr-defined]
                        error.retry_exhausted = True  # type: ignore[attr-defined]
                        raise error from exc
                    delay = min(self.retry_backoff * (2 ** attempt), self.max_backoff)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        continue
                    delay = min(delay, remaining)
                    self.sleep(delay)
        finally:
            if acquired:
                self._slots.release()
        return content

    def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        """Call native tools and return the chat-style message consumed by V4Session.

        GPT-6 Luna uses Responses items at the wire boundary; all other models
        keep the legacy Chat Completions request and response path."""
        if self.responses_only:
            body = {"model": self.model,
                    "input": _chat_messages_to_responses_input(messages),
                    "tools": _chat_tools_to_responses_tools(tools),
                    "tool_choice": "auto"}
            return self._run_request(json.dumps(body, ensure_ascii=False).encode(),
                                     "/responses", _extract_responses_tool_message)
        body = {"model": self.model, "messages": messages,
                "tools": tools, "tool_choice": "auto"}
        return self._run_request(json.dumps(body, ensure_ascii=False).encode(),
                                 "/chat/completions", self._extract_tool_message)

    @staticmethod
    def _extract_tool_message(result: dict) -> dict | None:
        try:
            message = result["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            return None
        if not isinstance(message, dict):
            return None
        # T1 文本即说话 (docs §4): a reply with text and no tool_calls is a
        # VALID decision — the words are spoken, the turn idles. Only an
        # unusable response shape (no content AND no calls) retries.
        calls = message.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            if str(message.get("content") or "").strip():
                return {"role": message.get("role", "assistant"),
                        "content": message.get("content", ""), "tool_calls": []}
            return None
        _fill_inner_from_reasoning(message)
        return message

    def _extract_text(self, result: dict) -> str | None:
        if self.api_style == "chat" and not self.responses_only:
            try:
                content = result["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                return None
            return content.strip() or None
        content = result.get("output_text")
        if isinstance(content, str) and content.strip():
            return content.strip()
        output = result.get("output")
        if not isinstance(output, list):
            return None
        pieces = []
        for item in output:
            if not isinstance(item, dict):
                continue
            for part in item.get("content", []):
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    pieces.append(part["text"])
        text = "".join(pieces).strip()
        return text or None

    def _call_budget_seconds(self) -> float:
        """Hard wall-clock budget for one provider call, over all attempts.

        ``max_duration`` when the caller set one; otherwise the structural
        worst case of the retry policy, so even a provider without an explicit
        duration still has a total bound instead of only per-recv timeouts."""
        if self.max_duration is not None:
            return self.max_duration
        backoff = sum(min(self.retry_backoff * (2 ** i), self.max_backoff)
                      for i in range(min(self.retries, self.max_retries)))
        return (self.retries + 1) * self.timeout + backoff

    @staticmethod
    def _deadline_error(attempt: int, elapsed: float, budget: float) -> RuntimeError:
        """Budget-exhausted error with the same retry metadata as before."""
        error = RuntimeError(
            f"provider retry deadline exhausted after {attempt} attempts "
            f"({elapsed:.1f}s of {budget:.1f}s budget)")
        error.attempts = attempt  # type: ignore[attr-defined]
        error.retryable = True  # type: ignore[attr-defined]
        error.retry_exhausted = True  # type: ignore[attr-defined]
        return error

    def worst_case_seconds(self) -> float:
        """Conservative wall-clock upper bound for one provider call.

        Ticket 54 bounds the call itself by ``_call_budget_seconds()`` and
        checks that deadline between response chunks; the final chunk read may
        still block for at most one socket timeout past the deadline."""
        return self._call_budget_seconds() + self.timeout


def provider_from_env(*, timeout: int | None = None, retries: int | None = None,
                      max_retries: int | None = None, max_backoff: float | None = None,
                      max_duration: float | None = None,
                      max_concurrency: int | None = None) -> OpenAICompatible:
    """A resilient provider whose retry budget is tuned from the environment.

    Provider blips are common, so the default budget is generous (8 retries,
    120 s max backoff, 600 s cap) and each knob is overridable via
    ``V3_PROVIDER_*`` so a run can survive an outage instead of exhausting a
    small fixed budget. The run's wall deadline is the ultimate bound; a run
    that dies anyway is resumable from its last checkpoint.

    ``V3_PROVIDER_MAX_DURATION`` is a true wall-clock bound for ONE call
    (ticket 54): it caps each attempt's socket timeout and is re-checked
    between response chunks, so a trickling or held-open upstream can no
    longer hang a single request past it.
    """
    timeout = int(os.environ.get("V3_PROVIDER_TIMEOUT", str(timeout if timeout is not None else 30)))
    retries = int(os.environ.get("V3_PROVIDER_RETRIES", str(retries if retries is not None else 8)))
    max_retries = int(os.environ.get("V3_PROVIDER_MAX_RETRIES", str(max_retries if max_retries is not None else retries)))
    max_backoff = float(os.environ.get("V3_PROVIDER_MAX_BACKOFF",
                                       str(max_backoff if max_backoff is not None else 120.0)))
    max_duration = float(os.environ.get("V3_PROVIDER_MAX_DURATION",
                                        str(max_duration if max_duration is not None else 600.0)))
    max_concurrency = int(os.environ.get("V3_PROVIDER_CONCURRENCY",
                                         str(max_concurrency if max_concurrency is not None else 4)))
    return OpenAICompatible(
        timeout=timeout, retries=retries, max_retries=max_retries,
        retry_backoff=1.0, max_backoff=max_backoff, max_duration=max_duration,
        max_concurrency=max_concurrency)
