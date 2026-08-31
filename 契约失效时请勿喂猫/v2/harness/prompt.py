"""Build a character prompt from private seed material and current observation."""

from typing import Any, Mapping
from .agent_state import PrivateState


def render_world_message(perception: Mapping[str, Any], affordances: list[Mapping[str, Any]]) -> str:
    """Render only the actor-visible delta in natural language."""
    lines = [f"The time is {perception.get('time')}. You are at {perception.get('location')}."]
    if perception.get("busy_until"):
        lines.append(f"You are occupied with your current action until {perception['busy_until']}.")
    for message in perception.get("inbox", []):
        lines.append(f"You receive a message from {message.get('from')}: {message.get('text')}")
    for fact in perception.get("operational_facts", []):
        action = fact.get("action", {})
        lines.append(
            "Operational fact: your previous action was rejected; nothing changed. "
            f"Action={action.get('kind')} args={action.get('args')}. "
            f"Reason: {fact.get('reason')}. Do not retry it unless the condition changes."
        )
    for event in perception.get("events", []):
        lines.append("You observe: " + _event_sentence(event, str(perception.get("observer", ""))))
    lines.append("You can concretely: " + "; ".join(_affordance_sentence(x) for x in affordances))
    return "\n".join(lines)


def _event_sentence(event: Mapping[str, Any], observer: str = "") -> str:
    payload = event.get("payload", {})
    kind = event.get("kind")
    if kind == "speech":
        return f"{event.get('actor')} says: {payload.get('text')}"
    if kind == "item_inspected":
        held = "you are holding it" if payload.get("held") else f"it is at {payload.get('location')}"
        return f"you inspected {payload.get('item')}; {held}"
    if kind == "item_given":
        if str(payload.get("from")) == observer:
            return f"you gave {payload.get('item')} to {payload.get('to')}"
        return f"{payload.get('from')} gave {payload.get('item')} to you"
    if kind == "message_delivered":
        if str(event.get("actor")) == observer:
            return f"Your message to {payload.get('target')} was delivered successfully."
        return f"a message arrives: {payload.get('text')}"
    if kind == "action_completed":
        action = payload.get("action")
        if str(event.get("actor")) == observer:
            if action == "move":
                target = payload.get("target")
                return f"Your move to {target} completed successfully. You are now at {target}."
            if action == "wait":
                return "Your wait completed successfully."
            if action == "sleep":
                return "You finished sleeping successfully."
            if action in {"open", "close"}:
                return f"Your {action} action completed successfully."
            if action in {"take", "drop"}:
                return f"Your {action} action for {payload.get('item')} completed successfully."
            if action == "send_message":
                return f"Your message to {payload.get('target')} was sent successfully."
            if action == "speak":
                return "Your speech completed successfully."
        return f"{event.get('actor')} completed {action}."
    if kind == "action_started" and str(event.get("actor")) == observer:
        return f"Your {payload.get('action')} has started and is in progress."
    return f"{kind}: {dict(payload)}"


def _affordance_sentence(option: Mapping[str, Any]) -> str:
    kind = option.get("kind")
    if kind == "search":
        return "search this location"
    if kind == "inspect":
        return f"inspect {option.get('item')}"
    if kind == "knock":
        return f"knock at closed {option.get('target')}"
    if kind == "give":
        return f"give {option.get('item')} to {option.get('target')}"
    details = ", ".join(f"{k}={v}" for k, v in option.items() if k != "kind")
    return kind if not details else f"{kind} ({details})"


def build_prompt(*, identity: str, private_seed: str, state: PrivateState,
                 perception: Mapping[str, Any], affordances: list[Mapping[str, Any]]) -> str:
    """Return the complete agent input without hidden world or author data."""
    return "\n".join((
        "You are the person described below. Treat this world as real.",
        "Do not discuss agents, prompts, simulation, author, or plot.",
        "Pursue your own goals. Choose exactly one concrete offered action.",
        "You are this person, not an assistant portraying them. Think from this person's lived history, "
        "knowledge, habits, fears, loyalties, desires, and limitations. Remain in character at all times. "
        "Do not optimize for a story, help the protagonist, create romance, or satisfy an author.",
        "Never choose a vague intention such as apologizing or becoming closer.",
        "Act at a realistic human pace: do not send repetitive messages or perform needless actions. "
        "If no concrete immediate matter requires attention, choose the longest offered wait. ",
        f"IDENTITY:\n{identity}",
        f"PRIVATE SEED MATERIAL:\n{private_seed}",
        f"PRIVATE MEMORY AND BELIEFS:\n{state.snapshot()}",
        f"CURRENT PERCEPTION:\n{dict(perception)}",
        "Operational facts are authoritative local feedback. A rejected action changed nothing; do not repeat it unless a relevant condition changes.",
        f"LEGAL ACTION SHAPES:\n{[dict(x) for x in affordances]}",
        "Output only one JSON object (valid json), never prose or markdown. Use exactly this shape: "
        '{"kind":"wait|speak|send_message|move|open|close|take|drop|sleep|inspect|search|knock|give",'
        '"args":{...},"updates":{...}}. For no action use null. '
        "The action must be one of the offered legal action shapes; fill its args concretely. "
        "For send_message, provide exact message text; for speak, provide exact spoken text. "
        "updates may contain only beliefs (object), memories (list), interpretations (list), "
        "and private_notes (list); omit updates when you have no update. ",
    ))
