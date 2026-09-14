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
            body, lines = original.split("\n", 1) if "\n" in original else (original, "")
            # Line 1 is the `# title` — leave it; mark the body.
            body_marked, n1 = _mark_text(body, names)
            lines_marked, n2 = _mark_text(lines, names)
            marked = body_marked + ("\n" + lines_marked if lines else "")
            if marked != original:
                total += n1 + n2
                print(f"{path.relative_to(root)}: {n1 + n2} marker(s)")
                if not args.dry_run:
                    path.write_text(marked, encoding="utf-8")

    manifest_path = root / "manifest.yml"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    out_lines, manifest_count = [], 0
    for line in manifest_text.splitlines():
        stripped = line.lstrip()
        key, sep, value = stripped.partition(": ")
        if sep and key.split("#")[0].strip() in _MANIFEST_FIELDS and value.strip():
            marked, n = _mark_yaml_value(value, names)
            if n:
                indent = line[:len(line) - len(stripped)]
                # A value that begins with [[ is a flow-sequence to YAML; quote
                # any scalar a marker could make ambiguous.
                quote_it = marked.startswith(("[", "{", "*", "!", "&", "|", ">", "%"))
                if not quote_it and ": " in marked:
                    quote_it = True
                if quote_it:
                    escaped = marked.replace("\\", "\\\\").replace('"', '\\"')
                    marked = '"' + escaped + '"';
                out_lines.append(f"{indent}{key}: {marked}")
                manifest_count += n
                continue
        out_lines.append(line)
    if manifest_count:
        print(f"manifest.yml: {manifest_count} marker(s)")
        total += manifest_count
        if not args.dry_run:
            manifest_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print(f"total: {total} marker(s)" + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
