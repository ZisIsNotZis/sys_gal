from datetime import datetime
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[2]))

from harness.kernel import Intention
from harness.seed import create_v1_world
from harness.trace import TraceRecorder


class TraceTests(unittest.TestCase):
    def test_trace_contains_private_agent_input_and_authoritative_world_log(self):
        world = create_v1_world()
        recorder = TraceRecorder("v1", "test-trace")
        perception = world.poll_perception("chen-mo")
        intention = Intention("chen-mo", "send_message", {"target": "lin-yao", "text": "Can we talk?"}, world.version)
        recorder.record_agent_turn(
            actor="chen-mo",
            perception=perception,
            affordances=world.affordances("chen-mo"),
            intention=intention,
            result="submitted",
        )
        world.submit(intention)
        world.advance()
        snapshot = recorder.snapshot(world)
        self.assertEqual(snapshot["source_version"], "v1")
        self.assertEqual(snapshot["agent_trajectory"][0]["intention"]["kind"], "send_message")
        self.assertEqual([event["kind"] for event in snapshot["world_trajectory"]], [
            "action_started", "message_sent", "action_completed", "message_delivered"
        ])
        self.assertEqual(snapshot["judge_trajectory"], [])
        self.assertEqual(snapshot["final_state"]["actors"]["lin-yao"]["inbox"][0]["text"], "Can we talk?")

    def test_agent_and_judge_inputs_are_snapshots_and_agent_turn_can_link_events(self):
        world = create_v1_world()
        recorder = TraceRecorder("v1", "immutability")
        perception = world.poll_perception("chen-mo")
        options = world.affordances("chen-mo")
        intention = Intention("chen-mo", "send_message", {"target": "lin-yao", "text": "hi"}, world.version)
        recorder.record_agent_turn(
            actor="chen-mo",
            perception=perception,
            affordances=options,
            intention=intention,
            result="submitted",
            committed_event_ids=[1],
            world_version_after=1,
        )
        recorder.record_judge_turn(
            request={"history": [{"id": 1}]},
            response={"effects": [{"type": "none"}]},
            result="accepted",
        )

        perception["inbox"].append({"from": "leak"})
        options[0]["duration_seconds"] = 999
        intention.args["text"] = "mutated"

        turn = recorder.agent_trajectory[0]
        self.assertEqual(turn["committed_event_ids"], [1])
        self.assertEqual(turn["world_version_after"], 1)
        self.assertEqual(turn["perception"]["inbox"], [])
        self.assertNotEqual(turn["affordances"][0].get("duration_seconds"), 999)
        self.assertEqual(turn["intention"]["args"]["text"], "hi")

        request = {"history": [{"id": 2}]}
        response = {"effects": []}
        recorder.record_judge_turn(request=request, response=response, result="accepted")
        request["history"].append({"id": 3})
        response["effects"].append({"type": "leak"})
        self.assertEqual(recorder.judge_trajectory[-1]["request"]["history"], [{"id": 2}])
        self.assertEqual(recorder.judge_trajectory[-1]["response"]["effects"], [])


if __name__ == "__main__":
    unittest.main()
