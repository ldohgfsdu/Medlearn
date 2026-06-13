import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_identity import INTERNAL_MEDICINE_10
from textbook_pipeline.knowledge_node_adapter import (
    convert_v4_file_to_knowledge_rows,
    finalize_knowledge_rows,
    v4_structured_to_knowledge_node,
)


class KnowledgeNodeAdapterTests(unittest.TestCase):
    def test_finalize_knowledge_rows_normalizes_identity(self):
        rows = finalize_knowledge_rows(
            [
                {
                    "id": "v3-abc",
                    "title": "肺脓肿",
                    "type": "disease",
                    "subject": "内科学（第10版）",
                    "chapter": "第一篇 呼吸系统疾病",
                    "sub_chapter": "第七章 肺脓肿",
                    "content": "肺脓肿是由多种病原微生物引起的肺组织化脓性病变。",
                    "structured_sections": [
                        {
                            "title": "定义",
                            "content": "肺脓肿是由多种病原微生物引起的肺组织化脓性病变。",
                        }
                    ],
                    "source": "pipeline_v3",
                }
            ],
            INTERNAL_MEDICINE_10,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject"], "内科学")
        self.assertEqual(rows[0]["textbook"], "internal-medicine-10")
        self.assertEqual(rows[0]["book_id"], "internal-medicine-10")

    def test_v4_structured_to_knowledge_node_maps_sections(self):
        row = v4_structured_to_knowledge_node(
            {
                "knowledge_point": {
                    "title": "社区获得性肺炎",
                    "type": "disease",
                    "book_id": "internal-medicine-10",
                },
                "content": {
                    "definition": {"content": "医院外获得的肺炎感染"},
                    "clinical_manifestations": {"content": "发热、咳嗽、咳痰"},
                },
                "relations": [
                    {"target_name": "呼吸衰竭", "relation_type": "complication"},
                ],
                "extraction_report": {"needs_human_review": True},
            },
            INTERNAL_MEDICINE_10,
            chapter="第一篇 呼吸系统疾病",
            sub_chapter="第六章 肺部感染性疾病",
            order_num=0,
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["title"], "社区获得性肺炎")
        self.assertEqual(row["type"], "disease")
        self.assertEqual(len(row["structured_sections"]), 2)
        self.assertEqual(row["causal_links"][0]["to"], "呼吸衰竭")
        self.assertEqual(row["textbook"], "internal-medicine-10")

    def test_convert_v4_file_skips_failed_nodes(self):
        temp = ROOT / "tests" / "_tmp_v4_nodes.json"
        temp.write_text(
            json.dumps(
                {
                    "nodes": [
                        {"title": "Extraction Failed", "error": True},
                        {
                            "knowledge_point": {"title": "支气管哮喘", "type": "disease"},
                            "content": {"definition": {"content": "慢性气道炎症性疾病"}},
                            "relations": [],
                            "extraction_report": {},
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        try:
            rows = convert_v4_file_to_knowledge_rows(
                str(temp),
                chapter="第一篇 呼吸系统疾病",
                sub_chapter="第四章 支气管哮喘",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "支气管哮喘")
        finally:
            temp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()