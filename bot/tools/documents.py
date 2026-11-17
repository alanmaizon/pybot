"""Registry adapters for explicitly selected local documents."""
from .. import documents
from .registry import ToolError, ToolSpec


def _state(context):
    state = context.get("documents")
    if not isinstance(state, dict):
        raise ToolError("Document storage is unavailable.")
    return state


def _list(arguments, context):
    return {"output": documents.list_documents(_state(context)), "format": "metadata"}


def _search(arguments, context):
    try:
        output = documents.search(_state(context), arguments["query"],
                                  arguments.get("document_id"), arguments.get("limit", 5))
    except documents.DocumentError as error:
        raise ToolError(str(error))
    return {"output": output, "format": "passages"}


def _read(arguments, context):
    try:
        output = documents.read(_state(context), arguments.get("document_id"),
                                arguments.get("chunk_id"))
    except documents.DocumentError as error:
        raise ToolError(str(error))
    return {"output": output, "format": "passages"}


def _remove(arguments, context):
    return {"output": documents.remove(_state(context), arguments["document_id"]),
            "format": "boolean"}


def _schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


def register_document_tools(registry):
    registry.register(ToolSpec(
        "list_documents", "List uploaded local document metadata.",
        _schema({}), "safe", "metadata", _list))
    registry.register(ToolSpec(
        "search_documents", "Search passages in an explicitly selected document.",
        _schema({"query": {"type": "string"}, "document_id": {"type": "string"},
                 "limit": {"type": "number"}}, ("query",)),
        "safe", "passages", _search))
    registry.register(ToolSpec(
        "read_document", "Read passages from an explicitly selected document.",
        _schema({"document_id": {"type": "string"}, "chunk_id": {"type": "string"}}),
        "safe", "passages", _read))
    registry.register(ToolSpec(
        "remove_document", "Delete an uploaded local document.",
        _schema({"document_id": {"type": "string"}}, ("document_id",)),
        "safe", "boolean", _remove))
