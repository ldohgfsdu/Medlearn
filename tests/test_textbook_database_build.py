import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_database_build import (  # noqa: E402
    MODEL_CONFIG,
    build_catalog,
    build_section_result,
    stable_hash,
)


class TextbookDatabaseBuildTests(unittest.TestCase):
    def test_build_catalog_prefers_document_chunks_and_attaches_nodes(self):
        chunks = [
            {
                "document_name": "internal-medicine-10",
                "chunk_index": 2,
                "content": "支气管哮喘教材正文片段",
                "page_number": 62,
                "chapter": "第二篇 呼吸系统疾病",
                "section": "第四章 支气管哮喘",
            },
            {
                "document_name": "internal-medicine-10",
                "chunk_index": 1,
                "content": "总论教材正文片段",
                "page_number": 41,
                "chapter": "第二篇 呼吸系统疾病",
                "section": "第一章 总论",
            },
        ]
        nodes = [
            {
                "id": "kn-asthma",
                "chapter": "第二篇 呼吸系统疾病",
                "sub_chapter": "第四章 支气管哮喘",
                "source_span": {"page_start": 62, "page_end": 70},
            }
        ]

        sections = build_catalog(chunks, nodes)

        self.assertEqual([section.section_id for section in sections], ["respiratory-01", "respiratory-02"])
        self.assertEqual(sections[0].section_title, "第一章 总论")
        self.assertEqual(sections[1].section_title, "第四章 支气管哮喘")
        self.assertEqual(len(sections[1].chunks), 1)
        self.assertEqual(len(sections[1].nodes), 1)

    def test_second_run_reuses_unchanged_section_chunks_embeddings_and_nodes(self):
        model_hash = stable_hash(MODEL_CONFIG)
        section = build_catalog(
            [
                {
                    "document_name": "internal-medicine-10",
                    "chunk_index": 1,
                    "content": "慢性阻塞性肺疾病教材正文片段",
                    "page_number": 54,
                    "chapter": "第二篇 呼吸系统疾病",
                    "section": "第三章 慢性阻塞性肺疾病",
                    "related_node_id": "kn-copd",
                }
            ],
            [
                {
                    "id": "kn-copd",
                    "chapter": "第二篇 呼吸系统疾病",
                    "sub_chapter": "第三章 慢性阻塞性肺疾病",
                    "source_span": {
                        "evidence": "慢性阻塞性肺疾病证据",
                        "page_start": 54,
                        "page_end": 61,
                    },
                }
            ],
        )[0]
        first = build_section_result(
            section,
            previous=None,
            previous_model_hash=None,
            model_config_hash=model_hash,
            upload_result={"chunks_uploaded": 1, "chunks_embedded": 1},
            total_chunks=1,
            built_at="2026-06-17T00:00:00+00:00",
        )
        second = build_section_result(
            section,
            previous=first.manifest_entry(),
            previous_model_hash=model_hash,
            model_config_hash=model_hash,
            upload_result={"chunks_uploaded": 1, "chunks_embedded": 1},
            total_chunks=1,
            built_at="2026-06-17T00:01:00+00:00",
        )

        self.assertEqual(second.chunks_created, 0)
        self.assertEqual(second.chunks_reused, 1)
        self.assertEqual(second.embeddings_created, 0)
        self.assertEqual(second.embeddings_reused, 1)
        self.assertEqual(second.nodes_created, 0)
        self.assertEqual(second.nodes_reused, 1)
        self.assertIn("unchanged_section_text", second.skipped_reason)
        self.assertIn("unchanged_chunks", second.skipped_reason)


if __name__ == "__main__":
    unittest.main()
