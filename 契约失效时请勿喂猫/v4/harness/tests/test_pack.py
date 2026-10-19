"""轨迹工件的紧凑形态（ticket 114）：记录全部，只去掉冗余。

一局运行的 `.json` 看着大，其实是同一段事实写了好几遍：世界事件、角色的感知快照、
它的可行动作清单、检查点里内嵌的整份轨迹、再加上 `indent=2` 的空格。实测 D1 全天
工件 17 MB → `zstd -19` 后 0.52 MB；23 MB 的检查点 → 0.85 MB，去掉与当天轨迹逐字
相同的 `trace` → 0.29 MB。

所以“文件太大就不进 git”是错的。规范形态 `<name>.jsonl.zst` 一行一条记录，
角色看到的、说出的、引擎记下的**一条不少**，只把逐字重复的那一份（检查点内嵌的
trace）去掉并在展开时从轨迹补回。

这里钉四件机械可判的事：
  1. 打包 → 展开，内容与原文逐件一致（trajectory 整份；checkpoint 除内嵌 trace 外每一栏）；
  2. 检查点展开时能从同名轨迹补回内嵌 trace；
  3. 原始文件比紧凑工件新 = 过期，`check` 失败（跑完不打包会在这里露出来）；
  4. 没有紧凑工件的原始文件 = 未打包，`check` 失败。

运行：python3 -m unittest discover -s harness/tests -p 'test_*.py'
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness import pack as packer


def _try_zstd() -> bool:
    try:
        packer.zstd()
    except SystemExit:
        return False
    return True


@unittest.skipUnless(_try_zstd(), "zstd not installed")
class PackRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "runs").mkdir()
        (self.root / "checkpoints").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _trajectory(self) -> Path:
        path = self.root / "runs" / "real-x.json"
        path.write_text(json.dumps({
            "format": "v3-trajectory-1", "seed_version": "v4-test",
            "run_id": "real-x", "outcome": {"reason": "stop_at_reached"},
            "tools": [{"name": "speak"}], "replay": {"event_count": 2},
            "agent_turns": [{"actor": "陈默", "inner": "先看一眼",
                             "perception": {"location": "中庭"}},
                            {"actor": "林瑶", "inner": "他来了"}],
            "system_turns": [{"tick": 1}], "gm_turns": [],
            "sessions": {"陈默": {"format": "v4-session-1", "actor": "陈默",
                                  "messages": [{"role": "user", "content": "早"}]}},
            "knowledge": {"陈默": [{"keys": ["陈默"], "desc": "我"}]},
            "world_events": [{"id": 1, "kind": "enter", "actor": "陈默",
                              "time": "2026-03-16T07:00:00+08:00",
                              "payload": {"location": "中庭"}}],
        }, ensure_ascii=False), encoding="utf-8")
        return path

    def test_a_packed_trajectory_unpacks_to_the_same_content(self):
        source = self._trajectory()
        original = json.loads(source.read_text(encoding="utf-8"))
        packed = packer.pack(source)
        self.assertIsNotNone(packed)
        self.assertTrue(packed.name.endswith(packer.SUFFIX))
        rebuilt = packer.object_of(packer.read_lines(packed))
        self.assertEqual(packer.digest(rebuilt), packer.digest(original))

    def test_the_packed_form_keeps_every_field_the_agent_saw(self):
        """角色看到的与说出的内容一条不少——压缩不是裁剪。"""
        source = self._trajectory()
        packed = packer.pack(source)
        rebuilt = packer.object_of(packer.read_lines(packed))
        self.assertEqual(rebuilt["agent_turns"][0]["perception"], {"location": "中庭"})
        self.assertEqual(rebuilt["agent_turns"][1]["inner"], "他来了")
        self.assertEqual(rebuilt["sessions"]["陈默"]["messages"][0]["content"], "早")
        self.assertEqual(rebuilt["world_events"][0]["payload"]["location"], "中庭")

    def test_an_old_trajectory_without_knowledge_stays_without_it(self):
        """旧工件没有 `knowledge` 一栏：展开时不得凭空多出一个空字典。"""
        source = self.root / "runs" / "real-old.json"
        source.write_text(json.dumps({"format": "v3-trajectory-1", "run_id": "old",
                                      "agent_turns": [], "world_events": []},
                                     ensure_ascii=False), encoding="utf-8")
        packed = packer.pack(source)
        rebuilt = packer.object_of(packer.read_lines(packed))
        self.assertNotIn("knowledge", rebuilt)

    def test_a_checkpoint_drops_the_duplicated_trace_and_restores_it(self):
        source = self._trajectory()
        big = json.loads(source.read_text(encoding="utf-8"))
        checkpoint = self.root / "runs" / "real-x.checkpoint.json"
        checkpoint.write_text(json.dumps({
            "format": "v4-checkpoint-2", "meta": {"run_id": "real-x"},
            "world": {"now": "2026-03-16T07:00:00+08:00"},
            "runner": {"states": {}}, "states": {}, "sessions": {},
            "trace": big}, ensure_ascii=False), encoding="utf-8")
        packed = packer.pack(checkpoint)
        lines = packer.read_lines(packed)
        self.assertEqual(lines[0]["omitted"], ["trace"])
        rebuilt = packer.object_of(lines)
        self.assertNotIn("trace", rebuilt)
        out = self.root / "restored.json"
        restored = packer.unpack(packed, out, trajectory=source)
        self.assertEqual(packer.digest(restored["trace"]), packer.digest(big))
        self.assertEqual(restored["world"]["now"], "2026-03-16T07:00:00+08:00")

    def test_check_passes_when_everything_is_packed(self):
        self._trajectory()
        for source in packer.sources(self.root):
            packer.pack(source)
        self.assertEqual(packer.check(self.root), [])

    def test_check_fails_on_an_unpacked_artifact(self):
        self._trajectory()
        problems = packer.check(self.root)
        self.assertEqual(len(problems), 1)
        self.assertIn("未打包", problems[0])

    def test_check_fails_when_the_source_is_newer_than_the_pack(self):
        """跑完一局却忘了打包：原始文件比紧凑工件新，预跑门必须挡住。"""
        source = self._trajectory()
        packed = packer.pack(source)
        newer = packed.stat().st_mtime + 10
        os.utime(source, (newer, newer))
        problems = packer.check(self.root)
        self.assertEqual(len(problems), 1)
        self.assertIn("过期", problems[0])


if __name__ == "__main__":
    unittest.main()
