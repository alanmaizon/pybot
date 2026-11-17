"""Local document extraction, chunking, and lexical retrieval.

The store is an ordinary dictionary so the browser can keep it in the Pyodide
session without introducing a database or sending document contents anywhere.
"""
import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone


MAX_DOCUMENT_BYTES = 1_000_000
MAX_DOCUMENTS = 20
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 160
SUPPORTED_EXTENSIONS = {"txt", "md", "markdown", "csv", "json"}
_WORD = re.compile(r"[a-z0-9][a-z0-9'-]*", re.I)
_STOPWORDS = {
    "a", "an", "and", "are", "about", "be", "does", "for", "from", "how",
    "in", "is", "it", "me", "of", "on", "or", "the", "this", "to", "was",
    "what", "where", "which", "with", "you",
}


class DocumentError(ValueError):
    """A safe, user-facing document validation or lookup error."""


def _clean_name(name):
    name = " ".join(str(name or "").split()).strip()
    if not name or len(name) > 160:
        raise DocumentError("Document names must be between 1 and 160 characters.")
    return name


def _extension(name):
    parts = _clean_name(name).lower().rsplit(".", 1)
    if len(parts) != 2 or parts[1] not in SUPPORTED_EXTENSIONS:
        raise DocumentError("Supported document types are TXT, Markdown, CSV, and JSON.")
    return parts[1]


def _decode(content):
    if isinstance(content, bytes):
        if len(content) > MAX_DOCUMENT_BYTES:
            raise DocumentError("Documents are limited to 1 MB.")
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DocumentError("Documents must be UTF-8 text.") from error
    text = str(content or "")
    if len(text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise DocumentError("Documents are limited to 1 MB.")
    return text


def _extract(text, extension):
    if extension in ("txt", "md", "markdown"):
        return text
    if extension == "csv":
        rows = list(csv.reader(io.StringIO(text)))
        return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)
    try:
        value = json.loads(text)
    except (TypeError, ValueError) as error:
        raise DocumentError("The JSON document is invalid.") from error
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _chunks(text):
    lines = text.splitlines() or [text]
    chunks = []
    start = 0
    while start < len(text) or (not chunks and not text):
        end = min(len(text), start + CHUNK_SIZE)
        if end < len(text):
            boundary = text.rfind("\n", start + CHUNK_SIZE // 2, end)
            if boundary > start:
                end = boundary
        fragment = text[start:end].strip()
        if fragment:
            line_start = text.count("\n", 0, start) + 1
            line_end = text.count("\n", 0, max(start, end)) + 1
            chunks.append({
                "id": str(len(chunks)),
                "section": f"chunk {len(chunks) + 1}",
                "line_start": line_start,
                "line_end": line_end,
                "text": fragment,
            })
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def _tokens(text):
    return {word.lower() for word in _WORD.findall(str(text)) if word.lower() not in _STOPWORDS}


def _store(state):
    if not isinstance(state, dict):
        raise DocumentError("Document storage is unavailable.")
    documents = state.setdefault("documents", {})
    if not isinstance(documents, dict):
        state["documents"] = documents = {}
    return documents


def add(state, name, content, *, consent=False):
    documents = _store(state)
    if len(documents) >= MAX_DOCUMENTS:
        raise DocumentError("You can keep at most 20 documents in this session.")
    name = _clean_name(name)
    extension = _extension(name)
    raw = _decode(content)
    text = _extract(raw, extension)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    document_id = digest
    suffix = 2
    while document_id in documents and documents[document_id]["name"] != name:
        document_id = f"{digest}-{suffix}"
        suffix += 1
    record = {
        "id": document_id,
        "name": name,
        "type": extension,
        "size": len(raw.encode("utf-8")),
        "characters": len(text),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "consent": bool(consent),
        "chunks": _chunks(text),
    }
    documents[document_id] = record
    return metadata(record)


def metadata(record):
    result = {key: record[key] for key in (
        "id", "name", "type", "size", "characters", "updated_at", "consent"
    )}
    result["chunks"] = len(record.get("chunks", []))
    return result


def list_documents(state):
    return [metadata(record) for record in _store(state).values()]


def _selected(state, document_id=None):
    documents = _store(state)
    document_id = document_id or state.get("selected_document_id")
    if not document_id:
        raise DocumentError("Select a document before asking about its contents.")
    record = documents.get(document_id)
    if not record:
        raise DocumentError("That document is no longer available.")
    return record


def search(state, query, document_id=None, limit=5):
    record = _selected(state, document_id)
    terms = _tokens(query)
    if not terms:
        raise DocumentError("Add a specific word or phrase to search for.")
    results = []
    for chunk in record.get("chunks", []):
        words = _tokens(chunk["text"])
        matched = terms & words
        phrase = str(query).strip().lower() in chunk["text"].lower()
        score = len(matched) / len(terms) + (0.5 if phrase else 0)
        if score:
            results.append({
                "source": {
                    "document_id": record["id"],
                    "file": record["name"],
                    "section": chunk["section"],
                    "lines": f"{chunk['line_start']}-{chunk['line_end']}",
                },
                "text": chunk["text"],
                "score": round(score, 4),
            })
    results.sort(key=lambda result: result["score"], reverse=True)
    return results[:max(1, min(int(limit), 10))]


def read(state, document_id=None, chunk_id=None):
    record = _selected(state, document_id)
    chunks = record.get("chunks", [])
    if chunk_id is None:
        selected = chunks[:3]
    else:
        selected = [chunk for chunk in chunks if chunk["id"] == str(chunk_id)]
    return [{
        "source": {
            "document_id": record["id"],
            "file": record["name"],
            "section": chunk["section"],
            "lines": f"{chunk['line_start']}-{chunk['line_end']}",
        },
        "text": chunk["text"],
    } for chunk in selected]


def remove(state, document_id):
    documents = _store(state)
    removed = documents.pop(document_id, None) is not None
    if state.get("selected_document_id") == document_id:
        state.pop("selected_document_id", None)
    return removed


def export_consent(state):
    return {
        key: value for key, value in _store(state).items()
        if value.get("consent") is True
    }


def restore(state, saved):
    if not isinstance(saved, dict):
        raise DocumentError("Stored documents are not valid.")
    state["documents"] = {
        key: value for key, value in saved.items()
        if isinstance(value, dict) and value.get("id") == key
        and isinstance(value.get("chunks"), list)
        and all(isinstance(chunk, dict) for chunk in value["chunks"])
    }
