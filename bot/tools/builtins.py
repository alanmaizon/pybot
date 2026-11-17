"""Built-in local tools backed by existing PyBot helpers."""
import ast
import datetime as _datetime
import io
import math
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


_SAFE_FUNCTIONS = {
    "abs": abs, "bool": bool, "float": float, "int": int, "len": len,
    "max": max, "min": min, "round": round, "sorted": sorted, "str": str,
    "sum": sum,
}
_SAFE_MATH = {
    name: getattr(math, name) for name in (
        "ceil", "cos", "floor", "log", "log10", "pi", "sin", "sqrt", "tan"
    )
}
_BINOPS = {
    ast.Add: lambda left, right: left + right,
    ast.Div: lambda left, right: left / right,
    ast.FloorDiv: lambda left, right: left // right,
    ast.Mod: lambda left, right: left % right,
    ast.Mult: lambda left, right: left * right,
    ast.Pow: lambda left, right: left ** right,
    ast.Sub: lambda left, right: left - right,
}
_UNARYOPS = {ast.UAdd: lambda value: +value, ast.USub: lambda value: -value}


def _python_execute(arguments, context):
    code = arguments["code"]
    if len(code) > 4000:
        raise ToolError("Python code is limited to 4,000 characters.")
    timeout = min(max(float(arguments.get("timeout_seconds", 1)), 0.1), 2.0)
    namespace = {}
    output = io.StringIO()
    started = time.monotonic()
    steps = [0]

    def visit(node):
        steps[0] += 1
        if steps[0] > 10000 or time.monotonic() - started > timeout:
            raise TimeoutError("Python execution time limit exceeded.")
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (str, int, float, bool, type(None))):
                raise ToolError("That Python value type is not allowed.")
            return node.value
        if isinstance(node, ast.List):
            return [visit(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(visit(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return {visit(key): visit(value) for key, value in zip(node.keys, node.values)}
        if isinstance(node, ast.Name):
            if node.id in namespace:
                return namespace[node.id]
            if node.id in _SAFE_FUNCTIONS:
                return _SAFE_FUNCTIONS[node.id]
            if node.id in _SAFE_MATH:
                return _SAFE_MATH[node.id]
            raise ToolError(f"Name is not allowed: {node.id}")
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return _BINOPS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
            return _UNARYOPS[type(node.op)](visit(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            function = visit(node.func)
            if function not in _SAFE_FUNCTIONS.values():
                raise ToolError("That function is not allowed.")
            return function(*(visit(arg) for arg in node.args))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "math":
                raise ToolError("Attribute access is not allowed.")
            function = _SAFE_MATH.get(node.func.attr)
            if function is None or not callable(function):
                raise ToolError("That math function is not allowed.")
            return function(*(visit(arg) for arg in node.args))
        if isinstance(node, ast.Attribute):
            raise ToolError("Attribute access is not allowed.")
        raise ToolError(f"Python syntax is not allowed: {type(node).__name__}")

    def emit(*values):
        output.write(" ".join(str(value) for value in values) + "\n")

    try:
        tree = ast.parse(code, mode="exec")
        if len(tree.body) > 20:
            raise ToolError("Python execution is limited to 20 statements.")
        for statement in tree.body:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) \
                    and isinstance(statement.value.func, ast.Name) \
                    and statement.value.func.id == "print":
                emit(*(visit(arg) for arg in statement.value.args))
            elif isinstance(statement, ast.Assign) and len(statement.targets) == 1 \
                    and isinstance(statement.targets[0], ast.Name):
                namespace[statement.targets[0].id] = visit(statement.value)
            elif isinstance(statement, ast.Expr):
                namespace["result"] = visit(statement.value)
            else:
                raise ToolError("Only expressions, assignments, and print are allowed.")
        value = namespace.get("result")
    except (SyntaxError, RuntimeError, TypeError, ValueError, ZeroDivisionError,
            OverflowError, TimeoutError) as error:
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
