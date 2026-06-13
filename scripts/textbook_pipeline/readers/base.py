"""Base reader interface for textbook pipeline."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class PageRecord:
    page_number: int
    text: str
    char_count: int = 0

@dataclass
class TocEntry:
    level: int
    title: str
    page: int

@dataclass
class ReaderResult:
    source_path: str
    book_id: str
    pages: list[PageRecord] = field(default_factory=list)
    toc: list[TocEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)

class TextbookReader(ABC):
    @abstractmethod
    def read(self, path: str | Path, book_id: str | None = None) -> ReaderResult: ...
