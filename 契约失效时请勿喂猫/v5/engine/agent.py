"""模型的接入：一次调用 = 一个动作。

两次教训写在这里：模型只看见渲染过的上下文（不看见状态键、不看见别人的记忆）；
拒绝也必须是有用的（为什么不成、眼前有什么），否则模型只能在原地打转。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .core import World
from .events import EventLog
from .prompt import system_prompt, tool_specs, turn_message
from .surface import block
from .rules import Receipt, submit


@dataclass
class Decision:
    verb: str
    args: dict[str, Any]
    raw: str = ""
    latency: float = 0.0


class ProviderError(RuntimeError):
    pass


class DecisionParseError(RuntimeError):
    """模型的工具调用无法解析：记成一条失败的回合，不让整局崩掉。"""

    def __init__(self, raw: str):
        super().__init__("工具调用无法解析")
        self.raw = raw


@dataclass
class ChatProvider:
    """OpenAI 兼容的 chat completions（本地 LiteLLM 代理）。"""

    model: str
    base_url: str = field(default_factory=lambda: os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1"))
    api_key: str = field(default_factory=lambda: os.environ.get("LITELLM_MASTER_KEY")
                         or os.environ.get("OPENAI_API_KEY", ""))
    timeout: int = 90
    retries: int = 3

    def decide(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Decision:
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "required",
            "temperature": 0.7,
            "max_tokens": 700,
        }, ensure_ascii=False).encode("utf-8")
        last: Exception | None = None
        for attempt in range(self.retries):
            started = time.time()
            try:
                request = urllib.request.Request(
                    f"{self.base_url.rstrip('/')}/chat/completions", data=body,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.api_key}"})
                with urllib.request.urlopen(request, timeout=self.timeout) as fh:
                    payload = json.loads(fh.read().decode("utf-8"))
                message = payload["choices"][0]["message"]
                calls = message.get("tool_calls") or []
                if not calls:
                    raise ProviderError("模型没有给出工具调用")
                call = calls[0]
                raw_call = json.dumps(call, ensure_ascii=False)
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError as exc:
                    raise DecisionParseError(raw_call) from exc
                return Decision(verb=call["function"]["name"], args=args,
                                raw=raw_call, latency=round(time.time() - started, 2))
            except DecisionParseError:
                raise
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError,
                    ProviderError) as exc:      # noqa: PERF203 - 退避重试是刻意的
                last = exc
                time.sleep(min(2 ** attempt, 8))
        raise ProviderError(f"provider 调用失败：{last}")


@dataclass
class MockProvider:
    """测试与干跑用：按脚本给出动作，证明这条回路本身是通的。"""

    script: list[Decision]
    cursor: int = 0

    def decide(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Decision:
        if self.cursor >= len(self.script):
            return Decision(verb="wait", args={}, raw="mock:wait")
        decision = self.script[self.cursor]
        self.cursor += 1
        if not decision.raw:
            decision.raw = json.dumps({"name": decision.verb, "arguments": decision.args},
                                      ensure_ascii=False)
        return decision


@dataclass
class Turn:
    actor: str
    at: int
    decision: Decision
    receipt: Receipt
    context: dict[str, Any]
    messages: int


def agent_turn(world: World, log: EventLog, actor: str, provider: Any,
               history: dict[str, list[dict[str, Any]]]) -> Turn:
    """一次模型回合：给上下文 → 收一个工具调用 → 交给世界裁。"""
    system = system_prompt(world, actor)
    blk = block(world, actor)
    context = {"system": system, "turn": turn_message(world, actor), "block": blk}
    messages = [{"role": "system", "content": system},
                *history.get(actor, []),
                {"role": "user", "content": context["turn"]}]
    started_at = world.clock
    decision = provider.decide(messages, tool_specs())
    receipt = submit(world, log, actor, decision.verb, dict(decision.args))

    result = ("；".join(receipt.texts) if receipt.ok
              else "没成：" + receipt.reason + ("\n" + "\n".join(receipt.hints) if receipt.hints else ""))
    history.setdefault(actor, []).extend([
        {"role": "user", "content": context["turn"]},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": f"call_{len(log)}", "type": "function",
                         "function": {"name": decision.verb,
                                      "arguments": json.dumps(decision.args, ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": f"call_{len(log)}", "content": result},
    ])
    # 只保留最近若干轮，避免上下文无限膨胀（M6 才做真正的记忆巩固）
    history[actor] = history[actor][-8:]
    return Turn(actor=actor, at=started_at, decision=decision, receipt=receipt,
                context=context, messages=len(messages))
