"""票 106（E109）工件回归：18:00 检查点短程续跑 + 唤醒是否换来回合。

用法（在 v4 目录下）：

    python3 .scratch/v4-first-day/analyze_e109_wakeup.py short     # 18:00 -> 18:40，stub 只 wait
    python3 .scratch/v4-first-day/analyze_e109_wakeup.py night     # 18:00 -> 20:00，MC 一律长睡
    python3 .scratch/v4-first-day/analyze_e109_wakeup.py load      # D1 22:00 检查点加载检查

两次续跑都走生产的 v4 路径（`resume_run.resume` → `make_persistent_agent_v4` +
`_execute_chain`），只是把 provider 换成按世界消息里的 `在场：<名字>(you)` 分派的 stub。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

V4 = Path(__file__).resolve().parents[2] / "v4"
os.chdir(V4)
sys.path.insert(0, str(V4))

from harness.checkpoint import load_checkpoint           # noqa: E402
from harness.engine import AsyncEngine                    # noqa: E402
from harness.kernel import World                          # noqa: E402
from harness.seed import load_story_pack                  # noqa: E402
from harness.resume_run import resume                     # noqa: E402

EIGHTEEN = "runs/real-20261018T062031+0800-1910732-547128242.checkpoint.json"
DAY_ONE = "runs/real-20261018T085705+0800-2116654-169068128.checkpoint.json"
MC = {"陈默", "林瑶", "唐小岚"}
NAME = re.compile(r"在场：([^，(\s]+)\(you\)")


class StubProvider:
    """每个角色第一拍按 `sleep` 剧本走，之后 60 秒一觉。"""

    def __init__(self, sleep_seconds: int = 0, sleepers: set[str] | None = None):
        self.sleep_seconds = sleep_seconds
        self.sleepers = MC if sleepers is None else sleepers
        self.turns: dict[str, int] = {}

    def __call__(self, messages) -> str:
        # V4Session.compact() 走文本通道；stub 只需要一句合法的回忆摘要。
        return "（前情提要：刚才在校园里各自等消息。）"

    def chat_with_tools(self, messages, tools):
        who = ""
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            hit = NAME.search(str(message.get("content") or ""))
            if hit:
                who = hit.group(1)
            break
        seen = self.turns.get(who, 0) + 1
        self.turns[who] = seen
        args = {"duration_seconds": 60, "inner": "（stub：先等着，看会不会有人来。）"}
        if self.sleep_seconds and who in self.sleepers and seen == 1:
            args = {"duration_seconds": self.sleep_seconds, "sleep": True,
                    "inner": "（stub：困了，睡下。）"}
        return {"role": "assistant", "content": "",
                "tool_calls": [{"id": "c0", "type": "function",
                                "function": {"name": "wait",
                                             "arguments": json.dumps(args)}}]}


def report(out: Path, since: str, sleeps: bool) -> None:
    data = json.load(open(out))
    turns = [turn for turn in data["agent_turns"]
             if str(turn["perception"].get("time", "")) >= since]
    print(f"--- {out.name}: resumed-segment turns={len(turns)} "
          f"events={data['outcome']['world_version']} end={data['outcome']['time']}")
    for turn in turns:
        calls = (turn.get("intention") or {}).get("args", {}).get("calls") or []
        shape = [c.get("args", {}) for c in calls]
        print("   ", turn["perception"]["time"], turn["actor"], turn.get("result"), shape)
    events = [event for event in data.get("world_events") or []
              if str(event.get("time", "")) > str(since)]
    for event in events:
        payload = event.get("payload") or {}
        brief = {key: payload.get(key) for key in
                 ("event", "action", "sleep", "duration_seconds", "target")
                 if payload.get(key) is not None}
        print("    world:", event["time"], event["kind"], event.get("actor"), brief,
              sorted(event.get("visible_to") or []))
    if sleeps:
        print("wait_woken:", [(event["time"], event.get("actor")) for event in events
                              if event["kind"] == "wait_woken"])


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "short"
    if mode == "load":
        checkpoint = load_checkpoint(Path(DAY_ONE))
        world = World.from_checkpoint(load_story_pack().build_world(), checkpoint["world"])
        from harness.agent_state import PrivateState
        agents = {name: (lambda text, state: {"text": "", "calls": []})
                  for name, actor in world.actors.items() if actor.role != "extra"}
        states = {name: PrivateState(name) for name in agents}
        engine = AsyncEngine(world, agents, states, None, None)
        engine.restore_checkpoint(checkpoint["runner"])
        print("loaded D1 22:00 checkpoint:",
              {"now": world.now.isoformat(), "events": len(world.event_log),
               "version": world.version, "queue": len(world._queue),
               "turns": engine._turns, "cursor": world._cursor})
        print("awake+idle actors at 22:00:",
              {name: {"busy_until": a.busy_until, "sleeping": a.sleeping,
                      "cursor": world._cursor.get(name)}
               for name, a in world.actors.items() if a.role != "extra"})
        return
    if mode == "short":
        out = Path("/tmp/e109-short.json")
        resume(Path(EIGHTEEN), out=out, endpoint="2026-03-16T18:40:00+08:00",
               call=StubProvider())
        report(out, "2026-03-16T18:00", sleeps=False)
        return
    if mode == "night_all":
        # 全部角色都在自己第一拍睡下：最后一个起睡的人那一刻没有别人在思考，
        # 正是 D1 18:35 林瑶那一拍的形状。
        actors = load_checkpoint(Path(EIGHTEEN))["world"]["actors"]
        out = Path("/tmp/e109-night-all.json")
        resume(Path(EIGHTEEN), out=out, endpoint="2026-03-16T20:00:00+08:00",
               call=StubProvider(sleep_seconds=12 * 3600, sleepers=set(actors)))
        report(out, "2026-03-16T18:00", sleeps=True)
        return
    if mode == "night":
        out = Path("/tmp/e109-night.json")
        resume(Path(EIGHTEEN), out=out, endpoint="2026-03-16T20:00:00+08:00",
               call=StubProvider(sleep_seconds=12 * 3600))
        report(out, "2026-03-16T18:00", sleeps=True)
        return
    raise SystemExit(f"unknown mode {mode}")


if __name__ == "__main__":
    main()
