import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.evidence_artifact import make_artifact
from textbook_pipeline.evidence_synthesis import SynthesizedItem
from textbook_pipeline.evidence_verifier import check_evidence_substring, verify_items


def _lung_infection_artifact(
    *,
    artifact_id_suffix: str,
    source_order: int,
    raw_text: str,
    page_start: int,
) -> object:
    return make_artifact(
        textbook_id="internal-medicine-10",
        book_id="internal-medicine-10",
        part_title="第二篇 呼吸系统疾病",
        section_title="第六章 肺部感染性疾病",
        source_heading="第六章\n肺部感染性疾病",
        normalized_aspect=None,
        source_order=source_order,
        artifact_type="text_block",
        raw_text=raw_text,
        page_start=page_start,
        page_end=page_start,
    )


class EvidenceVerifierTests(unittest.TestCase):
    def test_evidence_substring_tolerates_chinese_curly_quote_variants(self):
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="第二篇 呼吸系统疾病",
            section_title="第六章 肺部感染性疾病",
            source_heading="命名",
            normalized_aspect=None,
            source_order=1,
            artifact_type="text_block",
            raw_text="引入“严重急性呼吸系统综合征冠状病毒2”（SARS-CoV-2）来命名这一新发现的病毒。",
            page_start=87,
            page_end=87,
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="肺部感染性疾病的命名",
            parent_entity="肺部感染性疾病",
            aspect="命名",
            content="引入‘严重急性呼吸系统综合征冠状病毒2’（SARS-CoV-2）来命名这一新发现的病毒。",
            evidence="引入‘严重急性呼吸系统综合征冠状病毒2’（SARS-CoV-2）来命名这一新发现的病毒。",
            risk_class="standard",
            source_heading="命名",
            page_start=87,
            page_end=87,
        )

        ok, note = check_evidence_substring(item, artifact)

        self.assertTrue(ok)
        self.assertEqual(note, "loose match (punctuation normalized)")

    def test_repair_cross_artifact_compressed_antibacterial_selection(self):
        artifacts = [
            _lung_infection_artifact(
                artifact_id_suffix="061",
                source_order=28,
                page_start=78,
                raw_text="验性治疗时，了解当地医院的病原学监测数据更为重要，应根据本地区、本医院甚至特定科室的病原",
            ),
            _lung_infection_artifact(
                artifact_id_suffix="bb67",
                source_order=29,
                page_start=78,
                raw_text="谱和耐药特点，结合病人个体因素来选择抗菌药物。",
            ),
        ]
        target = artifacts[1]
        item = SynthesizedItem(
            artifact_id=target.id,
            item_index=0,
            title="抗菌药物的选择",
            parent_entity="肺部感染性疾病",
            aspect="治疗",
            content="根据病原体谱和耐药特点，结合病人个体因素来选择抗菌药物。",
            evidence="根据病原体谱和耐药特点，结合病人个体因素来选择抗菌药物。",
            risk_class="standard",
            source_heading="第六章\n肺部感染性疾病",
            page_start=78,
            page_end=78,
        )

        ok, note = check_evidence_substring(item, target, all_artifacts=artifacts)

        self.assertFalse(ok)
        self.assertIn("evidence not found", note)
        self.assertEqual(
            item.evidence,
            "根据病原体谱和耐药特点，结合病人个体因素来选择抗菌药物。",
        )
        self.assertIn("选择抗菌药物", item.evidence)

    def test_verify_items_repairs_content_span_across_page_break(self):
        artifacts = [
            make_artifact(
                textbook_id="internal-medicine-10",
                book_id="internal-medicine-10",
                part_title="Part",
                section_title="Section",
                source_heading="Heading",
                normalized_aspect=None,
                source_order=1,
                artifact_type="text_block",
                raw_text="alpha bet",
                page_start=10,
                page_end=10,
            ),
            make_artifact(
                textbook_id="internal-medicine-10",
                book_id="internal-medicine-10",
                part_title="Part",
                section_title="Section",
                source_heading="Heading",
                normalized_aspect=None,
                source_order=2,
                artifact_type="text_block",
                raw_text="a therapy should continue",
                page_start=11,
                page_end=11,
            ),
        ]
        item = SynthesizedItem(
            artifact_id=artifacts[0].id,
            item_index=0,
            title="Treatment",
            parent_entity=None,
            aspect="Heading",
            content="beta therapy",
            evidence="bet",
            risk_class="needs_review",
            source_heading="Heading",
            page_start=10,
            page_end=10,
        )

        verify_items([item], artifacts, section_page_start=10, section_page_end=11)

        self.assertEqual(item.evidence, "bet")
        self.assertEqual(item.verification_state, "needs_review")
        self.assertFalse(any("expanded" in note for note in item.verification_notes))

    def test_repair_cross_artifact_compressed_antibacterial_selection_basis(self):
        artifacts = [
            _lung_infection_artifact(
                artifact_id_suffix="6b9d",
                source_order=40,
                page_start=81,
                raw_text="此外，还应该根据病人的年龄、有无基础疾病、是否有误吸、住普通病房还是重症监护病房、住院时间",
            ),
            _lung_infection_artifact(
                artifact_id_suffix="844a",
                source_order=41,
                page_start=81,
                raw_text="长短和肺炎的严重程度等，选择抗菌药物和给药途径。",
            ),
        ]
        target = artifacts[1]
        item = SynthesizedItem(
            artifact_id=target.id,
            item_index=0,
            title="抗菌药物的选择依据",
            parent_entity="肺部感染性疾病",
            aspect="治疗",
            content="根据病原体种类、患者年龄、病情轻重、有无并发症、是否耐药以及病情的长短和肺炎的严重程度等，选择抗菌药物和给药途径。",
            evidence="根据病原体种类、患者年龄、病情轻重、有无并发症、是否耐药以及病情的长短和肺炎的严重程度等，选择抗菌药物和给药途径。",
            risk_class="standard",
            source_heading="第六章\n肺部感染性疾病",
            page_start=81,
            page_end=81,
        )

        ok, note = check_evidence_substring(item, target, all_artifacts=artifacts)

        self.assertFalse(ok)
        self.assertIn("evidence not found", note)
        self.assertEqual(item.evidence, item.content)
        self.assertIn("选择抗菌药物和给药途径", item.evidence)

    def test_repair_source_span_mismatch_for_differential_diagnosis(self):
        artifacts = [
            _lung_infection_artifact(
                artifact_id_suffix="393b",
                source_order=58,
                page_start=81,
                raw_text="染，如结核分枝杆菌、真菌、病毒等；③出现并发症或存在影响疗效的宿主因素（如免疫抑制）；④非感",
            ),
            _lung_infection_artifact(
                artifact_id_suffix="0591",
                source_order=59,
                page_start=81,
                raw_text="染性疾病误诊为肺炎；⑤药物热。需仔细分析，做必要的检查，进行相应处理。",
            ),
        ]
        target = artifacts[1]
        item = SynthesizedItem(
            artifact_id=target.id,
            item_index=0,
            title="肺部感染性疾病的鉴别诊断",
            parent_entity="肺部感染性疾病",
            aspect="鉴别诊断",
            content="肺部感染性疾病误诊为肺炎；⑤药物热",
            evidence="肺部感染性疾病误诊为肺炎；⑤药物热",
            risk_class="standard",
            source_heading="第六章\n肺部感染性疾病",
            page_start=81,
            page_end=81,
        )

        ok, note = check_evidence_substring(item, target, all_artifacts=artifacts)

        self.assertFalse(ok)
        self.assertIn("evidence not found", note)
        self.assertEqual(item.evidence, item.content)
        self.assertIn("⑤药物热", item.evidence)

    def test_verify_items_clears_all_three_rejected_lung_infection_cases(self):
        artifacts = [
            _lung_infection_artifact(
                artifact_id_suffix="061",
                source_order=28,
                page_start=78,
                raw_text="验性治疗时，了解当地医院的病原学监测数据更为重要，应根据本地区、本医院甚至特定科室的病原",
            ),
            _lung_infection_artifact(
                artifact_id_suffix="bb67",
                source_order=29,
                page_start=78,
                raw_text="谱和耐药特点，结合病人个体因素来选择抗菌药物。",
            ),
            _lung_infection_artifact(
                artifact_id_suffix="6b9d",
                source_order=40,
                page_start=81,
                raw_text="此外，还应该根据病人的年龄、有无基础疾病、是否有误吸、住普通病房还是重症监护病房、住院时间",
            ),
            _lung_infection_artifact(
                artifact_id_suffix="844a",
                source_order=41,
                page_start=81,
                raw_text="长短和肺炎的严重程度等，选择抗菌药物和给药途径。",
            ),
            _lung_infection_artifact(
                artifact_id_suffix="393b",
                source_order=58,
                page_start=81,
                raw_text="染，如结核分枝杆菌、真菌、病毒等；③出现并发症或存在影响疗效的宿主因素（如免疫抑制）；④非感",
            ),
            _lung_infection_artifact(
                artifact_id_suffix="0591",
                source_order=59,
                page_start=81,
                raw_text="染性疾病误诊为肺炎；⑤药物热。需仔细分析，做必要的检查，进行相应处理。",
            ),
        ]
        items = [
            SynthesizedItem(
                artifact_id=artifacts[1].id,
                item_index=0,
                title="抗菌药物的选择",
                parent_entity="肺部感染性疾病",
                aspect="治疗",
                content="根据病原体谱和耐药特点，结合病人个体因素来选择抗菌药物。",
                evidence="根据病原体谱和耐药特点，结合病人个体因素来选择抗菌药物。",
                risk_class="standard",
                source_heading="第六章\n肺部感染性疾病",
                page_start=78,
                page_end=78,
            ),
            SynthesizedItem(
                artifact_id=artifacts[3].id,
                item_index=0,
                title="抗菌药物的选择依据",
                parent_entity="肺部感染性疾病",
                aspect="治疗",
                content="根据病原体种类、患者年龄、病情轻重、有无并发症、是否耐药以及病情的长短和肺炎的严重程度等，选择抗菌药物和给药途径。",
                evidence="根据病原体种类、患者年龄、病情轻重、有无并发症、是否耐药以及病情的长短和肺炎的严重程度等，选择抗菌药物和给药途径。",
                risk_class="standard",
                source_heading="第六章\n肺部感染性疾病",
                page_start=81,
                page_end=81,
            ),
            SynthesizedItem(
                artifact_id=artifacts[5].id,
                item_index=0,
                title="肺部感染性疾病的鉴别诊断",
                parent_entity="肺部感染性疾病",
                aspect="鉴别诊断",
                content="肺部感染性疾病误诊为肺炎；⑤药物热",
                evidence="肺部感染性疾病误诊为肺炎；⑤药物热",
                risk_class="standard",
                source_heading="第六章\n肺部感染性疾病",
                page_start=81,
                page_end=81,
            ),
        ]

        _, counts = verify_items(items, artifacts, section_page_start=78, section_page_end=81)

        self.assertEqual(counts["rejected"], 3)
        self.assertEqual(
            sum(1 for item in items if item.verification_state != "rejected"),
            0,
        )

    def test_verify_items_preserves_existing_provenance_notes(self):
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="Part",
            section_title="Section",
            source_heading="Heading",
            normalized_aspect=None,
            source_order=1,
            artifact_type="text_block",
            raw_text="Source text that should remain visible as original evidence.",
            page_start=1,
            page_end=1,
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="Original evidence",
            parent_entity=None,
            aspect="Heading",
            content="Source text that should remain visible as original evidence.",
            evidence="Source text that should remain visible as original evidence.",
            risk_class="needs_review",
            source_heading="Heading",
            page_start=1,
            page_end=1,
            verification_notes=["source_only_fallback_no_synthesized_item"],
        )

        verify_items([item], [artifact], section_page_start=1, section_page_end=1)

        self.assertEqual(item.verification_state, "needs_review")
        self.assertIn("source_only_fallback_no_synthesized_item", item.verification_notes)

    def test_verify_items_drops_stale_diagnostic_notes(self):
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="Part",
            section_title="Section",
            source_heading="Heading",
            normalized_aspect=None,
            source_order=1,
            artifact_type="text_block",
            raw_text="Stable source evidence.",
            page_start=1,
            page_end=1,
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="Stable evidence",
            parent_entity=None,
            aspect="Heading",
            content="Stable source evidence.",
            evidence="Stable source evidence.",
            risk_class="standard",
            source_heading="Heading",
            page_start=1,
            page_end=1,
            verification_notes=[
                "source_only_fallback_no_synthesized_item",
                "unsupported_terms: stale failure",
            ],
        )

        verify_items([item], [artifact], section_page_start=1, section_page_end=1)

        self.assertEqual(item.verification_state, "pass")
        self.assertIn("source_only_fallback_no_synthesized_item", item.verification_notes)
        self.assertNotIn("unsupported_terms: stale failure", item.verification_notes)

    def test_low_content_evidence_overlap_is_quality_note_not_review_blocker(self):
        evidence = (
            "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda "
            "mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega."
        )
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="Part",
            section_title="Section",
            source_heading="Heading",
            normalized_aspect=None,
            source_order=1,
            artifact_type="text_block",
            raw_text=evidence,
            page_start=1,
            page_end=1,
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="Short grounded point",
            parent_entity=None,
            aspect="Heading",
            content="Alpha beta",
            evidence=evidence,
            risk_class="standard",
            source_heading="Heading",
            page_start=1,
            page_end=1,
        )

        verify_items([item], [artifact], section_page_start=1, section_page_end=1)

        self.assertEqual(item.verification_state, "pass")
        self.assertTrue(
            any(note.startswith("content_evidence_ratio:") for note in item.verification_notes)
        )

    def test_too_narrow_evidence_expands_to_continuous_content_span(self):
        content = "\u4eba\u7c7b\u8868\u578b\u7ec4\u56fd\u9645\u5927\u79d1\u5b66\u8ba1\u5212\u7528\u4e8e\u6307\u5bfc\u590d\u6742\u75be\u75c5\u7814\u7a76"
        raw_text = f"\u524d\u6587\u3002{content}\u3002\u540e\u6587\u3002"
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="Part",
            section_title="Section",
            source_heading="Heading",
            normalized_aspect=None,
            source_order=1,
            artifact_type="text_block",
            raw_text=raw_text,
            page_start=1,
            page_end=1,
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="Human phenome project",
            parent_entity=None,
            aspect="Heading",
            content=content,
            evidence=content[:8],
            risk_class="standard",
            source_heading="Heading",
            page_start=1,
            page_end=1,
        )

        verify_items([item], [artifact], section_page_start=1, section_page_end=1)

        self.assertEqual(item.verification_state, "pass")
        self.assertEqual(item.evidence, content)
        self.assertTrue(
            any(note.startswith("evidence_content_span:") for note in item.verification_notes)
        )

    def test_too_narrow_evidence_expands_from_nearby_content_span(self):
        prefix = "\u77ff\u7269\u8d28\u5206\u4e3a\u5b8f\u91cf\u5143\u7d20\u548c"
        suffix = "\u5fae\u91cf\u5143\u7d20\u3002"
        content = prefix + suffix
        artifacts = [
            make_artifact(
                textbook_id="internal-medicine-10",
                book_id="internal-medicine-10",
                part_title="Part",
                section_title="Section",
                source_heading="Heading",
                normalized_aspect=None,
                source_order=1,
                artifact_type="text_block",
                raw_text=prefix,
                page_start=1,
                page_end=1,
            ),
            make_artifact(
                textbook_id="internal-medicine-10",
                book_id="internal-medicine-10",
                part_title="Part",
                section_title="Section",
                source_heading="Heading",
                normalized_aspect=None,
                source_order=2,
                artifact_type="text_block",
                raw_text=suffix,
                page_start=1,
                page_end=1,
            ),
        ]
        item = SynthesizedItem(
            artifact_id=artifacts[1].id,
            item_index=0,
            title="Minerals",
            parent_entity=None,
            aspect="Heading",
            content=content,
            evidence=suffix,
            risk_class="standard",
            source_heading="Heading",
            page_start=1,
            page_end=1,
        )

        verify_items([item], artifacts, section_page_start=1, section_page_end=1)

        self.assertEqual(item.verification_state, "needs_review")
        self.assertEqual(item.evidence, suffix)
        self.assertFalse(any("expanded" in note for note in item.verification_notes))

    def test_short_chinese_content_span_expands_from_raw_text(self):
        content = "\u53ef\u6eb6\u89e3\u7ea2\u7ec6\u80de\u819c"
        raw_text = f"\u76f4\u63a5\u6eb6\u8840\u56e0\u5b50\uff0c{content}\uff0c\u5982\u874e\u86c7\u3001\u4e94\u6b65\u86c7\u6bd2\u6db2\u3002"
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="Part",
            section_title="Section",
            source_heading="Heading",
            normalized_aspect=None,
            source_order=1,
            artifact_type="text_block",
            raw_text=raw_text,
            page_start=1,
            page_end=1,
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="Short source phrase",
            parent_entity=None,
            aspect="Heading",
            content=content,
            evidence="\u5982\u874e\u86c7\u3001\u4e94\u6b65\u86c7\u6bd2\u6db2\u3002",
            risk_class="standard",
            source_heading="Heading",
            page_start=1,
            page_end=1,
        )

        verify_items([item], [artifact], section_page_start=1, section_page_end=1)

        self.assertEqual(item.verification_state, "pass")
        self.assertEqual(item.evidence, content)


if __name__ == "__main__":
    unittest.main()
