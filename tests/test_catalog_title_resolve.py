import importlib.util
import sys
import unittest
from pathlib import Path


INGEST = Path(__file__).resolve().parents[1] / "scripts" / "ingest_knowledge.py"
SPEC = importlib.util.spec_from_file_location("ingest_knowledge", INGEST)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CatalogTitleResolveTests(unittest.TestCase):
    def test_normalize_strips_spaces_and_hyphens(self) -> None:
        left = MODULE.normalize_catalog_title("第二章 急性上呼吸道感染和急性气管-支气管炎")
        right = MODULE.normalize_catalog_title("第二章 急性上呼吸道感染和急性气管支气管炎")
        self.assertEqual(left, right)

    def test_resolve_legacy_hypertension_title_by_keywords(self) -> None:
        resolved = MODULE.resolve_pdf_section_title(
            "第三篇 循环系统疾病",
            "第四章 高血压",
        )
        self.assertIn("高血压", resolved)

    def test_resolve_legacy_chd_title_by_keywords(self) -> None:
        resolved = MODULE.resolve_pdf_section_title(
            "第三篇 循环系统疾病",
            "第五章 冠状动脉粥样硬化性心脏病",
        )
        self.assertIn("动脉粥样硬化", resolved)


if __name__ == "__main__":
    unittest.main()