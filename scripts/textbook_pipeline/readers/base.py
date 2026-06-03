from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PageRecord:
    pageIndex: int
    pageNumber: int
    text: str
    sourceType: str = 'page'
    chunkIndex: int | None = None
    charStart: int | None = None
    charEnd: int | None = None


@dataclass
class TocEntry:
    level: int
    title: str
    pageNumber: int


@dataclass
class ReaderResult:
    pages: list[dict[str, Any]]
    toc: list[dict[str, Any]]
    report: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class TextbookReader:
    format = 'unknown'

    def read(self, path: Path) -> ReaderResult:
        raise NotImplementedError
