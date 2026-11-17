"""Intent-routed local tools; ambiguous messages remain with the normal engine."""
from ..tools.registry import default_registry
from ..tools.selector import select

PRIORITY = 8200
REGISTRY = default_registry()
DOCUMENTS = {}


def set_documents(state):
    """Replace browser-owned document state without putting it in chat memory."""
    global DOCUMENTS
    DOCUMENTS = state if isinstance(state, dict) else {}


def respond(text, memory):
    choice = select(text, document_selected=bool(DOCUMENTS.get("selected_document_id")))
    if not choice:
        return None
    if choice.get("approve"):
        pending = memory.pop("pending_tool", None)
        if not pending:
            return "There is no pending tool request to approve."
        result = REGISTRY.execute(pending["tool"], pending["arguments"],
                                  {"memory": memory, "documents": DOCUMENTS}, approved=True)
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
                              {"memory": memory, "documents": DOCUMENTS}, approved=False)
    memory["last_tool"] = {
        "id": choice["tool"],
        "arguments": choice["arguments"],
        "result": result,
    }
    if not result["ok"]:
        return "Tool " + choice["tool"] + " was not run: " + result["error"]
    output = result["result"]["output"]
    if result["result"].get("format") == "passages":
        if not output:
            return "I found no matching passage in the selected document."
        return "Document evidence (not an interpretation): " + " ".join(
            f"{item['source']['file']} [{item['source']['section']}, "
            f"lines {item['source']['lines']}]: {item['text']}"
            for item in output
        )
    if isinstance(output, dict):
        output = str(output)
    return "Using " + choice["tool"] + ": " + str(output)
