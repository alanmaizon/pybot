"""Built-in local tools backed by existing PyBot helpers."""
import ast
import contextlib
import datetime as _datetime
import io
import math
import sys
import time

from ..knowledge import maths, units
from ..memory import history, structured
from .registry import ToolError, ToolSpec


def _text_schema(name="text"):
    return {"type": "object", "required": [name],
            "properties": {name: {"type": "string"}}, "additionalProperties": False}


def _calculator(arguments, context):
    expression = arguments["expression"].strip()
    answer = maths.solve(expression, {"clean": expression.lower()}, context.get("memory", {}))
    if not answer:
        raise ToolError("That is not a supported arithmetic expression.")
    return {"output": answer, "format": "text"}


def _date_time(arguments, context):
    now = _datetime.datetime.now(_datetime.timezone.utc)
    return {"output": now.isoformat(), "format": "iso-8601", "timezone": "UTC"}


def _unit_conversion(arguments, context):
    query = arguments["query"].strip()
    answer = units.convert(query.lower(), context.get("memory", {}))
    if not answer:
        raise ToolError("I could not identify a compatible unit conversion.")
    return {"output": answer, "format": "text"}


def _history_search(arguments, context):
    query = arguments["query"].lower().strip()
    words = [word for word in query.split() if len(word) > 2]
    matches = []
    for turn in history.turns_before(context.get("memory", {})):
        text = str(turn.get("user", ""))
        if words and all(word in text.lower() for word in words):
            matches.append({"user": text, "bot": str(turn.get("bot", ""))})
    return {"output": matches[-10:], "format": "turns"}


def _memory_search(arguments, context):
    records = structured.find(context.get("memory", {}), arguments["query"])
    return {"output": records[:10], "format": "memories"}


def _restricted_builtins():
    return {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
        "enumerate": enumerate, "float": float, "int": int, "len": len,
        "list": list, "max": max, "min": min, "range": range, "round": round,
        "print": print, "set": set, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple,
    }


def _python_execute(arguments, context):
    code = arguments["code"]
    if len(code) > 4000:
        raise ToolError("Python code is limited to 4,000 characters.")
    timeout = min(max(float(arguments.get("timeout_seconds", 1)), 0.1), 2.0)
    namespace = {"__builtins__": _restricted_builtins(), "math": math}
    output = io.StringIO()
    started = time.monotonic()
    steps = [0]

    def trace(_frame, _event, _arg):
        steps[0] += 1
        if steps[0] > 10000 or time.monotonic() - started > timeout:
            raise TimeoutError("Python execution time limit exceeded.")
        return trace

    try:
        with contextlib.redirect_stdout(output):
            try:
                tree = ast.parse(code, mode="eval")
            except SyntaxError:
                tree = ast.parse(code, mode="exec")
                sys.settrace(trace)
                exec(compile(tree, "<pybot>", "exec"), namespace, namespace)
                sys.settrace(None)
                value = namespace.get("result")
            else:
                sys.settrace(trace)
                value = eval(compile(tree, "<pybot>", "eval"), namespace, namespace)
                sys.settrace(None)
    except (SyntaxError, RuntimeError, TypeError, ValueError, NameError, ZeroDivisionError,
            TimeoutError) as error:
        sys.settrace(None)
        raise ToolError(f"{type(error).__name__}: {error}")
    if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
        value = repr(value)
    return {"output": {"stdout": output.getvalue(), "value": value},
            "format": "python-result", "steps": steps[0]}


def register_builtins(registry):
    registry.register(ToolSpec(
        "calculator", "Evaluate a clearly specified arithmetic expression.",
        _text_schema("expression"), "safe", "text", _calculator))
    registry.register(ToolSpec(
        "date_time", "Return the current UTC date and time.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        "safe", "iso-8601", _date_time))
    registry.register(ToolSpec(
        "unit_conversion", "Convert a clearly specified measurement.",
        _text_schema("query"), "safe", "text", _unit_conversion))
    registry.register(ToolSpec(
        "conversation_search", "Search earlier user turns and replies.",
        _text_schema("query"), "safe", "turns", _history_search))
    registry.register(ToolSpec(
        "structured_memory_search", "Search explicit local structured memories.",
        _text_schema("query"), "safe", "memories", _memory_search))
    registry.register(ToolSpec(
        "python", "Run approved Python in a restricted local namespace.",
        {"type": "object", "required": ["code"],
         "properties": {"code": {"type": "string"},
                        "timeout_seconds": {"type": "number"}},
         "additionalProperties": False},
        "approval", "python-result", _python_execute))
