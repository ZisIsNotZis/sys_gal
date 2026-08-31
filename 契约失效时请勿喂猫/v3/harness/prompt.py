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
        line = ("Operational fact: your previous action was rejected and changed nothing. "
                f"Action={action.get('kind')} args={action.get('args')}. "
                f"Reason: {fact.get('reason')}.")
        alternatives = fact.get("alternatives")
        if alternatives:
            line += " The world suggests instead: " + "; ".join(str(a) for a in alternatives) + "."
        line += " Do not repeat the identical action unless a relevant condition changes."
        lines.append(line)
    for event in perception.get("events", []):
        lines.append("You observe: " + _event_sentence(event, str(perception.get("observer", "")),
                                                       str(perception.get("location", ""))))
    for entity, description in perception.get("descriptions", {}).items():
        lines.append(f"You can currently examine {entity}: {description}")
    notice = perception.get("situational_notice")
    if notice:
        lines.append(str(notice))
    lines.append("You can concretely: " + "; ".join(_affordance_sentence(x) for x in affordances))
    lines.append("For speak and send_message, the displayed text field is a placeholder: replace it with the exact words you intend to say or send. Never submit an empty text field.")
    return "\n".join(lines)


def _event_sentence(event: Mapping[str, Any], observer: str = "", location: str = "") -> str:
    payload = event.get("payload", {})
    kind = event.get("kind")
    if kind == "speech":
        return f"{event.get('actor')} says: {payload.get('text')}"
    if kind == "world_event":
        event_name = payload.get("event", "event")
        notice = payload.get("notice")
        if notice:
            return f"The world announces {event_name}: {notice}"
        return f"The world announces: {event_name}"
    if kind == "item_inspected":
        held = "you are holding it" if payload.get("held") else f"it is at {payload.get('location')}"
        return f"you inspected {payload.get('item')}; {held}"
    if kind == "knock":
        responded = "Someone inside heard you." if payload.get("responded") else "No one responded."
        return f"You knocked on {payload.get('target')}. {responded}"
    if kind == "interaction":
        responded = "Someone there heard you." if payload.get("responded") else "No one responded."
        return f"You interacted with {payload.get('target')} ({payload.get('verb')}). {responded}"
    if kind == "item_given":
        if str(payload.get("from")) == observer:
            return f"you gave {payload.get('item')} to {payload.get('to')}"
        return f"{payload.get('from')} gave {payload.get('item')} to you"
    if kind == "document_read":
        line = f"You read {payload.get('title')}: {payload.get('content')}"
        annotations = payload.get("annotations")
        if annotations:
            notes = "; ".join(
                f"{entry.get('by')} annotated: {entry.get('text')}" for entry in annotations)
            line += f" (on the record: {notes})"
        return line
    if kind == "document_annotated":
        return f"You annotated {payload.get('document')}: {payload.get('annotation')}"
    if kind == "document_copied":
        return f"You copied {payload.get('document')} into {payload.get('copy')}"
    if kind == "documents_compared":
        result = "matching" if payload.get("same_content") else "different"
        return f"You compared {payload.get('first')} and {payload.get('second')}; their contents are {result}."
    if kind == "document_labeled":
        return f"You labeled {payload.get('document')} as {payload.get('label')}."
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
                seconds = payload.get("duration_seconds")
                return f"You finished waiting (you waited {seconds} seconds)."
            if action == "sleep":
                return "You finished sleeping and woke up."
            if action == "open":
                return f"You opened {location or 'this place'}; it is now open to everyone."
            if action == "close":
                return f"You closed {location or 'this place'}; it is now closed to everyone."
            if action == "take":
                return f"You picked up {payload.get('item')}."
            if action == "drop":
                return f"You dropped {payload.get('item')} here."
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
        return f"inspect {option.get('item')} (item={option.get('item')})"
    if kind == "knock":
        return f"interact (target={option.get('target')}, verb=knock, parameters={{}})"
    if kind == "interact":
        return f"interact (target={option.get('target')}, verb={option.get('verb')}, parameters={option.get('parameters', {})})"
    if kind == "give":
        return f"give (item={option.get('item')}, target={option.get('target')})"
    if kind == "read":
        return f"read (document={option.get('document')})"
    if kind == "copy":
        return f"copy (document={option.get('document')})"
    if kind == "compare":
        return f"compare (first={option.get('first')}, second={option.get('second')})"
    if kind == "label":
        return f"label (document={option.get('document')}, label=your own text)"
    if kind == "annotate":
        return f"annotate (document={option.get('document')}, text=your note; visible on the record to anyone who reads it)"
    if kind == "wait":
        return f"wait for {option.get('duration_seconds')} seconds"
    if kind == "sleep":
        return f"sleep for {option.get('duration_seconds')} seconds"
    if kind == "move":
        return f"move to {option.get('target')} (takes {option.get('duration_seconds')} seconds)"
    if kind == "send_message":
        return f"send_message (target={option.get('target')}, text=your exact words)"
    if kind in {"open", "close"}:
        return f"{kind} this location"
    if kind.startswith("system_"):
        details = ", ".join(f"{key}={value}" for key, value in option.items() if key != "kind")
        return f"{kind} ({details})" if details else kind
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
        "Operational facts are authoritative local feedback. A rejected action changed nothing; "
        "prefer the alternatives the world suggests and never repeat the identical action unless "
        "a relevant condition changes.",
        f"LEGAL ACTION SHAPES:\n{[dict(x) for x in affordances]}",
        "Output only one JSON object (valid json), never prose or markdown. Use exactly this shape: "
        '{"kind":"wait|speak|send_message|move|open|close|take|drop|sleep|inspect|search|interact|knock|give",'
        '"args":{...},"updates":{...}}. For no action use null. '
        "Use kind and args only; never use legacy top-level keys such as action, target, text, or duration. "
        "Use the offered argument names exactly: inspect uses item; read, copy, label, and annotate "
        "use document; compare uses first and second; move uses target and duration_seconds; "
        "send_message and give use target. "
        "The action must be one of the offered legal action shapes; fill its args concretely. "
        "For send_message, provide exact message text; for speak, provide exact spoken text. "
        "updates may contain only goals (list of strings or text objects), beliefs (object or key/value list), memories (list), "
        "interpretations (list), and private_notes (list). Memory and interpretation entries may be "
        "short strings or objects with a text field; omit updates when you have no update. ",
    ))
