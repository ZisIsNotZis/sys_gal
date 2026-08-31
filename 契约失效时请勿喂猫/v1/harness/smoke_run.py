"""Short deterministic trajectory capture; deliberately not a story experiment."""

from datetime import datetime
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).parents[1]))

from harness.kernel import Intention
from harness.seed import create_v1_world
from harness.trace import TraceRecorder


def main() -> None:
    world = create_v1_world()
    recorder = TraceRecorder("v1", "smoke-2026-08-24")

    def act(intention: Intention) -> None:
        perception = world.poll_perception(intention.actor)
        recorder.record_agent_turn(
            actor=intention.actor,
            perception=perception,
            affordances=world.affordances(intention.actor),
            intention=intention,
            result="submitted",
        )
        world.submit(intention)
        while world.advance():
            pass

    # A deliberately short, deterministic interaction: no character LLM or judge.
    act(Intention("chen-mo", "send_message", {"target": "lin-yao", "text": "Can we talk?"}, world.version))
    act(Intention("chen-mo", "move", {"target": "greenhouse-courtyard", "duration_seconds": 720}, world.version))
    act(Intention("chen-mo", "speak", {"text": "I need to clarify what I promised."}, world.version))
    output = Path(__file__).parents[1] / "runs" / "smoke-2026-08-24.json"
    recorder.save(world, output)
    print(output)


if __name__ == "__main__":
    main()
