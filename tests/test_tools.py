"""Regression tests for local tool registration, selection, and execution."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.tools.registry import default_registry  # noqa: E402
from bot.tools.selector import select  # noqa: E402


class ToolRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = default_registry()

    def test_all_initial_tools_are_registered(self):
        self.assertEqual(
            {tool.id for tool in self.registry.list()},
            {"calculator", "date_time", "unit_conversion",
             "conversation_search", "structured_memory_search", "python"},
        )

    def test_calculator_reuses_safe_math_logic(self):
        result = self.registry.execute("calculator", {"expression": "15 * 8"})
        self.assertTrue(result["ok"])
        self.assertIn("120", result["result"]["output"])

    def test_input_validation_and_unknown_tool(self):
        self.assertFalse(self.registry.execute("calculator", {})["ok"])
        self.assertFalse(self.registry.execute("missing", {})["ok"])
        self.assertFalse(self.registry.execute(
            "calculator", {"expression": "2 + 2", "extra": True})["ok"])

    def test_python_requires_approval_and_captures_output(self):
        arguments = {"code": "print('hello')\nresult = 2 + 2"}
        denied = self.registry.execute("python", arguments)
        self.assertFalse(denied["ok"])
        approved = self.registry.execute("python", arguments, approved=True)
        self.assertTrue(approved["ok"])
        self.assertEqual(approved["result"]["output"]["stdout"], "hello\n")
        self.assertEqual(approved["result"]["output"]["value"], 4)

    def test_python_rejects_imports_and_runtime_errors(self):
        blocked = self.registry.execute("python", {"code": "__import__('os')"},
                                        approved=True)
        self.assertFalse(blocked["ok"])
        failed = self.registry.execute("python", {"code": "1 / 0"}, approved=True)
        self.assertFalse(failed["ok"])

    def test_python_timeout_is_bounded(self):
        result = self.registry.execute(
            "python", {"code": "while True: pass", "timeout_seconds": 0.1},
            approved=True)
        self.assertFalse(result["ok"])
        self.assertIn("time limit", result["error"])

    def test_selector_is_conservative(self):
        self.assertEqual(select("What is 15 multiplied by 8?")["tool"], "calculator")
        self.assertEqual(select("What time is it?")["tool"], "date_time")
        self.assertEqual(select("/python result = 2 + 2")["tool"], "python")
        self.assertIsNone(select("Tell me a story about a calculator."))


if __name__ == "__main__":
    unittest.main()
