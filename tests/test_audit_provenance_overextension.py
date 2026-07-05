"""Unit tests for audit_provenance_dry_run._detect_overextended_chain.

Covers backward-chain and ASCII boundary edge cases that the production
dry-run audit must handle correctly.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "textbook_pipeline"))

from textbook_pipeline.evidence_artifact import EvidenceArtifact, EvidenceLocator, make_artifact
from textbook_pipeline.evidence_span_context import normalize_loose

from audit_provenance_dry_run import _detect_overextended_chain


def _make_artifact(
    aid_suffix: str,
    raw_text: str,
    *,
    page: int = 5,
    order: int,
    heading: str = "测试章节",
    bbox: tuple[float, float, float, float] = (10.0, 20.0, 100.0, 40.0),
) -> EvidenceArtifact:
    """Build a stitchable text_block artifact with a locator.

    Adjacent artifacts must have:
      - same source_heading
      - source_order gap of exactly 1
      - same page_start
      - bbox x-overlap >= 0.5
      - vertical gap (right.top - left.bottom) in [0, 40]
    """
    return make_artifact(
        textbook_id="test-book",
        book_id="test-book",
        part_title="测试篇",
        section_title=heading,
        source_heading=heading,
        normalized_aspect=heading,
        source_order=order,
        artifact_type="text_block",
        raw_text=raw_text,
        page_start=page,
        page_end=page,
        locator=EvidenceLocator(page=page, kind="paragraph", bbox=bbox),
    )


def _stacked_artifacts(texts: list[str], *, page: int = 5, heading: str = "测试章节") -> list[EvidenceArtifact]:
    """Build a vertical stack of stitchable artifacts (each 30px tall, 10px gap)."""
    arts: list[EvidenceArtifact] = []
    base_top = 20.0
    for i, text in enumerate(texts):
        top = base_top + i * 40.0
        bottom = top + 30.0
        bbox = (10.0, top, 100.0, bottom)
        arts.append(_make_artifact(f"a{i+1}", text, order=i + 1, page=page, heading=heading, bbox=bbox))
    return arts


class OverextendedChainBackwardTests(unittest.TestCase):
    """Backward-chain: bound artifact sits in the middle/end of the chain."""

    def test_backward_chain_overextension_detected(self):
        """Three-block chain A→B→C; bound=B; evidence spans B+C only.
        A shorter subchain [B, C] also contains the evidence → over-extended.
        A's text must not end with a sentence terminator (otherwise A→B is not
        stitchable and the chain itself is invalid).
        """
        arts = _stacked_artifacts(["前置内容描述", "支气管舒张试验阳性", "提示可逆性气流受限"])
        artifact_map = {a.id: a for a in arts}
        ids = [a.id for a in arts]

        evidence_loose = normalize_loose("支气管舒张试验阳性提示可逆性气流受限")
        bound_id = arts[1].id  # B
        desc = _detect_overextended_chain(ids, artifact_map, evidence_loose, bound_artifact_id=bound_id)
        self.assertIsNotNone(desc, "must detect that [B, C] subchain also contains evidence")
        self.assertIn(arts[1].id, desc or "")
        self.assertIn(arts[2].id, desc or "")

    def test_backward_chain_not_overextended_when_evidence_spans_full(self):
        """Three-block chain A→B→C; bound=A; evidence spans A+B+C.
        No shorter subchain contains the complete evidence → not over-extended.
        """
        arts = _stacked_artifacts([
            "哮喘是慢性气道炎症性疾病",  # ends without 。
            "临床表现为反复发作的喘息",  # ends without 。
            "气促胸闷和咳嗽",           # ends without 。
        ])
        artifact_map = {a.id: a for a in arts}
        ids = [a.id for a in arts]

        evidence_loose = normalize_loose(
            "哮喘是慢性气道炎症性疾病临床表现为反复发作的喘息气促胸闷和咳嗽"
        )
        bound_id = arts[0].id
        desc = _detect_overextended_chain(ids, artifact_map, evidence_loose, bound_artifact_id=bound_id)
        self.assertIsNone(desc, "full chain is the shortest containing evidence; not over-extended")

    def test_bound_in_middle_overextension(self):
        """Four-block chain A→B→C→D; bound=B; evidence spans B+C only.
        Shorter subchain [B, C] also contains the evidence → over-extended.
        """
        arts = _stacked_artifacts([
            "前言部分",                 # ends without 。
            "肺结核是由结核分枝杆菌引起的传染病",  # ends without 。
            "主要经呼吸道传播",         # ends without 。
            "结尾部分",                 # ends without 。
        ])
        artifact_map = {a.id: a for a in arts}
        ids = [a.id for a in arts]

        evidence_loose = normalize_loose(
            "肺结核是由结核分枝杆菌引起的传染病主要经呼吸道传播"
        )
        bound_id = arts[1].id  # B
        desc = _detect_overextended_chain(ids, artifact_map, evidence_loose, bound_artifact_id=bound_id)
        self.assertIsNotNone(desc, "must detect that [B, C] subchain also contains evidence")
        self.assertIn(arts[1].id, desc or "")
        self.assertIn(arts[2].id, desc or "")


class OverextendedChainASCIIBoundaryTests(unittest.TestCase):
    """ASCII/alnum boundary: _join_raw_fragments inserts a space between
    ASCII alnum chars at fragment boundaries, changing loose normalization.
    The audit must use the same joiner.
    """

    def test_ascii_boundary_overextension_with_space_insertion(self):
        """A ends with "5" (ASCII alnum), B starts with "mg" (ASCII alnum).
        _join_raw_fragments("...5", "mg...") → "...5 mg...".
        normalize_loose removes the space, so the join is still detectable.
        Chain [A, B, C] with evidence spanning A+B only → must detect [A, B] shorter subchain.
        """
        arts = _stacked_artifacts([
            "起始剂量为氨茶碱5",   # ends with ASCII alnum 5
            "mg/kg体重",          # starts with ASCII alnum m
            "后续内容可拼接但不参与证据",
        ])
        artifact_map = {a.id: a for a in arts}
        ids = [a.id for a in arts]

        evidence_loose = normalize_loose("起始剂量为氨茶碱5mg/kg体重")
        bound_id = arts[0].id
        desc = _detect_overextended_chain(ids, artifact_map, evidence_loose, bound_artifact_id=bound_id)
        self.assertIsNotNone(
            desc,
            "must detect [A, B] shorter subchain even with ASCII boundary space insertion"
        )
        self.assertIn(arts[0].id, desc or "")
        self.assertIn(arts[1].id, desc or "")

    def test_ascii_boundary_no_false_positive_when_full_chain_required(self):
        """ASCII boundary at every fragment; evidence spans all three.
        No shorter subchain contains complete evidence → not over-extended.

        Junction A→B: A ends with ASCII digit '0', B starts with CJK '每' →
        LATIN_OR_DIGIT + CJK → valid continuation.
        Junction B→C: B ends with CJK '次', C starts with CJK '持' → CJK+CJK → valid.
        """
        arts = _stacked_artifacts([
            "VitD3 400",        # ends with ASCII alnum 0
            "每日一次",          # starts with CJK 每
            "持续6周后复查",
        ])
        artifact_map = {a.id: a for a in arts}
        ids = [a.id for a in arts]

        evidence_loose = normalize_loose("VitD3 400每日一次持续6周后复查")
        bound_id = arts[0].id
        desc = _detect_overextended_chain(ids, artifact_map, evidence_loose, bound_artifact_id=bound_id)
        self.assertIsNone(desc, "full chain required; not over-extended")

    def test_ascii_boundary_backward_chain_detection(self):
        """Backward chain with ASCII boundary: bound=B, evidence spans A+B.
        _join_raw_fragments must insert space at A→B boundary; the shorter
        subchain [A, B] must still be detected.
        """
        arts = _stacked_artifacts([
            "剂量为地塞米松5",   # ends with ASCII alnum 5
            "mg静脉注射",        # starts with ASCII alnum m
            "后续监测血压心率",
        ])
        artifact_map = {a.id: a for a in arts}
        ids = [a.id for a in arts]

        evidence_loose = normalize_loose("剂量为地塞米松5mg静脉注射")
        bound_id = arts[1].id  # B (middle position)
        desc = _detect_overextended_chain(ids, artifact_map, evidence_loose, bound_artifact_id=bound_id)
        self.assertIsNotNone(
            desc, "must detect [A, B] subchain with backward + ASCII boundary"
        )
        self.assertIn(arts[0].id, desc or "")
        self.assertIn(arts[1].id, desc or "")


class OverextendedChainEdgeCases(unittest.TestCase):
    """Additional edge cases for robustness."""

    def test_single_artifact_chain_returns_none(self):
        arts = _stacked_artifacts(["短内容"])
        artifact_map = {a.id: a for a in arts}
        desc = _detect_overextended_chain(
            [arts[0].id], artifact_map, normalize_loose("短内容"), bound_artifact_id=arts[0].id
        )
        self.assertIsNone(desc, "single-artifact chain cannot be over-extended")

    def test_short_evidence_returns_none(self):
        arts = _stacked_artifacts(["短内容", "更多内容"])
        artifact_map = {a.id: a for a in arts}
        # evidence_loose length < 8
        desc = _detect_overextended_chain(
            [arts[0].id, arts[1].id], artifact_map, normalize_loose("短"), bound_artifact_id=arts[0].id
        )
        self.assertIsNone(desc, "short evidence (< 8 chars) skips over-extension check")

    def test_bound_not_in_chain_returns_error(self):
        arts = _stacked_artifacts(["内容一", "内容二"])
        artifact_map = {a.id: a for a in arts}
        desc = _detect_overextended_chain(
            [arts[0].id, arts[1].id],
            artifact_map,
            normalize_loose("内容一内容二三四五六七八"),
            bound_artifact_id="missing-id",
        )
        self.assertIsNotNone(desc)
        self.assertIn("not in chain", desc or "")

    def test_unresolved_artifact_returns_error(self):
        arts = _stacked_artifacts(["内容一"])
        artifact_map = {a.id: a for a in arts}  # missing second
        desc = _detect_overextended_chain(
            [arts[0].id, "missing-id"],
            artifact_map,
            normalize_loose("内容一内容二三四五六七八"),
            bound_artifact_id=arts[0].id,
        )
        self.assertIsNotNone(desc)
        self.assertIn("unresolved", desc or "")


if __name__ == "__main__":
    unittest.main()
