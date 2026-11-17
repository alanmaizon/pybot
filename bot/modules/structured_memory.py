"""Extract and retrieve the compact structured memory index."""
import re

from ..memory import structured

PRIORITY = 7600

_RECALL = re.compile(
    r"\b(?:what is|what's|whats|who is|where do i|when is|what are|"
    r"what am i interested in|what am i working on|what am i building|"
    r"do you remember|what do you remember|tell me about|what have i told you)\b",
    re.I,
)


def observe(text, memory):
    structured.observe(memory, text, len(memory.get("turns") or []))


def respond(text, memory):
    if not _RECALL.search(str(text or "")):
        return None
    lowered = str(text or "").lower()
    if "what do you remember" in lowered or "what have i told you" in lowered:
        records = structured.all_records(memory)
    else:
        records = structured.find(memory, text)
    if not records:
        return None
    if "what do you remember" in lowered or "what have i told you" in lowered:
        return _summary(records)
    record = records[0]
    return _say(record)


def TAKES_AS_IT_COMES(text, memory):
    """Keep an explicit memory-management recall ahead of generic topic answers."""
    return respond(text, memory) is not None


def _say(record):
    key = record["key"]
    value = record["value"]
    if record.get("provenance") == "inferred":
        return "I may have inferred that your " + key + " is " + value + "; please confirm."
    if key == "name":
        return "Your name is " + value + "."
    if key == "location":
        return "You live in " + value + "."
    if key == "languages":
        return "You told me you speak " + value + "."
    if key.startswith("favourite "):
        return "Your " + key + " is " + value + "."
    if key in ("birthday", "anniversary"):
        return "Your " + key + " is " + value + "."
    if key == "project":
        return "You are working on " + value + "."
    if key == "interest":
        return "You are interested in " + value + "."
    return "You told me: " + key + " is " + value + "."


def _summary(records):
    return " ".join(_say(record) for record in records[:5])
