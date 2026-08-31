from datetime import datetime
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[2]))

from harness.kernel import Intention
from harness.seed import create_v1_world
from harness.trace import TraceRecorder
from harness.vn import project_vn


class VnProjectionTests(unittest.TestCase):
    def test_projection_derives_dialogue_choice_and_terminal_system_records(self):
        world = create_v1_world()
        world.submit(Intention("chen-mo", "speak", {"text": "I will state the scope."}))
        world.advance()
        world.submit(Intention("chen-mo", "ledger_choose", {"choice": "C"}))
        world.emit_system({"case": "three-way-ambiguity", "status": "settled", "reward": "objective-clarification"})

        projection = project_vn(world.replayable_log())
        records = [record for scene in projection["scenes"] for record in scene["records"]]
        self.assertEqual([record["type"] for record in records], ["dialogue", "choice", "consequence", "system", "epilogue"])
        self.assertEqual(records[0]["text"], "I will state the scope.")
        self.assertEqual(records[1]["options"], ["A", "B", "C"])
        self.assertEqual(records[1]["choice"], "C")
        self.assertEqual(records[2]["text"], "risk-Gao-trust")
        self.assertEqual(records[3]["status"], "settled")

    def test_setup_record_is_copied_from_authoritative_system_event(self):
        world = create_v1_world()
        event = world.emit_system({
            "case": "three-way-ambiguity",
            "terms": ["withdraw", "disclose"],
            "acceptance_deadline": "2026-03-16T18:00:00+08:00",
        })
        records = [r for s in project_vn(world.replayable_log())["scenes"] for r in s["records"]]
        record = next(r for r in records if r["type"] == "system" and r["status"] == "setup")
        self.assertEqual(record["event_id"], event.id)
        self.assertEqual(record["status"], "setup")
        self.assertEqual(record["terms"], ["withdraw", "disclose"])

    def test_private_message_projection_preserves_recipient_and_does_not_invent_dialogue(self):
        world = create_v1_world()
        world.submit(Intention("chen-mo", "send_message", {"target": "lin-yao", "text": "secret"}))
        world.advance()
        projection = project_vn(world.replayable_log())
        dialogue = [r for s in projection["scenes"] for r in s["records"] if r["type"] == "dialogue"]
        self.assertEqual(len(dialogue), 1)
        self.assertEqual(dialogue[0]["recipient"], "lin-yao")
        self.assertEqual(dialogue[0]["audience"], ["lin-yao"])
        self.assertNotIn("reply", str(projection))

    def test_trace_serializes_projection(self):
        world = create_v1_world()
        recorder = TraceRecorder("v1", "vn-trace")
        world.submit(Intention("chen-mo", "speak", {"text": "Hello."}))
        world.advance()
        snapshot = recorder.snapshot(world)
        self.assertEqual(snapshot["vn_projection"]["format"], "vn-projection-v2")
        self.assertEqual(snapshot["vn_projection"]["dialogue_count"], 1)

    def test_projection_has_chapters_scene_metadata_and_terminal_epilogue(self):
        world = create_v1_world()
        world.emit_system({"case": "three-way-ambiguity", "terms": ["disclose"]})
        world.submit(Intention("chen-mo", "ledger_choose", {"choice": "C"}))
        world.emit_system({"case": "three-way-ambiguity", "status": "settled", "reward": "objective-clarification"})
        projection = project_vn(world.replayable_log())
        self.assertEqual(projection["format"], "vn-projection-v2")
        self.assertTrue(projection["chapters"])
        self.assertTrue(all(scene["chapter"] for scene in projection["scenes"]))
        self.assertTrue(all("location" in scene and "background" in scene for scene in projection["scenes"]))
        self.assertEqual(projection["terminal_epilogue"]["status"], "settled")
        self.assertEqual(projection["terminal_epilogue"]["source_event_id"], projection["terminal_epilogue"]["event_id"])

    def test_trace_records_replay_contract_for_projection(self):
        world = create_v1_world()
        recorder = TraceRecorder("v1", "metadata")
        world.emit_system({"case": "three-way-ambiguity"})
        snapshot = recorder.snapshot(world)
        self.assertEqual(snapshot["trace_format"], "harness-trace-v2")
        self.assertEqual(snapshot["replay"]["event_count"], 1)
        self.assertTrue(snapshot["replay"]["contiguous_event_ids"])
        self.assertEqual(snapshot["replay"]["projection_format"], "vn-projection-v2")

    def test_story_beats_and_terminal_resolution_form_real_ending(self):
        world = create_v1_world()
        while world.next_event_time() is not None and world.next_event_time().date() <= datetime.fromisoformat("2026-03-27T21:30:00+08:00").date():
            world.advance()
        projection = project_vn(world.replayable_log())
        records = [r for s in projection["scenes"] for r in s["records"]]
        self.assertTrue(any(r["type"] == "scene_beat" and r["event"] == "chapter_2_deadline" for r in records))
        terminal = [r for r in records if r["type"] == "terminal"]
        self.assertFalse(terminal)
        self.assertIsNone(projection["terminal_epilogue"])


if __name__ == "__main__":
    unittest.main()
