"""Tests for the Docling adapter.

Two-tier (per project convention):
- Core tests (never skip): fingerprint normalization determinism,
  JSON serializability, synthetic RawSpan -> anchor ID stability,
  lazy-import guard (module loads without Docling runtime).
- PDF integration tests (skip if Docling cannot import or source PDF
  absent): real asthma page scanned twice, anchor IDs must be
  byte-identical across reruns.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.adapters.docling_adapter import (  # noqa: E402
    DOCLING_DEFAULT_COLOR,
    DOCLING_DEFAULT_FLAGS,
    DOCLING_DEFAULT_FONT,
    DOCLING_DEFAULT_SIZE,
    DoclingDocumentSnapshot,
    _normalize_docling_cell_for_fingerprint,
)
from textbook_pipeline.document_ir import (  # noqa: E402
    RawSpan,
    build_source_anchor,
)

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"
ASTHMA_PDF_PAGE_1BASED = 62
TEXTBOOK_VERSION_ID = "internal-medicine-10"
SCOPE_ID = "第二篇_呼吸系统疾病__第四章_支气管哮喘"


def _docling_runtime_available() -> bool:
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401
        return True
    except Exception:
        return False


# Lazy-evaluated to avoid triggering Docling's heavy import chain at module
# load time (can cause MemoryError on constrained page files).
_docling_ok = None
_pdf_available = PDF.exists()


def _make_docling_span(
    text: str = "哮喘",
    bbox_ltrb: list[float] | None = None,
    confidence: float = 1.0,
    from_ocr: bool = False,
):
    if bbox_ltrb is None:
        bbox_ltrb = [72.0, 100.0, 144.0, 112.5]
    return _normalize_docling_cell_for_fingerprint(
        text=text,
        bbox_ltrb=bbox_ltrb,
        confidence=confidence,
        from_ocr=from_ocr,
    )


class NormalizeDoclingCellFingerprintTests(unittest.TestCase):
    def test_deterministic_output_for_same_input(self):
        a = _make_docling_span(text="支气管哮喘", confidence=0.95)
        b = _make_docling_span(text="支气管哮喘", confidence=0.95)
        self.assertEqual(a, b)

    def test_float_rounding_absorbs_subpixel_noise(self):
        a = _make_docling_span(
            text="x",
            bbox_ltrb=[72.00001, 100.00002, 144.00003, 112.50004],
            confidence=0.99991,
        )
        b = _make_docling_span(
            text="x",
            bbox_ltrb=[72.00009, 100.00008, 144.00007, 112.50006],
            confidence=0.99998,
        )
        self.assertEqual(a, b)

    def test_sentinel_defaults_for_font_size_color_flags(self):
        span = _make_docling_span()
        self.assertEqual(span["font"], DOCLING_DEFAULT_FONT)
        self.assertEqual(span["size"], DOCLING_DEFAULT_SIZE)
        self.assertEqual(span["color"], DOCLING_DEFAULT_COLOR)
        self.assertEqual(span["flags"], DOCLING_DEFAULT_FLAGS)

    def test_docling_provenance_fields_retained(self):
        span = _make_docling_span(confidence=0.88, from_ocr=True)
        self.assertEqual(span["docling_confidence"], 0.88)
        self.assertTrue(span["docling_from_ocr"])

    def test_all_values_json_serializable(self):
        import json
        span = _make_docling_span(text="测试", confidence=0.5, from_ocr=True)
        payload = json.dumps([span], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertIn("测试", payload)
        self.assertIn("docling_from_ocr", payload)


class DoclingModuleLazyImportTests(unittest.TestCase):
    """Module must load even when Docling runtime is unavailable."""

    def test_module_importable_without_docling_runtime(self):
        # This test itself proves the module loaded — the imports at the
        # top of this file would have failed otherwise.
        import textbook_pipeline.adapters.docling_adapter as mod
        self.assertTrue(hasattr(mod, "scan_pdf_pages"))
        self.assertTrue(hasattr(mod, "DoclingDocumentSnapshot"))

    def test_compute_source_pdf_sha256_delegated_to_pymupdf_adapter(self):
        # Docling adapter reuses the canonical SHA-256 implementation
        # so all parsers share the same source-pdf binding contract.
        from textbook_pipeline.adapters.docling_adapter import compute_source_pdf_sha256
        from textbook_pipeline.adapters.pymupdf_adapter import (
            compute_source_pdf_sha256 as pymupdf_sha,
        )
        self.assertIs(compute_source_pdf_sha256, pymupdf_sha)


class SyntheticAnchorIdStabilityTests(unittest.TestCase):
    """Same Docling RawSpan -> same anchor ID, always."""

    def _anchor_id(self, span: RawSpan, source_sha: str = "a" * 64) -> str:
        return build_source_anchor(
            span,
            textbook_version_id=TEXTBOOK_VERSION_ID,
            scope_id=SCOPE_ID,
            source_pdf_sha256=source_sha,
        ).id

    def test_identical_docling_span_produces_identical_anchor_id(self):
        span = RawSpan(
            pdf_page_number=62,
            block_index=0,
            line_index=0,
            spans=(_make_docling_span(),),
        )
        self.assertEqual(self._anchor_id(span), self._anchor_id(span))

    def test_different_text_produces_different_anchor_id(self):
        span_a = RawSpan(62, 0, 0, (_make_docling_span(text="哮喘"),))
        span_b = RawSpan(62, 0, 0, (_make_docling_span(text="肺结核"),))
        self.assertNotEqual(self._anchor_id(span_a), self._anchor_id(span_b))

    def test_different_cell_index_produces_different_anchor_id(self):
        span_a = RawSpan(62, 0, 0, (_make_docling_span(),))
        span_b = RawSpan(62, 0, 5, (_make_docling_span(),))
        self.assertNotEqual(self._anchor_id(span_a), self._anchor_id(span_b))

    def test_different_ocr_flag_produces_different_anchor_id(self):
        """OCR vs non-OCR provenance must be distinguishable in the anchor."""
        span_native = RawSpan(62, 0, 0, (_make_docling_span(from_ocr=False),))
        span_ocr = RawSpan(62, 0, 0, (_make_docling_span(from_ocr=True),))
        self.assertNotEqual(self._anchor_id(span_native), self._anchor_id(span_ocr))

    def test_different_source_pdf_produces_different_anchor_id(self):
        span = RawSpan(62, 0, 0, (_make_docling_span(),))
        self.assertNotEqual(
            self._anchor_id(span, source_sha="a" * 64),
            self._anchor_id(span, source_sha="b" * 64),
        )

    def test_docling_anchor_id_differs_from_pymupdf_for_same_text_bbox(self):
        """Cross-parser: same text+bbox but different font/size/flags payload
        must produce different anchor IDs (known divergence, parity-accepted)."""
        from textbook_pipeline.adapters.pymupdf_adapter import (
            _normalize_span_for_fingerprint as pymupdf_norm,
        )
        docling_span = RawSpan(62, 0, 0, (_make_docling_span(text="哮喘"),))
        pymupdf_span = RawSpan(
            62, 0, 0,
            (pymupdf_norm(text="哮喘", font="SimSun", size=10.5,
                          bbox=[72.0, 100.0, 144.0, 112.5], color=0, flags=0),),
        )
        self.assertNotEqual(self._anchor_id(docling_span), self._anchor_id(pymupdf_span))


@unittest.skipUnless(_pdf_available, "source PDF not available")
class AsthmaPageDoclingAnchorIdStabilityTests(unittest.TestCase):
    """PDF integration: scan real asthma page twice, anchor IDs must match."""

    @classmethod
    def setUpClass(cls):
        global _docling_ok
        if _docling_ok is None:
            _docling_ok = _docling_runtime_available()
        if not _docling_ok:
            raise unittest.SkipTest("Docling runtime not available")
    def _scan_asthma_page(self) -> DoclingDocumentSnapshot:
        from textbook_pipeline.adapters.docling_adapter import scan_pdf_pages
        return scan_pdf_pages(PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED])

    def _anchor_ids(self, snapshot: DoclingDocumentSnapshot) -> list[str]:
        page = snapshot.pages[0]
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
        self.assertGreater(page.page_identity.width, 0)
        self.assertGreater(page.page_identity.height, 0)

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


if __name__ == "__main__":
    unittest.main()
