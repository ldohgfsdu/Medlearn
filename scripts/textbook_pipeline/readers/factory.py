from pathlib import Path

from .pdf_reader import PdfReader
from .txt_reader import TxtReader
from .base import TextbookReader


def reader_for(path: Path) -> TextbookReader:
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        return PdfReader()
    if suffix == '.txt':
        return TxtReader()
    raise ValueError(f'Unsupported textbook format: {path.suffix}')
