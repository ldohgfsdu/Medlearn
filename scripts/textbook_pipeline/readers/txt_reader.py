"""Simple text file reader."""
from __future__ import annotations
import hashlib
from pathlib import Path
from .base import TextbookReader, ReaderResult, PageRecord, TocEntry
from ..metadata import PIPELINE_VERSION

class TxtReader(TextbookReader):
    def read(self, path: str | Path, book_id: str | None = None) -> ReaderResult:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        text = path.read_text(encoding="utf-8", errors="replace")
        char_count = len(text)

        sample_hash = hashlib.md5(f"{path.name}:{char_count}".encode()).hexdigest()[:12]

        return ReaderResult(
            source_path=str(path),
            book_id=book_id or "",
            pages=[PageRecord(page_number=1, text=text, char_count=char_count)],
            toc=[],
            metadata={
                "fileName": path.name,
                "totalPages": 1,
                "totalChars": char_count,
                "sourceSize": path.stat().st_size,
                "sourceSampleHash": sample_hash,
                "pipelineVersion": PIPELINE_VERSION,
                "sourceType": "chunk",
            },
            report={
                "sourceType": "chunk",
                "totalPages": 1,
                "tocEntries": 0,
                "avgCharsPerPage": char_count,
            },
        )
