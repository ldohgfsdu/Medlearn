"""Docling adapter: outputs pre-classification RawSpan + page identity only.

Boundary (per stabilization spec):
- Outputs: RawSpan, page dimensions (width/height pt), PDF page identity
  (1-based page number), and source PDF SHA-256 (full 256-bit).
- Does NOT generate DocumentNode.
- Does NOT perform subject detection, medical classification, or summary.
- Does NOT write generated/ data.

Docling's TextCell provides text + bbox but NOT font/size/color/flags.
Those fields are filled with sentinel defaults so the RawSpan schema is
shared across parsers. Anchor IDs will naturally differ from PyMuPDF
(boundary divergence is expected and handled by parity tests).

Docling is imported lazily inside scan_pdf_pages so the adapter module
loads even when the Docling runtime is unavailable (e.g. scipy DLL
issues in .venv-sft). Core tests run without Docling; PDF integration
tests skip when Docling cannot import.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..document_ir import PageIdentity, RawSpan
from .pymupdf_adapter import compute_source_pdf_sha256


# Sentinel defaults for fields Docling does not provide.
DOCLING_DEFAULT_FONT = ""
DOCLING_DEFAULT_SIZE = 0.0
DOCLING_DEFAULT_COLOR = 0
DOCLING_DEFAULT_FLAGS = 0


@dataclass(frozen=True)
class DoclingPageSnapshot:
    """Read-only snapshot of a single PDF page from Docling."""

    page_identity: PageIdentity
    raw_spans: tuple[RawSpan, ...]


@dataclass(frozen=True)
class DoclingDocumentSnapshot:
    """Read-only snapshot of a PDF page range from Docling."""

    source_pdf_sha256: str
    pages: tuple[DoclingPageSnapshot, ...]


def _normalize_docling_cell_for_fingerprint(
    *,
    text: str,
    bbox_ltrb: list[float] | tuple[float, ...],
    confidence: float,
    from_ocr: bool,
) -> dict[str, Any]:
    """Normalize a Docling TextCell to a stable fingerprint dict.

    Only classification-independent fields are retained. Floats rounded
    to 2 decimals. ``font``/``size``/``color``/``flags`` are sentinels
    because Docling does not expose them — this is intentional and
    documented in parity tests as a known cross-parser divergence.
    """
    return {
        "text": text,
        "font": DOCLING_DEFAULT_FONT,
        "size": DOCLING_DEFAULT_SIZE,
        "bbox": [round(float(x), 2) for x in bbox_ltrb],
        "color": DOCLING_DEFAULT_COLOR,
        "flags": DOCLING_DEFAULT_FLAGS,
        # Docling-specific provenance fields (not in PyMuPDF payload)
        "docling_confidence": round(float(confidence), 2),
        "docling_from_ocr": bool(from_ocr),
    }


def _convert_page(page: Any, pdf_page_number_1based: int) -> DoclingPageSnapshot:
    """Convert a Docling Page to a DoclingPageSnapshot.

    ``page.cells`` returns TextCell objects with ``.rect`` (BoundingRectangle)
    and ``.text``. We call ``to_bounding_box()`` to get a BoundingBox with
    ``l, t, r, b`` (top-left origin by default in docling_core).
    """
    size = page.size
    width = float(size.width) if size else 0.0
    height = float(size.height) if size else 0.0

    raw_spans: list[RawSpan] = []
    for cell_index, cell in enumerate(page.cells):
        text = cell.text or ""
        if not text.strip():
            continue
        bbox_obj = cell.to_bounding_box()
        bbox_ltrb = [bbox_obj.l, bbox_obj.t, bbox_obj.r, bbox_obj.b]
        span_payload = _normalize_docling_cell_for_fingerprint(
            text=text,
            bbox_ltrb=bbox_ltrb,
            confidence=getattr(cell, "confidence", 1.0),
            from_ocr=getattr(cell, "from_ocr", False),
        )
        # Docling TextCell is cell-level, not line-level. Each cell becomes
        # one RawSpan with block_index=0 (Docling does not expose PDF blocks)
        # and line_index=cell_index (preserves reading order).
        raw_spans.append(
            RawSpan(
                pdf_page_number=pdf_page_number_1based,
                block_index=0,
                line_index=cell_index,
                spans=(span_payload,),
            )
        )

    return DoclingPageSnapshot(
        page_identity=PageIdentity(
            pdf_page_number=pdf_page_number_1based,
            printed_page_label=None,
            width=width,
            height=height,
        ),
        raw_spans=tuple(raw_spans),
    )


def scan_pdf_pages(
    pdf_path: Path | str,
    *,
    pdf_pages_1based: list[int],
) -> DoclingDocumentSnapshot:
    """Scan selected PDF pages via Docling and return RawSpan + page identity.

    Boundary: pure parser. No classification, no summary, no generated/ writes.

    Docling is imported lazily so the module loads even when the runtime
    is unavailable. Raises ``ImportError`` if Docling cannot be imported.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    source_sha = compute_source_pdf_sha256(pdf_path)

    # Lazy import — Docling's import chain may fail due to scipy DLL issues
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))

    # Build a lookup from page_no (1-based) to Page object
    pages_by_no = {page.page_no: page for page in result.pages}

    snapshots: list[DoclingPageSnapshot] = []
    for page_num in pdf_pages_1based:
        page = pages_by_no.get(page_num)
        if page is None:
            raise IndexError(
                f"Docling did not parse page {page_num}; "
                f"available pages: {sorted(pages_by_no.keys())[:10]}..."
            )
        snapshots.append(_convert_page(page, page_num))

    return DoclingDocumentSnapshot(
        source_pdf_sha256=source_sha,
        pages=tuple(snapshots),
    )
