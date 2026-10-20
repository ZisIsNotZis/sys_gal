"""M2：结构检查本身也要有门（不然它只是文档里的一句话）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import v5_lint  # noqa: E402


class LintTests(unittest.TestCase):
    def test_strict_lint_is_green(self):
        self.assertEqual(v5_lint.main(["--strict"]), 0)

    def test_reserved_entity_ids_are_rejected(self):
        seed = {"start_clock": 0, "objects": [{"id": "note", "name": "某物"}]}
        import tempfile

        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            story = Path(tmp) / "zz_probe"
            story.mkdir()
            (story / "seed.yml").write_text(yaml.safe_dump(seed, allow_unicode=True), encoding="utf-8")
            (story / "scenario.py").write_text("# probe\n", encoding="utf-8")
            original = v5_lint.story_dirs
            v5_lint.story_dirs = lambda: [story]
            try:
                fails: list[str] = []
                warns: list[str] = []
                v5_lint.check_seed_shape(fails, warns)
            finally:
                v5_lint.story_dirs = original
        self.assertTrue(any("与引擎词汇同名" in f for f in fails), fails)


if __name__ == "__main__":
    unittest.main()
