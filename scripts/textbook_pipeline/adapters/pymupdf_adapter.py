"""PyMuPDF adapter: outputs pre-classification RawSpan + page identity only.

Boundary (per stabilization spec):
- Outputs: RawSpan, page dimensions (width/height pt), PDF page identity
  (1-based page number), and source PDF SHA-256 (full 256-bit).
- Does NOT generate DocumentNode.
- Does NOT perform subject detection, medical classification, or summary.
- Does NOT write generated/ data.

Uses PyMuPDF rawdict for character-level positioning per project hard
constraint (PyMuPDF 1.27.2.3). Span text is reconstructed from rawdict
char arrays; span-level bbox/font/size/color/flags are retained as
classification-independent fingerprint inputs.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf as fitz

from ..document_ir import PageIdentity, RawSpan


@dataclass(frozen=True)
class PymupdfPageSnapshot:
    """Read-only snapshot of a single PDF page."""

    page_identity: PageIdentity
    raw_spans: tuple[RawSpan, ...]


@dataclass(frozen=True)
class PymupdfDocumentSnapshot:
    """Read-only snapshot of a PDF page range."""

    source_pdf_sha256: str
    pages: tuple[PymupdfPageSnapshot, ...]


def compute_source_pdf_sha256(pdf_path: Path) -> str:
    """Full SHA-256 of the source PDF file (256-bit, no truncation)."""
    sha = hashlib.sha256()
    with open(pdf_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _normalize_span_for_fingerprint(
    *,
    text: str,
    font: str,
    size: float,
    bbox: list[float] | tuple[float, ...],
    color: int,
    flags: int,
) -> dict[str, Any]:
    """Normalize a rawdict span to a stable, JSON-serializable fingerprint dict.

    Only classification-independent fields are retained so the anchor
    fingerprint is stable across parser patch versions. Floats are rounded
    to 2 decimals to absorb sub-pixel noise. Character-level bbox data is
    excluded; span-level bbox is sufficient for positioning and fingerprint.
    """
    return {
        "text": text,
        "font": font,
        "size": round(float(size), 2),
        "bbox": [round(float(x), 2) for x in bbox],
        "color": int(color),
        "flags": int(flags),
    }


def scan_page(page: fitz.Page, pdf_page_number_1based: int) -> PymupdfPageSnapshot:
    """Scan a single PDF page and return RawSpan list + page identity.

    Uses rawdict (char-level) per project hard constraint. Only text blocks
    (type 0) are scanned; image/vector blocks are skipped. The adapter does
    NOT infer printed page labels — that is a downstream concern.
    """
    raw = page.get_text("rawdict", sort=True)
    width = float(page.rect.width)
    height = float(page.rect.height)

    raw_spans: list[RawSpan] = []
    for block_index, block in enumerate(raw.get("blocks", [])):
        if block.get("type") != 0:
            continue
        for line_index, line in enumerate(block.get("lines", [])):
            spans_list: list[dict[str, Any]] = []
            for span in line.get("spans", []):
                span_text = "".join(ch.get("c", "") for ch in span.get("chars", []))
                if not span_text:
                    continue
                spans_list.append(
                    _normalize_span_for_fingerprint(
                        text=span_text,
                        font=span.get("font", ""),
                        size=span.get("size", 0),
                        bbox=span.get("bbox", [0, 0, 0, 0]),
                        color=span.get("color", 0),
                        flags=span.get("flags", 0),
                    )
                )
            if not spans_list:
                continue
            raw_spans.append(
                RawSpan(
                    pdf_page_number=pdf_page_number_1based,
                    block_index=block_index,
                    line_index=line_index,
                    spans=tuple(spans_list),
                )
            )

    return PymupdfPageSnapshot(
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
) -> PymupdfDocumentSnapshot:
    """Scan selected PDF pages and return RawSpan + page identity only.

    Boundary: this function is a pure parser. It does NOT classify, summarize,
    or write any output. Callers are responsible for downstream IR construction
    (DocumentNode, DocumentBlock) via build_source_anchor / raw_span_to_document_block.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    source_sha = compute_source_pdf_sha256(pdf_path)

    doc = fitz.open(str(pdf_path))
    try:
        pages: list[PymupdfPageSnapshot] = []
        for page_num in pdf_pages_1based:
            if page_num < 1 or page_num > doc.page_count:
                raise IndexError(
                    f"pdf page {page_num} out of range (1..{doc.page_count})"
                )
            page = doc.load_page(page_num - 1)
            pages.append(scan_page(page, page_num))
    finally:
        doc.close()

    return PymupdfDocumentSnapshot(
        source_pdf_sha256=source_sha,
        pages=tuple(pages),
    )
