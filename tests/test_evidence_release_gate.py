import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_identity import INTERNAL_MEDICINE_10
from textbook_pipeline.evidence_to_knowledge import candidate_cache_to_knowledge_rows
from textbook_pipeline.evidence_release_gate import (
    summarize_gate_results,
    validate_ev1_normalized_payload,
)
from test_evidence_to_knowledge import _payload


class EvidenceReleaseGateTests(unittest.TestCase):
    def _normalized_payload(self) -> dict:
        rows, summary = candidate_cache_to_knowledge_rows(
            _payload(),
            INTERNAL_MEDICINE_10,
            source_pdf="textbook/内科学（第10版）.pdf",
            candidate_path=Path("candidate.json"),
        )
        return {
            "textbook_id": "internal-medicine-10",
            "part_title": "第四篇 消化系统疾病",
            "section_title": "第四章 胃炎",
            "pipeline_version": "ev1_candidate_to_knowledge_node",
            "adapter_version": "1.0.0",
            "source_path": "candidate.json",
            "node_count": len(rows),
            "conversion_summary": summary,
            "nodes": rows,
        }

    def test_gate_accepts_valid_ev1_normalized_payload(self):
        result = validate_ev1_normalized_payload(
            self._normalized_payload(),
            path=Path("ev1.normalized.json"),
            identity=INTERNAL_MEDICINE_10,
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.node_count, 1)
        self.assertTrue(result.warnings)

    def test_gate_rejects_non_pass_node(self):
        payload = self._normalized_payload()
        payload["nodes"][0]["source_span"]["verification_state"] = "needs_review"

        result = validate_ev1_normalized_payload(
            payload,
            path=Path("ev1.normalized.json"),
            identity=INTERNAL_MEDICINE_10,
        )

        self.assertFalse(result.passed)
        self.assertTrue(any("verification_state" in error for error in result.errors))

    def test_gate_rejects_unstable_id(self):
        payload = self._normalized_payload()
        payload["nodes"][0]["id"] = "kn-bad"

        result = validate_ev1_normalized_payload(
            payload,
            path=Path("ev1.normalized.json"),
            identity=INTERNAL_MEDICINE_10,
        )

        self.assertFalse(result.passed)
        self.assertTrue(any("stable" in error for error in result.errors))

    def test_gate_rejects_audit_blocked_artifact(self):
        payload = self._normalized_payload()

        result = validate_ev1_normalized_payload(
            payload,
            path=Path("ev1.normalized.json"),
            identity=INTERNAL_MEDICINE_10,
            blocked_artifact_ids={payload["nodes"][0]["source_span"]["artifact_id"]},
        )

        self.assertFalse(result.passed)
        self.assertTrue(any("blocked by EV1 artifact audit" in error for error in result.errors))

    def test_summary_requires_at_least_one_result(self):
        self.assertFalse(summarize_gate_results([])["passed"])


if __name__ == "__main__":
    unittest.main()
