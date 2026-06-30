import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "test_pdf_vision_compare.py"
SPEC = importlib.util.spec_from_file_location("test_pdf_vision_compare", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TextFirstRoutingTests(unittest.TestCase):
    def test_text_success_ignores_vision_json_failure(self) -> None:
        decision = MODULE.decide_text_first_route(
            "text",
            {"json_valid": True, "data": {"nodes": [{"title": "pneumonia"}]}},
            {"json_valid": False, "data": {}},
        )

        self.assertEqual(decision["selected_route"], "text")
        self.assertEqual(decision["fallback_reason"], "")
        self.assertIn("vision_json_failed_ignored", decision["quality_notes"])

    def test_vision_nodes_more_does_not_override_text(self) -> None:
        decision = MODULE.decide_text_first_route(
            "mixed",
            {"json_valid": True, "data": {"nodes": [{"title": "text"}]}},
            {
                "json_valid": True,
                "data": {"nodes": [{"title": "v1"}, {"title": "v2"}]},
            },
        )

        self.assertEqual(decision["selected_route"], "text")
        self.assertIn("needs_quality_review", decision["quality_notes"])

    def test_table_page_type_does_not_force_vision(self) -> None:
        decision = MODULE.decide_text_first_route(
            "table",
            {"json_valid": True, "data": {"nodes": [{"title": "t"} for _ in range(28)]}},
            {"json_valid": True, "data": {"nodes": [{"title": "v"} for _ in range(9)]}},
        )

        self.assertEqual(decision["selected_route"], "text")
        self.assertIn("table_page_not_automatic_vision", decision["quality_notes"])

    def test_text_failure_falls_back_to_vision_when_vision_has_nodes(self) -> None:
        decision = MODULE.decide_text_first_route(
            "unknown",
            {"json_valid": False, "data": {}},
            {"json_valid": True, "data": {"nodes": [{"title": "fallback"}]}},
        )

        self.assertEqual(decision["selected_route"], "vision")
        self.assertEqual(decision["fallback_reason"], "text_json_invalid")
        self.assertIn("fallback_improved", decision["quality_notes"])


if __name__ == "__main__":
    unittest.main()
