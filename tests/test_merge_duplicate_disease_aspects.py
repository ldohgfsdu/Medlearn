import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "merge_duplicate_disease_aspects.py"
)
SPEC = importlib.util.spec_from_file_location("merge_duplicate_disease_aspects", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DuplicateDiseaseAspectMergeTests(unittest.TestCase):
    def test_build_merge_plan_keeps_one_primary_and_numbers_items(self) -> None:
        nodes = [
            {
                "id": "node-b",
                "title": "利尿剂",
                "aspect": "treatment",
                "content": "促进钠水排泄。",
                "order_num": 2,
                "disease_id": "disease-1",
                "chapter_section_id": "section-1",
                "key_points": ["监测电解质"],
            },
            {
                "id": "node-a",
                "title": "ACEI 类药物",
                "aspect": "treatment",
                "content": "抑制肾素-血管紧张素系统。",
                "order_num": 1,
                "disease_id": "disease-1",
                "chapter_section_id": "section-1",
                "key_points": ["监测血压"],
            },
        ]

        plan = MODULE.build_merge_plan(nodes)

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["primary_id"], "node-a")
        self.assertEqual(plan[0]["duplicate_ids"], ["node-b"])
        self.assertEqual(plan[0]["primary_update"]["display_title"], "治疗方案")
        self.assertIn("1. ACEI 类药物", plan[0]["primary_update"]["content"])
        self.assertIn("2. 利尿剂", plan[0]["primary_update"]["content"])

    def test_build_merge_plan_does_not_cross_sections(self) -> None:
        nodes = [
            {
                "id": "node-a",
                "title": "治疗 A",
                "aspect": "treatment",
                "content": "治疗内容 A。",
                "disease_id": "disease-1",
                "chapter_section_id": "section-1",
            },
            {
                "id": "node-b",
                "title": "治疗 B",
                "aspect": "treatment",
                "content": "治疗内容 B。",
                "disease_id": "disease-1",
                "chapter_section_id": "section-2",
            },
        ]

        self.assertEqual(MODULE.build_merge_plan(nodes), [])

    def test_build_merge_plan_does_not_merge_unlabeled_other_nodes(self) -> None:
        nodes = [
            {
                "id": "node-a",
                "title": "技术原理",
                "aspect": "other",
                "content": "技术原理内容。",
                "disease_id": "disease-1",
                "chapter_section_id": "section-1",
            },
            {
                "id": "node-b",
                "title": "操作要点",
                "aspect": "other",
                "content": "操作要点内容。",
                "disease_id": "disease-1",
                "chapter_section_id": "section-1",
            },
        ]

        self.assertEqual(MODULE.build_merge_plan(nodes), [])


if __name__ == "__main__":
    unittest.main()
