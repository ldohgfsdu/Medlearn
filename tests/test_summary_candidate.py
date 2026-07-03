import unittest

from scripts.textbook_pipeline.evidence_artifact import make_artifact
from scripts.textbook_pipeline.summary_candidate import (
    EditorialSummaryCandidate,
    SummaryEvidenceRef,
    evaluate_summary_candidate,
)


def _artifact(raw_text: str):
    return make_artifact(
        textbook_id="internal-medicine-10",
        book_id="internal-medicine-10",
        part_title="第二篇 呼吸系统疾病",
        section_title="第四章 支气管哮喘",
        source_heading="定义与概述",
        normalized_aspect=None,
        source_order=1,
        artifact_type="text_block",
        raw_text=raw_text,
        page_start=62,
        page_end=62,
    )


class EditorialSummaryCandidateTests(unittest.TestCase):
    def test_abstractive_summary_is_allowed_only_as_hidden_review_candidate(self):
        artifact = _artifact(
            "支气管哮喘是一种以慢性气道炎症和气道高反应性为特征的异质性疾病。"
        )
        candidate = EditorialSummaryCandidate(
            textbook_id="internal-medicine-10",
            section_id="asthma",
            title="核心概念",
            summary_text="哮喘的核心特征包括慢性气道炎症与气道高反应性。",
            evidence_refs=[
                SummaryEvidenceRef(
                    artifact_id=artifact.id,
                    evidence_text=artifact.raw_text,
                )
            ],
            created_by="local-model",
        )

        result = evaluate_summary_candidate(candidate, [artifact])

        self.assertEqual(result.verdict, "needs_review")
        self.assertTrue(result.source_integrity)
        self.assertTrue(result.evidence_integrity)
        self.assertTrue(result.semantic_review_required)
        self.assertFalse(result.eligible_for_organized_display)
        self.assertEqual(candidate.publication_state, "hidden")

    def test_missing_artifact_rejects_candidate(self):
        candidate = EditorialSummaryCandidate(
            textbook_id="internal-medicine-10",
            section_id="asthma",
            title="核心概念",
            summary_text="候选总结",
            evidence_refs=[
                SummaryEvidenceRef(
                    artifact_id="missing",
                    evidence_text="不存在的证据",
                )
            ],
            created_by="local-model",
        )

        result = evaluate_summary_candidate(candidate, [])
        self.assertEqual(result.verdict, "rejected")
        self.assertFalse(result.source_integrity)
        self.assertEqual(candidate.publication_state, "hidden")

    def test_non_source_evidence_rejects_candidate(self):
        artifact = _artifact("教材原文只包含这一句话。")
        candidate = EditorialSummaryCandidate(
            textbook_id="internal-medicine-10",
            section_id="asthma",
            title="核心概念",
            summary_text="候选总结",
            evidence_refs=[
                SummaryEvidenceRef(
                    artifact_id=artifact.id,
                    evidence_text="模型虚构的证据",
                )
            ],
            created_by="local-model",
        )

        result = evaluate_summary_candidate(candidate, [artifact])
        self.assertEqual(result.verdict, "rejected")
        self.assertFalse(result.evidence_integrity)

    def test_procedural_summary_is_high_risk_and_stays_hidden(self):
        artifact = _artifact("操作步骤要求照射30分钟。")
        candidate = EditorialSummaryCandidate(
            textbook_id="internal-medicine-10",
            section_id="tuberculosis",
            title="操作摘要",
            summary_text="照射时间为30分钟。",
            evidence_refs=[
                SummaryEvidenceRef(
                    artifact_id=artifact.id,
                    evidence_text=artifact.raw_text,
                )
            ],
            created_by="local-model",
        )

        result = evaluate_summary_candidate(candidate, [artifact])
        self.assertEqual(result.verdict, "needs_review")
        self.assertEqual(candidate.risk_class, "high_risk")
        self.assertFalse(result.eligible_for_organized_display)

    def test_candidate_id_is_stable(self):
        artifact = _artifact("稳定来源文本。")
        kwargs = dict(
            textbook_id="internal-medicine-10",
            section_id="asthma",
            title="摘要",
            summary_text="稳定摘要。",
            evidence_refs=[
                SummaryEvidenceRef(artifact.id, artifact.raw_text)
            ],
            created_by="local-model",
        )
        self.assertEqual(
            EditorialSummaryCandidate(**kwargs).candidate_id,
            EditorialSummaryCandidate(**kwargs).candidate_id,
        )

    def test_candidate_id_drifts_on_evidence_version(self):
        artifact = _artifact("稳定来源文本。")
        base = dict(
            textbook_id="internal-medicine-10",
            section_id="asthma",
            title="摘要",
            summary_text="稳定摘要。",
            evidence_refs=[SummaryEvidenceRef(artifact.id, artifact.raw_text)],
            created_by="local-model",
        )
        v1 = EditorialSummaryCandidate(**base, evidence_version="1").candidate_id
        v2 = EditorialSummaryCandidate(**base, evidence_version="2").candidate_id
        self.assertNotEqual(v1, v2)

    def test_candidate_id_drifts_on_model_version(self):
        artifact = _artifact("稳定来源文本。")
        base = dict(
            textbook_id="internal-medicine-10",
            section_id="asthma",
            title="摘要",
            summary_text="稳定摘要。",
            evidence_refs=[SummaryEvidenceRef(artifact.id, artifact.raw_text)],
            created_by="local-model",
        )
        v1 = EditorialSummaryCandidate(**base, model_version="qwen2.5:7b").candidate_id
        v2 = EditorialSummaryCandidate(**base, model_version="qwen2.5:14b").candidate_id
        self.assertNotEqual(v1, v2)

    def test_candidate_id_drifts_on_prompt_version(self):
        artifact = _artifact("稳定来源文本。")
        base = dict(
            textbook_id="internal-medicine-10",
            section_id="asthma",
            title="摘要",
            summary_text="稳定摘要。",
            evidence_refs=[SummaryEvidenceRef(artifact.id, artifact.raw_text)],
            created_by="local-model",
        )
        v1 = EditorialSummaryCandidate(**base, prompt_version="v1").candidate_id
        v2 = EditorialSummaryCandidate(**base, prompt_version="v2").candidate_id
        self.assertNotEqual(v1, v2)

    def test_candidate_id_drifts_on_rule_version(self):
        artifact = _artifact("稳定来源文本。")
        base = dict(
            textbook_id="internal-medicine-10",
            section_id="asthma",
            title="摘要",
            summary_text="稳定摘要。",
            evidence_refs=[SummaryEvidenceRef(artifact.id, artifact.raw_text)],
            created_by="local-model",
        )
        v1 = EditorialSummaryCandidate(**base, rule_version="1").candidate_id
        v2 = EditorialSummaryCandidate(**base, rule_version="2").candidate_id
        self.assertNotEqual(v1, v2)


if __name__ == "__main__":
    unittest.main()
