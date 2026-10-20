"""M1 的重放门：逐字节一致，且篡改必被抓到。"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import library  # noqa: F401
from engine.events import EventLog, ReplayMismatch, dump_log, replay
from engine.seed import load
from stories.s1_last_bus.scenario import DEFAULT_SEED, play


class ReplayTests(unittest.TestCase):
    def test_replay_reproduces_the_run(self):
        for variant in ("a", "b", "c"):
            run = play(variant)
            replayed = replay(lambda: load(DEFAULT_SEED), run.log)
            self.assertEqual(replayed.digest(), run.world.digest(), variant)

    def test_log_round_trips_byte_identically(self):
        run = play("a")
        rows = json.loads(json.dumps(run.log.to_json()))
        again = EventLog.from_json(rows)
        self.assertEqual(dump_log(again), dump_log(run.log))

    def test_tampered_atom_is_caught(self):
        run = play("a")
        rows = copy.deepcopy(run.log.to_json())
        target = next(row for row in rows
                      if any(atom.get("op") == "move" for atom in row["atoms"]))
        for atom in target["atoms"]:
            if atom.get("op") == "move":
                atom["to"] = "jia" if atom["to"] != "jia" else "car"
                break
        tampered = EventLog.from_json(rows)
        with self.assertRaises(ReplayMismatch):
            replay(lambda: load(DEFAULT_SEED), tampered)

    def test_dropping_an_event_is_caught(self):
        run = play("a")
        rows = run.log.to_json()
        del rows[5]
        with self.assertRaises(ReplayMismatch):
            replay(lambda: load(DEFAULT_SEED), EventLog.from_json(rows))


if __name__ == "__main__":
    unittest.main()
