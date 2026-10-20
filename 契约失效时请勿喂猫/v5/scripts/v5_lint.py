"""v5 的结构检查：机械可判的那部分。

用法（在 `v5/` 目录下）：

    python3 scripts/v5_lint.py            # 报告；孤儿概念记为"待补"
    python3 scripts/v5_lint.py --strict    # 孤儿概念也算失败（M2 起使用）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

import library  # noqa: E402,F401
from engine.render import STATE_RENDERERS, pairing_report  # noqa: E402
from engine.rules import REGISTRY  # noqa: E402
from engine.seed import entity_names, state_keys  # noqa: E402

IMPERATIVE = ("让", "应当", "应该", "必须", "记得", "务必")

#: 引擎词汇：种子里的 id 撞上它们，会让"引擎不认识故事名词"这条检查失效。
RESERVED = {"note", "event", "state", "memory", "flag", "clock", "schedule", "parent",
            "marks", "identity", "beliefs", "knowledge", "world", "actor", "target"}


def story_dirs() -> list[Path]:
    return sorted(p for p in (ROOT / "stories").iterdir() if p.is_dir() and not p.name.startswith("_"))


def seed_files() -> list[Path]:
    return [p / "seed.yml" for p in story_dirs() if (p / "seed.yml").exists()]


def check_seed_shape(fails: list[str], warns: list[str]) -> None:
    for path in seed_files():
        seed = yaml.safe_load(path.read_text(encoding="utf-8"))
        story = path.parent.name
        for section in ("places", "people", "objects"):
            for row in seed.get(section, []):
                if row["id"] in RESERVED:
                    fails.append(f"{story}: 实体 id「{row['id']}」与引擎词汇同名")
        for problem in pairing_report(state_keys(seed)):
            fails.append(f"{story}: {problem}")
        for section in ("places", "people", "objects"):
            for row in seed.get(section, []):
                for field in ("prose",):
                    text = row.get(field, "")
                    for word in IMPERATIVE:
                        if word in text:
                            warns.append(f"{story}: {row['id']} 的散文里出现祈使词「{word}」：{text}")
                for value in (row.get("state") or {}).values():
                    if isinstance(value, str):
                        for word in IMPERATIVE:
                            if word in value:
                                warns.append(f"{story}: {row['id']} 的状态文本里出现祈使词「{word}」：{value}")


def check_engine_is_story_blind(fails: list[str]) -> None:
    """引擎里不许出现故事名词。

    ASCII 的 id 只查"被当成字面量写进去"（`"note"`），因为 `event.note` 这类
    普通属性名与故事无关；中文名足够独特，按子串查。
    """
    names: set[str] = set()
    for path in seed_files():
        names |= entity_names(yaml.safe_load(path.read_text(encoding="utf-8")))
    names = {n for n in names if len(n) >= 2}
    for path in sorted((ROOT / "engine").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for name in sorted(names):
            if re.fullmatch(r"[a-z_]+", name):
                hit = re.search(rf"[\"']{name}[\"']", source)
            else:
                hit = name in source
            if hit:
                fails.append(f"engine/{path.name} 把故事名词「{name}」写成了字面量")


def check_concepts(fails: list[str], warns: list[str], strict: bool) -> None:
    """孤儿检查：一个概念至少要"被两支故事用到"。

    已建(present)与已规划(declared)分开报：设计上短故事阶梯就是为长弧预备概念，
    所以声明到 ≥2 即可；但只有一支故事真用过时仍然要报出来，免得声明变成空话。
    """
    stories = {p.name for p in story_dirs()}
    for verb, rule in sorted(REGISTRY.items()):
        if not callable(rule.when) or not callable(rule.atoms) or not callable(rule.render):
            fails.append(f"概念 {verb} 缺少 when/atoms/render 之一")
        present = set(rule.used_by) & stories
        declared = set(rule.used_by)
        if len(declared) < 2:
            fails.append(f"概念 {verb} 只声明了 {sorted(declared) or '零'} 支故事（孤儿禁令要求 ≥2）")
        elif len(present) < 2:
            warns.append(f"概念 {verb} 目前只有 {sorted(present)} 真用过；已声明 {len(declared)} 支")


def check_scripts(fails: list[str]) -> None:
    for path in seed_files():
        module = path.parent / "scenario.py"
        if not module.exists():
            fails.append(f"{path.parent.name}: 缺少 scenario.py（演员/脚本与验收入口）")
            continue
        source = module.read_text(encoding="utf-8")
        for verb in re.findall(r'\("([a-z_]+)",\s*\{', source):
            if verb not in REGISTRY:
                fails.append(f"{path.parent.name}: 脚本用到库里没有的动词「{verb}」")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="孤儿概念也算失败")
    args = parser.parse_args(argv)

    fails: list[str] = []
    warns: list[str] = []
    check_seed_shape(fails, warns)
    check_engine_is_story_blind(fails)
    check_concepts(fails, warns, args.strict)
    check_scripts(fails)

    print(f"状态键渲染：{len(STATE_RENDERERS)} 个已登记")
    print(f"库动词：{len(REGISTRY)} 个 → {'、'.join(sorted(REGISTRY))}")
    print(f"故事：{'、'.join(p.name for p in story_dirs())}")
    for warn in warns:
        print(f"待补：{warn}")
    for fail in fails:
        print(f"失败：{fail}")
    if fails:
        print(f"\n{fails.__len__()} 项失败")
        return 1
    print(f"\n通过（待补 {len(warns)} 项）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
