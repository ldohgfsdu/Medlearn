from pathlib import Path
from typing import Any

import fitz

from .base import ReaderResult, TextbookReader


class PdfReader(TextbookReader):
    format = 'pdf'

    def read(self, path: Path) -> ReaderResult:
        errors: list[str] = []
        pages: list[dict[str, Any]] = []
        toc: list[dict[str, Any]] = []
        encrypted = False
        no_text_pages = 0
        page_errors: list[dict[str, Any]] = []

        doc = fitz.open(path)
        try:
            encrypted = bool(doc.is_encrypted)
            if encrypted:
                errors.append('PDF is encrypted')
            for page_index in range(len(doc)):
                try:
                    text = doc[page_index].get_text('text')
                    if not text.strip():
                        no_text_pages += 1
                    pages.append({
                        'pageIndex': page_index,
                        'pageNumber': page_index + 1,
                        'sourceType': 'page',
                        'text': text,
                    })
                except Exception as exc:
                    message = str(exc)
                    page_errors.append({'pageIndex': page_index, 'error': message})
                    errors.append(f'page {page_index + 1}: {message}')
            toc = [
                {'level': level, 'title': title, 'pageNumber': page}
                for level, title, page in doc.get_toc(simple=True)
            ]
        finally:
            doc.close()

        report = {
            'format': self.format,
            'pageCount': len(pages),
            'tocCount': len(toc),
            'emptyPageCount': no_text_pages,
            'encrypted': encrypted,
            'emptyToc': len(toc) < 5,
            'noTextLayer': len(pages) > 0 and no_text_pages / max(len(pages), 1) > 0.8,
            'pageErrors': page_errors,
        }
        return ReaderResult(pages=pages, toc=toc, report=report, errors=errors)
