"""Intent-routed local tools; ambiguous messages remain with the normal engine."""
from ..tools.registry import default_registry
from ..tools.selector import select

PRIORITY = 8200
REGISTRY = default_registry()


def respond(text, memory):
    choice = select(text)
    if not choice:
        return None
    if choice.get("approve"):
        pending = memory.pop("pending_tool", None)
        if not pending:
            return "There is no pending tool request to approve."
        result = REGISTRY.execute(pending["tool"], pending["arguments"],
                                  {"memory": memory}, approved=True)
        memory["last_tool"] = {
            "id": pending["tool"], "arguments": pending["arguments"], "result": result,
        }
        if not result["ok"]:
            return "Tool " + pending["tool"] + " was not run: " + result["error"]
        return "Using " + pending["tool"] + ": " + str(result["result"]["output"])
    if choice.get("clarification"):
        memory["tool_notice"] = choice["clarification"]
        return choice["clarification"]
    if choice["tool"] == "python":
        memory["pending_tool"] = {
            "tool": choice["tool"], "arguments": choice["arguments"],
        }
        return "Python execution requires explicit approval. Type /approve to run it locally."
    result = REGISTRY.execute(choice["tool"], choice["arguments"],
                              {"memory": memory}, approved=False)
    memory["last_tool"] = {
        "id": choice["tool"],
        "arguments": choice["arguments"],
        "result": result,
    }
    if not result["ok"]:
        return "Tool " + choice["tool"] + " was not run: " + result["error"]
    output = result["result"]["output"]
    if isinstance(output, dict):
        output = str(output)
    return "Using " + choice["tool"] + ": " + str(output)
