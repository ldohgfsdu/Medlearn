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
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.adapters.docling_adapter import (  # noqa: E402
    DOCLING_DEFAULT_COLOR,
    DOCLING_DEFAULT_FLAGS,
    DOCLING_DEFAULT_FONT,
    DOCLING_DEFAULT_SIZE,
    DoclingDocumentSnapshot,
    _contiguous_page_ranges,
    _convert_page,
    _normalize_docling_cell_for_fingerprint,
    probe_docling_runtime,
)
from textbook_pipeline.document_ir import (  # noqa: E402
    RawSpan,
    build_source_anchor,
)

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"
ASTHMA_PDF_PAGE_1BASED = 62
TEXTBOOK_VERSION_ID = "internal-medicine-10"
SCOPE_ID = "第二篇_呼吸系统疾病__第四章_支气管哮喘"


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

    @mock.patch(
        "textbook_pipeline.adapters.docling_adapter.subprocess.run"
    )
    def test_runtime_probe_uses_isolated_subprocess(self, run):
        run.return_value.returncode = 0
        self.assertTrue(probe_docling_runtime(timeout_seconds=7.5))
        self.assertEqual(run.call_args.kwargs["timeout"], 7.5)
        self.assertIn(
            "docling.document_converter",
            run.call_args.args[0][-1],
        )

    @mock.patch(
        "textbook_pipeline.adapters.docling_adapter.subprocess.run",
        side_effect=TimeoutError,
    )
    def test_runtime_probe_returns_false_on_timeout(self, _run):
        self.assertFalse(probe_docling_runtime(timeout_seconds=0.01))


class DoclingPageConversionTests(unittest.TestCase):
    def test_bottom_left_bbox_is_converted_to_top_left_origin(self):
        class FakeBBox:
            l = 10.0
            t = 120.0
            r = 20.0
            b = 100.0

            def __init__(self):
                self.converted_with = None

            def to_top_left_origin(self, *, page_height):
                self.converted_with = page_height
                return types.SimpleNamespace(
                    l=self.l,
                    t=page_height - self.t,
                    r=self.r,
                    b=page_height - self.b,
                )

        bbox = FakeBBox()
        cell = types.SimpleNamespace(
            text="test",
            confidence=1.0,
            from_ocr=False,
            to_bounding_box=lambda: bbox,
        )
        page = types.SimpleNamespace(
            size=types.SimpleNamespace(width=100.0, height=200.0),
            cells=[cell],
        )

        snapshot = _convert_page(page, 4)

        self.assertEqual(bbox.converted_with, 200.0)
        self.assertEqual(
            snapshot.raw_spans[0].spans[0]["bbox"],
            [10.0, 80.0, 20.0, 100.0],
        )

    def test_contiguous_page_ranges_are_minimal_and_sorted(self):
        self.assertEqual(
            _contiguous_page_ranges([5, 3, 2, 2, 8, 7]),
            ((2, 3), (5, 5), (7, 8)),
        )

    def test_contiguous_page_ranges_reject_invalid_input(self):
        for invalid in ([], [0], [-1], [True], [1.5]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    _contiguous_page_ranges(invalid)

    def test_scan_converts_only_requested_page_ranges(self):
        calls = []

        class FakeConverter:
            def convert(self, path, *, page_range):
                with fitz.open(path) as compact_pdf:
                    calls.append((page_range, compact_pdf.page_count))
                return types.SimpleNamespace(
                    pages=[
                        types.SimpleNamespace(
                            page_no=page_number,
                            size=types.SimpleNamespace(
                                width=100.0, height=200.0
                            ),
                            cells=[],
                        )
                        for page_number in range(
                            page_range[0], page_range[1] + 1
                        )
                    ]
                )

        from textbook_pipeline.adapters.docling_adapter import scan_pdf_pages

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "fixture.pdf"
            source_pdf = fitz.open()
            try:
                for _ in range(5):
                    source_pdf.new_page(width=100.0, height=200.0)
                source_pdf.save(pdf_path)
            finally:
                source_pdf.close()
            with mock.patch(
                "textbook_pipeline.adapters.docling_adapter."
                "_build_document_converter",
                return_value=FakeConverter(),
            ):
                snapshot = scan_pdf_pages(
                    pdf_path,
                    pdf_pages_1based=[3, 2, 2, 5],
                )

        self.assertEqual(calls, [((1, 3), 3)])
        self.assertEqual(
            [page.page_identity.pdf_page_number for page in snapshot.pages],
            [3, 2, 2, 5],
        )


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

    def test_ocr_flag_does_not_change_anchor_id(self):
        """Parser provenance is retained but excluded from source identity."""
        span_native = RawSpan(62, 0, 0, (_make_docling_span(from_ocr=False),))
        span_ocr = RawSpan(62, 0, 0, (_make_docling_span(from_ocr=True),))
        self.assertEqual(self._anchor_id(span_native), self._anchor_id(span_ocr))

    def test_confidence_does_not_change_anchor_id(self):
        span_a = RawSpan(
            62, 0, 0, (_make_docling_span(confidence=0.51),)
        )
        span_b = RawSpan(
            62, 0, 0, (_make_docling_span(confidence=0.99),)
        )
        self.assertEqual(self._anchor_id(span_a), self._anchor_id(span_b))

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
            _docling_ok = probe_docling_runtime()
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
