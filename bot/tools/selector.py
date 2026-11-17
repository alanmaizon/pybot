"""Conservative intent selection for built-in tools."""
import re


_MATH = re.compile(r"\d\s*(?:[+\-*/^]|times|plus|minus|divided|multiplied)", re.I)
_UNITS = re.compile(r"\b(?:convert|in|into|to)\b.*\b(?:kg|g|lb|pounds?|miles?|km|"
                    r"litres?|liters?|ml|hours?|minutes?|days?)\b", re.I)
_DATE = re.compile(r"\b(?:what(?:'s| is)?|tell me)\b.*\b(?:time|date|today|now)\b", re.I)
_HISTORY = re.compile(r"\b(?:search|find|look up)\b.*\b(?:conversation|chat|said|turns?)\b|"
                      r"\bwhat did (?:i|we) say\b|\bwhat have we talked about\b", re.I)
_MEMORY = re.compile(r"\b(?:what is my|what are my|do you remember|what do you remember|"
                     r"what have i told you)\b", re.I)
_PYTHON = re.compile(r"^\s*(?:/python|run python|execute python)\b\s*:?\s*", re.I)


def select(text):
    line = " ".join(str(text or "").split())
    if not line:
        return None
    if re.fullmatch(r"/approve", line, re.I):
        return {"approve": True}
    match = _PYTHON.match(line)
    if match:
        code = line[match.end():].strip()
        return {"tool": "python", "arguments": {"code": code}} if code else {
            "clarification": "What Python code should I run?"
        }
    if _MATH.search(line):
        return {"tool": "calculator", "arguments": {"expression": line}}
    if _UNITS.search(line):
        return {"tool": "unit_conversion", "arguments": {"query": line}}
    if _DATE.search(line):
        return {"tool": "date_time", "arguments": {}}
    if _HISTORY.search(line):
        return {"tool": "conversation_search", "arguments": {"query": line}}
    if _MEMORY.search(line):
        return {"tool": "structured_memory_search", "arguments": {"query": line}}
    return None
