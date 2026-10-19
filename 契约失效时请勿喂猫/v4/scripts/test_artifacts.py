"""轨迹工件的声明与持久化（ticket 113）。

丢过一次证据才需要这套东西：`v4/runs/` 与 `v4/checkpoints/` 里的轨迹很大，
被 `.gitignore` 挡在 git 外面之后仍然只是一个本地文件——D1 第三次验收的整份
轨迹和 d1-pm 的检查点就是这样丢的，而报告与票据还在引用它们。

这里只钉三件机械可判的事：
  1. `archive` 会把本地工件复制到第二处位置，并把它登记进 `artifacts.tsv`
     （路径 / 字节数 / sha256 / 存档路径）；
  2. `check` 逐条核对，缺一个或哈希对不上就是失败——声明里写了却不在，等于没有；
  3. `--strict` 把“还有本地工件没归档”也判成失败，这样预跑门能挡住“又跑了一局
     却没有留下证据”。

运行：python3 -m unittest discover -s scripts -p 'test_*.py'
"""
from __future__ import annotations

import importlib.util
import io
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "artifacts.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("artifacts_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArtifactsScriptTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_module()
        self.tmp = TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "v4"
        (self.root / "runs").mkdir(parents=True)
        (self.root / "checkpoints").mkdir()
        self.archive_dir = base / "archive"
        self.module.ROOT = self.root
        self.module.MANIFEST = self.root / "artifacts.tsv"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.module.main(argv)
        return code, buffer.getvalue()

    def test_archive_then_check_passes(self):
        (self.root / "runs" / "real-x.json").write_text('{"world_events": []}',
                                                       encoding="utf-8")
        code, out = self._run(["archive", "--archive-dir", str(self.archive_dir)])
        self.assertEqual(code, 0, out)
        self.assertTrue((self.archive_dir / "runs" / "real-x.json").is_file())
        code, out = self._run(["check", "--archive-dir", str(self.archive_dir)])
        self.assertEqual(code, 0, out)
        self.assertIn("artifacts OK", out)

    def test_check_fails_when_the_only_copy_is_gone(self):
        """这正是 D1 第三次验收的形态：本地被删、没有第二处、报告还在引用。"""
        (self.root / "runs" / "real-x.json").write_text("{}", encoding="utf-8")
        self._run(["archive", "--archive-dir", str(self.archive_dir)])
        (self.root / "runs" / "real-x.json").unlink()
        shutil.rmtree(self.archive_dir)
        code, out = self._run(["check", "--archive-dir", str(self.archive_dir)])
        self.assertEqual(code, 1, out)
        self.assertIn("缺失", out)

    def test_check_fails_when_the_copy_no_longer_matches_the_hash(self):
        target = self.root / "runs" / "real-x.json"
        target.write_text("{}", encoding="utf-8")
        self._run(["archive", "--archive-dir", str(self.archive_dir)])
        target.write_text('{"changed": true}', encoding="utf-8")
        code, out = self._run(["check", "--archive-dir", str(self.archive_dir)])
        self.assertEqual(code, 1, out)
        self.assertIn("字节数不符", out)

    def test_strict_check_flags_an_unarchived_run(self):
        (self.root / "runs" / "real-a.json").write_text("{}", encoding="utf-8")
        self._run(["archive", "--archive-dir", str(self.archive_dir)])
        (self.root / "runs" / "real-b.json").write_text("{}", encoding="utf-8")
        code, out = self._run(["check", "--archive-dir", str(self.archive_dir)])
        self.assertEqual(code, 0, "非 strict 只报告未归档，不算失败")
        self.assertIn("未归档", out)
        code, out = self._run(["check", "--archive-dir", str(self.archive_dir),
                               "--strict"])
        self.assertEqual(code, 1, out)
        self.assertIn("未归档：runs/real-b.json", out)

    def test_an_empty_manifest_is_not_a_pass(self):
        code, out = self._run(["check", "--archive-dir", str(self.archive_dir)])
        self.assertEqual(code, 1, out)
        self.assertIn("没有任何声明", out)


if __name__ == "__main__":
    unittest.main()
