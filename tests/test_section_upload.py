import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.section_upload import (
    build_section_causal_chains,
    build_section_document_chunks,
)


class SectionUploadTests(unittest.TestCase):
    def test_build_section_document_chunks_links_nodes(self):
        rows = [
            {
                "id": "kn-111",
                "title": "肺炎",
                "type": "disease",
                "content": "肺炎内容",
                "source_span": {
                    "chunk_index": 3,
                    "evidence": "肺炎是由病原微生物引起的肺实质炎症，伴或不伴肺泡炎。",
                    "page_start": 88,
                },
            }
        ]
        chunks = build_section_document_chunks(
            rows,
            book_id="internal-medicine-10",
            part_title="第二篇 呼吸系统疾病",
            section_title="第六章 肺部感染性疾病",
            section_unit_index=12,
            extraction_cache=None,
        )
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["related_node_id"], "kn-111")
        self.assertEqual(chunks[0]["chapter"], "第二篇 呼吸系统疾病")
        self.assertEqual(chunks[0]["section"], "第六章 肺部感染性疾病")

    def test_build_section_causal_chains_filters_clinical_links(self):
        rows = [
            {
                "id": "kn-a",
                "title": "高血压",
                "type": "disease",
                "causal_links": [
                    {
                        "from": "高血压",
                        "to": "头痛",
                        "target_id": "kn-b",
                        "relation": "characteristic_of",
                    }
                ],
            },
            {
                "id": "kn-b",
                "title": "头痛",
                "type": "symptom",
                "causal_links": [],
            },
        ]
        chains = build_section_causal_chains(
            rows,
            book_id="internal-medicine-10",
            part_title="第三篇 循环系统疾病",
            section_title="第五章 高血压",
        )
        self.assertEqual(len(chains), 1)
        self.assertTrue(chains[0]["id"].startswith("cc-"))
        self.assertEqual(len(chains[0]["steps"]), 1)
        self.assertIn("kn-a", chains[0]["related_nodes"])
        self.assertIn("kn-b", chains[0]["related_nodes"])


if __name__ == "__main__":
    unittest.main()