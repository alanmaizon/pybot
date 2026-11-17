"""Regression tests for the structured memory index and retrieval module."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import runtime  # noqa: E402
from bot.memory import structured  # noqa: E402


class StructuredMemory(unittest.TestCase):
    def test_extracts_each_supported_category(self):
        memory = {}
        structured.observe(memory, "My name is Alan.", 0)
        structured.observe(memory, "My favourite language is Spanish.", 1)
        structured.observe(memory, "I am interested in astronomy.", 2)
        structured.observe(memory, "My birthday is 4 May.", 3)
        structured.observe(memory, "I am working on a garden project.", 4)
        records = structured.all_records(memory)
        self.assertEqual({record["category"] for record in records},
                         {"personal_facts", "preferences", "interests",
                          "important_dates", "ongoing_topics"})

    def test_retrieves_relevant_memory_after_unrelated_turns(self):
        memory = {}
        runtime.turn("I am interested in astronomy.", memory)
        runtime.turn("What is 15 multiplied by 8?", memory)
        reply = runtime.turn("What am I interested in?", memory)["reply"]
        self.assertIn("astronomy", reply)

    def test_new_value_replaces_conflicting_value_without_duplicates(self):
        memory = {}
        structured.observe(memory, "My favourite language is Spanish.", 0)
        structured.observe(memory, "Actually, my favourite language is French.", 1)
        records = structured.find(memory, "favourite language")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["value"], "French")

    def test_edit_and_delete_are_user_controlled(self):
        memory = {}
        structured.observe(memory, "My name is Alan.", 0)
        record_id = structured.all_records(memory)[0]["id"]
        self.assertTrue(structured.update(memory, record_id, "Alicia"))
        self.assertIn("Alicia", structured.all_records(memory)[0]["value"])
        self.assertTrue(structured.delete(memory, record_id))
        self.assertEqual(structured.all_records(memory), [])

    def test_json_round_trip_and_conversation_isolation(self):
        memory = {}
        runtime.turn("My name is Alan.", memory)
        restored = json.loads(json.dumps(memory))
        self.assertIn("Alan", runtime.turn("What is my name?", restored)["reply"])
        fresh = {}
        reply = runtime.turn("What is my name?", fresh)["reply"]
        self.assertNotIn("Alan", reply)


if __name__ == "__main__":
    unittest.main()
