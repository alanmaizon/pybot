"""Regression tests for local document intelligence."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import documents  # noqa: E402
from bot.modules import tools  # noqa: E402
from bot.tools.registry import default_registry  # noqa: E402


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.state = {}
        self.registry = default_registry()

    def test_extracts_supported_formats_and_metadata(self):
        txt = documents.add(self.state, "notes.txt", b"alpha\nbeta", consent=False)
        md = documents.add(self.state, "readme.md", "# Heading\ntext", consent=False)
        csv = documents.add(self.state, "table.csv", "Name,Score\nAlan,10")
        data = documents.add(self.state, "data.json", '{"risk": "high"}')
        self.assertEqual({item["type"] for item in documents.list_documents(self.state)},
                         {"txt", "md", "csv", "json"})
        self.assertEqual(txt["name"], "notes.txt")
        self.assertEqual(csv["chunks"], 1)
        self.assertEqual(data["size"], len('{"risk": "high"}'.encode()))
        self.assertNotEqual(md["id"], txt["id"])

    def test_chunks_large_text_and_returns_source_references(self):
        record = documents.add(self.state, "report.txt", "safe " * 400)
        self.state["selected_document_id"] = record["id"]
        results = documents.search(self.state, "safe")
        self.assertGreater(len(results), 1)
        self.assertEqual(results[0]["source"]["file"], "report.txt")
        self.assertIn("lines", results[0]["source"])
        self.assertIn("section", results[0]["source"])

    def test_invalid_and_oversized_documents_are_rejected(self):
        with self.assertRaises(documents.DocumentError):
            documents.add(self.state, "report.pdf", "not supported")
        with self.assertRaises(documents.DocumentError):
            documents.add(self.state, "bad.json", "{")
        with self.assertRaises(documents.DocumentError):
            documents.add(self.state, "large.txt", b"x" * (documents.MAX_DOCUMENT_BYTES + 1))

    def test_explicit_selection_is_required_and_document_isolation_holds(self):
        first = documents.add(self.state, "one.txt", "alpha deadline Friday")
        second = documents.add(self.state, "two.txt", "beta deadline Monday")
        with self.assertRaises(documents.DocumentError):
            documents.search(self.state, "deadline")
        self.state["selected_document_id"] = first["id"]
        self.assertEqual(documents.search(self.state, "Friday")[0]["source"]["file"], "one.txt")
        self.assertEqual(documents.search(self.state, "Monday"), [])
        self.assertEqual(documents.read(self.state, second["id"])[0]["source"]["file"], "two.txt")

    def test_tool_search_and_remove(self):
        record = documents.add(self.state, "project.txt", "The project deadline is 4 May.")
        self.state["selected_document_id"] = record["id"]
        tools.set_documents(self.state)
        result = self.registry.execute("search_documents", {"query": "project deadline"},
                                       {"documents": self.state})
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["output"][0]["source"]["file"], "project.txt")
        removed = self.registry.execute("remove_document", {"document_id": record["id"]},
                                        {"documents": self.state})
        self.assertTrue(removed["ok"])
        self.assertEqual(documents.list_documents(self.state), [])

    def test_consent_export_and_restore(self):
        transient = documents.add(self.state, "temp.txt", "private", consent=False)
        saved = documents.add(self.state, "saved.txt", "keep", consent=True)
        exported = documents.export_consent(self.state)
        self.assertNotIn(transient["id"], exported)
        self.assertIn(saved["id"], exported)
        restored = {}
        documents.restore(restored, json.loads(json.dumps(exported)))
        self.assertEqual([item["name"] for item in documents.list_documents(restored)], ["saved.txt"])

    def test_conversation_module_cites_selected_passages(self):
        record = documents.add(self.state, "risks.txt", "Main risk: the deadline may slip.")
        self.state["selected_document_id"] = record["id"]
        tools.set_documents(self.state)
        answer = tools.respond("What are the main risks?", {})
        self.assertIn("Document evidence", answer)
        self.assertIn("risks.txt", answer)
        self.assertIn("deadline", answer)


if __name__ == "__main__":
    unittest.main()
