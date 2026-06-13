import importlib.util
import sys
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
