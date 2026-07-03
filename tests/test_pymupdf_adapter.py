"""Tests for the PyMuPDF adapter.

Two-tier (per project convention):
- Core tests (never skip): fingerprint normalization determinism,
  compute_source_pdf_sha256, synthetic RawSpan -> anchor ID stability.
- PDF integration tests (skip if source PDF absent): real asthma page
  scanned twice, anchor IDs must be byte-identical across runs.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.adapters.pymupdf_adapter import (  # noqa: E402
    PymupdfDocumentSnapshot,
    PymupdfPageSnapshot,
    _normalize_span_for_fingerprint,
    compute_source_pdf_sha256,
)
from textbook_pipeline.document_ir import (  # noqa: E402
    PageIdentity,
    RawSpan,
    build_source_anchor,
)

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"
ASTHMA_PDF_PAGE_1BASED = 62  # first asthma page (printed label "31")
TEXTBOOK_VERSION_ID = "internal-medicine-10"
SCOPE_ID = "第二篇_呼吸系统疾病__第四章_支气管哮喘"

_pdf_available = PDF.exists()


def _make_synthetic_span(text: str = "哮喘", font: str = "SimSun", size: float = 10.5):
    return _normalize_span_for_fingerprint(
        text=text,
        font=font,
        size=size,
        bbox=[72.0, 100.0, 144.0, 112.5],
        color=0,
        flags=0,
    )


class NormalizeSpanFingerprintTests(unittest.TestCase):
    def test_deterministic_output_for_same_input(self):
        a = _make_synthetic_span(text="支气管哮喘", size=12.0)
        b = _make_synthetic_span(text="支气管哮喘", size=12.0)
        self.assertEqual(a, b)

    def test_float_rounding_absorbs_subpixel_noise(self):
        a = _normalize_span_for_fingerprint(
            text="x", font="f", size=10.0001,
            bbox=[72.00001, 100.00002, 144.00003, 112.50004],
            color=0, flags=0,
        )
        b = _normalize_span_for_fingerprint(
            text="x", font="f", size=10.0009,
            bbox=[72.00009, 100.00008, 144.00007, 112.50006],
            color=0, flags=0,
        )
        self.assertEqual(a, b)

    def test_all_values_json_serializable(self):
        import json
        span = _make_synthetic_span(text="测试", size=9.0)
        payload = json.dumps([span], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertIn("测试", payload)


class ComputeSourcePdfSha256Tests(unittest.TestCase):
    def test_full_256_bit_hex(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(b"%PDF-1.4 test payload\n")
            tmp_path = Path(tmp.name)
        try:
            sha = compute_source_pdf_sha256(tmp_path)
            self.assertEqual(len(sha), 64)
            int(sha, 16)  # valid hex
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_deterministic_for_same_content(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(b"deterministic content\n")
            tmp_path = Path(tmp.name)
        try:
            sha1 = compute_source_pdf_sha256(tmp_path)
            sha2 = compute_source_pdf_sha256(tmp_path)
            self.assertEqual(sha1, sha2)
        finally:
            tmp_path.unlink(missing_ok=True)


class SyntheticAnchorIdStabilityTests(unittest.TestCase):
    """Same RawSpan -> same anchor ID, always (core guarantee)."""

    def _anchor_id(self, span: RawSpan, source_sha: str = "a" * 64) -> str:
        return build_source_anchor(
            span,
            textbook_version_id=TEXTBOOK_VERSION_ID,
            scope_id=SCOPE_ID,
            source_pdf_sha256=source_sha,
        ).id

    def test_identical_raw_span_produces_identical_anchor_id(self):
        span = RawSpan(
            pdf_page_number=62,
            block_index=0,
            line_index=0,
            spans=(_make_synthetic_span(),),
        )
        self.assertEqual(self._anchor_id(span), self._anchor_id(span))

    def test_different_text_produces_different_anchor_id(self):
        span_a = RawSpan(62, 0, 0, (_make_synthetic_span(text="哮喘"),))
        span_b = RawSpan(62, 0, 0, (_make_synthetic_span(text="肺结核"),))
        self.assertNotEqual(self._anchor_id(span_a), self._anchor_id(span_b))

    def test_different_position_produces_different_anchor_id(self):
        span_a = RawSpan(62, 0, 0, (_make_synthetic_span(),))
        span_b = RawSpan(62, 0, 1, (_make_synthetic_span(),))
        self.assertNotEqual(self._anchor_id(span_a), self._anchor_id(span_b))

    def test_different_source_pdf_produces_different_anchor_id(self):
        span = RawSpan(62, 0, 0, (_make_synthetic_span(),))
        self.assertNotEqual(
            self._anchor_id(span, source_sha="a" * 64),
            self._anchor_id(span, source_sha="b" * 64),
        )


@unittest.skipUnless(_pdf_available, "asthma source PDF not present")
class AsthmaPageAnchorIdStabilityTests(unittest.TestCase):
    """PDF integration: scan real asthma page twice, anchor IDs must match."""

    def _scan_asthma_page(self) -> PymupdfDocumentSnapshot:
        from textbook_pipeline.adapters.pymupdf_adapter import scan_pdf_pages
        return scan_pdf_pages(PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED])

    def _anchor_ids(self, snapshot: PymupdfDocumentSnapshot) -> list[str]:
        page: PymupdfPageSnapshot = snapshot.pages[0]
        return [
            build_source_anchor(
                span,
                textbook_version_id=TEXTBOOK_VERSION_ID,
                scope_id=SCOPE_ID,
                source_pdf_sha256=snapshot.source_pdf_sha256,
            ).id
            for span in page.raw_spans
        ]

    def test_asthma_page_has_nonempty_raw_spans(self):
        snapshot = self._scan_asthma_page()
        self.assertEqual(len(snapshot.pages), 1)
        page = snapshot.pages[0]
        self.assertGreater(len(page.raw_spans), 0)
        self.assertEqual(page.page_identity.pdf_page_number, ASTHMA_PDF_PAGE_1BASED)
        self.assertIsNotNone(page.page_identity.width)
        self.assertIsNotNone(page.page_identity.height)

    def test_anchor_ids_identical_across_reruns(self):
        snap_a = self._scan_asthma_page()
        snap_b = self._scan_asthma_page()
        ids_a = self._anchor_ids(snap_a)
        ids_b = self._anchor_ids(snap_b)
        self.assertEqual(ids_a, ids_b)

    def test_source_pdf_sha256_identical_across_reruns(self):
        snap_a = self._scan_asthma_page()
        snap_b = self._scan_asthma_page()
        self.assertEqual(snap_a.source_pdf_sha256, snap_b.source_pdf_sha256)
        self.assertEqual(len(snap_a.source_pdf_sha256), 64)

    def test_anchor_ids_contain_full_pdf_sha256_binding(self):
        snapshot = self._scan_asthma_page()
        ids = self._anchor_ids(snapshot)
        self.assertGreater(len(ids), 0)
        for aid in ids:
            self.assertIn(snapshot.source_pdf_sha256, aid)
            self.assertTrue(aid.startswith(f"dt:{TEXTBOOK_VERSION_ID}:{SCOPE_ID}:"))


if __name__ == "__main__":
    unittest.main()
