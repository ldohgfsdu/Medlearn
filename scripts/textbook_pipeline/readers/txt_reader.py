import re
from pathlib import Path
from typing import Any

from .base import ReaderResult, TextbookReader


def detect_encoding(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            return best.encoding, 'charset-normalizer'
    except Exception:
        pass
    try:
        import chardet
        result = chardet.detect(data)
        if result.get('encoding'):
            return str(result['encoding']), 'chardet'
    except Exception:
        pass
    return 'utf-8', 'fallback'


def split_text(text: str, min_chars: int = 200, max_chars: int = 1200) -> list[tuple[int, int, str]]:
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    chunks: list[tuple[int, int, str]] = []
    cursor = 0
    buffer = ''
    start = 0

    for paragraph in paragraphs or text.splitlines():
        idx = text.find(paragraph, cursor)
        if idx >= 0 and not buffer:
            start = idx
        if buffer and len(buffer) + len(paragraph) > max_chars and len(buffer) >= min_chars:
            end = start + len(buffer)
            chunks.append((start, end, buffer.strip()))
            buffer = paragraph
            start = idx if idx >= 0 else end
        else:
            buffer = f'{buffer}\n\n{paragraph}' if buffer else paragraph
        if idx >= 0:
            cursor = idx + len(paragraph)

    if buffer.strip():
        chunks.append((start, start + len(buffer), buffer.strip()))

    if not chunks and text.strip():
        pos = 0
        while pos < len(text):
            end = min(pos + max_chars, len(text))
            punctuation = max(text.rfind('。', pos, end), text.rfind('；', pos, end), text.rfind('\n', pos, end))
            if punctuation > pos + min_chars:
                end = punctuation + 1
            chunks.append((pos, end, text[pos:end].strip()))
            pos = end
    return chunks


class TxtReader(TextbookReader):
    format = 'txt'

    def read(self, path: Path) -> ReaderResult:
        encoding, method = detect_encoding(path)
        text = path.read_text(encoding=encoding, errors='replace')
        chunks = split_text(text)
        pages: list[dict[str, Any]] = []
        for index, (start, end, chunk) in enumerate(chunks):
            pages.append({
                'pageIndex': index,
                'pageNumber': -1,
                'sourceType': 'chunk',
                'chunkIndex': index,
                'charStart': start,
                'charEnd': end,
                'text': chunk,
            })
        report = {
            'format': self.format,
            'pageCount': len(pages),
            'tocCount': 0,
            'encoding': encoding,
            'encodingMethod': method,
            'sourceType': 'chunk',
        }
        return ReaderResult(pages=pages, toc=[], report=report, errors=[])
