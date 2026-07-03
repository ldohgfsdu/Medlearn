"""RapidOCR adapter: outputs pre-classification RawSpan + page identity only.

Boundary:
- Outputs RawSpan, PDF page dimensions, 1-based PDF page identity, and the
  full source PDF SHA-256.
- Uses PyMuPDF only to render requested pages in memory; RapidOCR is the text
  parser.
- Does not generate DocumentNode, classify content, summarize, or write
  generated/ data.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf as fitz

from ..document_ir import PageIdentity, RawSpan
from .pymupdf_adapter import compute_source_pdf_sha256


RAPIDOCR_DEFAULT_FONT = ""
RAPIDOCR_DEFAULT_SIZE = 0.0
RAPIDOCR_DEFAULT_COLOR = 0
RAPIDOCR_DEFAULT_FLAGS = 0
DEFAULT_RENDER_DPI = 180


@dataclass(frozen=True)
class RapidocrPageSnapshot:
    """Read-only OCR snapshot of one source PDF page."""

    page_identity: PageIdentity
    raw_spans: tuple[RawSpan, ...]


@dataclass(frozen=True)
class RapidocrDocumentSnapshot:
    """Read-only OCR snapshot of selected source PDF pages."""

    source_pdf_sha256: str
    pages: tuple[RapidocrPageSnapshot, ...]


def _normalize_rapidocr_line_for_fingerprint(
    *,
    text: str,
    bbox_ltrb: list[float] | tuple[float, ...],
    confidence: float,
    render_dpi: int,
) -> dict[str, Any]:
    """Normalize an OCR line to the shared, stable RawSpan payload shape."""
    return {
        "text": text,
        "font": RAPIDOCR_DEFAULT_FONT,
        "size": RAPIDOCR_DEFAULT_SIZE,
        "bbox": [round(float(value), 2) for value in bbox_ltrb],
        "color": RAPIDOCR_DEFAULT_COLOR,
        "flags": RAPIDOCR_DEFAULT_FLAGS,
        # Parser diagnostics are retained for audit but excluded from anchor ID.
        "rapidocr_confidence": round(float(confidence), 4),
        "rapidocr_render_dpi": int(render_dpi),
    }


def _quad_to_pdf_bbox(
    box: Any,
    *,
    page_width: float,
    page_height: float,
    image_width: int,
    image_height: int,
) -> list[float]:
    """Convert an OCR pixel quadrilateral to a clamped top-left PDF bbox."""
    points = list(box)
    if len(points) < 4 or image_width <= 0 or image_height <= 0:
        raise ValueError("RapidOCR box must contain four image-space points")
    x_values = [float(point[0]) for point in points]
    y_values = [float(point[1]) for point in points]
    scale_x = page_width / image_width
    scale_y = page_height / image_height
    left = max(0.0, min(page_width, min(x_values) * scale_x))
    top = max(0.0, min(page_height, min(y_values) * scale_y))
    right = max(0.0, min(page_width, max(x_values) * scale_x))
    bottom = max(0.0, min(page_height, max(y_values) * scale_y))
    return [left, top, right, bottom]


def _convert_ocr_result(
    result: Any,
    *,
    pdf_page_number_1based: int,
    page_width: float,
    page_height: float,
    image_width: int,
    image_height: int,
    render_dpi: int,
) -> RapidocrPageSnapshot:
    """Convert RapidOCR output to deterministic top-left RawSpan records."""
    boxes = result.boxes if result.boxes is not None else ()
    texts = result.txts if result.txts is not None else ()
    scores = result.scores if result.scores is not None else ()
    if not (len(boxes) == len(texts) == len(scores)):
        raise ValueError("RapidOCR boxes/texts/scores length mismatch")

    records: list[tuple[list[float], str, float]] = []
    for box, text_value, score in zip(boxes, texts, scores):
        text = str(text_value or "")
        if not text.strip():
            continue
        bbox = _quad_to_pdf_bbox(
            box,
            page_width=page_width,
            page_height=page_height,
            image_width=image_width,
            image_height=image_height,
        )
        records.append((bbox, text, float(score)))

    # RapidOCR usually returns reading order already, but an explicit geometric
    # order keeps line indices deterministic across runtime patch releases.
    records.sort(
        key=lambda record: (
            round(record[0][1], 2),
            round(record[0][0], 2),
            round(record[0][3], 2),
            record[1],
        )
    )
    raw_spans = tuple(
        RawSpan(
            pdf_page_number=pdf_page_number_1based,
            block_index=0,
            line_index=line_index,
            spans=(
                _normalize_rapidocr_line_for_fingerprint(
                    text=text,
                    bbox_ltrb=bbox,
                    confidence=score,
                    render_dpi=render_dpi,
                ),
            ),
        )
        for line_index, (bbox, text, score) in enumerate(records)
    )
    return RapidocrPageSnapshot(
        page_identity=PageIdentity(
            pdf_page_number=pdf_page_number_1based,
            printed_page_label=None,
            width=page_width,
            height=page_height,
        ),
        raw_spans=raw_spans,
    )


def _build_rapidocr_engine() -> Any:
    """Construct RapidOCR lazily so importing the adapter stays lightweight."""
    from rapidocr import RapidOCR

    return RapidOCR()


def scan_pdf_pages(
    pdf_path: Path | str,
    *,
    pdf_pages_1based: list[int],
    render_dpi: int = DEFAULT_RENDER_DPI,
) -> RapidocrDocumentSnapshot:
    """OCR selected PDF pages fully in memory and return the shared contract."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    if not pdf_pages_1based:
        raise ValueError("pdf_pages_1based must not be empty")
    if any(
        isinstance(page, bool) or not isinstance(page, int) or page < 1
        for page in pdf_pages_1based
    ):
        raise ValueError("pdf_pages_1based must contain positive integers")
    if isinstance(render_dpi, bool) or not isinstance(render_dpi, int):
        raise ValueError("render_dpi must be a positive integer")
    if render_dpi < 72:
        raise ValueError("render_dpi must be at least 72")

    source_sha = compute_source_pdf_sha256(pdf_path)
    engine = _build_rapidocr_engine()
    document = fitz.open(str(pdf_path))
    try:
        snapshots_by_page: dict[int, RapidocrPageSnapshot] = {}
        for page_number in sorted(set(pdf_pages_1based)):
            if page_number > document.page_count:
                raise IndexError(
                    f"pdf page {page_number} out of range "
                    f"(1..{document.page_count})"
                )
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(dpi=render_dpi, alpha=False)
            result = engine(pixmap.tobytes("png"))
            snapshots_by_page[page_number] = _convert_ocr_result(
                result,
                pdf_page_number_1based=page_number,
                page_width=float(page.rect.width),
                page_height=float(page.rect.height),
                image_width=pixmap.width,
                image_height=pixmap.height,
                render_dpi=render_dpi,
            )
    finally:
        document.close()

    return RapidocrDocumentSnapshot(
        source_pdf_sha256=source_sha,
        pages=tuple(
            snapshots_by_page[page_number]
            for page_number in pdf_pages_1based
        ),
    )
