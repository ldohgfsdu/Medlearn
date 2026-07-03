"""Tests for the RapidOCR RawSpan adapter."""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.adapters.rapidocr_adapter import (  # noqa: E402
    DEFAULT_RENDER_DPI,
    RAPIDOCR_DEFAULT_COLOR,
    RAPIDOCR_DEFAULT_FLAGS,
    RAPIDOCR_DEFAULT_FONT,
    RAPIDOCR_DEFAULT_SIZE,
    RapidocrDocumentSnapshot,
    _convert_ocr_result,
    _normalize_rapidocr_line_for_fingerprint,
)
from textbook_pipeline.document_ir import RawSpan, build_source_anchor  # noqa: E402

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"
ASTHMA_PDF_PAGE_1BASED = 62
TEXTBOOK_VERSION_ID = "internal-medicine-10"
SCOPE_ID = "第二篇_呼吸系统疾病__第四章_支气管哮喘"
_pdf_available = PDF.exists()


def _payload(
    *,
    text: str = "哮喘",
    bbox: list[float] | None = None,
    confidence: float = 0.9,
    render_dpi: int = DEFAULT_RENDER_DPI,
):
    return _normalize_rapidocr_line_for_fingerprint(
        text=text,
        bbox_ltrb=bbox or [10.0, 20.0, 50.0, 35.0],
        confidence=confidence,
        render_dpi=render_dpi,
    )


class RapidocrNormalizationTests(unittest.TestCase):
    def test_shared_sentinel_fields_and_provenance(self):
        payload = _payload(confidence=0.87654)
        self.assertEqual(payload["font"], RAPIDOCR_DEFAULT_FONT)
        self.assertEqual(payload["size"], RAPIDOCR_DEFAULT_SIZE)
        self.assertEqual(payload["color"], RAPIDOCR_DEFAULT_COLOR)
        self.assertEqual(payload["flags"], RAPIDOCR_DEFAULT_FLAGS)
        self.assertEqual(payload["rapidocr_confidence"], 0.8765)
        self.assertEqual(payload["rapidocr_render_dpi"], DEFAULT_RENDER_DPI)

    def test_confidence_and_dpi_do_not_change_anchor_identity(self):
        def anchor(payload):
            return build_source_anchor(
                RawSpan(62, 0, 0, (payload,)),
                textbook_version_id=TEXTBOOK_VERSION_ID,
                scope_id=SCOPE_ID,
                source_pdf_sha256="a" * 64,
            ).id

        self.assertEqual(
            anchor(_payload(confidence=0.5, render_dpi=180)),
            anchor(_payload(confidence=0.99, render_dpi=240)),
        )

    def test_text_and_bbox_still_change_anchor_identity(self):
        def anchor(payload):
            return build_source_anchor(
                RawSpan(62, 0, 0, (payload,)),
                textbook_version_id=TEXTBOOK_VERSION_ID,
                scope_id=SCOPE_ID,
                source_pdf_sha256="a" * 64,
            ).id

        baseline = anchor(_payload())
        self.assertNotEqual(baseline, anchor(_payload(text="肺结核")))
        self.assertNotEqual(
            baseline,
            anchor(_payload(bbox=[11.0, 20.0, 50.0, 35.0])),
        )


class RapidocrResultConversionTests(unittest.TestCase):
    def test_pixel_quads_become_sorted_top_left_pdf_bboxes(self):
        result = types.SimpleNamespace(
            boxes=[
                [[20, 100], [80, 100], [80, 120], [20, 120]],
                [[10, 20], [50, 20], [50, 40], [10, 40]],
            ],
            txts=("second", "first"),
            scores=(0.8, 0.9),
        )

        snapshot = _convert_ocr_result(
            result,
            pdf_page_number_1based=3,
            page_width=100.0,
            page_height=200.0,
            image_width=200,
            image_height=400,
            render_dpi=180,
        )

        self.assertEqual(
            [span.spans[0]["text"] for span in snapshot.raw_spans],
            ["first", "second"],
        )
        self.assertEqual(
            snapshot.raw_spans[0].spans[0]["bbox"],
            [5.0, 10.0, 25.0, 20.0],
        )
        self.assertEqual(
            [span.line_index for span in snapshot.raw_spans],
            [0, 1],
        )

    def test_empty_ocr_result_is_valid_empty_page(self):
        snapshot = _convert_ocr_result(
            types.SimpleNamespace(boxes=None, txts=None, scores=None),
            pdf_page_number_1based=1,
            page_width=100.0,
            page_height=200.0,
            image_width=100,
            image_height=200,
            render_dpi=180,
        )
        self.assertEqual(snapshot.raw_spans, ())

    def test_mismatched_result_lengths_are_rejected(self):
        with self.assertRaises(ValueError):
            _convert_ocr_result(
                types.SimpleNamespace(
                    boxes=[[[0, 0], [1, 0], [1, 1], [0, 1]]],
                    txts=("text",),
                    scores=(),
                ),
                pdf_page_number_1based=1,
                page_width=100.0,
                page_height=200.0,
                image_width=100,
                image_height=200,
                render_dpi=180,
            )


@unittest.skipUnless(_pdf_available, "source PDF not available")
class AsthmaPageRapidocrIntegrationTests(unittest.TestCase):
    @classmethod
    def _scan(cls) -> RapidocrDocumentSnapshot:
        from textbook_pipeline.adapters.rapidocr_adapter import scan_pdf_pages

        return scan_pdf_pages(
            PDF,
            pdf_pages_1based=[ASTHMA_PDF_PAGE_1BASED],
        )

    @staticmethod
    def _anchor_ids(snapshot: RapidocrDocumentSnapshot) -> list[str]:
        return [
            build_source_anchor(
                span,
                textbook_version_id=TEXTBOOK_VERSION_ID,
                scope_id=SCOPE_ID,
                source_pdf_sha256=snapshot.source_pdf_sha256,
            ).id
            for span in snapshot.pages[0].raw_spans
        ]

    def test_real_page_has_text_and_valid_identity(self):
        snapshot = self._scan()
        self.assertEqual(len(snapshot.pages), 1)
        page = snapshot.pages[0]
        self.assertEqual(
            page.page_identity.pdf_page_number,
            ASTHMA_PDF_PAGE_1BASED,
        )
        self.assertGreater(len(page.raw_spans), 0)
        self.assertGreater(page.page_identity.width, 0)
        self.assertGreater(page.page_identity.height, 0)

    def test_anchor_ids_are_stable_across_reruns(self):
        first = self._scan()
        second = self._scan()
        self.assertEqual(
            self._anchor_ids(first),
            self._anchor_ids(second),
        )

    def test_source_sha_is_full_and_stable(self):
        first = self._scan()
        second = self._scan()
        self.assertEqual(first.source_pdf_sha256, second.source_pdf_sha256)
        self.assertEqual(len(first.source_pdf_sha256), 64)


if __name__ == "__main__":
    unittest.main()
