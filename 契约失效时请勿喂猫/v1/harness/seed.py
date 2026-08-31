"""Small executable slice of the story seed for harness tests and later agents."""

from datetime import datetime

from .kernel import ActorState, LocationState, WorldHarness


def create_v1_world() -> WorldHarness:
    return WorldHarness(
        start=datetime.fromisoformat("2026-03-16T07:00:00+08:00"),
        actors=[
            ActorState("chen-mo", "dorm-3-room-417", {"outdated-permit-form"}),
            ActorState("gao-rui", "dorm-3-room-417"),
            ActorState("lin-yao", "greenhouse-courtyard"),
            ActorState("he-qian", "river-market-cafe"),
            ActorState("luo-wen", "community-partnerships-office"),
            ActorState("qiao-shun", "student-union-room"),
            ActorState("xu-meiling", "river-market-cafe"),
            ActorState("amani-njoroge", "greenhouse-courtyard"),
            ActorState("park-minseo", "international-residence"),
            ActorState("three-legged-cat", "dorm-3-room-417"),
        ],
        locations=[
            LocationState("dorm-3-room-417", open=True),
            LocationState("greenhouse-courtyard", open=True),
            LocationState("river-market-cafe", open=True),
            LocationState("community-partnerships-office", open=False),
            LocationState("old-neighborhood-office", open=False),
            LocationState("student-union-room", open=True),
            LocationState("international-residence", open=True),
        ],
        item_locations={"blue-rabbit-umbrella": "old-neighborhood-office", "red-plastic-whistle": "old-neighborhood-office"},
        routes={
            ("dorm-3-room-417", "greenhouse-courtyard"): 12 * 60,
            ("dorm-3-room-417", "community-partnerships-office"): 18 * 60,
            ("greenhouse-courtyard", "dorm-3-room-417"): 12 * 60,
            ("river-market-cafe", "dorm-3-room-417"): 20 * 60,
            ("student-union-room", "dorm-3-room-417"): 15 * 60,
            ("dorm-3-room-417", "student-union-room"): 15 * 60,
            ("greenhouse-courtyard", "international-residence"): 10 * 60,
            ("international-residence", "greenhouse-courtyard"): 10 * 60,
            ("river-market-cafe", "student-union-room"): 25 * 60,
            ("student-union-room", "river-market-cafe"): 25 * 60,
        },
        system_events=[
            {"event": "cat_found_receipt", "target": "chen-mo", "text": "The three-legged cat drags a rain-softened receipt under your door.", "time": "2026-03-16T07:20:00+08:00"},
            {"event": "qiao_deadline", "target": "qiao-shun", "text": "The student-union audit portal closes at 16:00; an unsigned summary is still queued.", "time": "2026-03-16T09:00:00+08:00"},
            {"event": "xu_cash_pressure", "target": "xu-meiling", "text": "The cooperative bank calls: the deposit explanation is needed today.", "time": "2026-03-16T09:20:00+08:00"},
            {"event": "amani_accessibility_gap", "target": "amani-njoroge", "text": "Rain blocks the only ramp route shown on the fair map.", "time": "2026-03-16T09:40:00+08:00"},
            {"event": "editor_deadline", "target": "he-qian", "text": "The campus paper wants a verified pitch by 17:40.", "time": "2026-03-16T10:00:00+08:00"},
            {"event": "luo_reminder", "target": "chen-mo", "text": "Corrected reconciliation and named signatories are required before 18:00.", "time": "2026-03-16T10:30:00+08:00"},
            # These are objective pressure points, not plot resolutions.  They
            # wake the cast over the ten-day arc; terminality is deliberately
            # the final fair review, not the first paperwork deadline.
            {"kind": "story_beat", "event": "chapter_2_deadline", "phase": "investigation", "text": "Three versions of the same number reach the student-union review queue.", "time": "2026-03-16T11:00:00+08:00"},
            {"kind": "story_beat", "event": "chapter_3_interview", "phase": "interview", "text": "The records room has one box, two people requesting it, and no spare hour.", "time": "2026-03-16T14:00:00+08:00"},
            {"kind": "story_beat", "event": "chapter_4_precision", "phase": "disclosure", "text": "The written scope must name a person, a document, and a deadline.", "time": "2026-03-17T09:00:00+08:00"},
            {"kind": "story_beat", "event": "chapter_5_bank", "phase": "institutional", "text": "Riverbend needs a truthful cash-flow explanation before the bank call.", "time": "2026-03-19T10:00:00+08:00"},
            {"kind": "story_beat", "event": "chapter_6_storm", "phase": "memory", "text": "The old basement inventory connects a blue umbrella to an unfinished childhood account.", "time": "2026-03-20T15:00:00+08:00"},
            {"kind": "story_beat", "event": "chapter_7_minutes", "phase": "review", "text": "The formal meeting separates accounting error, access breach, instruction, and permit duty.", "time": "2026-03-21T10:00:00+08:00"},
            {"kind": "story_beat", "event": "chapter_8_pressure", "phase": "preparation", "text": "A rain warning breaks the cheap access plan two days before opening.", "time": "2026-03-24T16:00:00+08:00"},
            {"kind": "story_beat", "event": "chapter_9_fair", "phase": "fair", "text": "The fair opens under conditional approval; every named owner must perform their part.", "time": "2026-03-26T08:00:00+08:00"},
            {"kind": "story_beat", "event": "chapter_9_close", "phase": "fair", "text": "Closing reveals one Ledger term was worded correctly but never mutually acknowledged.", "time": "2026-03-26T21:30:00+08:00"},
            {"kind": "story_beat", "event": "chapter_10_review", "phase": "ending", "text": "The final reconciliation, access report, archive checksum, and publication decision are compared.", "time": "2026-03-27T17:00:00+08:00"},
            {"kind": "story_terminal_beat", "event": "story_end", "phase": "ending", "terminal_reason": "The fair closes under conditional approval; the record is corrected, the remaining institutional consequences are owned, and Chen and Lin choose an uncontracted future meeting.", "resolutions": {
                "chen-mo": "stays to inspect the corrected file",
                "gao-rui": "signs the accounting correction",
                "lin-yao": "reviews without granting approval",
                "he-qian": "holds publication pending verification",
                "luo-wen": "closes the corrected submission for the day",
                "qiao-shun": "withdraws the unlabeled summary and signs the audit note",
                "xu-meiling": "accepts a transparent deposit timeline",
                "amani-njoroge": "publishes a rain-safe accessibility map",
            "park-minseo": "locks the archive with a matching checksum and retains the audit trail",
            "three-legged-cat": "keeps the receipt and occupies the compliance chair without entering a human contract"
            }, "time": "2026-03-27T21:30:00+08:00"},
        ],
        major_actors=["chen-mo", "gao-rui", "lin-yao", "he-qian", "luo-wen", "qiao-shun", "xu-meiling", "amani-njoroge", "park-minseo", "three-legged-cat"],
    )
