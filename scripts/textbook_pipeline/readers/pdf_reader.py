"""PDF reader using PyMuPDF."""
from __future__ import annotations
import re
import hashlib
from pathlib import Path
import pymupdf as fitz
from .base import TextbookReader, ReaderResult, PageRecord, TocEntry
from ..metadata import PIPELINE_VERSION

class PdfReader(TextbookReader):
    def read(self, path: str | Path, book_id: str | None = None) -> ReaderResult:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        doc = fitz.open(str(path))
        total_pages = doc.page_count
        raw_toc = doc.get_toc()

        toc: list[TocEntry] = []
        for lvl, title, page in raw_toc:
            clean = title.replace('\n', '').strip()
            if lvl <= 3 and clean:
                toc.append(TocEntry(level=lvl, title=clean, page=page))

        pages: list[PageRecord] = []
        total_chars = 0
        for page_num in range(total_pages):
            text = re.sub(r'\s+', ' ', doc[page_num].get_text()).strip()
            char_count = len(text)
            total_chars += char_count
            pages.append(PageRecord(page_number=page_num + 1, text=text, char_count=char_count))

        doc.close()

        source_sample = f"{path.name}:{total_pages}:{total_chars}"
        sample_hash = hashlib.md5(source_sample.encode()).hexdigest()[:12]

        return ReaderResult(
            source_path=str(path),
            book_id=book_id or "",
            pages=pages,
            toc=toc,
            metadata={
                "fileName": path.name,
                "totalPages": total_pages,
                "totalChars": total_chars,
                "sourceSize": path.stat().st_size,
                "sourceSampleHash": sample_hash,
                "pipelineVersion": PIPELINE_VERSION,
            },
            report={
                "sourceType": "pdf",
                "totalPages": total_pages,
                "tocEntries": len(toc),
                "avgCharsPerPage": round(total_chars / max(total_pages, 1)),
            },
        )
