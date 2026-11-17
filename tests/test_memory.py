"""Regression tests for conversation facts and turn-to-turn memory."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import runtime  # noqa: E402


def converse(messages):
    memory = {}
    replies = []
    for message in messages:
        replies.append(runtime.turn(message, memory)["reply"])
    return replies, memory


class ConversationalMemory(unittest.TestCase):
    def test_remembers_favourite_language_with_punctuation(self):
        replies, _ = converse([
            "My favourite language is Spanish.",
            "What is my favourite language?",
        ])
        self.assertIn("Spanish", replies[-1])

    def test_retains_name_across_an_unrelated_question(self):
        replies, _ = converse([
            "My name is Alan.",
            "How do you say hello in Spanish?",
            "What is my name?",
        ])
        self.assertIn("Alan", replies[-1])

    def test_remembers_a_place_from_a_multi_fact_statement(self):
        replies, _ = converse([
            "I live in Ireland and speak English and Spanish.",
            "Where do I live?",
        ])
        self.assertIn("Ireland", replies[-1])

    def test_retains_favourite_after_an_unrelated_calculation(self):
        replies, _ = converse([
            "My favourite language is Spanish.",
            "What is 15 multiplied by 8?",
            "What is my favourite language?",
        ])
        self.assertIn("Spanish", replies[-1])

    def test_new_memory_does_not_inherit_previous_conversation(self):
        _, old_memory = converse(["My name is Alan."])
        replies, new_memory = converse(["What is my name?"])
        self.assertNotIn("Alan", replies[-1])
        self.assertNotIn("user", new_memory.get("facts_log", []))
        self.assertNotEqual(old_memory, new_memory)

    def test_memory_survives_json_round_trip_for_refresh_persistence(self):
        _, memory = converse(["My favourite language is Spanish."])
        restored = json.loads(json.dumps(memory))
        reply = runtime.turn("What is my favourite language?", restored)["reply"]
        self.assertIn("Spanish", reply)


if __name__ == "__main__":
    unittest.main()
