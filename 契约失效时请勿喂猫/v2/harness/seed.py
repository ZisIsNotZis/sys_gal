"""Initial seed for the emergent romance story, without plot directives."""

from datetime import datetime
from .kernel import ActorState, LocationState, World


def create_world() -> World:
    return World(
        start=datetime.fromisoformat("2026-03-16T07:00:00+08:00"),
        actors=[
            ActorState("chen-mo", "dorm", {"old-permit-form", "red-whistle"}), ActorState("lin-yao", "archive"),
            ActorState("gao-rui", "dorm"), ActorState("qiao-shun", "union"),
            ActorState("he-qian", "cafe"), ActorState("amani-njoroge", "courtyard"),
            ActorState("xu-meiling", "market"), ActorState("park-minseo", "archive"),
        ],
        locations=[
            LocationState("dorm", x=0, y=0, sound_radius=18),
            LocationState("archive", x=14, y=0, sound_radius=14),
            LocationState("union", x=0, y=12, sound_radius=14),
            LocationState("cafe", x=14, y=12, sound_radius=16),
            LocationState("courtyard", x=28, y=0, sound_radius=35),
            LocationState("market", x=28, y=14, sound_radius=22),
            LocationState("old-basement", x=-18, y=-12, sound_radius=8, sound_loss=8),
        ],
        item_locations={"blue-rabbit-umbrella": "old-basement", "storm-inventory-box": "old-basement", "original-export": "archive"},
        routes={
            ("dorm", "archive"): 900, ("archive", "dorm"): 900,
            ("dorm", "union"): 720, ("union", "dorm"): 720,
            ("archive", "cafe"): 600, ("cafe", "archive"): 600,
            ("archive", "courtyard"): 480, ("courtyard", "archive"): 480,
            ("cafe", "market"): 900, ("market", "cafe"): 900,
            ("archive", "old-basement"): 1200, ("old-basement", "archive"): 1200,
        },
        sound_barriers={
            ("dorm", "archive"): 12, ("dorm", "union"): 10,
            ("archive", "cafe"): 8, ("archive", "courtyard"): 6,
            ("cafe", "market"): 5, ("archive", "old-basement"): 16,
        },
        scheduled=[
            {"event": "class_begins", "time": "2026-03-16T08:10:00+08:00", "target": "chen-mo"},
            {"event": "private_copy_due", "time": "2026-03-16T09:30:00+08:00", "target": "lin-yao"},
            {"event": "audit_deadline", "time": "2026-03-16T16:00:00+08:00", "target": "qiao-shun"},
            {"event": "editor_pitch_due", "time": "2026-03-16T17:40:00+08:00", "target": "he-qian"},
            {"event": "permit_review", "time": "2026-03-17T09:00:00+08:00"},
            {"event": "bank_call", "time": "2026-03-19T10:00:00+08:00", "target": "xu-meiling"},
            {"event": "storm_records_available", "time": "2026-03-20T15:00:00+08:00"},
            {"event": "review_meeting", "time": "2026-03-21T10:00:00+08:00"},
            {"event": "rain_warning", "time": "2026-03-24T16:00:00+08:00"},
            {"event": "fair_opens", "time": "2026-03-26T08:00:00+08:00"},
            {"event": "fair_closes", "time": "2026-03-26T21:30:00+08:00"},
            {"event": "world_stops", "time": "2026-03-27T21:30:00+08:00"},
        ],
    )
