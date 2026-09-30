"""Ticket 54: one provider request must have a real wall-clock bound.

``urlopen(request, timeout=...)`` bounds a single socket operation, not the
whole call: an upstream that trickle-feeds a body (or holds the connection
open) keeps ``response.read()`` blocked forever, so the run's provider layer
had no bound of its own — the 2026-10-01 run died at sim 11:32 exactly this
way (ticket 53/54). These gates drive a local fake upstream (stdlib
``http.server``, seconds-scale budgets, no minute-long sleeps):

(a) a trickling/never-finishing response must error out inside the budget
    instead of blocking;
(b) a normal response and a transient 502 retry sequence behave exactly as
    before (one request, same retry count, same result);
(c) a slow-but-completing response inside the budget must succeed and must
    not be truncated by the new bound.
"""

from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from harness.provider import OpenAICompatible


def _text_response(text: str) -> bytes:
    return json.dumps({"output_text": text}, ensure_ascii=False).encode()


class _FakeUpstreamHandler(BaseHTTPRequestHandler):
    """Records the request path and answers per the server's behavior."""

    behavior = "normal"

    def log_message(self, *args: object) -> None:  # silence request spam
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.server.seen.append(self.path)  # type: ignore[attr-defined]
        if self.behavior == "trickle":
            self._trickle()
        elif self.behavior == "slow":
            self._slow()
        elif self.behavior == "flaky":
            seen = self.server.seen  # type: ignore[attr-defined]
            if len(seen) <= 2:
                self._respond(502, b"upstream blip")
            else:
                self._respond(200, _text_response("重试后成功"))
        else:
            self._respond(200, _text_response("正常回复"))

    def _respond(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _slow(self) -> None:
        """A body that arrives in pieces over ~0.4s, well inside the budget."""
        body = _text_response("慢慢来也算完成")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        time.sleep(0.15)  # silent before the first byte: still one live socket
        try:
            step = max(1, len(body) // 4)
            for start in range(0, len(body), step):
                self.wfile.write(body[start:start + step])
                self.wfile.flush()
                if start + step < len(body):
                    time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _trickle(self) -> None:
        """Declare a huge body, then dribble it out; never completes on its
        own. The 11:13/11:16/11:32 upstream held exactly like this."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "10000000")
        self.end_headers()
        try:
            for _ in range(4000):          # ~80s of dribble, far past any budget
                self.wfile.write(b"    ")
                self.wfile.flush()
                time.sleep(0.02)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True


class FakeUpstream:
    """Ephemeral localhost HTTP server for provider round-trip tests."""

    def __init__(self, behavior: str) -> None:
        handler = type("_Handler", (_FakeUpstreamHandler,), {"behavior": behavior})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.seen: list[str] = []
        self.server.seen = self.seen  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def __enter__(self) -> "FakeUpstream":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _provider(base_url: str, *, timeout: float = 5, retries: int = 0,
              max_duration: float = 5.0) -> OpenAICompatible:
    return OpenAICompatible(
        base_url=base_url, model="m", api_key="k", timeout=timeout,
        retries=retries, max_retries=retries, retry_backoff=0.0, max_backoff=0.0,
        max_duration=max_duration, max_concurrency=1, sleep=lambda _: None)


class ProviderWallClockBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        # The plain-text path is what _extract_text reads; pin it so a host
        # environment cannot flip the wire style under the test.
        patcher = mock.patch.dict("os.environ", {"V3_PROVIDER_API": "responses"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_trickling_response_is_cut_off_within_the_budget(self):
        """(a) ticket 54: a dribbling upstream must not block the call.

        Before the fix `response.read()` never returned (socket timeout only
        bounds one recv, and every recv got bytes): the 11:32 decision hung
        with no provider-level bound at all.
        """
        with FakeUpstream("trickle") as upstream:
            provider = _provider(upstream.base_url, timeout=5, retries=8,
                                 max_duration=0.6)
            started = time.monotonic()
            with self.assertRaises(RuntimeError) as raised:
                provider([{"role": "user", "content": "喂猫"}])
            elapsed = time.monotonic() - started
        error = raised.exception
        self.assertIn("budget exhausted", str(error))
        self.assertIn("trickled", str(error))
        self.assertGreaterEqual(elapsed, 0.4)   # it really waited the budget
        self.assertLess(elapsed, 4.0)           # …and did not hang
        self.assertTrue(getattr(error, "retryable"))
        self.assertTrue(getattr(error, "retry_exhausted"))
        self.assertGreaterEqual(getattr(error, "attempts"), 1)
        self.assertEqual(upstream.seen, ["/responses"])

    def test_normal_response_is_unchanged(self):
        """(b) a healthy round-trip: same result, exactly one request."""
        with FakeUpstream("normal") as upstream:
            provider = _provider(upstream.base_url)
            started = time.monotonic()
            out = provider([{"role": "user", "content": "你好"}])
            elapsed = time.monotonic() - started
        self.assertEqual(out, "正常回复")
        self.assertEqual(upstream.seen, ["/responses"])
        self.assertLess(elapsed, 2.0)

    def test_transient_502_retries_the_same_number_of_times(self):
        """(b) retry semantics are untouched: two blips, then success."""
        with FakeUpstream("flaky") as upstream:
            provider = _provider(upstream.base_url, retries=3, max_duration=5.0)
            out = provider([{"role": "user", "content": "你好"}])
        self.assertEqual(out, "重试后成功")
        self.assertEqual(len(upstream.seen), 3)

    def test_slow_but_completing_response_succeeds(self):
        """(c) slow is not hung: a body that lands inside the budget wins."""
        with FakeUpstream("slow") as upstream:
            provider = _provider(upstream.base_url, timeout=2, retries=0,
                                 max_duration=5.0)
            started = time.monotonic()
            out = provider([{"role": "user", "content": "慢慢答"}])
            elapsed = time.monotonic() - started
        self.assertEqual(out, "慢慢来也算完成")   # not truncated, not killed
        self.assertEqual(upstream.seen, ["/responses"])
        self.assertGreaterEqual(elapsed, 0.3)
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
