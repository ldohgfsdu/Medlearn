import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.evidence_display_contract import (  # noqa: E402
    DISPLAY_CONTRACT_VERSION,
    build_display_contract_payload,
)


def _row(
    row_id: str,
    *,
    title: str,
    body: str,
    evidence: str,
    heading: str,
    artifact_id: str,
    page: int,
    order: int,
) -> dict:
    return {
        "id": row_id,
        "title": title,
        "content": body,
        "sub_chapter": "Chapter 7 Congenital cardiovascular disease",
        "order_num": order,
        "source_span": {
            "artifact_id": artifact_id,
            "item_index": order,
            "source_heading": heading,
            "evidence": evidence,
            "page_start": page,
            "page_end": page,
            "verification_state": "pass",
            "candidate_only": True,
        },
    }


class EvidenceDisplayContractTests(unittest.TestCase):
    def _normalized_payload(self) -> dict:
        return {
            "textbook_id": "internal-medicine-10",
            "part_title": "Part 3 Circulatory diseases",
            "section_title": "Chapter 7 Congenital cardiovascular disease",
            "source_path": "candidate.json",
            "node_count": 3,
            "nodes": [
                _row(
                    "kn-a",
                    title="Definition",
                    body="Congenital cardiovascular disease refers to abnormal development",
                    evidence="Congenital cardiovascular disease refers to abnormal development",
                    heading="Definition",
                    artifact_id="art-a",
                    page=319,
                    order=0,
                ),
                _row(
                    "kn-b",
                    title="Definition",
                    body="of the heart and great vessels during fetal life.",
                    evidence="of the heart and great vessels during fetal life.",
                    heading="Definition",
                    artifact_id="art-b",
                    page=319,
                    order=1,
                ),
                _row(
                    "kn-c",
                    title="Atrial septal defect",
                    body="Atrial septal defect is a common adult congenital heart disease.",
                    evidence="Atrial septal defect is a common adult congenital heart disease.",
                    heading="Atrial septal defect",
                    artifact_id="art-c",
                    page=320,
                    order=2,
                ),
            ],
        }

    def test_builds_frontend_display_contract(self):
        payload = build_display_contract_payload(self._normalized_payload())

        self.assertEqual(payload["version"], DISPLAY_CONTRACT_VERSION)
        self.assertEqual(payload["textbook_id"], "internal-medicine-10")
        self.assertEqual(payload["summary"]["organized"], 2)
        first = payload["nodes"][0]
        self.assertEqual(first["render_type"], "merged")
        self.assertEqual(first["publication_state"], "organized")
        self.assertEqual(first["display"]["page_label"], "p.319")
        self.assertIn("merged", first["quality_badges"])
        self.assertEqual(first["merge"]["child_node_ids"], ["kn-a", "kn-b"])
        self.assertEqual(
            first["display"]["body"],
            "Congenital cardiovascular disease refers to abnormal development "
            "of the heart and great vessels during fetal life.",
        )
        self.assertEqual(len(first["evidence_items"]), 2)

    def test_does_not_merge_different_source_heading(self):
        payload = build_display_contract_payload(self._normalized_payload())

        self.assertEqual(payload["nodes"][1]["render_type"], "normal")
        self.assertEqual(payload["nodes"][1]["display"]["source_heading"], "Atrial septal defect")

    def test_needs_review_candidate_becomes_evidence_only(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-risk",
                    "item_index": 0,
                    "title": "Intervention",
                    "aspect": "Treatment",
                    "source_heading": "Treatment",
                    "evidence": "If anatomical conditions are suitable, catheter closure is preferred.",
                    "page_start": 321,
                    "page_end": 321,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-rejected",
                    "item_index": 0,
                    "title": "Rejected item",
                    "evidence": "This should not appear.",
                    "page_start": 321,
                    "page_end": 321,
                    "verification_state": "rejected",
                },
            ]
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        evidence_only = [node for node in payload["nodes"] if node["publication_state"] == "evidence_only"]
        self.assertEqual(len(evidence_only), 1)
        self.assertEqual(evidence_only[0]["render_type"], "evidence_only")
        self.assertEqual(evidence_only[0]["display"]["body"], "")
        self.assertIn("conservative_fallback", evidence_only[0]["quality_badges"])
        self.assertEqual(evidence_only[0]["evidence_items"][0]["artifact_id"], "art-risk")

    def test_evidence_only_nodes_are_sorted_back_into_source_order(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-risk-early",
                    "item_index": 0,
                    "title": "Treatment note",
                    "aspect": "Treatment",
                    "source_heading": "Definition",
                    "evidence": "Original treatment evidence on the earlier page.",
                    "page_start": 318,
                    "page_end": 318,
                    "verification_state": "needs_review",
                }
            ]
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        self.assertEqual(payload["nodes"][0]["id"], "view-evidence-art-risk-early-0")
        self.assertEqual(payload["nodes"][0]["publication_state"], "evidence_only")

    def test_related_classification_items_become_numbered_group(self):
        normalized_payload = {
            "textbook_id": "internal-medicine-10",
            "part_title": "Part 2 Respiratory diseases",
            "section_title": "Chapter 6 Pulmonary infections",
            "source_path": "candidate.json",
            "nodes": [
                _row(
                    "kn-class",
                    title="\u80ba\u708e\u7684\u5206\u7c7b",
                    body="\u80ba\u708e\u53ef\u6309\u89e3\u5256\u3001\u75c5\u56e0\u6216\u60a3\u75c5\u73af\u5883\u52a0\u4ee5\u5206\u7c7b\u3002",
                    evidence="\u3010\u5206\u7c7b\u3011 \u80ba\u708e\u53ef\u6309\u89e3\u5256\u3001\u75c5\u56e0\u6216\u60a3\u75c5\u73af\u5883\u52a0\u4ee5\u5206\u7c7b\u3002",
                    heading="Chapter 6 Pulmonary infections",
                    artifact_id="art-class",
                    page=77,
                    order=0,
                ),
                _row(
                    "kn-lobar",
                    title="\u5927\u53f6\u6027\uff08\u80ba\u6ce1\u6027\uff09\u80ba\u708e",
                    body="\u75c5\u539f\u4f53\u5148\u5728\u80ba\u6ce1\u5f15\u8d77\u708e\u75c7\u3002",
                    evidence="\u75c5\u539f\u4f53\u5148\u5728\u80ba\u6ce1\u5f15\u8d77\u708e\u75c7\u3002",
                    heading="Chapter 6 Pulmonary infections",
                    artifact_id="art-lobar",
                    page=77,
                    order=1,
                ),
                _row(
                    "kn-broncho",
                    title="\u5c0f\u53f6\u6027\uff08\u652f\u6c14\u7ba1\u6027\uff09\u80ba\u708e",
                    body="\u75c5\u539f\u4f53\u7ecf\u652f\u6c14\u7ba1\u5165\u4fb5\u3002",
                    evidence="\u75c5\u539f\u4f53\u7ecf\u652f\u6c14\u7ba1\u5165\u4fb5\u3002",
                    heading="Chapter 6 Pulmonary infections",
                    artifact_id="art-broncho",
                    page=77,
                    order=2,
                ),
            ],
        }

        payload = build_display_contract_payload(normalized_payload)

        self.assertEqual(len(payload["nodes"]), 1)
        group = payload["nodes"][0]
        self.assertEqual(group["render_type"], "grouped")
        self.assertEqual(group["group"]["topic"], "classification")
        self.assertEqual(len(group["display"]["items"]), 3)
        self.assertIn("group:classification", group["quality_badges"])


if __name__ == "__main__":
    unittest.main()
