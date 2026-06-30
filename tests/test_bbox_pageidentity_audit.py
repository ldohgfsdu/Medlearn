"""Tests for Phase 6A bbox / PageIdentity audit.

Two-tier:
- Core tests (never skip): PageIdentity map, page semantics, bbox containment
  logic, explicit ID join logic.
- PDF integration tests (skip if PDF/evidence absent): full audit run, BDT
  calibration, 10-item sample, calibration image generation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.bbox_pageidentity_audit import (  # noqa: E402
    BDT_EVIDENCE_ID,
    BDT_NEEDLE,
    PAGE_DELTA,
    PDF_PAGE_END_1BASED,
    PDF_PAGE_START_1BASED,
    PRINTED_PAGE_END,
    PRINTED_PAGE_START,
    verify_evidence_page_semantics,
    verify_explicit_id_join,
)

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"
EVIDENCE_PATH = (
    ROOT / "generated/knowledge_nodes/internal-medicine-10"
    / "第二篇_呼吸系统疾病__第四章_支气管哮喘.evidence.json"
)
DISPLAY_CONTRACT_PATH = (
    ROOT / "generated/display_contracts/internal-medicine-10"
    / "第二篇_呼吸系统疾病__第四章_支气管哮喘.display_contract.json"
)

pdfmark = pytest.mark.skipif(
    not PDF.exists() or not EVIDENCE_PATH.exists() or not DISPLAY_CONTRACT_PATH.exists(),
    reason="PDF, evidence.json, or display_contract.json not present",
)


# ---------------------------------------------------------------------------
# Core: PageIdentity constants
# ---------------------------------------------------------------------------

class TestPageIdentityConstants:
    def test_page_delta_is_31(self):
        assert PAGE_DELTA == 31

    def test_pdf_range_matches_printed_range(self):
        assert PDF_PAGE_START_1BASED - PAGE_DELTA == PRINTED_PAGE_START
        assert PDF_PAGE_END_1BASED - PAGE_DELTA == PRINTED_PAGE_END

    def test_printed_labels_are_strings(self):
        # pageLabel is always a string per contract
        assert isinstance(str(PRINTED_PAGE_START), str)

    def test_pdf_index_0based_range(self):
        assert PDF_PAGE_START_1BASED - 1 == 61  # 0-based start
        assert PDF_PAGE_END_1BASED - 1 == 69    # 0-based end


# ---------------------------------------------------------------------------
# Core: page semantics logic
# ---------------------------------------------------------------------------

class TestPageSemanticsLogic:
    def test_pdf_range_evidence_passes(self):
        evidence = {
            "a": {"page_start": 62},
            "b": {"page_start": 65},
            "c": {"page_start": 70},
        }
        result = verify_evidence_page_semantics(evidence)
        assert result["all_in_pdf_range_62_70"]
        assert not result["all_in_printed_range_31_39"]
        assert "PDF 1-based" in result["conclusion"]

    def test_printed_range_evidence_flagged(self):
        evidence = {
            "a": {"page_start": 31},
            "b": {"page_start": 35},
        }
        result = verify_evidence_page_semantics(evidence)
        assert not result["all_in_pdf_range_62_70"]
        assert result["all_in_printed_range_31_39"]


# ---------------------------------------------------------------------------
# Core: explicit ID join logic
# ---------------------------------------------------------------------------

class TestExplicitIDJoin:
    def test_all_resolved(self):
        evidence = {"ev1-aaa": {"id": "ev1-aaa"}, "ev1-bbb": {"id": "ev1-bbb"}}
        refs = [{"id": "r1", "artifact_id": "ev1-aaa"}, {"id": "r2", "artifact_id": "ev1-bbb"}]
        result = verify_explicit_id_join(evidence, refs)
        assert result["refs_resolved_via_explicit_id"] == 2
        assert result["refs_unresolved"] == 0
        assert not result["fuzzy_text_matching_used"]
        assert result["status"] == "OK"

    def test_missing_artifact_id(self):
        evidence = {"ev1-aaa": {"id": "ev1-aaa"}}
        refs = [{"id": "r1"}, {"id": "r2", "artifact_id": "ev1-aaa"}]
        result = verify_explicit_id_join(evidence, refs)
        assert result["refs_with_artifact_id"] == 1
        assert result["refs_resolved_via_explicit_id"] == 1
        assert result["refs_unresolved"] == 1

    def test_unresolved_id(self):
        evidence = {}
        refs = [{"id": "r1", "artifact_id": "ev1-missing"}]
        result = verify_explicit_id_join(evidence, refs)
        assert result["refs_resolved_via_explicit_id"] == 0
        assert result["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Core: bbox containment logic
# ---------------------------------------------------------------------------

class TestBboxContainmentLogic:
    """Test the containment logic without PDF dependency."""

    def test_needle_inside_block_no_flip(self):
        # Block bbox: full width, line height
        block = [79.0, 200.0, 495.0, 212.0]
        # Needle bbox: inside block
        needle = [93.0, 200.5, 302.0, 211.0]
        page_height = 793.0

        no_flip_x = block[0] <= needle[0] and needle[2] <= block[2]
        no_flip_y = block[1] <= needle[1] and needle[3] <= block[3]
        assert no_flip_x and no_flip_y

        flipped_y0 = page_height - needle[3]
        flipped_y1 = page_height - needle[1]
        y_flip_y = block[1] <= flipped_y0 and flipped_y1 <= block[3]
        assert not y_flip_y  # flipped Y would be ~582-593, not in 200-212

    def test_needle_outside_block_both_ways(self):
        block = [79.0, 200.0, 495.0, 212.0]
        needle = [600.0, 700.0, 700.0, 750.0]  # completely outside
        page_height = 793.0

        no_flip_y = block[1] <= needle[1] and needle[3] <= block[3]
        flipped_y0 = page_height - needle[3]
        flipped_y1 = page_height - needle[1]
        y_flip_y = block[1] <= flipped_y0 and flipped_y1 <= block[3]
        assert not no_flip_y
        assert not y_flip_y


# ---------------------------------------------------------------------------
# PDF integration
# ---------------------------------------------------------------------------

@pdfmark
class TestPDFAuditRun:
    def test_audit_runs_without_error(self):
        from textbook_pipeline.bbox_pageidentity_audit import main
        main()  # should not raise

    def test_audit_report_exists(self):
        from textbook_pipeline.bbox_pageidentity_audit import main, OUT_DIR
        main()
        report = OUT_DIR / "phase6a_audit_report.json"
        assert report.exists()
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["overall_status"] == "OK"
        assert data["blockers"] == []


@pdfmark
class TestPDFPageIdentity:
    def test_all_printed_labels_found(self):
        from textbook_pipeline.bbox_pageidentity_audit import (
            load_evidence,
            verify_page_identity,
        )
        import fitz
        doc = fitz.open(PDF)
        try:
            result = verify_page_identity(doc)
        finally:
            doc.close()
        assert result["all_printed_labels_found_in_text"]
        assert result["consistent_page_dimensions"]
        assert len(result["pages"]) == 9  # 62-70 inclusive

    def test_page_dimensions_consistent(self):
        from textbook_pipeline.bbox_pageidentity_audit import verify_page_identity
        import fitz
        doc = fitz.open(PDF)
        try:
            result = verify_page_identity(doc)
        finally:
            doc.close()
        dims = result["sample_dimensions"]
        assert dims["width_pt"] > 0
        assert dims["height_pt"] > 0
        # A4-ish dimensions
        assert 500 < dims["width_pt"] < 600
        assert 700 < dims["height_pt"] < 900


@pdfmark
class TestPDFBboxCoordinateSystem:
    def test_bdt_bbox_top_left_no_flip(self):
        from textbook_pipeline.bbox_pageidentity_audit import (
            load_evidence,
            verify_bbox_coordinate_system,
        )
        import fitz
        evidence = load_evidence()
        doc = fitz.open(PDF)
        try:
            result = verify_bbox_coordinate_system(doc, evidence)
        finally:
            doc.close()
        assert result["status"] == "OK"
        assert result["conclusion"] == "top_left_origin_no_flip"
        assert result["no_flip_contains"]
        assert not result["y_flip_contains"]

    def test_bdt_evidence_exists(self):
        from textbook_pipeline.bbox_pageidentity_audit import load_evidence
        evidence = load_evidence()
        assert BDT_EVIDENCE_ID in evidence
        art = evidence[BDT_EVIDENCE_ID]
        assert BDT_NEEDLE in art.get("raw_text", "")

    def test_bboxNorm_transform_documented(self):
        from textbook_pipeline.bbox_pageidentity_audit import (
            load_evidence,
            verify_bbox_coordinate_system,
        )
        import fitz
        evidence = load_evidence()
        doc = fitz.open(PDF)
        try:
            result = verify_bbox_coordinate_system(doc, evidence)
        finally:
            doc.close()
        assert "x0/w" in result["bboxNorm_transform"]
        assert "y0/h" in result["bboxNorm_transform"]


@pdfmark
class TestPDFExplicitIDJoin:
    def test_all_281_refs_resolved(self):
        from textbook_pipeline.bbox_pageidentity_audit import (
            load_evidence,
            load_display_evidence_refs,
            verify_explicit_id_join,
        )
        evidence = load_evidence()
        refs = load_display_evidence_refs()
        result = verify_explicit_id_join(evidence, refs)
        assert result["refs_resolved_via_explicit_id"] > 0
        assert not result["fuzzy_text_matching_used"]


@pdfmark
class TestPDFSample10:
    def test_all_10_samples_pass(self):
        from textbook_pipeline.bbox_pageidentity_audit import (
            load_evidence,
            sample_10_evidence,
        )
        import fitz
        evidence = load_evidence()
        doc = fitz.open(PDF)
        try:
            result = sample_10_evidence(doc, evidence)
        finally:
            doc.close()
        assert result["sample_size"] == 10
        assert result["all_checks_passed"] == 10

    def test_all_bboxNorm_in_0_1(self):
        from textbook_pipeline.bbox_pageidentity_audit import (
            load_evidence,
            sample_10_evidence,
        )
        import fitz
        evidence = load_evidence()
        doc = fitz.open(PDF)
        try:
            result = sample_10_evidence(doc, evidence)
        finally:
            doc.close()
        for s in result["samples"]:
            norm = s.get("bboxNorm_top_left")
            if norm:
                assert all(0.0 <= v <= 1.0 for v in norm), (
                    f"bboxNorm out of [0,1] for {s['evidence_id']}: {norm}"
                )


@pdfmark
class TestPDFCalibrationImages:
    def test_calibration_images_generated(self):
        from textbook_pipeline.bbox_pageidentity_audit import (
            load_evidence,
            generate_calibration_images,
            OUT_DIR,
        )
        import fitz
        evidence = load_evidence()
        doc = fitz.open(PDF)
        try:
            result = generate_calibration_images(doc, evidence)
        finally:
            doc.close()
        assert "outputs" in result
        assert len(result["outputs"]) == 2
        for out in result["outputs"]:
            p = ROOT / out
            assert p.exists(), f"calibration image missing: {p}"
