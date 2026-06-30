import importlib.util
import sys
import unittest
from pathlib import Path


QUALITY = Path(__file__).resolve().parents[1] / "scripts" / "textbook_pipeline" / "extraction_quality.py"
SPEC = importlib.util.spec_from_file_location("extraction_quality", QUALITY)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ExtractionQualityTests(unittest.TestCase):
    def test_rejects_boilerplate_chunk(self) -> None:
        self.assertFalse(MODULE.is_extractable_chunk("目录"))

    def test_accepts_real_medical_chunk(self) -> None:
        text = "心力衰竭是各种心脏结构或功能性疾病导致心室充盈和（或）射血功能受损的一组临床综合征。" * 3
        self.assertTrue(MODULE.is_extractable_chunk(text))

    def test_enrich_row_adds_parent_to_content(self) -> None:
        row = {
            "title": "心力衰竭的临床表现",
            "content": "主要表现为呼吸困难、乏力及液体潴留。",
            "source_span": {"parent_entity": "心力衰竭", "evidence": "心力衰竭的主要表现为呼吸困难"},
        }
        enriched = MODULE.enrich_row_content(row)
        self.assertIn("心力衰竭", enriched["content"])

    def test_chunk_coverage_gate_rejects_low_ratio(self) -> None:
        low = MODULE.assess_chunk_coverage(10, 1)
        self.assertFalse(low["passed"])
        ok = MODULE.assess_chunk_coverage(10, 8)
        self.assertTrue(ok["passed"])
        tiny = MODULE.assess_chunk_coverage(2, 2)
        self.assertTrue(tiny["passed"])

    def test_assess_rows_passes_good_payload(self) -> None:
        rows = [
            {
                "title": "心力衰竭的定义",
                "content": "心力衰竭是心室充盈和射血功能受损的临床综合征。",
                "source_span": {
                    "parent_entity": "心力衰竭",
                    "evidence": "心力衰竭定义为心室充盈和射血功能受损",
                },
            }
        ]
        report = MODULE.assess_rows(rows)
        self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()