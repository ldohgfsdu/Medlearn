"""Reader factory: dispatch by file extension."""
from __future__ import annotations
from pathlib import Path
from .base import TextbookReader, ReaderResult


def get_reader(path: str | Path) -> TextbookReader:
    """Factory function. Production ingest uses pipeline_v3 PyMuPDF path, not this reader.
    EnhancedPdfReader exists for experiments only and is not wired here."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        from .pdf_reader import PdfReader
        return PdfReader()
    elif ext == ".txt":
        from .txt_reader import TxtReader
        return TxtReader()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def read_file(path: str | Path, book_id: str | None = None) -> ReaderResult:
    reader = get_reader(path)
    return reader.read(path, book_id=book_id)
