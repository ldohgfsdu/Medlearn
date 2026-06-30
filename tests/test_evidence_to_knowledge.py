import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_identity import INTERNAL_MEDICINE_10
from textbook_pipeline.evidence_to_knowledge import (
    EvidenceCandidateConversionError,
    candidate_cache_to_knowledge_rows,
)


def _payload(status: str = "ready_candidate") -> dict:
    return {
        "version": "ev1-candidate-0.1.0",
        "book_id": "internal-medicine-10",
        "part_title": "第四篇 消化系统疾病",
        "section_title": "第四章 胃炎",
        "page_start": 400,
        "page_end": 404,
        "candidate_status": status,
        "candidate_items": [
            {
                "artifact_id": "ev1-artifact-a",
                "item_index": 0,
                "title": "胃炎的病因",
                "parent_entity": "胃炎",
                "aspect": "病因和发病机制",
                "content": "幽门螺杆菌感染是慢性胃炎的主要病因之一。",
                "evidence": "幽门螺杆菌感染是慢性胃炎的主要病因之一。",
                "risk_class": "standard",
                "source_heading": "病因和发病机制",
                "page_start": 400,
                "page_end": 400,
                "verification_state": "pass",
                "verification_notes": [],
            },
            {
                "artifact_id": "ev1-artifact-b",
                "item_index": 0,
                "title": "胃炎的治疗",
                "parent_entity": "胃炎",
                "aspect": "治疗",
                "content": "治疗内容需要人工审核。",
                "evidence": "治疗内容需要人工审核。",
                "risk_class": "needs_review",
                "source_heading": "治疗",
                "page_start": 403,
                "page_end": 403,
                "verification_state": "needs_review",
                "verification_notes": ["risk_downgrade"],
            },
            {
                "artifact_id": "ev1-artifact-c",
                "item_index": 0,
                "title": "无证据项",
                "parent_entity": "胃炎",
                "aspect": "概述",
                "content": "这条不应进入 normalized cache。",
                "evidence": "不匹配证据",
                "risk_class": "standard",
                "source_heading": "概述",
                "page_start": 401,
                "page_end": 401,
                "verification_state": "rejected",
                "verification_notes": ["evidence_substring"],
            },
        ],
    }


class EvidenceToKnowledgeTests(unittest.TestCase):
    def test_converts_only_pass_candidates(self):
        rows, summary = candidate_cache_to_knowledge_rows(
            _payload(),
            INTERNAL_MEDICINE_10,
            source_pdf="textbook/内科学（第10版）.pdf",
            candidate_path=Path("candidate.json"),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(summary["converted"], 1)
        self.assertEqual(summary["skipped_needs_review"], 1)
        self.assertEqual(summary["skipped_rejected"], 1)
        self.assertEqual(rows[0]["title"], "胃炎的病因")
        self.assertEqual(rows[0]["source_span"]["evidence"], "幽门螺杆菌感染是慢性胃炎的主要病因之一。")
        self.assertEqual(rows[0]["source_span"]["candidate_only"], True)

    def test_preserves_source_heading_and_page_reference(self):
        rows, _summary = candidate_cache_to_knowledge_rows(
            _payload(),
            INTERNAL_MEDICINE_10,
            source_pdf="textbook/内科学（第10版）.pdf",
            candidate_path=Path("candidate.json"),
        )

        row = rows[0]
        self.assertEqual(row["structured_sections"][0]["title"], "病因和发病机制")
        self.assertEqual(row["source_span"]["source_heading"], "病因和发病机制")
        self.assertEqual(row["source_span"]["page_start"], 400)
        self.assertEqual(row["source_span"]["provenance"]["page_start"], 400)
        self.assertEqual(row["node_source"], "ev1_candidate")

    def test_id_is_stable_and_anchored_to_artifact(self):
        first, _ = candidate_cache_to_knowledge_rows(
            _payload(),
            INTERNAL_MEDICINE_10,
            source_pdf="textbook/内科学（第10版）.pdf",
            candidate_path=Path("candidate.json"),
        )
        second, _ = candidate_cache_to_knowledge_rows(
            _payload(),
            INTERNAL_MEDICINE_10,
            source_pdf="textbook/内科学（第10版）.pdf",
            candidate_path=Path("candidate.json"),
        )

        self.assertEqual(first[0]["id"], second[0]["id"])
        self.assertTrue(first[0]["id"].startswith("kn-"))
        self.assertEqual(first[0]["source_span"]["artifact_id"], "ev1-artifact-a")

    def test_non_ready_candidate_is_rejected(self):
        with self.assertRaises(EvidenceCandidateConversionError):
            candidate_cache_to_knowledge_rows(
                _payload("needs_pipeline_review"),
                INTERNAL_MEDICINE_10,
                source_pdf="textbook/内科学（第10版）.pdf",
                candidate_path=Path("candidate.json"),
            )

    def test_audit_blocked_artifact_is_skipped(self):
        rows, summary = candidate_cache_to_knowledge_rows(
            _payload(),
            INTERNAL_MEDICINE_10,
            source_pdf="textbook/内科学（第10版）.pdf",
            candidate_path=Path("candidate.json"),
            blocked_artifact_ids={"ev1-artifact-a"},
        )

        self.assertEqual(rows, [])
        self.assertEqual(summary["skipped_artifact_audit"], 1)


if __name__ == "__main__":
    unittest.main()
