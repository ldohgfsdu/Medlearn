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

import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import pymupdf as fitz

from ..document_ir import PageIdentity, RawSpan
from .pymupdf_adapter import compute_source_pdf_sha256


# Sentinel defaults for fields Docling does not provide.
DOCLING_DEFAULT_FONT = ""
DOCLING_DEFAULT_SIZE = 0.0
DOCLING_DEFAULT_COLOR = 0
DOCLING_DEFAULT_FLAGS = 0


def probe_docling_runtime(*, timeout_seconds: float = 30.0) -> bool:
    """Return whether Docling imports successfully in an isolated process.

    Docling's import chain loads native scipy libraries.  A broken native
    runtime can raise ``MemoryError`` or terminate the interpreter, so tests
    and callers must not probe it inside the long-lived parent process.
    """
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import scipy.optimize, scipy.spatial.transform; "
                    "from docling.document_converter import DocumentConverter"
                ),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


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
    and ``.text``. Docling bounding boxes default to a bottom-left origin, so
    every box is explicitly converted to the IR's top-left coordinate space.
    """
    size = page.size
    width = float(size.width) if size else 0.0
    height = float(size.height) if size else 0.0

    raw_spans: list[RawSpan] = []
    for cell_index, cell in enumerate(page.cells):
        text = cell.text or ""
        if not text.strip():
            continue
        bbox_obj = cell.to_bounding_box().to_top_left_origin(
            page_height=height
        )
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


def _contiguous_page_ranges(
    pdf_pages_1based: list[int],
) -> tuple[tuple[int, int], ...]:
    """Return minimal 1-based inclusive ranges covering requested pages."""
    if not pdf_pages_1based:
        raise ValueError("pdf_pages_1based must not be empty")
    if any(
        isinstance(page, bool) or not isinstance(page, int) or page < 1
        for page in pdf_pages_1based
    ):
        raise ValueError("pdf_pages_1based must contain positive integers")

    unique_pages = sorted(set(pdf_pages_1based))
    ranges: list[tuple[int, int]] = []
    start = previous = unique_pages[0]
    for page in unique_pages[1:]:
        if page == previous + 1:
            previous = page
            continue
        ranges.append((start, previous))
        start = previous = page
    ranges.append((start, previous))
    return tuple(ranges)


@contextmanager
def _selected_pages_pdf(
    source_pdf_path: Path,
    pdf_pages_1based: list[int],
) -> Iterator[tuple[Path, tuple[int, ...]]]:
    """Materialize only requested pages in a short-lived compact PDF.

    Docling resolves local inputs by reading the entire file into memory
    before applying ``page_range``.  Large textbooks therefore need a compact
    input slice even when only one page was requested.  PyMuPDF is used only
    for lossless page selection; Docling remains the text/layout parser.

    The yielded tuple maps compact 1-based page positions back to original
    source PDF page numbers.  The temporary file is removed on context exit.
    """
    page_ranges = _contiguous_page_ranges(pdf_pages_1based)
    original_pages = tuple(sorted(set(pdf_pages_1based)))

    source_document = fitz.open(str(source_pdf_path))
    try:
        for page_number in original_pages:
            if page_number > source_document.page_count:
                raise IndexError(
                    f"pdf page {page_number} out of range "
                    f"(1..{source_document.page_count})"
                )

        compact_document = fitz.open()
        try:
            for start, end in page_ranges:
                compact_document.insert_pdf(
                    source_document,
                    from_page=start - 1,
                    to_page=end - 1,
                )
            with tempfile.TemporaryDirectory(
                prefix="medlearn-docling-"
            ) as temp_dir:
                compact_path = Path(temp_dir) / "selected-pages.pdf"
                compact_document.save(str(compact_path))
                yield compact_path, original_pages
        finally:
            compact_document.close()
    finally:
        source_document.close()


def _build_document_converter() -> Any:
    """Build a low-memory Docling converter for native-text textbook pages."""
    # Preloading scipy avoids an intermittent Windows import failure observed
    # when transformers imports scipy's compiled modules under memory pressure.
    import scipy.optimize  # noqa: F401
    import scipy.spatial.transform  # noqa: F401
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.legacy_standard_pdf_pipeline import (
        LegacyStandardPdfPipeline,
    )

    options = PdfPipelineOptions(
        # Scanned pages are owned by the separate RapidOCR adapter.
        do_ocr=False,
        # RawSpan only needs source text/layout cells, not reconstructed tables.
        do_table_structure=False,
        force_backend_text=True,
        images_scale=0.5,
        # The adapter reads Page.cells after conversion.
        generate_parsed_pages=True,
        ocr_batch_size=1,
        layout_batch_size=1,
        table_batch_size=1,
        accelerator_options=AcceleratorOptions(
            device="cpu",
            num_threads=1,
        ),
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                # Sequential execution avoids the threaded pipeline's large
                # transient queues and reproducible std::bad_alloc on Windows.
                pipeline_cls=LegacyStandardPdfPipeline,
                pipeline_options=options,
            )
        }
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
    converter = _build_document_converter()
    pages_by_no: dict[int, Any] = {}
    with _selected_pages_pdf(
        pdf_path, pdf_pages_1based
    ) as (compact_path, original_pages):
        result = converter.convert(
            str(compact_path),
            page_range=(1, len(original_pages)),
        )
        for page in result.pages:
            compact_page_number = page.page_no
            if not 1 <= compact_page_number <= len(original_pages):
                raise IndexError(
                    "Docling returned unexpected compact page number "
                    f"{compact_page_number}"
                )
            original_page_number = original_pages[
                compact_page_number - 1
            ]
            pages_by_no[original_page_number] = page

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
