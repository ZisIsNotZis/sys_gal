"""M5：轨迹打包的机械判据——一份轨迹回答不了"他知道什么"，就不是证据。

一次运行留下四件原始材料（视图、上下文、事件账、摘要）；进 git 的是它们的紧凑形态
`runs/<story>-<路>.jsonl.zst`（一行一条记录 + `zstd -19`，内容一条不少）。这一份钉
四件机械可判的事：

1. 打包 → 展开，四件逐字节一致（压缩不是裁剪）；
2. `pack` 幂等：内容没变时一件不重写，字节不变；
3. `check` 的三种坏各自点名并失败——删掉某条路的 `context.md`、改一个包、
   原始文件比包新（跑完忘了打包）；
4. 原始文件只在本地时（别人 clone 下来），`check` 只核对工件自身也必须能判红。

运行：python3 -m unittest discover -s tests -p 'test_*.py'
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pack_trajectory as packer  # noqa: E402


def _try_zstd() -> bool:
    try:
        packer.zstd()
    except SystemExit:
        return False
    return True


BUNDLE = {
    "a.md": "# 《某车》轨迹\n\n- 路径：a\n\n`[脚本]` **2026-03-15 22:30** 甲 细看\n> 你细看：车外在下雨。\n",
    "a.context.md": "# 《某车》上下文审计\n\n## `[脚本]` 2026-03-15 22:30 甲：细看\n\n```\n【你】你二十七岁。\n```\n",
    "a.events.json": '[{"id": 1, "kind": "intent", "actor": "jia", "at": 1350}]\n',
    "a.json": '{\n "events": [{"id": 1, "kind": "intent"}],\n "summary": {"结局": "车走了"}\n}\n',
}
AGENT = {
    "transcript.md": "# 《某车》模型试点轨迹\n\n全部由模型决定。\n",
    "context.md": "# 《某车》上下文审计\n\n## `[角色]` 2026-03-15 22:30 甲：细看\n",
    "events.jsonl": '{"id": 1, "kind": "intent"}\n{"id": 2, "kind": "remember"}\n',
    "run.json": '{"run_id": "agent-x", "model": "mock"}\n',
}


@unittest.skipUnless(_try_zstd(), "zstd not installed")
class PackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stories = self.root / "stories"
        self.packs = self.root / "runs"
        self.stories.mkdir()
        self.packs.mkdir()
        # 一条脚本局（四件同级）+ 一条模型局（一个唯一目录），正是两种真实的形状。
        self.bundle_home = self.stories / "s9_probe" / "runs"
        self.bundle_home.mkdir(parents=True)
        for name, text in BUNDLE.items():
            (self.bundle_home / name).write_text(text, encoding="utf-8")
        self.agent_home = self.bundle_home / "agent-20260101T000000-4242-mock"
        self.agent_home.mkdir()
        for name, text in AGENT.items():
            (self.agent_home / name).write_text(text, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def pack_all(self) -> None:
        for unit in packer.units(self.stories).values():
            packer.pack_unit(unit, packs_root=self.packs)

    def check(self) -> list[str]:
        return packer.check(self.stories, self.packs)

    # ---- 正向：打包不裁剪 -------------------------------------------------

    def test_a_packed_run_unpacks_to_the_same_four_files(self):
        """四件逐字节还原：视图、上下文、事件账、摘要一条不少。"""
        self.pack_all()
        for story, name, home, expected, pack_name in (
            ("s9_probe", "a", self.bundle_home, BUNDLE, "s9_probe-a"),
            ("s9_probe", "agent-20260101T000000-4242-mock", self.agent_home, AGENT,
             "s9_probe-agent-20260101T000000-4242-mock"),
        ):
            pack = self.packs / f"{pack_name}{packer.SUFFIX}"
            self.assertTrue(pack.is_file(), pack)
            out = self.root / "restored" / name
            target, count = packer.unpack(pack, out)
            self.assertEqual(target, out)
            self.assertEqual(count, 4)
            for file_name, text in expected.items():
                restored = (out / file_name).read_bytes()
                self.assertEqual(restored, text.encode("utf-8"), file_name)
                self.assertEqual(restored, (home / file_name).read_bytes(), file_name)

    def test_packing_twice_changes_nothing(self):
        """幂等：内容没变就不重写，字节不变（不然每次 pack 都在动 git）。"""
        self.pack_all()
        before = {path.name: path.read_bytes() for path in sorted(self.packs.iterdir())}
        self.pack_all()
        after = {path.name: path.read_bytes() for path in sorted(self.packs.iterdir())}
        self.assertEqual(before, after)
        self.assertTrue(all(packer.pack_unit(unit, packs_root=self.packs) is None
                            for unit in packer.units(self.stories).values()))

    def test_check_is_green_when_every_run_is_packed(self):
        self.pack_all()
        self.assertEqual(self.check(), [])

    def test_a_clone_without_the_raw_files_is_still_green(self):
        """原始文件不进 git：别人 clone 下来只剩工件，核对工件自身也要能过。"""
        self.pack_all()
        shutil.rmtree(self.bundle_home)
        self.assertEqual(self.check(), [])

    def test_unpacking_a_pack_restores_a_green_tree(self):
        """从工件展开回原始四件之后，`check` 还是绿的（展开出的文件不晚于工件本身，
        否则只是在复核时展开一次就会被自己的“过期”判据误判）。"""
        self.pack_all()
        pack = self.packs / f"s9_probe-a{packer.SUFFIX}"
        shutil.rmtree(self.bundle_home)
        self.assertEqual(self.check(), [])
        target, count = packer.unpack(pack, root=self.root)
        self.assertEqual(target, self.bundle_home)
        self.assertEqual(count, 4)
        self.assertEqual(self.check(), [])
        for name, text in BUNDLE.items():
            self.assertEqual((self.bundle_home / name).read_text(encoding="utf-8"), text, name)

    # ---- 反向控制 1：少一份 context.md -----------------------------------

    def test_check_fails_when_a_run_loses_its_context_view(self):
        """删掉某条路的 context.md：这一局回答不了"他知道什么"，`check` 必须红，
        并且点名是哪个故事哪条路。"""
        self.pack_all()
        (self.bundle_home / "a.context.md").unlink()
        problems = self.check()
        self.assertTrue(problems, "缺 context.md 的运行没有被挡住")
        self.assertTrue(any("s9_probe/a" in p for p in problems), problems)
        self.assertTrue(any("a.context.md" in p for p in problems), problems)

    def test_a_run_that_never_had_a_context_view_is_not_evidence(self):
        """没打过包就少了 context.md：同样不算证据（不许因为"没包"就换个理由过关）。"""
        (self.bundle_home / "a.context.md").unlink()
        problems = self.check()
        self.assertTrue(any("不是证据" in p and "s9_probe/a" in p for p in problems), problems)

    # ---- 反向控制 2：包被改过 --------------------------------------------

    def test_check_fails_when_a_pack_no_longer_matches_the_original(self):
        """改一个包里的一条记录：展开出来与原始文件不再逐字节相同，`check` 必须红。"""
        self.pack_all()
        pack = self.packs / f"s9_probe-a{packer.SUFFIX}"
        records = packer.read_records(pack)
        for record in records[1:]:
            if record["name"] == "a.events.json":
                record["text"] = record["text"].replace("intent", "schedule")
        body = ("\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"))
                          for r in records) + "\n").encode("utf-8")
        subprocess.run([packer.zstd(), "-19", "-q", "-f", "-o", str(pack)], input=body,
                       capture_output=True, check=True)
        problems = self.check()
        self.assertTrue(any("不一致" in p and "a.events.json" in p for p in problems), problems)

    def test_a_tampered_pack_is_caught_without_the_raw_files(self):
        """连原始文件都不在了也要判红：摘要记在工件里，改了就露。"""
        self.pack_all()
        pack = self.packs / f"s9_probe-agent-20260101T000000-4242-mock{packer.SUFFIX}"
        records = packer.read_records(pack)
        records[1]["text"] = "改过的一行\n"
        body = ("\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"))
                          for r in records) + "\n").encode("utf-8")
        subprocess.run([packer.zstd(), "-19", "-q", "-f", "-o", str(pack)], input=body,
                       capture_output=True, check=True)
        shutil.rmtree(self.stories / "s9_probe")
        problems = self.check()
        self.assertTrue(problems, "工件自身被改过却没被发现")
        self.assertTrue(any("记录与全文不一致" in p for p in problems), problems)

    # ---- 反向控制 3：包比原始文件旧 --------------------------------------

    def test_check_fails_when_the_pack_is_older_than_the_run(self):
        """跑完忘了打包：原始文件比工件新，预跑门必须挡住并点名。"""
        self.pack_all()
        source = self.bundle_home / "a.md"
        newer = (self.packs / f"s9_probe-a{packer.SUFFIX}").stat().st_mtime + 10
        os.utime(source, (newer, newer))
        problems = self.check()
        self.assertTrue(any("过期" in p and "s9_probe/a" in p and "a.md" in p
                            for p in problems), problems)

    def test_pack_rewrites_a_stale_pack(self):
        """`pack` 不是只看在不在：过期/被改过就重写回对得上的那一份。"""
        self.pack_all()
        pack = self.packs / f"s9_probe-a{packer.SUFFIX}"
        pack.write_bytes(b"not a pack\n")
        self.pack_all()
        self.assertEqual(self.check(), [])

    # ---- 真实树：M5 的收尾判据 -------------------------------------------

    def test_the_real_tree_has_one_pack_per_run(self):
        """每条路一件工件，且 `check` 绿：五支故事的轨迹都在 git 里。"""
        packs = sorted((ROOT / "runs").glob(f"*{packer.SUFFIX}"))
        self.assertGreaterEqual(len(packs), 25, [p.name for p in packs])
        for story in ("s1_last_bus", "s2_borrow_note", "s3_night_market",
                      "s4_night_shop", "s5_wedding"):
            self.assertTrue(any(p.name.startswith(story + "-") for p in packs), story)
        self.assertEqual(packer.check(), [])


if __name__ == "__main__":
    unittest.main()
