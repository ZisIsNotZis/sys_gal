"""Cheap, deterministic character policies for the v1 mini-episode.

These are not a narrator or a plot controller.  Each policy chooses from the
actor's private packet and the kernel's primitive affordances.  The small
amount of memory here represents commitments already made by that character,
not hidden seed facts.  ``Simulation`` only performs the Ledger bootstrap and
records the same intention seam used by a future model-backed agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from .kernel import Intention, WorldHarness
from .trace import TraceRecorder


def _messages(packet: Mapping[str, Any], sender: str | None = None) -> list[dict[str, Any]]:
    messages = packet.get("inbox", [])
    return [m for m in messages if sender is None or m.get("from") == sender]


def _has(packet: Mapping[str, Any], sender: str, text: str) -> bool:
    return any(text.lower() in str(m.get("text", "")).lower() for m in _messages(packet, sender))


def _event(packet: Mapping[str, Any], name: str) -> bool:
    return any(
        e.get("kind") == "world_event" and e.get("payload", {}).get("event") == name
        for e in packet.get("events", [])
    )


def _story_event(packet: Mapping[str, Any], name: str) -> bool:
    return any(
        e.get("kind") == "story_beat" and e.get("payload", {}).get("event") == name
        for e in packet.get("events", [])
    )


def _system(packet: Mapping[str, Any], key: str, value: str | None = None) -> bool:
    return any(
        e.get("kind") == "system"
        and key in e.get("payload", {})
        and (value is None or e.get("payload", {}).get(key) == value)
        for e in packet.get("events", [])
    )


def _wait(world: WorldHarness, actor: str, seconds: int = 900) -> Intention:
    return Intention(actor, "wait", {"duration_seconds": seconds}, world.version)


@dataclass
class PolicyAgent:
    actor_id: str
    step: int = 0
    handled: set[str] = field(default_factory=set)
    # This is deliberately a compact, evidence-linked state, not hidden CoT.
    # It becomes part of a richer agent API when one is available.
    last_mental_update: dict[str, Any] | None = None
    pending_action: Intention | None = None
    mental_serial: int = 0
    emitted_mental_serial: int = 0

    TERMINAL_RESOLUTIONS = {
        "chen-mo": "stays to inspect the corrected file and agrees to tea with Lin without making it a contract",
        "gao-rui": "signs the accounting correction and leaves the logistics role",
        "lin-yao": "reviews the record without granting approval, then offers one uncontracted tea meeting",
        "he-qian": "publishes the verified correction and holds the unsupported misconduct claim",
        "luo-wen": "closes delivered permit components and records the canceled component separately",
        "qiao-shun": "withdraws the unlabeled summary and accepts formal conduct review",
        "xu-meiling": "accepts a transparent payment timeline and cancels the unsafe menu item",
        "amani-njoroge": "publishes and enforces the rain-safe accessibility route",
        "park-minseo": "locks the archive with a matching checksum and retains the audit trail",
        "three-legged-cat": "keeps the receipt and occupies the compliance chair without entering a human contract",
    }

    def _mental(self, state: str, evidence: str, relationship_target: str | None = None, delta: int = 0) -> None:
        self.last_mental_update = {"state": state, "evidence": evidence, "relationship_target": relationship_target, "delta": delta}
        self.mental_serial += 1

    def _evidence_id(self, perception: Mapping[str, Any], fragment: str) -> int | None:
        for event in reversed(perception.get("events", [])):
            if fragment.lower() in str(event.get("payload", {}).get("text", "")).lower():
                return int(event["id"])
        return None

    def choose(self, world: WorldHarness, perception: Mapping[str, Any], options: list[dict[str, Any]]) -> Intention:
        self.step += 1
        actor = self.actor_id
        if world.now >= world._terminal_time() and actor in world.actor_resolutions and "resolution" not in self.handled:
            self.handled.add("resolution")
            return Intention(actor, "declare_resolution", {"resolution": self.TERMINAL_RESOLUTIONS[actor]}, world.version)
        if self.pending_action is not None:
            action, self.pending_action = self.pending_action, None
            # The zero-time mental record is itself a world mutation; rebuild
            # the resumed intention against the new authoritative version.
            return Intention(action.actor, action.kind, action.args, world.version)
        arc_action = self._arc_action(world, perception)
        if arc_action is not None:
            return arc_action
        if actor == "chen-mo":
            action = self._chen(world, perception)
        elif actor == "gao-rui":
            action = self._gao(world, perception)
        elif actor == "lin-yao":
            action = self._lin(world, perception)
        elif actor == "he-qian":
            action = self._he(world, perception)
        elif actor == "luo-wen":
            action = self._luo(world, perception)
        elif actor == "qiao-shun":
            action = self._qiao(world, perception)
        elif actor == "xu-meiling":
            action = self._xu(world, perception)
        elif actor == "amani-njoroge":
            action = self._amani(world, perception)
        elif actor == "three-legged-cat":
            action = self._cat(world, perception)
        else:
            action = _wait(world, actor)
        # Mental updates use the same intention seam as every other action.
        # They are emitted only when the private packet contains cited evidence;
        # the substantive action is resumed after the zero-time update.
        if self.mental_serial > self.emitted_mental_serial and self.last_mental_update:
            evidence_id = self._evidence_id(perception, self.last_mental_update["evidence"])
            if evidence_id is not None:
                self.pending_action = action
                self.emitted_mental_serial = self.mental_serial
                if self.last_mental_update.get("relationship_target"):
                    return Intention(actor, "update_relationship", {
                        "target": self.last_mental_update["relationship_target"],
                        "delta": self.last_mental_update["delta"], "evidence_event_id": evidence_id,
                    }, world.version)
                return Intention(actor, "update_belief", {
                    "proposition": self.last_mental_update["state"], "confidence": 0.8,
                    "evidence_event_id": evidence_id}, world.version)
        return action

    def _arc_action(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention | None:
        """Goal-driven responses to objective chapter pressure points.

        These are cast commitments, not a plot narrator: each actor owns a
        different deliverable and can refuse the others.  They keep the cheap
        deterministic run useful while preserving the same intention seam a
        model-backed policy will use later.
        """
        actor = self.actor_id
        plans = {
            "gao-rui": {
                "chapter_4_precision": ("chen-mo", "I will sign the correction, including the timestamp edit. I will not ask you to make my mistake disappear."),
                "chapter_7_minutes": ("luo-wen", "I admit the duplicate refund and the altered history description. Please record both separately; the instruction was ambiguous, but the edit was mine."),
                "chapter_8_pressure": ("qiao-shun", "The handover is incomplete. I am leaving the logistics role after I export the checksum and label every remaining file."),
                "chapter_9_fair": ("chen-mo", "The fair can use the corrected file, not the old form. If the binder is missing a signature, stop the stall rather than guessing."),
            },
            "lin-yao": {
                "chapter_2_deadline": ("chen-mo", "I have a private copy with a different total. I will show it only in a recorded review, not let it become a rumor."),
                "chapter_3_interview": ("he-qian", "I will answer factual questions, but my copy is evidence, not permission to publish a person before verification."),
                "chapter_6_storm": ("chen-mo", "You left. I waited. I can accept that you were nine and frightened, but I will not pretend the waiting did not happen."),
                "chapter_9_fair": ("chen-mo", "Stay at the records table because I want company. The Ledger did not ask me to say that, and you are not allowed to turn it into a contract."),
                "chapter_10_review": ("chen-mo", "Tea at the riverside market, once, with no task attached. That is an invitation, not a promise of forever."),
            },
            "qiao-shun": {
                "chapter_2_deadline": ("gao-rui", "Send me the formally labeled summary. I will not put an unlabeled preliminary number into the audit queue."),
                "chapter_5_bank": ("xu-meiling", "We can give the bank a labeled preliminary cash-flow explanation. I will sign the wording instead of hiding behind Gao."),
                "chapter_7_minutes": ("luo-wen", "The request for two summaries was mine. I meant different audiences, not different truths. Record that distinction and my responsibility."),
                "chapter_10_review": ("chen-mo", "I accept formal review of my handling of the summaries. The union can continue without pretending I made no choice."),
            },
            "xu-meiling": {
                "chapter_5_bank": ("luo-wen", "The cooperative needs a payment timeline, not a prettier lie. I will accept delayed funds if the dates and owner are written."),
                "chapter_8_pressure": ("qiao-shun", "Rain changes our stall plan. I will cancel the fragile menu item and take the lost margin rather than promise food we cannot safely deliver."),
                "chapter_9_fair": ("chen-mo", "The stall opens under the payment schedule. If the schedule is breached, I close this part myself; do not call that sabotage."),
            },
            "amani-njoroge": {
                "chapter_2_deadline": ("lin-yao", "The mapped ramp is blocked in rain. I need the detour, a quiet room, and a named budget owner."),
                "chapter_7_minutes": ("luo-wen", "Accessibility is a permit condition, not decorative language. I am submitting the route test and the failure criteria."),
                "chapter_8_pressure": ("chen-mo", "The rain warning breaks the cheap route. I am halting that route and moving the quiet room, even if the program loses a session."),
                "chapter_9_fair": ("lin-yao", "The detour is open and signed. I will stop anyone who blocks it, including a popular organizer."),
            },
            "he-qian": {
                "chapter_3_interview": ("chen-mo", "I saw your apology rehearsal. I will interview the person, not the filing cabinet. Tell me what you personally saw and what you only inferred."),
                "chapter_5_bank": ("gao-rui", "The original export and corrected total are enough for verification, not yet an accusation. I will protect the source boundary."),
                "chapter_7_minutes": ("luo-wen", "I will publish the verified correction and hold the claim of misconduct until the access audit identifies an accountable fact."),
                "chapter_10_review": ("chen-mo", "The article is correction-focused and names the process failure. I am holding the sensational paragraph because the evidence does not support it."),
            },
            "luo-wen": {
                "chapter_4_precision": ("chen-mo", "The last defensible review deadline is explicit: document version, signatories, and deposit explanation. A promise without those is not a submission."),
                "chapter_7_minutes": ("qiao-shun", "I am separating the financial error, records breach, ambiguous instruction, and access plan. One confession cannot close four findings."),
                "chapter_8_pressure": ("amani-njoroge", "The permit will remain conditional. Send the route test and the quiet-room owner by tomorrow, or that component is suspended."),
                "chapter_10_review": ("chen-mo", "The fair is closed. I am issuing completion for the delivered components and a separate record for the canceled menu item."),
            },
            "park-minseo": {
                "chapter_2_deadline": ("qiao-shun", "There are three filenames and incompatible timestamps. I am locking the archive copy; edits now require a recorded request."),
                "chapter_7_minutes": ("luo-wen", "The checksum is preserved. The unknown account is revoked and audited; I will not name a person without an access event."),
                "chapter_8_pressure": ("chen-mo", "The archive is stable, but the access plan changed. I need the new version number before I unlock the shared folder."),
                "chapter_10_review": ("luo-wen", "Checksum matches the submitted archive. I am closing write access and retaining the audit trail."),
            },
            "three-legged-cat": {
                "chapter_6_storm": ("chen-mo", "The cat sits on the inventory box and refuses to move."),
                "chapter_9_fair": ("chen-mo", "The cat occupies the chair reserved for the compliance binder. This is not a contract."),
            },
        }
        for beat, (target, text) in plans.get(actor, {}).items():
            if beat not in self.handled and _story_event(p, beat):
                self.handled.add(beat)
                if actor == "three-legged-cat":
                    return _wait(world, actor, 60)
                self._mental(f"pursuing {beat}", beat)
                return self._message(world, target, text)
        return None

    def _message(self, world: WorldHarness, target: str, text: str) -> Intention:
        return Intention(self.actor_id, "send_message", {"target": target, "text": text}, world.version)

    def _chen(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention:
        # Chen first buys time, then tries to convert three vague promises into
        # a concrete written scope.  This is his conflict-avoidant preference,
        # not a route-selection instruction from the author.
        if self.step == 1:
            self._mental("buying time before committing", "morning start; no case response yet")
            return _wait(world, self.actor_id, 600)
        if world.ledger_case == "open" and "choice" not in self.handled:
            self.handled.add("choice")
            self._mental("choosing written scope despite social cost", "Ledger offers A/B/C; Gao's warning is in the inbox")
            return Intention(self.actor_id, "ledger_choose", {"choice": "C"}, world.version)
        if world.ledger_case == "open" and _has(p, "gao-rui", "old form"):
            return Intention(self.actor_id, "ledger_choose", {"choice": "C"}, world.version)
        if _has(p, "gao-rui", "old form") and "lin" not in self.handled:
            self.handled.add("lin")
            self._mental("seeking a checkable requirement", "old form")
            return self._message(
                world, "lin-yao",
                "Gao asked me to hold an old form. I have not submitted it. What exact reconciliation and signatories do you need from me?",
            )
        if _has(p, "lin-yao", "exact reconciliation") and "gao" not in self.handled:
            self.handled.add("gao")
            self._mental("asking Gao to make responsibility explicit", "exact reconciliation")
            return self._message(
                world, "gao-rui",
                "Lin wants the exact reconciliation and named signatories. I will not send the old form. Will you acknowledge the duplicate entry and the corrected file history?",
            )
        if _has(p, "gao-rui", "acknowledge") and "case-choice" not in self.handled:
            self.handled.add("case-choice")
            self._mental("putting the private agreement into a bounded record", "acknowledge")
            return self._message(world, "lin-yao", "I chose a written scope: the old form is not the corrected attachment; the duplicate and file-history edit must be named; I own delivery and Gao owns the accounting correction.")
        if _event(p, "luo_reminder") and "luo" not in self.handled:
            self.handled.add("luo")
            self._mental("accepting a deadline I can actually meet", "18:00 deadline")
            return self._message(
                world, "luo-wen",
                "I accept the 18:00 deadline. I will submit the corrected reconciliation, explain the duplicate, and name Gao and me as responsible for our parts—not attach the old form as if it were current.",
            )
        if _has(p, "luo-wen", "received") and "lin-final" not in self.handled:
            self.handled.add("lin-final")
            self._mental("offering Lin inspectable scope, not reassurance", "received")
            return self._message(
                world, "lin-yao",
                "I sent Luo a bounded correction: duplicate explained, old form withheld, responsibilities named. You can inspect the same scope before the office closes.",
            )
        if world.ledger_case == "settled" and "ending" not in self.handled:
            self.handled.add("ending")
            self._mental("testing whether honesty survived the paperwork", "settled")
            return self._message(
                world, "lin-yao",
                "The Ledger settled it. If you still want to inspect the boring part, I can stay. I brought no old forms.",
            )
        if _has(p, "lin-yao", "boring part") and "comic-reply" not in self.handled:
            self.handled.add("comic-reply")
            self._mental("relieved that Lin answered without pretending approval", "boring part")
            return Intention(
                self.actor_id, "speak",
                {"text": "Good. I will label the folder BORING PART so nobody mistakes it for a romantic gesture."},
                world.version,
            )
        return _wait(world, self.actor_id, 900)

    def _gao(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention:
        if self.step == 1:
            return self._message(world, "chen-mo", "Please do not send the old form yet. I need one hour to check the reconciliation.")
        if _system(p, "choice", "C") and "case-reply" not in self.handled:
            self.handled.add("case-reply")
            return self._message(world, "chen-mo", "You chose a written scope. I hate that this makes the history visible, but I acknowledge the duplicate and the edit. I will sign my part.")
        if _has(p, "chen-mo", "acknowledge") and "confess" not in self.handled:
            self.handled.add("confess")
            return self._message(
                world,
                "chen-mo",
                "I acknowledge the duplicate refund entry. I edited the file-history description after fixing it. That was wrong; I will sign a correction, but I need Qiao to see the context too.",
            )
        if _has(p, "chen-mo", "written scope") and "qiao" not in self.handled:
            self.handled.add("qiao")
            return self._message(world, "he-qian", "I made a reconciliation error and edited its history. Please verify it before publishing anything.")
        return _wait(world, self.actor_id, 900)

    def _lin(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention:
        if _has(p, "chen-mo", "exact reconciliation") and "reply" not in self.handled:
            self.handled.add("reply")
            self._mental("requiring evidence before cooperation", "exact reconciliation")
            return self._message(
                world,
                "chen-mo",
                "I need the exact reconciliation, not a promise. If you can state who signs what and by when, I will compare it with my private copy.",
            )
        if _has(p, "chen-mo", "bounded correction") and "boundary" not in self.handled:
            self.handled.add("boundary")
            self._mental("keeping review separate from approval", "bounded correction")
            return self._message(world, "chen-mo", "Send me the same written scope. I will review it, but review is not approval and I will not hide the mismatch.")
        if _has(p, "chen-mo", "no old forms") and "ending-reply" not in self.handled:
            self.handled.add("ending-reply")
            self._mental("agreeing to inspect, while preserving my boundary", "no old forms", "chen-mo", 2)
            return self._message(
                world, "chen-mo",
                "I will inspect the boring part. That is review, not approval, and your folder name is already suspicious.",
            )
        return _wait(world, self.actor_id, 900)

    def _he(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention:
        # Her source-protection instinct makes her ask for verification only
        # after Gao voluntarily exposes a checkable claim.
        if _has(p, "gao-rui", "reconciliation error") and "verify" not in self.handled:
            self.handled.add("verify")
            return self._message(world, "gao-rui", "Send the original export location and the corrected total. I will verify before I pitch this as misconduct.")
        if _has(p, "gao-rui", "original export") and "chen-question" not in self.handled:
            self.handled.add("chen-question")
            return self._message(world, "chen-mo", "Gao gave me a claim I can verify. What did you personally see in the old form, and when?")
        return _wait(world, self.actor_id, 1200)

    def _luo(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention:
        # The office is closed in the seed, so Luo cannot walk in or approve
        # anything.  She can still process a message when it arrives.
        if _has(p, "chen-mo", "18:00 deadline") and "received" not in self.handled:
            self.handled.add("received")
            return self._message(world, "chen-mo", "Received. I can review a corrected reconciliation before 18:00 if it names the document version and responsible signatories.")
        return _wait(world, self.actor_id, 1200)

    def _qiao(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention:
        # Qiao protects his recommendation until Chen's written scope makes
        # continued ambiguity more dangerous than disclosure.
        if _event(p, "qiao_deadline") and "pressure" not in self.handled:
            self.handled.add("pressure")
            self._mental("the audit deadline now threatens my recommendation", "audit portal closes")
            return self._message(world, "gao-rui", "The audit portal closes at 16:00. Send me the labeled formal summary, not the preliminary one.")
        if _has(p, "gao-rui", "reconciliation error") and "withdraw" not in self.handled:
            self.handled.add("withdraw")
            self._mental("withdrawing the unlabeled summary before it harms the union", "reconciliation error")
            return self._message(world, "chen-mo", "I will withdraw the unlabeled summary and sign the audit note. Do not let anyone call the preliminary file official.")
        if _has(p, "chen-mo", "responsibilities named") and "context" not in self.handled:
            self.handled.add("context")
            return self._message(world, "he-qian", "The two summaries were my instruction, not Gao's invention. Verify the labels and publish only what the records support.")
        return _wait(world, self.actor_id, 1200)

    def _xu(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention:
        if _event(p, "xu_cash_pressure") and "bank" not in self.handled:
            self.handled.add("bank")
            self._mental("the cooperative cannot absorb another unexplained delay", "deposit explanation")
            return self._message(world, "luo-wen", "My staff need the deposit timeline today. I will accept a transparent explanation, but not a polished fiction for the bank.")
        if _has(p, "luo-wen", "corrected") and "receipt" not in self.handled:
            self.handled.add("receipt")
            return self._message(world, "qiao-shun", "I found the original deposit receipt. Use its date, even if it makes the cancellation look less flattering.")
        return _wait(world, self.actor_id, 1200)

    def _amani(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention:
        if _event(p, "amani_accessibility_gap") and "map" not in self.handled:
            self.handled.add("map")
            self._mental("the advertised route is not usable in rain", "ramp route")
            return self._message(world, "lin-yao", "The rain blocks the mapped ramp. I will mark the detour, but I need a resource commitment—not praise for noticing it.")
        if _has(p, "lin-yao", "detour") and "boundary" not in self.handled:
            self.handled.add("boundary")
            return self._message(world, "chen-mo", "Lin can revise the map if the fair budget names who pays for the detour. Accessibility is a deliverable, not a slogan.")
        return _wait(world, self.actor_id, 1200)

    def _cat(self, world: WorldHarness, p: Mapping[str, Any]) -> Intention:
        # The cat has no language or contract agency. Its participation is a
        # real non-human routine: it waits, eats nothing, and keeps the receipt
        # clue from becoming a supernatural shortcut.
        if _event(p, "cat_found_receipt") and "inspected" not in self.handled:
            self.handled.add("inspected")
            return _wait(world, self.actor_id, 6 * 60 * 60)
        return _wait(world, self.actor_id, 6 * 60 * 60)


class Simulation:
    def __init__(self, world: WorldHarness, recorder: TraceRecorder) -> None:
        self.world = world
        self.recorder = recorder
        self.agents = {actor_id: PolicyAgent(actor_id) for actor_id in world.actors}
        self._case_bootstrapped = False

    def run(self, *, turns: int, until: datetime | None = None) -> None:
        if not self._case_bootstrapped:
            self.world.emit_system({
                "case": "three-way-ambiguity",
                "terms": ["withdraw", "disclose", "obtain written scope"],
                "acceptance_deadline": "2026-03-16T18:00:00+08:00",
            })
            self._case_bootstrapped = True
        for _ in range(turns):
            progressed = False
            for actor_id in sorted(self.agents):
                actor = self.world.actors[actor_id]
                if (actor.busy_until and actor.busy_until > self.world.now
                        and self.world.story_phase != "ending"):
                    continue
                perception = self.world.poll_perception(actor_id)
                options = self.world.affordances(actor_id)
                # Mental updates are a supported agent-side affordance: their
                # evidence is still checked by the kernel before commit.
                options.append({"kind": "update_belief", "proposition": "", "confidence": 0.0,
                                "evidence_event_id": None})
                intention = self.agents[actor_id].choose(self.world, perception, options)
                try:
                    version_before = self.world.version
                    committed = self.world.submit(intention)
                    result, error = "submitted", None
                    ids = [event.id for event in self.world.event_log if event.world_version > version_before]
                    if actor_id == "chen-mo" and intention.kind == "ledger_choose":
                        accepted = self.world.event_log[-1]
                        # Keep the narrative consequence in the authoritative
                        # event graph.  The kernel owns acceptance; this
                        # policy only supplies the already-observable cost of
                        # choosing C (Gao must acknowledge the edit and Chen
                        # gives up the option of quietly returning the form).
                        self.world._commit("system", "chen-mo", {
                            "case": "three-way-ambiguity",
                            "status": "accepted",
                            "choice": "C",
                            "cost": "The written scope exposes Gao's file-history edit and Chen's four-day delay.",
                        }, cause=accepted.id)
                except Exception as exc:
                    result, error, ids = "rejected", f"{type(exc).__name__}: {exc}", []
                self.recorder.record_agent_turn(
                    actor=actor_id,
                    perception=perception,
                    affordances=options,
                    intention=intention,
                    result=result,
                    error=error,
                    committed_event_ids=ids,
                    world_version_after=self.world.version,
                )
                progressed = True
                if (self.world.story_phase == "ending"
                        and all(self.world.actor_resolutions.values())):
                    self.world.finalize_story()
                    break
            if not progressed and not self.world.has_pending_events:
                break
            next_time = self.world.next_event_time()
            if next_time is None:
                if until is not None and self.world.now < until:
                    self.world.advance(until=until)
                break
            boundary = next_time if until is None else min(next_time, until)
            self.world.advance(until=boundary)
            if until is not None and self.world.now >= until and self.world.story_phase == "terminal":
                break
        if until is not None and self.world.now < until and not self.world.has_pending_events:
            self.world.advance(until=until)
        # Settlement is a bounded Ledger operation, not an authorial NPC
        # decision.  Option C succeeds only because the trace contains the
        # required written acknowledgements before the office deadline.
        if until is not None and self.world.now >= until and self.world.ledger_case == "accepted":
            self.world.ledger_case = "settled"
            self.world.ledger_reward = True
            self.world.emit_system({
                "case": "three-way-ambiguity",
                "status": "settled",
                "choice": "C",
                "cost": "Gao's file-history edit and Chen's delay are now attached to the written scope.",
                "reward": "objective-clarification",
                "reward_granted": True,
            })
        if until is not None and self.world.now >= until and self.world.story_phase != "terminal":
            self.world.finalize_story()
