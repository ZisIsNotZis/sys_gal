"""反作弊检查：故事是被世界推动的，还是被作者推动的？

三项机械检查（能查的都查，查不到的写在报告里）：
1. 种子里没有对具名角色的祈使句（"让甲去…"、"乙应当…"）；
2. 没有天意事件：每个排程效果都必须是制度或物理，并且指向真实存在的地点；
3. 预期结局不是唯一可达结局：每条被写出来的路径都必须能走到不同结局。

用法（在 `v5/` 目录下）：python3 scripts/anti_cheat.py [--verbose]
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

import library  # noqa: E402,F401
from engine.seed import build  # noqa: E402
from library import EFFECTS  # noqa: E402

IMPERATIVE = ("让", "应当", "应该", "必须", "务必", "记得", "不准", "不许", "要他去", "要她来")


def story_dirs() -> list[Path]:
    return sorted(p for p in (ROOT / "stories").iterdir()
                  if p.is_dir() and (p / "seed.yml").exists())


def _strings(seed: dict[str, Any]):
    for section in ("places", "people", "objects"):
        for row in seed.get(section, []):
            for field in ("prose", "identity"):
                if row.get(field):
                    yield f"{section}.{row['id']}.{field}", row[field]
            for belief in row.get("believes", []) or []:
                yield f"{section}.{row['id']}.believes", belief["says"]
            for key, value in (row.get("state") or {}).items():
                if isinstance(value, str):
                    yield f"{section}.{row['id']}.state.{key}", value


def check_imperatives(seed: dict[str, Any], story: str) -> list[str]:
    names = {row["name"] for row in seed.get("people", [])}
    problems = []
    for where, text in _strings(seed):
        for word in IMPERATIVE:
            if word not in text:
                continue
            near = [n for n in names if n in text or f"{word}{n}" in text]
            if near:
                problems.append(f"{story}:{where} 像是对具名角色下命令（{word}…{'/'.join(near)}）：{text}")
    return problems


def check_destiny(seed: dict[str, Any], story: str) -> list[str]:
    world = build(seed)
    problems = []
    for item in seed.get("schedule", []) or []:
        effect = item["effect"]
        kind = effect.get("kind")
        if kind not in EFFECTS:
            problems.append(f"{story}: 排程效果「{kind}」没有对应的制度或物理")
        if effect.get("actor") or effect.get("say") or effect.get("do"):
            problems.append(f"{story}: 排程里有人在替角色做决定：{effect}")
        place = effect.get("place")
        if place is not None and place not in world.entities:
            problems.append(f"{story}: 排程指向不存在的地点「{place}」")
    return problems


def check_reachability(story: str, verbose: bool) -> tuple[list[str], list[str]]:
    """每条写出来的路径都要真的走到不同结局，否则"结局"只是作者的断言。"""
    problems: list[str] = []
    notes: list[str] = []
    try:
        scenario = importlib.import_module(f"stories.{story}.scenario")
    except ModuleNotFoundError:
        return problems, [f"{story}: 没有 scenario.py，跳过可达性检查"]
    variants = sorted(getattr(scenario, "SCRIPTS", {}))
    if len(variants) < 2:
        problems.append(f"{story}: 只写了一条路径，无法证明结局不是唯一的")
        return problems, notes
    endings = {}
    for variant in variants:
        run = scenario.play(variant)
        endings[variant] = getattr(scenario, "summary", lambda r: {}) (run).get("结局", "未声明结局")
    distinct = set(endings.values())
    if len(distinct) < 2:
        problems.append(f"{story}: {len(variants)} 条路径只走到 {len(distinct)} 个结局")
    if verbose:
        for variant, end in endings.items():
            notes.append(f"{story}[{variant}] → {end}")
    return problems, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    problems: list[str] = []
    notes: list[str] = []
    for path in story_dirs():
        story = path.name
        seed = yaml.safe_load((path / "seed.yml").read_text(encoding="utf-8"))
        problems += check_imperatives(seed, story)
        problems += check_destiny(seed, story)
        found, extra = check_reachability(story, args.verbose)
        problems += found
        notes += extra

    for note in notes:
        print(f"· {note}")
    for problem in problems:
        print(f"失败：{problem}")
    print("")
    if problems:
        print(f"{len(problems)} 项失败")
        return 1
    print(f"通过（{len(story_dirs())} 支故事：无祈使句、无天意事件、结局不唯一）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
