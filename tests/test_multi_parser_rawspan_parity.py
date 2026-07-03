"""Cross-parser RawSpan parity tests.

Parity standard (pinned per user spec, 2026-07-03):
  1. Page identity consistency: all parsers agree on pdf_page_number and
     page dimensions for the same PDF page.
  2. Canonical text coverage: each parser extracts non-trivial text from
     the same page; text length is within a documented ratio (not exact
     match, since parsers segment differently).
  3. Reading order monotonicity: within each parser's output, line_index
     is strictly increasing for sequential RawSpans on the same page.
  4. Bbox within page bounds: every span bbox is inside the page
     rectangle (allowing a small tolerance for renderer rounding).
  5. No duplicate or empty RawSpans: no parser emits empty-text spans
     or two identical RawSpans (same fingerprint) on the same page.
  6. Divergence has explicit cause classification: when cross-parser
     anchor IDs differ, the test documents an identity-affecting cause
     (font/size/color/flags absent in Docling vs present in PyMuPDF,
     cell-level vs span-level segmentation, etc.).

Cross-parser anchor ID equality is NOT required (parsers segment and
fingerprint differently). Only same-parser rerun stability is required.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.adapters.pymupdf_adapter import (  # noqa: E402
    PymupdfDocumentSnapshot,
    compute_source_pdf_sha256,
    scan_pdf_pages as pymupdf_scan,
)
from textbook_pipeline.adapters.docling_adapter import (  # noqa: E402
    _normalize_docling_cell_for_fingerprint,
    probe_docling_runtime,
)
from textbook_pipeline.adapters.rapidocr_adapter import (  # noqa: E402
    scan_pdf_pages as rapidocr_scan,
)
from textbook_pipeline.document_ir import (  # noqa: E402
    RawSpan,
    build_source_anchor,
)
from textbook_pipeline.text_layers import canonicalize_source_text  # noqa: E402

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"
ASTHMA_PDF_PAGE_1BASED = 62
TEXTBOOK_VERSION_ID = "internal-medicine-10"
SCOPE_ID = "第二篇_呼吸系统疾病__第四章_支气管哮喘"
BBOX_TOLERANCE_PT = 2.0

_pdf_available = PDF.exists()


# NOTE: _docling_ok is evaluated lazily inside setUpClass to avoid triggering
# Docling's heavy import chain (scipy etc.) at module load time, which can
# cause MemoryError when the system page file is constrained.
_docling_ok = None


def _extract_span_text(span_payload: dict[str, Any]) -> str:
    """Extract canonical text from a span payload dict."""
    return span_payload.get("text", "")


def _extract_span_bbox(span_payload: dict[str, Any]) -> list[float]:
    """Extract bbox [l, t, r, b] from a span payload dict."""
    return list(span_payload.get("bbox", [0, 0, 0, 0]))


def _anchor_ids(snapshot, source_sha: str) -> list[str]:
    """Compute anchor IDs for all RawSpans in the first page of a snapshot."""
    page = snapshot.pages[0]
    return [
        build_source_anchor(
            span,
            textbook_version_id=TEXTBOOK_VERSION_ID,
            scope_id=SCOPE_ID,
            source_pdf_sha256=source_sha,
        ).id
        for span in page.raw_spans
    ]


# ---------------------------------------------------------------------------
# Reusable parity assertion functions (the 6 checks, pinned)
# ---------------------------------------------------------------------------

def assert_page_identity_consistency(
    test: unittest.TestCase,
    snapshots: list[Any],
    expected_page_number: int,
) -> None:
    """Check 1: all parsers agree on pdf_page_number and page dimensions."""
    test.assertTrue(len(snapshots) >= 1)
    base = snapshots[0].pages[0].page_identity
    test.assertEqual(base.pdf_page_number, expected_page_number)
    base_w, base_h = base.width, base.height
    test.assertGreater(base_w, 0)
    test.assertGreater(base_h, 0)
    for snap in snapshots[1:]:
        pid = snap.pages[0].page_identity
        test.assertEqual(pid.pdf_page_number, expected_page_number)
        # Page dimensions may differ by < 1pt due to renderer rounding
        test.assertAlmostEqual(pid.width, base_w, delta=1.0,
                               msg=f"width mismatch: {pid.width} vs {base_w}")
        test.assertAlmostEqual(pid.height, base_h, delta=1.0,
                               msg=f"height mismatch: {pid.height} vs {base_h}")


def assert_canonical_text_coverage(
    test: unittest.TestCase,
    snapshots: list[Any],
    min_spans: int = 1,
    min_relative_coverage: float = 0.5,
) -> None:
    """Check 2: each parser extracts comparable canonical text volume.

    Exact text equality is intentionally not required because parsers segment
    and normalize differently.  The shortest extraction must retain at least
    ``min_relative_coverage`` of the longest extraction on the same page.
    """
    test.assertTrue(snapshots, "at least one parser snapshot is required")
    test.assertGreaterEqual(min_relative_coverage, 0.0)
    test.assertLessEqual(min_relative_coverage, 1.0)
    canonical_lengths: list[int] = []
    for snap in snapshots:
        page = snap.pages[0]
        test.assertGreaterEqual(
            len(page.raw_spans), min_spans,
            f"parser produced too few spans: {len(page.raw_spans)}",
        )
        total_text = "\n".join(
            _extract_span_text(s)
            for span in page.raw_spans
            for s in span.spans
        )
        canonical_text = canonicalize_source_text(total_text)
        test.assertGreater(
            len(canonical_text.strip()), 0,
            "parser produced empty total text",
        )
        canonical_lengths.append(len(canonical_text))

    longest = max(canonical_lengths)
    for length in canonical_lengths:
        test.assertGreaterEqual(
            length / longest,
            min_relative_coverage,
            "parser canonical text coverage is below the allowed ratio: "
            f"{length}/{longest} < {min_relative_coverage:.2f}",
        )


def assert_reading_order_monotonic(test: unittest.TestCase, snapshot: Any) -> None:
    """Check 3: (block_index, line_index) is strictly increasing for sequential RawSpans.

    Cross-block line_index resets are expected (each PDF block has its own
    line 0), so we check the (block_index, line_index) tuple for monotonicity.
    Within the same block, line_index must be strictly increasing.
    """
    page = snapshot.pages[0]
    prev_key: tuple[int, int] | None = None
    for i, span in enumerate(page.raw_spans):
        key = (span.block_index, span.line_index)
        if prev_key is not None:
            test.assertGreater(
                key, prev_key,
                f"reading order not monotonic at index {i}: "
                f"{prev_key} -> {key}",
            )
        prev_key = key


def assert_bbox_within_page_bounds(
    test: unittest.TestCase,
    snapshot: Any,
    tolerance: float = BBOX_TOLERANCE_PT,
) -> None:
    """Check 4: every span bbox is inside the page rectangle."""
    page = snapshot.pages[0]
    w, h = page.page_identity.width, page.page_identity.height
    for span_idx, span in enumerate(page.raw_spans):
        for s_idx, s in enumerate(span.spans):
            bbox = _extract_span_bbox(s)
            test.assertEqual(len(bbox), 4,
                             f"span {span_idx}.{s_idx} bbox not 4-tuple")
            l, t, r, b = bbox
            test.assertLessEqual(l, r + tolerance,
                                 f"span {span_idx}.{s_idx}: l > r")
            test.assertLessEqual(t, b + tolerance,
                                 f"span {span_idx}.{s_idx}: t > b")
            test.assertGreaterEqual(l, -tolerance,
                                    f"span {span_idx}.{s_idx}: l < 0")
            test.assertGreaterEqual(t, -tolerance,
                                    f"span {span_idx}.{s_idx}: t < 0")
            test.assertLessEqual(r, w + tolerance,
                                 f"span {span_idx}.{s_idx}: r > page width")
            test.assertLessEqual(b, h + tolerance,
                                 f"span {span_idx}.{s_idx}: b > page height")


def assert_no_duplicate_or_empty_raw_spans(test: unittest.TestCase, snapshot: Any) -> None:
    """Check 5: no empty-text spans or identical RawSpan fingerprints."""
    page = snapshot.pages[0]
    seen: set[str] = set()
    for span_idx, span in enumerate(page.raw_spans):
        for s_idx, s in enumerate(span.spans):
            text = _extract_span_text(s)
            test.assertTrue(
                text.strip(),
                f"empty-text span at raw_span {span_idx}, sub-span {s_idx}",
            )
        # Dedup by (text, bbox) pair — same text+position is a duplicate
        for s in span.spans:
            key = (_extract_span_text(s), tuple(_extract_span_bbox(s)))
            test.assertNotIn(
                key, seen,
                f"duplicate RawSpan fingerprint: {key}",
            )
            seen.add(key)


def assert_divergence_has_explicit_cause(
    test: unittest.TestCase,
    pymupdf_snapshot: Any,
    docling_snapshot: Any,
) -> None:
    """Check 6: cross-parser anchor ID divergence has a known cause.

    Known causes (must be documented in test output):
    - Docling does not expose font/size/color/flags (sentinel defaults)
    - Docling TextCell is cell-level, PyMuPDF span is line-level
    - Segmentation boundaries differ (one parser may merge/split text)

    Parser provenance fields are intentionally excluded from anchor identity,
    so they are not accepted as an explanation for ID divergence.
    """
    source_sha = pymupdf_snapshot.source_pdf_sha256
    test.assertEqual(
        source_sha, docling_snapshot.source_pdf_sha256,
        "source PDF SHA-256 must match across parsers (same PDF file)",
    )

    pymupdf_ids = set(_anchor_ids(pymupdf_snapshot, source_sha))
    docling_ids = set(_anchor_ids(docling_snapshot, source_sha))

    # Cross-parser anchor IDs are NOT required to be equal.
    # But divergence must be explainable.
    if pymupdf_ids == docling_ids:
        # Unlikely but not invalid — parsers happened to agree.
        return

    # Verify the divergence is caused by known payload differences.
    pymupdf_page = pymupdf_snapshot.pages[0]
    docling_page = docling_snapshot.pages[0]
    known_causes: list[str] = []

    # Known cause 1: Docling uses sentinel font/size/color/flags
    if len(docling_page.raw_spans) > 0 and len(pymupdf_page.raw_spans) > 0:
        first_pymupdf_span = pymupdf_page.raw_spans[0].spans[0]
        first_docling_span = docling_page.raw_spans[0].spans[0]
        if (
            first_docling_span.get("font") == ""
            and first_docling_span.get("size") == 0.0
            and first_docling_span.get("color") == 0
            and first_docling_span.get("flags") == 0
            and any(
                first_pymupdf_span.get(key)
                != first_docling_span.get(key)
                for key in ("font", "size", "color", "flags")
            )
        ):
            known_causes.append("docling_layout_sentinels")
    # Known cause 2: segmentation boundaries differ.
    pymupdf_count = len(pymupdf_page.raw_spans)
    docling_count = len(docling_page.raw_spans)
    if pymupdf_count != docling_count:
        known_causes.append("segmentation_boundary_count")
    elif pymupdf_count and any(
        (
            _extract_span_text(pymupdf_span.spans[0]),
            tuple(_extract_span_bbox(pymupdf_span.spans[0])),
        )
        != (
            _extract_span_text(docling_span.spans[0]),
            tuple(_extract_span_bbox(docling_span.spans[0])),
        )
        for pymupdf_span, docling_span in zip(
            pymupdf_page.raw_spans,
            docling_page.raw_spans,
        )
    ):
        known_causes.append("segmentation_payload_boundary")

    test.assertTrue(
        known_causes,
        "cross-parser anchor divergence has no recognized cause",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class ParityCheckFunctionsTests(unittest.TestCase):
    """Core tests: the 6 parity assertion functions work on synthetic data."""

    def _make_synthetic_snapshot(
        self,
        *,
        spans: list[RawSpan],
        width: float = 595.0,
        height: float = 842.0,
        source_sha: str = "a" * 64,
    ):
        """Build a minimal snapshot-like object for testing parity functions."""
        from textbook_pipeline.adapters.pymupdf_adapter import (
            PymupdfPageSnapshot,
            PymupdfDocumentSnapshot,
        )
        from textbook_pipeline.document_ir import PageIdentity

        page_snap = PymupdfPageSnapshot(
            page_identity=PageIdentity(
                pdf_page_number=62,
                printed_page_label=None,
                width=width,
                height=height,
            ),
            raw_spans=tuple(spans),
        )
        return PymupdfDocumentSnapshot(
            source_pdf_sha256=source_sha,
            pages=(page_snap,),
        )

    def _make_span(self, text: str, line_index: int = 0, bbox=None):
        from textbook_pipeline.adapters.pymupdf_adapter import (
            _normalize_span_for_fingerprint,
        )
        if bbox is None:
            bbox = [72.0, 100.0, 144.0, 112.5]
        return RawSpan(
            pdf_page_number=62,
            block_index=0,
            line_index=line_index,
            spans=(_normalize_span_for_fingerprint(
                text=text, font="f", size=10.0, bbox=bbox, color=0, flags=0,
            ),),
        )

    def test_page_identity_consistency_pass(self):
        snap = self._make_synthetic_snapshot(spans=[self._make_span("test")])
        assert_page_identity_consistency(self, [snap], expected_page_number=62)

    def test_canonical_text_coverage_pass(self):
        snap = self._make_synthetic_snapshot(spans=[self._make_span("test")])
        assert_canonical_text_coverage(self, [snap], min_spans=1)

    def test_canonical_text_coverage_fails_on_large_relative_loss(self):
        full = self._make_synthetic_snapshot(
            spans=[self._make_span("abcdefghij")]
        )
        partial = self._make_synthetic_snapshot(
            spans=[self._make_span("ab")]
        )
        with self.assertRaises(AssertionError):
            assert_canonical_text_coverage(
                self,
                [full, partial],
                min_relative_coverage=0.5,
            )

    def test_reading_order_monotonic_pass(self):
        spans = [
            self._make_span("a", line_index=0),
            self._make_span("b", line_index=1),
            self._make_span("c", line_index=2),
        ]
        snap = self._make_synthetic_snapshot(spans=spans)
        assert_reading_order_monotonic(self, snap)

    def test_reading_order_monotonic_fail(self):
        spans = [
            self._make_span("a", line_index=0),
            self._make_span("b", line_index=0),  # not strictly increasing
        ]
        snap = self._make_synthetic_snapshot(spans=spans)
        with self.assertRaises(AssertionError):
            assert_reading_order_monotonic(self, snap)

    def test_bbox_within_page_bounds_pass(self):
        snap = self._make_synthetic_snapshot(spans=[self._make_span("test")])
        assert_bbox_within_page_bounds(self, snap)

    def test_bbox_within_page_bounds_fail(self):
        span = self._make_span("test", bbox=[-100, -100, 10000, 10000])
        snap = self._make_synthetic_snapshot(spans=[span])
        with self.assertRaises(AssertionError):
            assert_bbox_within_page_bounds(self, snap)

    def test_no_duplicate_or_empty_pass(self):
        spans = [
            self._make_span("a", line_index=0),
            self._make_span("b", line_index=1),
        ]
        snap = self._make_synthetic_snapshot(spans=spans)
        assert_no_duplicate_or_empty_raw_spans(self, snap)

    def test_no_duplicate_or_empty_fail_on_empty(self):
        span = self._make_span("", line_index=0)
        snap = self._make_synthetic_snapshot(spans=[span])
        with self.assertRaises(AssertionError):
            assert_no_duplicate_or_empty_raw_spans(self, snap)

    def test_no_duplicate_or_empty_fail_on_duplicate(self):
        spans = [
            self._make_span("dup", line_index=0),
            self._make_span("dup", line_index=1),
        ]
        snap = self._make_synthetic_snapshot(spans=spans)
        with self.assertRaises(AssertionError):
            assert_no_duplicate_or_empty_raw_spans(self, snap)

    def test_divergence_accepts_known_cause_when_span_counts_match(self):
        pymupdf = self._make_synthetic_snapshot(
            spans=[self._make_span("same")]
        )
        docling_span = RawSpan(
            pdf_page_number=62,
            block_index=0,
            line_index=0,
            spans=(
                _normalize_docling_cell_for_fingerprint(
                    text="same",
                    bbox_ltrb=[72.0, 100.0, 144.0, 112.5],
                    confidence=0.8,
                    from_ocr=False,
                ),
            ),
        )
        docling = self._make_synthetic_snapshot(spans=[docling_span])
        assert_divergence_has_explicit_cause(self, pymupdf, docling)


@unittest.skipUnless(_pdf_available, "asthma source PDF not present")
class PyMuPDFParityIntegrationTests(unittest.TestCase):
    """Run all 5 same-parser parity checks on real PyMuPDF asthma page output."""

    @classmethod
    def setUpClass(cls):
        cls.snapshot = pymupdf_scan(
            PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED]
        )

    def test_01_page_identity(self):
        assert_page_identity_consistency(
            self, [self.snapshot], ASTHMA_PDF_PAGE_1BASED
        )

    def test_02_canonical_text_coverage(self):
        assert_canonical_text_coverage(self, [self.snapshot], min_spans=1)

    def test_03_reading_order_monotonic(self):
        assert_reading_order_monotonic(self, self.snapshot)

    def test_04_bbox_within_page_bounds(self):
        assert_bbox_within_page_bounds(self, self.snapshot)

    def test_05_no_duplicate_or_empty(self):
        assert_no_duplicate_or_empty_raw_spans(self, self.snapshot)

    def test_06_anchor_ids_stable_across_reruns(self):
        snap_b = pymupdf_scan(PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED])
        ids_a = _anchor_ids(self.snapshot, self.snapshot.source_pdf_sha256)
        ids_b = _anchor_ids(snap_b, snap_b.source_pdf_sha256)
        self.assertEqual(ids_a, ids_b)


@unittest.skipUnless(_pdf_available, "asthma source PDF not present")
class RapidocrParityIntegrationTests(unittest.TestCase):
    """Run the same RawSpan parity checks on real RapidOCR page output."""

    @classmethod
    def setUpClass(cls):
        cls.snapshot = rapidocr_scan(
            PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED]
        )

    def test_01_page_identity(self):
        assert_page_identity_consistency(
            self, [self.snapshot], ASTHMA_PDF_PAGE_1BASED
        )

    def test_02_canonical_text_coverage(self):
        assert_canonical_text_coverage(self, [self.snapshot], min_spans=1)

    def test_03_reading_order_monotonic(self):
        assert_reading_order_monotonic(self, self.snapshot)

    def test_04_bbox_within_page_bounds(self):
        assert_bbox_within_page_bounds(self, self.snapshot)

    def test_05_no_duplicate_or_empty(self):
        assert_no_duplicate_or_empty_raw_spans(self, self.snapshot)


@unittest.skipUnless(_pdf_available, "asthma source PDF not present")
class DoclingParityIntegrationTests(unittest.TestCase):
    """Run all 5 same-parser parity checks on real Docling asthma page output."""

    @classmethod
    def setUpClass(cls):
        global _docling_ok
        if _docling_ok is None:
            _docling_ok = probe_docling_runtime()
        if not _docling_ok:
            raise unittest.SkipTest("Docling runtime not available")
        from textbook_pipeline.adapters.docling_adapter import scan_pdf_pages as docling_scan
        cls.snapshot = docling_scan(
            PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED]
        )

    def test_01_page_identity(self):
        assert_page_identity_consistency(
            self, [self.snapshot], ASTHMA_PDF_PAGE_1BASED
        )

    def test_02_canonical_text_coverage(self):
        assert_canonical_text_coverage(self, [self.snapshot], min_spans=1)

    def test_03_reading_order_monotonic(self):
        assert_reading_order_monotonic(self, self.snapshot)

    def test_04_bbox_within_page_bounds(self):
        assert_bbox_within_page_bounds(self, self.snapshot)

    def test_05_no_duplicate_or_empty(self):
        assert_no_duplicate_or_empty_raw_spans(self, self.snapshot)

    def test_06_anchor_ids_stable_across_reruns(self):
        from textbook_pipeline.adapters.docling_adapter import scan_pdf_pages as docling_scan
        snap_b = docling_scan(PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED])
        ids_a = _anchor_ids(self.snapshot, self.snapshot.source_pdf_sha256)
        ids_b = _anchor_ids(snap_b, snap_b.source_pdf_sha256)
        self.assertEqual(ids_a, ids_b)


@unittest.skipUnless(_pdf_available, "asthma source PDF not present")
class CrossParserDivergenceTests(unittest.TestCase):
    """Check all three real parsers share identity and explain divergence."""

    @classmethod
    def setUpClass(cls):
        global _docling_ok
        if _docling_ok is None:
            _docling_ok = probe_docling_runtime()
        if not _docling_ok:
            raise unittest.SkipTest("Docling runtime not available")
        from textbook_pipeline.adapters.docling_adapter import scan_pdf_pages as docling_scan
        cls.pymupdf_snap = pymupdf_scan(
            PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED]
        )
        cls.docling_snap = docling_scan(
            PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED]
        )
        cls.rapidocr_snap = rapidocr_scan(
            PDF, pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED]
        )

    def test_source_pdf_sha256_matches(self):
        self.assertEqual(
            self.pymupdf_snap.source_pdf_sha256,
            self.docling_snap.source_pdf_sha256,
        )
        self.assertEqual(
            self.pymupdf_snap.source_pdf_sha256,
            self.rapidocr_snap.source_pdf_sha256,
        )
        self.assertEqual(len(self.pymupdf_snap.source_pdf_sha256), 64)

    def test_page_identity_consistent_across_parsers(self):
        assert_page_identity_consistency(
            self,
            [
                self.pymupdf_snap,
                self.docling_snap,
                self.rapidocr_snap,
            ],
            ASTHMA_PDF_PAGE_1BASED,
        )

    def test_canonical_coverage_is_comparable_across_all_parsers(self):
        assert_canonical_text_coverage(
            self,
            [
                self.pymupdf_snap,
                self.docling_snap,
                self.rapidocr_snap,
            ],
            min_relative_coverage=0.5,
        )

    def test_cross_parser_anchor_ids_diverge_with_known_cause(self):
        """The key cross-parser divergence test (check 6)."""
        assert_divergence_has_explicit_cause(
            self, self.pymupdf_snap, self.docling_snap
        )

    def test_rapidocr_anchor_ids_diverge_with_known_cause(self):
        source_sha = self.pymupdf_snap.source_pdf_sha256
        pymupdf_ids = set(_anchor_ids(self.pymupdf_snap, source_sha))
        rapidocr_ids = set(_anchor_ids(self.rapidocr_snap, source_sha))
        self.assertNotEqual(pymupdf_ids, rapidocr_ids)
        first = self.rapidocr_snap.pages[0].raw_spans[0].spans[0]
        self.assertEqual(first.get("font"), "")
        self.assertEqual(first.get("size"), 0.0)
        self.assertIn("rapidocr_confidence", first)


if __name__ == "__main__":
    unittest.main()
