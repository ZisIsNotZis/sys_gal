"""OpenAI-compatible Responses API provider using only the standard library."""

from __future__ import annotations

import json
from typing import Any, Callable
import os
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


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
        # by the compatible Responses endpoint.
        api_messages = [{key: message[key] for key in ("role", "content")}
                        for message in messages]
        # Two API shapes (V4-DESIGN §1 reasoning matrix): the Responses API
        # for OpenAI-style channels, Chat Completions for local
        # llama-server (its /v1/responses parser is picky about bare
        # role/content items — chat is its battle-tested path).
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
        acquired = False
        try:
            remaining = None if self.max_duration is None else max(0.0, self.max_duration)
            acquired = self._slots.acquire(timeout=remaining)
            if not acquired:
                error = RuntimeError("provider concurrency wait exceeded retry deadline")
                error.attempts = 0  # type: ignore[attr-defined]
                error.retryable = True  # type: ignore[attr-defined]
                error.retry_exhausted = True  # type: ignore[attr-defined]
                raise error
            for attempt in range(retry_limit + 1):
                if self.max_duration is not None and time.monotonic() - started >= self.max_duration:
                    error = RuntimeError(f"provider retry deadline exhausted after {attempt} attempts")
                    error.attempts = attempt  # type: ignore[attr-defined]
                    error.retryable = True  # type: ignore[attr-defined]
                    error.retry_exhausted = True  # type: ignore[attr-defined]
                    raise error
                try:
                    with urlopen(request, timeout=self.timeout) as response:
                        raw_response = response.read()
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
                        if self.max_duration is not None:
                            remaining = self.max_duration - (time.monotonic() - started)
                            if remaining <= 0:
                                error = RuntimeError(
                                    f"provider retry deadline exhausted after {attempt + 1} attempts")
                                error.attempts = attempt + 1  # type: ignore[attr-defined]
                                error.retryable = True  # type: ignore[attr-defined]
                                error.retry_exhausted = True  # type: ignore[attr-defined]
                                raise error
                            delay = min(delay, remaining)
                        self.sleep(delay)
                        continue
                    break
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
                    if self.max_duration is not None:
                        remaining = self.max_duration - (time.monotonic() - started)
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
                    if self.max_duration is not None:
                        remaining = self.max_duration - (time.monotonic() - started)
                        if remaining <= 0:
                            continue
                        delay = min(delay, remaining)
                    self.sleep(delay)
        finally:
            if acquired:
                self._slots.release()
        return content

    def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        """One chat-completions call with native function tools; returns the
        raw assistant message (``tool_calls`` entries carry
        {id, function: {name, arguments-as-JSON-string}}). A reply with no
        tool_calls is a valid decision (no world action); only unusable
        response shapes retry."""
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
        return message

    def _extract_text(self, result: dict) -> str | None:
        if self.api_style == "chat":
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

    def worst_case_seconds(self) -> float:
        """Conservative wall-clock upper bound for one provider call."""
        # max_duration bounds retry bookkeeping/backoff; one request may have
        # already entered urlopen when that budget expires.
        return (self.max_duration if self.max_duration is not None
                else (self.retries + 1) * self.timeout +
                     sum(min(self.retry_backoff * (2 ** i), self.max_backoff)
                         for i in range(min(self.retries, self.max_retries)))) + self.timeout


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
