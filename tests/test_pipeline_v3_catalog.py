import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pipeline_v3_extract.py"
SPEC = importlib.util.spec_from_file_location("pipeline_v3_extract", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CatalogTests(unittest.TestCase):
    def test_builds_non_overlapping_units_with_hierarchy(self) -> None:
        toc = [
            [1, "封面页", 1],
            [1, "第一篇 总论", 10],
            [2, "第一章 基础", 11],
            [3, "第一节 概念", 12],
            [3, "第二节 机制", 15],
        ]

        entries, units = MODULE.build_catalog_units(toc, total_pages=20)

        self.assertEqual(len(entries), 5)
        self.assertEqual(
            [(unit.page_start, unit.page_end) for unit in units],
            [(10, 10), (11, 11), (12, 14), (15, 20)],
        )
        self.assertEqual(
            units[-1].headings,
            ["第一篇 总论", "第一章 基础", "第二节 机制"],
        )

    def test_discards_backward_bookmark_after_content_start(self) -> None:
        toc = [
            [1, "第一章 总论", 30],
            [2, "第一节 基础", 31],
            [3, "错误倒跳书签", 1],
            [2, "第二节 应用", 35],
        ]

        entries, units = MODULE.build_catalog_units(toc, total_pages=40)

        self.assertEqual(units[0].page_start, 30)
        self.assertNotIn(1, [unit.page_start for unit in units])
        bad_entry = next(entry for entry in entries if entry["page"] == 1)
        self.assertFalse(bad_entry["page_is_in_content_range"])

    def test_resolves_map_hierarchy(self) -> None:
        part, chapter = MODULE.resolve_map_hierarchy(
            ["第三篇 循环系统疾病", "第五章 高血压", "第一节 原发性高血压"]
        )

        self.assertEqual(part, "第三篇 循环系统疾病")
        self.assertEqual(chapter, "第五章 高血压")


    def test_build_catalog_falls_back_to_page_windows_without_bookmarks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "plain.pdf"
            document = pymupdf.open()
            for page_number in range(5):
                page = document.new_page()
                page.insert_text(
                    (72, 72),
                    f"Plain textbook body page {page_number + 1}. " * 8,
                )
            document.save(pdf_path)
            document.close()

            pipeline = MODULE.MedlearnPipeline(
                source_path=pdf_path,
                output_dir=root / "generated",
                model="unused",
                ollama_url="http://127.0.0.1:11434",
                max_chars=2800,
                num_ctx=4096,
                limit=None,
                subject="Plain",
                section_limit=None,
                section_start=0,
                pdf_parser_mode="pymupdf",
            )
            units = pipeline.build_catalog(force=True)

            self.assertEqual(
                [(unit.page_start, unit.page_end) for unit in units],
                [(1, 4), (5, 5)],
            )
            payload = __import__("json").loads(
                pipeline.catalog_path.read_text(encoding="utf-8")
            )
            self.assertEqual(payload["catalog_source"], "page_windows")


if __name__ == "__main__":
    unittest.main()
