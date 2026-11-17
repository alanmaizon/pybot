"""Small, validated registry for local assistant tools."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


class ToolError(Exception):
    """A user-visible, structured tool failure."""


@dataclass(frozen=True)
class ToolSpec:
    id: str
    description: str
    input_schema: Dict[str, Any]
    permission: str
    output_format: str
    execute: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, spec):
        if not isinstance(spec, ToolSpec) or not spec.id.strip():
            raise ValueError("tool must be a named ToolSpec")
        if spec.permission not in ("safe", "approval"):
            raise ValueError("permission must be safe or approval")
        if spec.id in self._tools:
            raise ValueError("tool already registered: " + spec.id)
        self._tools[spec.id] = spec
        return spec

    def get(self, tool_id):
        return self._tools.get(tool_id)

    def list(self):
        return tuple(self._tools.values())

    def _validate(self, spec, arguments):
        schema = spec.input_schema or {}
        if not isinstance(arguments, dict):
            raise ToolError("Tool input must be an object.")
        required = schema.get("required", ())
        missing = [key for key in required if key not in arguments]
        if missing:
            raise ToolError("Missing required input: " + ", ".join(missing))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = [key for key in arguments if key not in properties]
            if unknown:
                raise ToolError("Unknown input: " + ", ".join(unknown))
        for key, value in arguments.items():
            expected = properties.get(key, {}).get("type")
            if expected == "string" and not isinstance(value, str):
                raise ToolError(f"{key} must be a string.")
            if expected == "number" and (isinstance(value, bool) or
                                         not isinstance(value, (int, float))):
                raise ToolError(f"{key} must be a number.")
            if expected == "boolean" and not isinstance(value, bool):
                raise ToolError(f"{key} must be a boolean.")

    def execute(self, tool_id, arguments=None, context=None, *, approved=False):
        spec = self.get(tool_id)
        if spec is None:
            return {"ok": False, "tool": tool_id, "error": "Unknown tool."}
        try:
            self._validate(spec, arguments or {})
            if spec.permission == "approval" and not approved:
                raise ToolError("Explicit approval is required for this tool.")
            result = spec.execute(dict(arguments or {}), context or {})
            if not isinstance(result, dict) or "output" not in result:
                raise ToolError("Tool returned an invalid result.")
            return {"ok": True, "tool": tool_id, "result": result}
        except ToolError as error:
            return {"ok": False, "tool": tool_id, "error": str(error)}
        except Exception as error:  # tool boundary: expose a safe error, never a fake result
            return {"ok": False, "tool": tool_id,
                    "error": f"{type(error).__name__}: {error}"}


def default_registry():
    from .builtins import register_builtins
    from .documents import register_document_tools
    registry = ToolRegistry()
    register_builtins(registry)
    register_document_tools(registry)
    return registry
