"""Golden-section paragraph reconstruction safety tests (real + synthetic fixtures)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.evidence_artifact import EvidenceArtifact, EvidenceLocator, make_artifact
from textbook_pipeline.evidence_synthesis import SynthesizedItem
from textbook_pipeline.evidence_verifier import (
    _apply_chain_provenance,
    _build_stitched_chain_for_evidence,
    _normalize_loose,
    verify_items,
)
from textbook_pipeline.knowledge_quality_audit import (
    audit_section_bundle,
    dry_run_repair_candidate_items,
    load_artifacts_from_evidence_payload,
)
from textbook_pipeline.paragraph_reconstruction import (
    can_stitch_artifacts,
    can_stitch_continuation,
    classify_expanded_content_risk,
    detect_title_body_mismatch,
    evidence_within_bound_artifact,
    is_extractive_paraphrase,
    normalize_display_text,
    reconstruct_forward_span,
    repair_truncated_fields,
)


GENERATED_ROOT = ROOT / "generated"
ASTHMA_SECTION = "第二篇_呼吸系统疾病__第四章_支气管哮喘"
TB_SECTION = "第二篇_呼吸系统疾病__第八章_肺结核"


def _load_evidence_payload(section_id: str) -> dict:
    path = (
        GENERATED_ROOT
        / "knowledge_nodes"
        / "internal-medicine-10"
        / f"{section_id}.evidence.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_by_order(payload: dict, source_order: int) -> EvidenceArtifact:
    artifacts = load_artifacts_from_evidence_payload(payload)
    return next(artifact for artifact in artifacts if artifact.source_order == source_order)


def _make_block(
    *,
    artifact_id: str,
    source_order: int,
    page: int,
    raw_text: str,
    source_heading: str = "第四章 支气管哮喘",
    bbox: tuple[float, float, float, float],
    artifact_type: str = "text_block",
) -> EvidenceArtifact:
    return make_artifact(
        textbook_id="internal-medicine-10",
        book_id="internal-medicine-10",
        part_title="第二篇 呼吸系统疾病",
        section_title="第四章 支气管哮喘",
        source_heading=source_heading,
        normalized_aspect=None,
        source_order=source_order,
        artifact_type=artifact_type,
        raw_text=raw_text,
        page_start=page,
        page_end=page,
        locator=EvidenceLocator(page=page, kind=artifact_type, bbox=bbox),
    )


class ParagraphReconstructionSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.asthma_payload = _load_evidence_payload(ASTHMA_SECTION)
        cls.tb_payload = _load_evidence_payload(TB_SECTION)
        cls.asthma_artifacts = load_artifacts_from_evidence_payload(cls.asthma_payload)
        cls.tb_artifacts = load_artifacts_from_evidence_payload(cls.tb_payload)

    def test_asthma_definition_requires_structural_stitch(self):
        left = _artifact_by_order(self.asthma_payload, 0)
        right = _artifact_by_order(self.asthma_payload, 1)
        self.assertTrue(can_stitch_artifacts(left, right))
        span = reconstruct_forward_span(self.asthma_artifacts, left.id)
        self.assertIsNotNone(span)
        self.assertGreaterEqual(len(span.artifact_ids), 2)
        self.assertIn("异质性疾病", span.raw_text)

    def test_asthma_definition_repair_returns_provenance_span(self):
        left = _artifact_by_order(self.asthma_payload, 0)
        repair = repair_truncated_fields(
            content=left.raw_text,
            evidence=left.raw_text,
            artifact=left,
            all_artifacts=self.asthma_artifacts,
        )
        self.assertIsNotNone(repair)
        self.assertTrue(repair.span.is_multi_artifact)
        self.assertGreaterEqual(len(repair.span.locators), 2)
        self.assertFalse(evidence_within_bound_artifact(repair.raw_text, left))

    def test_cross_heading_adjacent_lines_do_not_stitch(self):
        left = _make_block(
            artifact_id="cross-heading-left",
            source_order=10,
            page=70,
            raw_text="治疗应个体化，剂量需调整",
            source_heading="治疗",
            bbox=(60.0, 100.0, 490.0, 112.0),
        )
        right = _make_block(
            artifact_id="cross-heading-right",
            source_order=11,
            page=70,
            raw_text="化吸入治疗可减轻症状",
            source_heading="药物治疗",
            bbox=(60.0, 116.0, 490.0, 128.0),
        )
        self.assertFalse(can_stitch_artifacts(left, right))

    def test_list_marker_next_block_does_not_stitch(self):
        latent = _make_block(
            artifact_id="latent-trunc",
            source_order=20,
            page=107,
            raw_text="机体内感染了结核分枝杆菌，但没有发生临床结核病，没有临",
            source_heading="第八章 肺结核",
            bbox=(59.0, 200.0, 490.0, 212.0),
        )
        active = _make_block(
            artifact_id="active-next",
            source_order=21,
            page=107,
            raw_text="（二）活动性结核病 具有结核病相关的临床症状和体征",
            source_heading="第八章 肺结核",
            bbox=(59.0, 216.0, 490.0, 228.0),
        )
        self.assertFalse(can_stitch_artifacts(latent, active))

    def test_table_artifact_does_not_stitch_to_text_block(self):
        left = _make_block(
            artifact_id="table-left",
            source_order=30,
            page=70,
            raw_text="FEV1/FVC",
            bbox=(60.0, 300.0, 200.0, 312.0),
        )
        right = _make_block(
            artifact_id="table-right",
            source_order=31,
            page=70,
            raw_text="<70% 提示气流受限",
            bbox=(60.0, 316.0, 200.0, 328.0),
            artifact_type="table",
        )
        self.assertFalse(can_stitch_artifacts(left, right))

    def test_two_column_layout_does_not_stitch(self):
        left = _make_block(
            artifact_id="left-column",
            source_order=40,
            page=70,
            raw_text="左侧正文在栏内被截断，末尾词未",
            bbox=(60.0, 400.0, 250.0, 412.0),
        )
        right = _make_block(
            artifact_id="right-column",
            source_order=41,
            page=70,
            raw_text="结束于右侧栏继续书写",
            bbox=(300.0, 400.0, 490.0, 412.0),
        )
        self.assertFalse(can_stitch_artifacts(left, right))

    def test_tb_uv_lamp_reconstruction_flags_procedural_risk(self):
        middle = _artifact_by_order(self.tb_payload, 22)
        repair = repair_truncated_fields(
            content="10W 紫外线灯距照射",
            evidence="10W 紫外线灯距照射",
            artifact=middle,
            all_artifacts=self.tb_artifacts,
        )
        self.assertIsNotNone(repair)
        self.assertTrue(repair.span.is_multi_artifact)
        self.assertIsNotNone(classify_expanded_content_risk(repair.display_text, repair.raw_text))

    def test_display_normalization_preserves_abbreviation_space(self):
        raw = "结核病是HIV/AIDS 最常见的机会感染性疾病"
        normalized = normalize_display_text(raw)
        self.assertIn("HIV/AIDS", normalized)
        self.assertNotIn("HIV/AIDS  最", normalized)

    def test_display_normalization_merges_cjk_line_wrap_space(self):
        # PDF extractor introduces ASCII space at line breaks between CJK chars
        raw = "气道 炎症是支气管哮喘 的核心机制"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "气道炎症是支气管哮喘的核心机制")

    def test_display_normalization_merges_cjk_line_wrap_newline(self):
        # Single \n between CJK chars is a PDF line-wrap, not a paragraph break
        raw = "气道\n炎症\n是慢性疾病"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "气道炎症是慢性疾病")

    def test_display_normalization_preserves_paragraph_boundary(self):
        raw = "哮喘是一种慢性气道炎症性疾病\n\n定义是指可逆性气流受限"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "哮喘是一种慢性气道炎症性疾病\n\n定义是指可逆性气流受限")

    def test_display_normalization_preserves_english_phrase(self):
        raw = "支气管哮喘 bronchial asthma 是慢性气道炎症"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "支气管哮喘 bronchial asthma 是慢性气道炎症")

    def test_display_normalization_preserves_unit_spacing(self):
        # "10 mg" should keep the space; "10 岁" should not (digit-CJK rule)
        raw = "口服 10 mg 每次 10 岁以下慎用"
        normalized = normalize_display_text(raw)
        self.assertIn("10 mg", normalized)
        self.assertIn("10岁以下", normalized)

    def test_display_normalization_removes_chinese_punctuation_spaces(self):
        raw = "哮喘 ， 是慢性疾病 ； 表现为喘息"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "哮喘，是慢性疾病；表现为喘息")

    def test_display_normalization_removes_punctuation_suffix_space(self):
        # Suffix-only space (after punctuation) must also be removed
        raw = "哮喘， 是慢性疾病； 表现为喘息"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "哮喘，是慢性疾病；表现为喘息")

    def test_display_normalization_removes_bracket_spaces(self):
        raw = "（ 支气管哮喘 ） 是一种【 慢性疾病 】"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "（支气管哮喘）是一种【慢性疾病】")

    def test_display_normalization_strips_zero_width_chars(self):
        raw = "气道\u200b炎症\u200c\u200d是\u3000疾病\ufeff"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "气道炎症是疾病")

    def test_display_normalization_preserves_double_newline_across_cjk(self):
        # Real paragraph boundary between CJK chars must survive
        raw = "第一段结束\n\n第二段开始"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "第一段结束\n\n第二段开始")

    def test_display_normalization_handles_mixed_line_wrap_and_paragraph(self):
        raw = "气道 炎症\n是慢性疾病\n\n定义\n是指可逆性气流受限"
        normalized = normalize_display_text(raw)
        self.assertEqual(
            normalized,
            "气道炎症是慢性疾病\n\n定义是指可逆性气流受限",
        )

    def test_display_normalization_digit_newline_cjk(self):
        raw = "剂量 10\n岁以下禁用"
        normalized = normalize_display_text(raw)
        self.assertEqual(normalized, "剂量10岁以下禁用")


class GoldenSectionVerifierSafetyTests(unittest.TestCase):
    def test_asthma_definition_multi_artifact_reconstruction_needs_review(self):
        payload = _load_evidence_payload(ASTHMA_SECTION)
        artifacts = load_artifacts_from_evidence_payload(payload)
        artifact = _artifact_by_order(payload, 0)
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="支气管哮喘的定义",
            parent_entity="支气管哮喘",
            aspect="第四章 支气管哮喘",
            content=artifact.raw_text,
            evidence=artifact.raw_text,
            risk_class="standard",
            source_heading="第四章 支气管哮喘",
            page_start=artifact.page_start,
            page_end=artifact.page_end,
        )

        verify_items([item], artifacts, section_page_start=62, section_page_end=70)

        self.assertEqual(item.verification_state, "needs_review")
        self.assertGreater(len(item.source_artifact_ids), 1)
        self.assertGreater(len(item.reconstructed_locators), 1)
        self.assertFalse(evidence_within_bound_artifact(item.evidence, artifact))
        self.assertTrue(any("multi-artifact span pending provenance review" in note for note in item.verification_notes))

    def test_uv_lamp_expansion_downgrades_procedural_standard_risk(self):
        payload = _load_evidence_payload(TB_SECTION)
        artifacts = load_artifacts_from_evidence_payload(payload)
        artifact = _artifact_by_order(payload, 22)
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="紫外线灯的功率和距离要求",
            parent_entity=None,
            aspect="第八章 肺结核",
            content="10W 紫外线灯距照射",
            evidence="10W 紫外线灯距照射",
            risk_class="standard",
            source_heading="第八章 肺结核",
            page_start=artifact.page_start,
            page_end=artifact.page_end,
        )

        verify_items([item], artifacts, section_page_start=100, section_page_end=120)

        self.assertEqual(item.verification_state, "needs_review")
        self.assertEqual(item.risk_class, "needs_review")
        self.assertTrue(any("expanded_content_risk" in note for note in item.verification_notes))

    def test_unresolved_procedural_truncation_stays_needs_review(self):
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="第二篇 呼吸系统疾病",
            section_title="第八章 肺结核",
            source_heading="第八章 肺结核",
            normalized_aspect=None,
            source_order=199,
            artifact_type="text_block",
            raw_text="10W 紫外线灯距照射",
            page_start=102,
            page_end=102,
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="紫外线灯的功率和距离要求",
            parent_entity=None,
            aspect="第八章 肺结核",
            content=artifact.raw_text,
            evidence=artifact.raw_text,
            risk_class="standard",
            source_heading="第八章 肺结核",
            page_start=102,
            page_end=102,
        )

        verify_items([item], [artifact], section_page_start=100, section_page_end=120)

        self.assertEqual(item.verification_state, "needs_review")
        self.assertEqual(item.risk_class, "needs_review")

    def test_unresolved_truncation_becomes_evidence_only(self):
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="第二篇 呼吸系统疾病",
            section_title="第四章 支气管哮喘",
            source_heading="第四章 支气管哮喘",
            normalized_aspect=None,
            source_order=99,
            artifact_type="text_block",
            raw_text="哮喘是世界上最常见的慢性疾病之一，全球约有",
            page_start=70,
            page_end=70,
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="孤立半句",
            parent_entity=None,
            aspect="第四章 支气管哮喘",
            content=artifact.raw_text,
            evidence=artifact.raw_text,
            risk_class="standard",
            source_heading="第四章 支气管哮喘",
            page_start=70,
            page_end=70,
        )

        verify_items([item], [artifact], section_page_start=62, section_page_end=70)

        self.assertEqual(item.verification_state, "evidence_only")
        self.assertTrue(any("evidence_only_required" in note for note in item.verification_notes))

    def test_extractive_paraphrase_stays_needs_review(self):
        payload = _load_evidence_payload(ASTHMA_SECTION)
        artifacts = load_artifacts_from_evidence_payload(payload)
        artifact = _artifact_by_order(payload, 1)
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="支气管哮喘的临床表现",
            parent_entity="支气管哮喘",
            aspect="第四章 支气管哮喘",
            content="反复发作的喘息、气急、胸闷或咳嗽等症状",
            evidence=artifact.raw_text,
            risk_class="standard",
            source_heading="第四章 支气管哮喘",
            page_start=artifact.page_start,
            page_end=artifact.page_end,
        )

        verify_items([item], artifacts, section_page_start=62, section_page_end=70)

        self.assertEqual(item.verification_state, "needs_review")
        self.assertTrue(is_extractive_paraphrase(item.content, artifact.raw_text))

    def test_title_body_mismatch_stays_needs_review(self):
        payload = _load_evidence_payload(TB_SECTION)
        artifacts = load_artifacts_from_evidence_payload(payload)
        artifact = _artifact_by_order(payload, 21)
        body = "结核分枝杆菌对干燥、冷、酸、碱等抵抗力强，对紫外线比较敏感，太阳光直射"
        self.assertEqual(detect_title_body_mismatch("抗酸杆菌的定义", body), "title_definition_body_property_mismatch")
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="抗酸杆菌的定义",
            parent_entity=None,
            aspect="第八章 肺结核",
            content=body,
            evidence=body,
            risk_class="standard",
            source_heading="第八章 肺结核",
            page_start=artifact.page_start,
            page_end=artifact.page_end,
        )

        verify_items([item], artifacts, section_page_start=100, section_page_end=120)

        self.assertEqual(item.verification_state, "needs_review")
        self.assertTrue(any("title_body_mismatch" in note for note in item.verification_notes))


class GoldenSectionAuditBaselineTests(unittest.TestCase):
    def test_baseline_audit_finds_known_asthma_and_tb_defects(self):
        for section_id in (ASTHMA_SECTION, TB_SECTION):
            report = audit_section_bundle(
                section_id=section_id,
                generated_root=GENERATED_ROOT,
                repo_root=ROOT,
            )
            self.assertGreater(report.stats.get("truncated_sentence", 0), 0)

        tb = audit_section_bundle(
            section_id=TB_SECTION,
            generated_root=GENERATED_ROOT,
            repo_root=ROOT,
        )
        self.assertGreater(tb.stats.get("title_body_mismatch", 0), 0)

    def test_dry_run_never_promotes_multi_artifact_reconstruction_to_pass(self):
        candidate_path = (
            GENERATED_ROOT
            / "evidence_candidates"
            / "internal-medicine-10"
            / f"{ASTHMA_SECTION}.candidate.json"
        )
        if not candidate_path.exists():
            candidate_path = (
                GENERATED_ROOT
                / "pipeline_v3"
                / "evidence_candidates"
                / "internal-medicine-10"
                / f"{ASTHMA_SECTION}.candidate.json"
            )
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
        artifacts = load_artifacts_from_evidence_payload(_load_evidence_payload(ASTHMA_SECTION))
        repaired_payload, stats = dry_run_repair_candidate_items(payload, artifacts)

        if stats["multi_artifact_reconstructions"] > 0:
            for item in repaired_payload.get("candidate_items") or []:
                if len(item.get("source_artifact_ids") or []) > 1:
                    self.assertEqual(item.get("verification_state"), "needs_review")
        self.assertGreater(stats["downgraded_paraphrase"], 0)


class CrossArtifactNegativeStitchTests(unittest.TestCase):
    """Negative tests: verify that invalid cross-artifact stitching is rejected."""

    def test_cross_page_same_heading_does_not_stitch(self):
        """Same heading + same column but different page must not stitch."""
        left = _make_block(
            artifact_id="p70-trunc",
            source_order=50,
            page=70,
            raw_text="哮喘的长期治疗方案需要根据",
            bbox=(60.0, 500.0, 490.0, 512.0),
        )
        right = _make_block(
            artifact_id="p71-cont",
            source_order=51,
            page=71,
            raw_text="患者的病情严重程度进行调整",
            bbox=(60.0, 100.0, 490.0, 112.0),
        )
        self.assertFalse(can_stitch_artifacts(left, right))

    def test_non_adjacent_source_order_does_not_stitch(self):
        """Same heading + same page but source_order gap > 1 must not stitch."""
        left = _make_block(
            artifact_id="order-60",
            source_order=60,
            page=70,
            raw_text="气流受限的可逆性评估",
            bbox=(60.0, 200.0, 490.0, 212.0),
        )
        right = _make_block(
            artifact_id="order-63",
            source_order=63,
            page=70,
            raw_text="是诊断哮喘的重要指标",
            bbox=(60.0, 216.0, 490.0, 228.0),
        )
        self.assertFalse(can_stitch_artifacts(left, right))

    def test_excessive_vertical_gap_does_not_stitch(self):
        """Same heading + same page + adjacent order but vertical gap > 40pt."""
        left = _make_block(
            artifact_id="vgap-low",
            source_order=70,
            page=70,
            raw_text="支气管舒张剂主要通过松弛",
            bbox=(60.0, 200.0, 490.0, 212.0),
        )
        right = _make_block(
            artifact_id="vgap-high",
            source_order=71,
            page=70,
            raw_text="气道平滑肌发挥作用的",
            bbox=(60.0, 300.0, 490.0, 312.0),  # 88pt gap > 40
        )
        self.assertFalse(can_stitch_artifacts(left, right))

    def test_partial_column_overlap_does_not_stitch(self):
        """x-range overlap < 50% must not stitch (different columns)."""
        left = _make_block(
            artifact_id="col-a",
            source_order=80,
            page=70,
            raw_text="左栏文字被截断在中间",
            bbox=(60.0, 400.0, 250.0, 412.0),
        )
        right = _make_block(
            artifact_id="col-b",
            source_order=81,
            page=70,
            raw_text="右栏继续书写内容",
            bbox=(200.0, 416.0, 490.0, 428.0),  # overlap 50pt / 190pt = 26%
        )
        self.assertFalse(can_stitch_artifacts(left, right))

    def test_sentence_ending_blocks_stitch(self):
        """Left ending with sentence punctuation must not stitch."""
        left = _make_block(
            artifact_id="sent-end",
            source_order=90,
            page=70,
            raw_text="哮喘是一种慢性气道炎症性疾病。",
            bbox=(60.0, 500.0, 490.0, 512.0),
        )
        right = _make_block(
            artifact_id="sent-next",
            source_order=91,
            page=70,
            raw_text="其发病机制涉及多种细胞和细胞组分",
            bbox=(60.0, 516.0, 490.0, 528.0),
        )
        self.assertFalse(can_stitch_artifacts(left, right))

    def test_new_block_prefix_blocks_stitch(self):
        """Right starting with a numbered/list marker must not stitch."""
        left = _make_block(
            artifact_id="list-prev",
            source_order=100,
            page=70,
            raw_text="常用药物包括以下几类",
            bbox=(60.0, 200.0, 490.0, 212.0),
        )
        right = _make_block(
            artifact_id="list-mark",
            source_order=101,
            page=70,
            raw_text="（一）β2受体激动剂是首选药物",
            bbox=(60.0, 216.0, 490.0, 228.0),
        )
        self.assertFalse(can_stitch_artifacts(left, right))

    def test_can_stitch_continuation_is_text_only_no_structural_guards(self):
        """can_stitch_continuation must not be used as production stitch check."""
        # Text-level junction looks valid
        self.assertTrue(can_stitch_continuation("气流受限的可", "逆性改变"))
        # But this function does NOT check heading, page, column, or order —
        # production must use can_stitch_artifacts which enforces all of those.
        # This test documents the gap, not endorses the usage.

    def test_expanded_risk_regex_covers_dosage_time_distance(self):
        """PROCEDURAL_RISK_RE must flag dosage, time, distance, steps."""
        for keyword in [
            "剂量", "给药", "mg", "ml", "μg", "口服", "静脉", "肌注",
            "分钟", "小时", "秒", "每日", "单次", "疗程",
            "距离", "cm", "mm", "照射", "消毒",
            "操作步骤", "禁忌", "不良反应", "最大剂量", "起始剂量",
        ]:
            self.assertIsNotNone(
                classify_expanded_content_risk(keyword, keyword),
                f"keyword '{keyword}' should be flagged as procedural risk",
            )

    def test_expanded_risk_regex_does_not_flag_standard_text(self):
        """Standard clinical text without procedural risk must not be flagged."""
        standard = "哮喘是一种以慢性气道炎症为特征的异质性疾病"
        self.assertIsNone(classify_expanded_content_risk(standard, standard))

    def test_dry_run_truncated_procedural_risk_goes_needs_review_not_evidence_only(self):
        """Unresolved truncation with procedural risk → needs_review, not evidence_only."""
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="第二篇 呼吸系统疾病",
            section_title="第八章 肺结核",
            source_heading="第八章 肺结核",
            normalized_aspect=None,
            source_order=299,
            artifact_type="text_block",
            raw_text="紫外线灯消毒照射剂量为",
            page_start=102,
            page_end=102,
        )
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": artifact.id,
                    "content": "紫外线灯消毒照射剂量为",
                    "evidence": "紫外线灯消毒照射剂量为",
                    "risk_class": "standard",
                    "verification_state": "pass",
                    "verification_notes": [],
                }
            ]
        }
        repaired_payload, stats = dry_run_repair_candidate_items(
            candidate_payload, [artifact]
        )
        item = repaired_payload["candidate_items"][0]
        self.assertEqual(item["verification_state"], "needs_review")
        self.assertEqual(item["risk_class"], "needs_review")
        self.assertNotIn("evidence_only", item.get("verification_state", ""))


class VerifierBypassNegativeTests(unittest.TestCase):
    """Regression tests for the P0 verifier bypass vulnerabilities.

    These cover the three exploit vectors reported in the user's verification:
    1. Different-heading neighbor blocks must not produce a pass via nearby_page_text.
    2. Prefix-only evidence match must not produce a pass.
    3. Multi-artifact cross-block matches must propagate provenance and force needs_review.
    Also: verify_items summary must include an evidence_only counter.
    """

    def _make_two_block_setup(
        self,
        *,
        left_heading: str,
        right_heading: str,
        left_text: str,
        right_text: str,
        left_order: int = 10,
        right_order: int = 11,
        page: int = 70,
    ) -> tuple[EvidenceArtifact, EvidenceArtifact, list[EvidenceArtifact]]:
        left = _make_block(
            artifact_id="verifier-bypass-left",
            source_order=left_order,
            page=page,
            raw_text=left_text,
            source_heading=left_heading,
            bbox=(60.0, 100.0, 490.0, 112.0),
        )
        right = _make_block(
            artifact_id="verifier-bypass-right",
            source_order=right_order,
            page=page,
            raw_text=right_text,
            source_heading=right_heading,
            bbox=(60.0, 116.0, 490.0, 128.0),
        )
        return left, right, [left, right]

    def test_different_heading_neighbor_blocks_do_not_pass(self):
        """Construct the exact bypass reported by the user.

        Two same-page, adjacent-order artifacts with DIFFERENT source_heading.
        Evidence spans both blocks. Before the fix, nearby_page_text concatenated
        them and the verifier returned verdict=pass with empty provenance.
        After the fix, the verifier must NOT stitch across different headings
        and the item must be rejected (or at minimum not pass).
        """
        left, right, artifacts = self._make_two_block_setup(
            left_heading="第四章 支气管哮喘",
            right_heading="第五章 慢性阻塞性肺疾病",
            left_text="哮喘的典型症状包括反复发作的",
            right_text="喘息、气急、胸闷和咳嗽等症状",
        )
        # Evidence deliberately spans both blocks (would pass under the bypass)
        cross_block_evidence = "反复发作的喘息、气急、胸闷和咳嗽等症状"
        item = SynthesizedItem(
            artifact_id=left.id,
            item_index=0,
            title="哮喘的典型症状",
            parent_entity="支气管哮喘",
            aspect="第四章 支气管哮喘",
            content=cross_block_evidence,
            evidence=cross_block_evidence,
            risk_class="standard",
            source_heading="第四章 支气管哮喘",
            page_start=70,
            page_end=70,
        )

        results, counts = verify_items(
            [item], artifacts, section_page_start=62, section_page_end=80
        )

        self.assertNotEqual(
            results[0].verdict,
            "pass",
            "different-heading neighbor blocks must not produce a pass",
        )
        # Empty provenance must not coexist with a pass
        self.assertFalse(
            results[0].verdict == "pass" and not item.source_artifact_ids,
            "pass verdict with empty source_artifact_ids is forbidden",
        )

    def test_prefix_only_evidence_match_does_not_pass(self):
        """Evidence whose first 20 chars match but whose remainder does not
        must NOT produce verdict=pass. Before the fix, prefix match returned
        (True, 'partial match (prefix found)') and the item passed.
        """
        artifact = _make_block(
            artifact_id="prefix-only-art",
            source_order=15,
            page=70,
            raw_text=(
                "哮喘是一种以慢性气道炎症为特征的异质性疾病，"
                "其发病机制涉及多种细胞"
            ),
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 200.0, 490.0, 212.0),
        )
        # First 20 chars match, but the second half is fabricated/unsupported
        prefix_only_evidence = (
            "哮喘是一种以慢性气道炎症为特征的异质性疾病"
            "这种疾病的致死率高达百分之五十"
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="哮喘的定义",
            parent_entity="支气管哮喘",
            aspect="第四章 支气管哮喘",
            content=prefix_only_evidence,
            evidence=prefix_only_evidence,
            risk_class="standard",
            source_heading="第四章 支气管哮喘",
            page_start=70,
            page_end=70,
        )

        results, counts = verify_items(
            [item], [artifact], section_page_start=62, section_page_end=80
        )

        self.assertNotEqual(
            results[0].verdict,
            "pass",
            "prefix-only evidence match must not produce a pass",
        )

    def test_legal_multi_artifact_match_propagates_provenance_and_forces_review(self):
        """When evidence genuinely spans a structurally legal stitch chain,
        the verifier must (a) propagate source_artifact_ids and locators,
        and (b) force verdict=needs_review, never pass.
        """
        # Same heading, same page, same column, adjacent order, valid junction
        left = _make_block(
            artifact_id="legal-chain-left",
            source_order=20,
            page=70,
            raw_text="哮喘是世界上最常见的慢性疾病之一，全球约有",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 300.0, 490.0, 312.0),
        )
        right = _make_block(
            artifact_id="legal-chain-right",
            source_order=21,
            page=70,
            raw_text="3亿患者，我国约有2000万患者",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 316.0, 490.0, 328.0),
        )
        artifacts = [left, right]
        # Full evidence spanning both blocks
        cross_block_evidence = "哮喘是世界上最常见的慢性疾病之一，全球约有3亿患者，我国约有2000万患者"
        item = SynthesizedItem(
            artifact_id=left.id,
            item_index=0,
            title="哮喘的流行病学",
            parent_entity="支气管哮喘",
            aspect="第四章 支气管哮喘",
            content=cross_block_evidence,
            evidence=cross_block_evidence,
            risk_class="standard",
            source_heading="第四章 支气管哮喘",
            page_start=70,
            page_end=70,
        )

        results, counts = verify_items(
            [item], artifacts, section_page_start=62, section_page_end=80
        )

        self.assertEqual(results[0].verdict, "needs_review")
        self.assertGreater(
            len(item.source_artifact_ids), 1,
            "multi-artifact match must propagate source_artifact_ids",
        )
        self.assertGreater(
            len(item.reconstructed_locators), 1,
            "multi-artifact match must propagate reconstructed_locators",
        )

    def test_verify_items_summary_includes_evidence_only_counter(self):
        """verify_items summary counts must include 'evidence_only' so totals add up."""
        # Truncated content with no procedural risk → evidence_only verdict
        artifact = _make_block(
            artifact_id="summary-counter-art",
            source_order=25,
            page=70,
            raw_text="哮喘的长期管理需要",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 400.0, 490.0, 412.0),
        )
        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=0,
            title="孤立半句",
            parent_entity=None,
            aspect="第四章 支气管哮喘",
            content="哮喘的长期管理需要",
            evidence="哮喘的长期管理需要",
            risk_class="standard",
            source_heading="第四章 支气管哮喘",
            page_start=70,
            page_end=70,
        )

        results, counts = verify_items(
            [item], [artifact], section_page_start=62, section_page_end=80
        )

        self.assertIn("evidence_only", counts)
        # The sum of all categories must equal total
        categorized = (
            counts["pass"]
            + counts["needs_review"]
            + counts["evidence_only"]
            + counts["rejected"]
        )
        self.assertEqual(categorized, counts["total"])

    def test_shortest_legal_chain_returned_when_evidence_spans_subset(self):
        """P1 provenance precision: three legally stitchable blocks where
        evidence spans only the first two.

        Before the fix, ``_build_stitched_chain_for_evidence`` extended the
        forward chain to its maximum (up to 6 blocks) BEFORE checking whether
        the evidence was contained. The unused third block was therefore
        written into ``source_artifact_ids`` even though it contributed no
        evidence text.

        After the fix, the builder returns the shortest legal chain that
        contains the evidence and stops extending immediately. The third
        block must NOT appear in the chain or in the propagated provenance.
        """
        block_a = _make_block(
            artifact_id="p1-precision-a",
            source_order=30,
            page=70,
            raw_text="支气管舒张试验阳性标准为",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 300.0, 490.0, 312.0),
        )
        block_b = _make_block(
            artifact_id="p1-precision-b",
            source_order=31,
            page=70,
            raw_text="改善率大于等于百分之12",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 316.0, 490.0, 328.0),
        )
        block_c = _make_block(
            artifact_id="p1-precision-c",
            source_order=32,
            page=70,
            raw_text="该指标可用于哮喘诊断",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 332.0, 490.0, 344.0),
        )
        artifacts = [block_a, block_b, block_c]

        # Sanity: all three blocks form a legally stitchable forward chain
        self.assertTrue(can_stitch_artifacts(block_a, block_b))
        self.assertTrue(can_stitch_artifacts(block_b, block_c))

        # Evidence spans ONLY block_a + block_b (loose-normalized)
        evidence_text = "支气管舒张试验阳性标准为改善率大于等于百分之12"
        evidence_loose = _normalize_loose(evidence_text)

        chain_result = _build_stitched_chain_for_evidence(
            block_a, artifacts, evidence_loose
        )
        self.assertIsNotNone(
            chain_result, "evidence spanning A+B must produce a legal chain"
        )
        chain, _joined = chain_result

        # The shortest legal chain containing the evidence is exactly [A, B]
        self.assertEqual(
            len(chain),
            2,
            "shortest legal chain must be 2 blocks, not 3; "
            "unused stitchable block C must not be appended",
        )
        self.assertEqual([art.id for art in chain], [block_a.id, block_b.id])
        self.assertNotIn(block_c.id, [art.id for art in chain])

        # Provenance propagation: source_artifact_ids must only contain A and B
        item = SynthesizedItem(
            artifact_id=block_a.id,
            item_index=0,
            title="舒张试验阳性标准",
            parent_entity="支气管哮喘",
            aspect="第四章 支气管哮喘",
            content=evidence_text,
            evidence=evidence_text,
            risk_class="standard",
            source_heading="第四章 支气管哮喘",
            page_start=70,
            page_end=70,
        )
        _apply_chain_provenance(item, chain)
        self.assertEqual(item.source_artifact_ids, [block_a.id, block_b.id])
        self.assertEqual(len(item.reconstructed_locators), 2)
        self.assertNotIn(block_c.id, item.source_artifact_ids)

    def test_repair_truncated_fields_trims_unused_third_block_from_span(self):
        """P1 provenance precision on the production reconstruction path.

        ``verify_item`` → ``repair_truncated_fields`` → ``reconstruct_forward_span``
        previously built a chain up to ``max_artifacts=4`` and returned the
        full chain in ``RepairResult.span`` even when ``expanded_raw`` ended
        inside an earlier block. The unused trailing block was therefore
        written into ``source_artifact_ids``.

        Scenario: three legally stitchable blocks A, B, C. The sentence
        terminator lands inside block B, so ``expanded_raw`` never reaches
        block C. After the fix, ``RepairResult.span.artifact_ids`` must
        contain only [A, B]; C must not appear in any provenance tuple.
        """
        block_a = _make_block(
            artifact_id="repair-trim-a",
            source_order=40,
            page=71,
            raw_text="支气管舒张试验阳性标准为",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 300.0, 490.0, 312.0),
        )
        # Block B has a sentence terminator (。) in the MIDDLE so that B-C
        # still stitches (B does not end with a terminator), but
        # expand_to_sentence_boundary stops at the 。.
        block_b = _make_block(
            artifact_id="repair-trim-b",
            source_order=41,
            page=71,
            raw_text="改善率大于等于百分之12。该指标",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 316.0, 490.0, 328.0),
        )
        block_c = _make_block(
            artifact_id="repair-trim-c",
            source_order=42,
            page=71,
            raw_text="可用于哮喘诊断和鉴别",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 332.0, 490.0, 344.0),
        )
        artifacts = [block_a, block_b, block_c]

        # Sanity: all three blocks form a legally stitchable forward chain
        self.assertTrue(can_stitch_artifacts(block_a, block_b))
        self.assertTrue(can_stitch_artifacts(block_b, block_c))

        truncated_content = "支气管舒张试验阳性标准为"

        result = repair_truncated_fields(
            content=truncated_content,
            evidence=truncated_content,
            artifact=block_a,
            all_artifacts=artifacts,
        )

        self.assertIsNotNone(result, "truncated content must trigger repair")
        assert result is not None  # narrow type for mypy

        # expanded_raw ends at the 。 inside block B
        self.assertTrue(result.raw_text.endswith("。"))
        self.assertNotIn(block_c.raw_text, result.raw_text)

        # The span must be trimmed: only A and B contributed
        self.assertEqual(
            len(result.span.artifact_ids), 2,
            "RepairResult.span.artifact_ids must be trimmed to [A, B]; "
            "unused stitchable block C must not appear",
        )
        self.assertEqual(
            list(result.span.artifact_ids), [block_a.id, block_b.id]
        )
        self.assertEqual(
            list(result.span.source_orders),
            [block_a.source_order, block_b.source_order],
        )
        self.assertEqual(
            list(result.span.pages), [block_a.page_start, block_b.page_start]
        )
        self.assertEqual(len(result.span.locators), 2)
        self.assertNotIn(block_c.id, result.span.artifact_ids)
        # Object self-consistency: span.raw_text must match the trimmed chain,
        # not the original 3-block chain. Before the fix, span.raw_text still
        # contained block C's text while artifact_ids had been trimmed to [A, B].
        self.assertEqual(
            result.span.raw_text, result.raw_text,
            "span.raw_text must equal RepairResult.raw_text (both reflect expanded_raw)",
        )
        self.assertNotIn(
            block_c.raw_text, result.span.raw_text,
            "span.raw_text must not contain unused block C's raw_text",
        )

    def test_repair_truncated_fields_span_self_consistent_when_sentence_ends_mid_last_block(self):
        """Two-block boundary: sentence terminator lands INSIDE the last
        contributing block.

        Before the fix, ``_trim_span_to_expanded_raw`` set ``cut`` to
        ``len(chain)`` initial value and returned the original ``span`` when
        the covering prefix happened to equal the full chain (cut == len(chain)).
        That left ``span.raw_text`` containing the trailing text after the
        sentence terminator while ``RepairResult.raw_text`` was correctly
        trimmed — the span object was not self-consistent.

        After the fix, ``cut`` is ``None`` until a covering prefix is found,
        and a new span with ``raw_text=expanded_raw`` is always created when
        a cover exists, even when ``cut == len(chain)``.
        """
        block_a = _make_block(
            artifact_id="two-block-boundary-a",
            source_order=60,
            page=73,
            raw_text="支气管舒张试验阳性标准为",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 300.0, 490.0, 312.0),
        )
        # Block B has a sentence terminator (。) in the MIDDLE; the covering
        # prefix is the full chain [A, B] but expanded_raw stops at the 。.
        block_b = _make_block(
            artifact_id="two-block-boundary-b",
            source_order=61,
            page=73,
            raw_text="改善率大于等于百分之12。该指标可用于诊断",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 316.0, 490.0, 328.0),
        )
        artifacts = [block_a, block_b]

        self.assertTrue(can_stitch_artifacts(block_a, block_b))

        truncated_content = "支气管舒张试验阳性标准为"
        result = repair_truncated_fields(
            content=truncated_content,
            evidence=truncated_content,
            artifact=block_a,
            all_artifacts=artifacts,
        )

        self.assertIsNotNone(result, "truncated content must trigger repair")
        assert result is not None  # narrow type for mypy

        # expanded_raw ends at the 。inside block B; both blocks contribute
        self.assertTrue(result.raw_text.endswith("。"))
        self.assertEqual(
            list(result.span.artifact_ids),
            [block_a.id, block_b.id],
            "both A and B contribute to expanded_raw",
        )

        # The critical self-consistency assertion: span.raw_text must equal
        # RepairResult.raw_text (both stop at the 。), not contain B's
        # trailing text "该指标可用于诊断".
        self.assertEqual(
            result.span.raw_text,
            result.raw_text,
            "span.raw_text must equal RepairResult.raw_text; "
            "before the fix span.raw_text kept B's trailing text",
        )
        self.assertNotIn(
            "该指标可用于诊断",
            result.span.raw_text,
            "span.raw_text must not contain trailing text after the sentence terminator",
        )

    def test_verify_items_provenance_excludes_unused_third_block(self):
        """End-to-end provenance precision through ``verify_items``.

        Verifies that the production path
        ``verify_item`` → ``repair_truncated_fields`` → ``reconstruct_forward_span``
        writes only the contributing artifacts (A, B) into
        ``item.source_artifact_ids`` and ``item.reconstructed_locators``,
        not the unused third block C.
        """
        block_a = _make_block(
            artifact_id="verify-trim-a",
            source_order=50,
            page=72,
            raw_text="支气管舒张试验阳性标准为",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 300.0, 490.0, 312.0),
        )
        block_b = _make_block(
            artifact_id="verify-trim-b",
            source_order=51,
            page=72,
            raw_text="改善率大于等于百分之12。该指标",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 316.0, 490.0, 328.0),
        )
        block_c = _make_block(
            artifact_id="verify-trim-c",
            source_order=52,
            page=72,
            raw_text="可用于哮喘诊断和鉴别",
            source_heading="第四章 支气管哮喘",
            bbox=(60.0, 332.0, 490.0, 344.0),
        )
        artifacts = [block_a, block_b, block_c]

        # Sanity: chain is legally stitchable end-to-end
        self.assertTrue(can_stitch_artifacts(block_a, block_b))
        self.assertTrue(can_stitch_artifacts(block_b, block_c))

        truncated_content = "支气管舒张试验阳性标准为"
        item = SynthesizedItem(
            artifact_id=block_a.id,
            item_index=0,
            title="舒张试验阳性标准",
            parent_entity="支气管哮喘",
            aspect="第四章 支气管哮喘",
            content=truncated_content,
            evidence=truncated_content,
            risk_class="standard",
            source_heading="第四章 支气管哮喘",
            page_start=72,
            page_end=72,
        )

        results, _counts = verify_items(
            [item], artifacts, section_page_start=62, section_page_end=80
        )

        # Multi-artifact reconstruction must force needs_review (never pass)
        self.assertNotEqual(results[0].verdict, "pass")

        # Provenance must contain only [A, B]; C must not leak in
        self.assertEqual(item.source_artifact_ids, [block_a.id, block_b.id])
        self.assertEqual(len(item.reconstructed_locators), 2)
        self.assertNotIn(block_c.id, item.source_artifact_ids)
        # Evidence ends at the 。inside block B; C's raw_text must not appear
        self.assertTrue(item.evidence.endswith("。"))
        self.assertNotIn(block_c.raw_text, item.evidence)


if __name__ == "__main__":
    unittest.main()