"""OpenAI-compatible Responses API provider using only the standard library."""

from __future__ import annotations

import json
import os
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class OpenAICompatible:
    def __init__(self, *, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, timeout: int = 12,
                 retries: int = 3, retry_backoff: float = 0.5,
                 max_retries: int = 6, max_backoff: float = 8.0,
                 max_duration: float | None = None,
                 sleep=time.sleep) -> None:
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "http://localhost:20128/v1")).rstrip("/")
        self.model = model or os.environ.get("OPENAI_MODEL", "")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout = timeout
        self.retries = retries
        self.retry_backoff = retry_backoff
        # A caller may request a large retry count, but an outage must never
        # turn into an unbounded wall-clock stall.
        self.max_retries = max_retries
        self.max_backoff = max_backoff
        self.max_duration = max_duration
        self.sleep = sleep
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
        body = {"model": self.model, "input": api_messages, "max_output_tokens": 500,
                "thinking": "none"}
        request = Request(self.base_url + "/responses",
                          data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json",
                                   "Authorization": f"Bearer {self.api_key}"}, method="POST")
        retry_limit = min(self.retries, self.max_retries)
        started = time.monotonic()
        for attempt in range(retry_limit + 1):
            if self.max_duration is not None and time.monotonic() - started >= self.max_duration:
                error = RuntimeError(f"provider retry deadline exhausted after {attempt} attempts")
                error.attempts = attempt  # type: ignore[attr-defined]
                error.retryable = True  # type: ignore[attr-defined]
                raise error
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    result = json.loads(response.read().decode())
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
                    raise error from exc
                delay = min(self.retry_backoff * (2 ** attempt), self.max_backoff)
                if self.max_duration is not None:
                    remaining = self.max_duration - (time.monotonic() - started)
                    if remaining <= 0:
                        continue
                    delay = min(delay, remaining)
                self.sleep(delay)
        content = result.get("output_text")
        if isinstance(content, str):
            content = content.strip()
        if not content:
            content = "".join(part.get("text", "") for item in result["output"]
                               for part in item.get("content", []) if isinstance(part, dict))
        if not content or not content.strip():
            raise ValueError(f"model returned no textual output (status={result.get('status')})")
        return content

    def worst_case_seconds(self) -> float:
        """Conservative wall-clock upper bound for one provider call."""
        # max_duration bounds retry bookkeeping/backoff; one request may have
        # already entered urlopen when that budget expires.
        return (self.max_duration if self.max_duration is not None
                else (self.retries + 1) * self.timeout +
                     sum(min(self.retry_backoff * (2 ** i), self.max_backoff)
                         for i in range(min(self.retries, self.max_retries)))) + self.timeout
