"""Structured, user-controlled memories built from explicit statements.

The existing memory modules remain the source of truth for their specialised replies. This
store is a small searchable index for the browser memory panel and for broad recall questions.
Only explicit first-person statements are stored; questions and guesses are ignored.
"""
import re


CATEGORIES = ("personal_facts", "preferences", "interests", "important_dates",
              "ongoing_topics")
CATEGORY_LABELS = {
    "personal_facts": "Personal facts",
    "preferences": "Preferences",
    "interests": "Interests",
    "important_dates": "Important dates",
    "ongoing_topics": "Ongoing topics",
}

_NAME = re.compile(r"^\s*(?:my name is|i am called|i'm called)\s+(?P<value>[^.!?]+)", re.I)
_LOCATION = re.compile(
    r"^\s*i\s+(?:live|am living|currently live)\s+in\s+(?P<value>[^.!?,;]+)", re.I)
_LANGUAGES = re.compile(
    r"\bi\s+(?:speak|know|am learning)\s+(?P<value>[^.!?]+)", re.I)
_FAVOURITE = re.compile(
    r"\bmy\s+(?:favou?rite|fav)\s+(?P<key>[a-z][a-z -]{1,30})"
    r"\s+(?:is|are)\s+(?P<value>[^.!?,;]+)", re.I)
_PREFERENCE = re.compile(
    r"^\s*i\s+(?:prefer|like|love)\s+(?P<value>[^.!?]+)", re.I)
_INTEREST = re.compile(
    r"^\s*i\s+(?:am\s+interested\s+in|i'm\s+interested\s+in|enjoy|am\s+into)\s+"
    r"(?P<value>[^.!?]+)", re.I)
_DATE = re.compile(
    r"^\s*my\s+(?P<key>birthday|anniversary)\s+is\s+(?P<value>[^.!?]+)", re.I)
_PROJECT = re.compile(
    r"^\s*(?:i\s+am|i'm|i\s+am\s+currently|i'm\s+currently)\s+"
    r"(?:working\s+on|building|developing)\s+(?P<value>[^.!?]+)", re.I)

_TRAILING = re.compile(r"\s+(?:now|these days|at the moment|currently)\s*$", re.I)
_VALUE_END = re.compile(r"\s*(?:,|;)\s*(?:and|but|while)\b.*$", re.I)


def _clean(value):
    value = " ".join(str(value or "").split()).strip(" \t,.;:!?")
    value = _TRAILING.sub("", value).strip(" \t,.;:!?")
    return value


def _key(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _record(category, key, value, text, turn):
    value = _clean(value)
    key = _key(key)
    if not value or not key or "?" in value:
        return None
    return {
        "id": category + ":" + key,
        "category": category,
        "key": key,
        "value": value,
        "source": str(text or "").strip(),
        "turn": int(turn),
    }


def extract(text, turn=0):
    """Return explicit structured facts from one user message."""
    line = " ".join(str(text or "").split()).strip()
    if not line or "?" in line:
        return []
    records = []
    match = _NAME.match(line)
    if match:
        records.append(_record("personal_facts", "name", match.group("value"), line, turn))
    match = _LOCATION.match(line)
    if match:
        records.append(_record("personal_facts", "location", match.group("value"), line, turn))
    match = _LANGUAGES.search(line)
    if match and not line.lower().startswith(("what ", "how ", "do ", "can ")):
        value = _VALUE_END.sub("", match.group("value"))
        records.append(_record("personal_facts", "languages", value, line, turn))
    for match in _FAVOURITE.finditer(line):
        records.append(_record("preferences", "favourite " + match.group("key"),
                               match.group("value"), line, turn))
    match = _PREFERENCE.match(line)
    if match:
        records.append(_record("preferences", "preference", match.group("value"), line, turn))
    match = _INTEREST.match(line)
    if match:
        records.append(_record("interests", "interest", match.group("value"), line, turn))
    match = _DATE.match(line)
    if match:
        records.append(_record("important_dates", match.group("key"), match.group("value"),
                               line, turn))
    match = _PROJECT.match(line)
    if match:
        records.append(_record("ongoing_topics", "project", match.group("value"), line, turn))
    return [record for record in records if record]


def _bucket(memory, category):
    structured = memory.setdefault("structured_memory", {})
    values = structured.setdefault(category, [])
    if not isinstance(values, list):
        values = structured[category] = []
    return values


def remember(memory, records):
    """Upsert records by category/key, preserving the newest explicit value."""
    if not isinstance(memory, dict):
        return
    for record in records or []:
        if not isinstance(record, dict) or record.get("category") not in CATEGORIES:
            continue
        category = record["category"]
        values = _bucket(memory, category)
        current = next((item for item in values if item.get("id") == record.get("id")), None)
        if current is None:
            values.append(dict(record))
        else:
            current.update(record)


def observe(memory, text, turn=0):
    records = extract(text, turn)
    remember(memory, records)
    return records


def all_records(memory):
    structured = memory.get("structured_memory", {}) if isinstance(memory, dict) else {}
    result = []
    for category in CATEGORIES:
        for record in structured.get(category, []) or []:
            if isinstance(record, dict):
                result.append(dict(record, category=category))
    return result


def find(memory, query):
    """Find explicit memories whose category, key, or value matches query words."""
    lowered = str(query or "").lower()
    words = set(re.findall(r"[a-z0-9]+", lowered))
    if "interest" in lowered:
        words.update(("interest", "interests"))
    if any(term in lowered for term in ("working on", "building", "project")):
        words.update(("ongoing", "topics"))
    if any(term in lowered for term in ("birthday", "anniversary", "important date")):
        words.update(("important", "dates"))
    if any(term in lowered for term in ("favourite", "favorite", "prefer", "like")):
        words.add("preferences")
    if any(term in lowered for term in ("name", "live in", "speak", "language")):
        words.add("personal_facts")
    if not words:
        return []
    scored = []
    for record in all_records(memory):
        haystack = set(re.findall(r"[a-z0-9]+",
                                  " ".join((record.get("category", ""),
                                            record.get("key", ""),
                                            record.get("value", ""))).lower()
                                  .replace("_", " ")))
        score = sum(word in haystack for word in words)
        if score:
            scored.append((score, int(record.get("turn", 0)), record))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    return [record for _, _, record in scored]


def update(memory, record_id, value):
    """Edit one record without changing its category or identity."""
    value = _clean(value)
    if not value:
        return False
    for record in all_records(memory):
        if record.get("id") == record_id:
            bucket = _bucket(memory, record["category"])
            for current in bucket:
                if current.get("id") == record_id:
                    current["value"] = value
                    current["source"] = "Edited in memory"
                    return True
    return False


def delete(memory, record_id):
    for category in CATEGORIES:
        values = _bucket(memory, category)
        kept = [record for record in values if record.get("id") != record_id]
        if len(kept) != len(values):
            memory["structured_memory"][category] = kept
            return True
    return False


def clear(memory):
    if isinstance(memory, dict):
        memory.pop("structured_memory", None)
