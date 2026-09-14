#!/usr/bin/env python3
"""Insert [[name]] reference markers into authored seed prose (T5 裁决).

Every person/location/item/document/concept reference in the seed prose gets
marked so `seed_lint.py` can scope-check it per recipient. The script:

1. loads the world pack and builds the full name table (entity ids, concept
   names, aliases);
2. for each authored file, rewrites the *longest* names first (so `2013年台风
   台账` wins over `台账`) and skips text inside code fences, YAML keys, and
   already-marked spans;
3. leaves everything else untouched — unmarked name-like tokens are then the
   linter's job to report.

Usage:
    python3 scripts/mark_seed.py [world_dir] [--dry-run]

Run it, review the diff, then `python3 scripts/seed_lint.py` must pass.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.world_loader import load_world_pack, ref_names, strip_refs  # noqa: E402

_PROSE_GLOBS = ("characters/*.md", "items/*.md", "documents/*.md",
                "locations/*.md", "organizations/*.md")
# Manifest prose fields worth marking (id fields, keys, coordinates are not).
_MANIFEST_FIELDS = ("notice", "knowledge_notes", "desc", "memory", "content",
                    "fragment")


def _name_table(pack) -> list[str]:
    names: set[str] = set()
    for row in (*pack.locations, *pack.items, *pack.documents, *pack.actors):
        names.add(str(row["id"]))
    for concept in pack.concepts:
        names.add(concept["name"])
        names.update(concept["aliases"])
    return sorted((n for n in names if len(n) >= 2), key=lambda n: (-len(n), n))


_SENTINEL = "\u0001"

def _mark_text(text: str, names: list[str]) -> tuple[str, int]:
    """Mark every known name, longest-first. Idempotent, and nesting-safe:
    marked spans are swapped to sentinels before each pass so a short alias
    (老街坊) cannot match inside an already-marked longer name (老街坊代表)."""
    text = strip_refs(text)
    count = 0
    protected: dict[str, str] = {}
    for name in names:
        def stash(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            key = f"{_SENTINEL}{len(protected):06d}{_SENTINEL}"
            protected[key] = f"[[{match.group(0)}]]"
            return key
        text = re.sub(re.escape(name), stash, text)
    for key, value in protected.items():
        text = text.replace(key, value)
    return text, count


def _mark_yaml_value(value: str, names: list[str]) -> tuple[str, int]:
    """Mark prose inside a YAML scalar; leaves keys/ids alone."""
    if not isinstance(value, str) or not value.strip():
        return value, 0
    return _mark_text(value, names)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("world", nargs="?",
                        default=str(Path(__file__).resolve().parents[1] / "world"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.world)
    pack = load_world_pack(root)
    names = _name_table(pack)

    total = 0
    for pattern in _PROSE_GLOBS:
        for path in sorted(root.glob(pattern)):
            original = path.read_text(encoding="utf-8")
            lines = original.splitlines(keepends=True)
            # Line 1 is the `# title` — the file's own name, never marked
            # (it is the definition of the term, and must stay a clean title).
            title, body = (lines[0], "".join(lines[1:])) if lines else ("", "")
            body_marked, n = _mark_text(body, names)
            marked = title + body_marked
            if marked != original:
                total += n
                print(f"{path.relative_to(root)}: {n} marker(s)")
                if not args.dry_run:
                    path.write_text(marked, encoding="utf-8")

    # Manifest prose is marked with a ruamel round-trip: comments, quotes,
    # key order and indentation are preserved exactly, and marked scalars are
    # written as valid YAML (quoted where a leading [[ would parse as a flow
    # sequence). Structural fields (ids, titles, keys, coordinates) are not
    # prose and stay untouched.
    from ruamel.yaml import YAML
    from ruamel.yaml.scalarstring import DoubleQuotedScalarString
    ryaml = YAML()
    ryaml.preserve_quotes = True
    ryaml.width = 10 ** 6   # never wrap long Chinese lines
    manifest_path = root / "manifest.yml"
    manifest = ryaml.load(manifest_path.read_text(encoding="utf-8"))

    PROSE_FIELDS = {"desc", "content", "notice", "knowledge_notes",
                    "fragment", "memory"}
    manifest_count = 0

    def quote(text: str):
        # A scalar starting with [[ would parse as a flow sequence.
        return (DoubleQuotedScalarString(text)
                if text.startswith(("[", "{", "*", "!", "&", "|", ">", "%"))
                or ": " in text else text)

    def apply_tree(node, field=None):
        """Mark authored prose in place on the ruamel tree. `field` is the key
        that led here; a `memory:` map is actor-keyed, so its values count as
        memory prose regardless of the actor key they sit under."""
        nonlocal manifest_count
        if isinstance(node, dict):
            for key in list(node.keys()):
                value = node[key]
                child_field = key if isinstance(key, str) else field
                if isinstance(value, (dict, list)):
                    apply_tree(value, child_field)
                elif isinstance(value, str) and value.strip():
                    effective = "memory" if field == "memory" else child_field
                    if effective not in PROSE_FIELDS:
                        continue
                    marked, _ = _mark_yaml_value(value, names)
                    if marked != value:
                        node[key] = quote(marked)
                        manifest_count += 1
        elif isinstance(node, list):
            for item in node:
                apply_tree(item, field)

    for section in ("scheduled", "locations", "items", "documents",
                    "concepts", "kb", "contacts"):
        apply_tree(manifest.get(section), section)

    if manifest_count and not args.dry_run:
        from io import StringIO
        buffer = StringIO()
        ryaml.dump(manifest, buffer)
        manifest_path.write_text(buffer.getvalue(), encoding="utf-8")
    if manifest_count:
        print(f"manifest.yml: {manifest_count} marker(s)")
        total += manifest_count
    print(f"total: {total} marker(s)" + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
