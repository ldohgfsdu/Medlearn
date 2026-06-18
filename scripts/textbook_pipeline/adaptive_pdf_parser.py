"""Adaptive PDF parsing for textbook ingestion.

The parser keeps the existing Markdown interface while adding page-level routing,
quality metrics, table/text deduplication, and source locators.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median
from typing import Any, Iterable


PAGE_MARKER_RE = re.compile(r"<!--\s*PDF page\s+(\d+)\s*-->")
SENTENCE_END_RE = re.compile(r"(?<=[.!?;\u3002\uff01\uff1f\uff1b])\s*")
HEADING_RE = re.compile(
    r"^(?:"
    r"\u7b2c[\u4e00-\u9fff0-9]+[\u7bc7\u7ae0\u8282]"
    r"|[0-9]+(?:\.[0-9]+){0,3}\s+\S+"
    r"|[\u4e00-\u9fff]{2,24}"
    r")$"
)
MOJIBAKE_RE = re.compile(r"(?:\ufffd|[\u00c0-\u00ff]{2,}|锟斤拷)")
BOILERPLATE_LINE_RE = re.compile(
    r"^(?:"
    r"\u672c\u7ae0\u6570\u5b57\u8d44\u6e90"
    r"|\u626b\u7801\u67e5\u770b"
    r"|\u7248\u6743\u6240\u6709"
    r"|\u63a8\u8350\u9605\u8bfb"
    r")$"
)


@dataclass(frozen=True)
class SourceLocator:
    artifact_id: str
    page: int
    kind: str
    bbox: tuple[float, float, float, float]
    text: str
    parser: str
    confidence: float
    asset_path: str | None = None


@dataclass(frozen=True)
class PageAnalysis:
    page: int
    route: str
    text_chars: int
    image_coverage: float
    table_count: int
    column_count: int
    quality_score: float
    issues: tuple[str, ...]


@dataclass(frozen=True)
class ParsedPage:
    page: int
    markdown: str
    parser: str
    analysis: PageAnalysis
    locators: tuple[SourceLocator, ...]


def normalize_line(text: str) -> str:
    return re.sub(r"\s+", "", text or "").strip().lower()


def bbox_overlap_ratio(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    area = max((left[2] - left[0]) * (left[3] - left[1]), 1.0)
    return intersection / area


def garbled_ratio(text: str) -> float:
    if not text:
        return 1.0
    bad = sum(len(match.group(0)) for match in MOJIBAKE_RE.finditer(text))
    controls = sum(ord(char) < 32 and char not in "\n\t\r" for char in text)
    return min(1.0, (bad + controls) / max(len(text), 1))


def duplicate_line_ratio(lines: Iterable[str]) -> float:
    normalized = [normalize_line(line) for line in lines if normalize_line(line)]
    if not normalized:
        return 0.0
    counts = Counter(normalized)
    duplicates = sum(count - 1 for count in counts.values() if count > 1)
    return duplicates / len(normalized)


def _artifact_id(
    source_fingerprint: str,
    page: int,
    kind: str,
    bbox: tuple[float, float, float, float],
    text: str,
) -> str:
    rounded_bbox = ",".join(f"{value:.1f}" for value in bbox)
    digest = hashlib.sha256(
        f"{source_fingerprint}\0{page}\0{kind}\0{rounded_bbox}\0{text}".encode("utf-8")
    ).hexdigest()[:24]
    return f"artifact-{digest}"


def _block_text(block: dict[str, Any]) -> tuple[str, float]:
    lines: list[str] = []
    sizes: list[float] = []
    for line in block.get("lines") or []:
        spans = line.get("spans") or []
        value = "".join(str(span.get("text") or "") for span in spans).strip()
        if value:
            lines.append(value)
        sizes.extend(float(span.get("size") or 0) for span in spans if span.get("size"))
    return "\n".join(lines).strip(), (max(sizes) if sizes else 0.0)


def _estimate_columns(blocks: list[dict[str, Any]], page_width: float) -> int:
    usable = []
    for block in blocks:
        text, _ = _block_text(block)
        bbox = tuple(float(value) for value in block.get("bbox") or (0, 0, 0, 0))
        if len(text) >= 20 and bbox[2] > bbox[0]:
            usable.append(bbox)
    if len(usable) < 4:
        return 1
    left = sum(1 for bbox in usable if bbox[2] <= page_width * 0.58)
    right = sum(1 for bbox in usable if bbox[0] >= page_width * 0.42)
    return 2 if left >= 2 and right >= 2 else 1


def _image_coverage(page: Any) -> float:
    page_area = max(float(page.rect.width * page.rect.height), 1.0)
    covered = 0.0
    try:
        images = page.get_images(full=True)
    except Exception:
        images = []
    for image in images:
        try:
            rects = page.get_image_rects(image[0])
        except Exception:
            rects = []
        for rect in rects:
            covered += max(float(rect.width * rect.height), 0.0)
    return min(1.0, covered / page_area)


def _table_payloads(page: Any) -> list[tuple[tuple[float, float, float, float], str]]:
    try:
        tables = page.find_tables().tables
    except Exception:
        return []
    payloads = []
    for table in tables:
        try:
            markdown = table.to_markdown().strip()
            bbox = tuple(float(value) for value in table.bbox)
        except Exception:
            continue
        if markdown:
            payloads.append((bbox, markdown))
    return payloads


def infer_toc_from_layout(document: Any) -> list[list[Any]]:
    """Infer conservative TOC entries from heading-like layout spans."""
    body_sizes: list[float] = []
    page_spans: list[tuple[int, float, str, tuple[float, float, float, float]]] = []
    for page_index in range(document.page_count):
        page = document[page_index]
        try:
            blocks = page.get_text("dict", sort=True).get("blocks") or []
        except Exception:
            continue
        for block in blocks:
            if block.get("type", 0) != 0:
                continue
            text, size = _block_text(block)
            if not text or not size:
                continue
            bbox = tuple(float(value) for value in block.get("bbox") or (0, 0, 0, 0))
            if len(text) >= 40:
                body_sizes.append(size)
            page_spans.append((page_index + 1, size, text.replace("\n", " ").strip(), bbox))

    body_size = median(body_sizes) if body_sizes else 10.0
    candidates: list[list[Any]] = []
    seen: set[str] = set()
    for page_number, size, text, bbox in page_spans:
        compact = re.sub(r"\s+", " ", text).strip()
        normalized = normalize_line(compact)
        if normalized in seen or not (2 <= len(compact) <= 60):
            continue
        explicit = bool(re.match(r"^\u7b2c.+[\u7bc7\u7ae0\u8282]", compact))
        if not explicit and (size < body_size * 1.45 or not HEADING_RE.match(compact)):
            continue
        if bbox[1] > 760:
            continue
        level = 1
        if "\u7ae0" in compact:
            level = 2
        if "\u8282" in compact:
            level = 3
        candidates.append([level, compact, page_number])
        seen.add(normalized)
    return candidates


def page_window_toc(total_pages: int, *, window: int = 4) -> list[list[Any]]:
    return [
        [1, f"Pages {start}-{min(start + window - 1, total_pages)}", start]
        for start in range(1, total_pages + 1, window)
    ]


def _split_long_prose(text: str, max_chars: int) -> list[str]:
    sentences = [item.strip() for item in SENTENCE_END_RE.split(text) if item.strip()]
    if len(sentences) <= 1:
        return [
            text[start : start + max_chars].strip()
            for start in range(0, len(text), max_chars)
            if text[start : start + max_chars].strip()
        ]
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current}{sentence}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _split_markdown_table(lines: list[str], max_chars: int) -> list[str]:
    if len("\n".join(lines)) <= max_chars or len(lines) <= 3:
        return ["\n".join(lines)]
    header = lines[:2]
    rows = lines[2:]
    pieces: list[str] = []
    current = header.copy()
    for row in rows:
        candidate = "\n".join([*current, row])
        if len(candidate) > max_chars and len(current) > len(header):
            pieces.append("\n".join(current))
            current = [*header, row]
        else:
            current.append(row)
    if len(current) > len(header):
        pieces.append("\n".join(current))
    return pieces


def structure_aware_split(text: str, max_chars: int) -> list[str]:
    """Split prose at sentence boundaries and tables only between rows."""
    lines = text.splitlines()
    units: list[str] = []
    paragraph: list[str] = []
    table: list[str] = []

    def flush_paragraph() -> None:
        value = "\n".join(paragraph).strip()
        if value:
            units.extend(_split_long_prose(value, max_chars))
        paragraph.clear()

    def flush_table() -> None:
        if table:
            units.extend(_split_markdown_table(table, max_chars))
        table.clear()

    for line in lines:
        stripped = line.strip()
        is_table = stripped.startswith("|") and stripped.endswith("|")
        is_page_marker = bool(PAGE_MARKER_RE.fullmatch(stripped))
        if is_table:
            flush_paragraph()
            table.append(stripped)
        else:
            flush_table()
            if not stripped:
                flush_paragraph()
            elif is_page_marker:
                flush_paragraph()
                units.append(stripped)
            else:
                paragraph.append(line)
    flush_table()
    flush_paragraph()

    pieces: list[str] = []
    current = ""
    pending_marker = ""
    for unit in units:
        if PAGE_MARKER_RE.fullmatch(unit):
            pending_marker = unit
            continue
        value = f"{pending_marker}\n{unit}".strip() if pending_marker else unit
        pending_marker = ""
        candidate = f"{current}\n\n{value}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = value
        else:
            current = candidate
    if pending_marker:
        current = f"{current}\n\n{pending_marker}".strip()
    if current:
        pieces.append(current)
    return pieces


class AdaptivePdfParser:
    """Parse PDF ranges with automatic PyMuPDF, Docling, and OCR routing."""

    def __init__(
        self,
        source_path: Path,
        *,
        mode: str = "auto",
        profile_cache_path: Path | None = None,
        artifact_dir: Path | None = None,
    ) -> None:
        self.source_path = source_path.resolve()
        self.mode = mode if mode in {"auto", "pymupdf", "docling"} else "auto"
        stat = self.source_path.stat()
        self.source_fingerprint = hashlib.sha256(
            f"{self.source_path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
        ).hexdigest()
        self.profile_cache_path = profile_cache_path
        self.artifact_dir = artifact_dir
        self._margin_noise: set[str] | None = None
        self._docling_converters: dict[bool, Any] = {}
        self._docling_unavailable_reason: str | None = None

    def _build_margin_noise(self, document: Any) -> set[str]:
        if self._margin_noise is not None:
            return self._margin_noise
        if self.profile_cache_path and self.profile_cache_path.exists():
            try:
                cached = json.loads(self.profile_cache_path.read_text(encoding="utf-8"))
                if cached.get("source_fingerprint") == self.source_fingerprint:
                    self._margin_noise = set(cached.get("margin_noise") or [])
                    return self._margin_noise
            except (OSError, ValueError, TypeError):
                pass
        counts: Counter[str] = Counter()
        pages_seen = 0
        sample_count = min(document.page_count, 48)
        if sample_count == document.page_count:
            page_indexes = range(document.page_count)
        else:
            page_indexes = sorted(
                {
                    round(index * (document.page_count - 1) / (sample_count - 1))
                    for index in range(sample_count)
                }
            )
        for page_index in page_indexes:
            page = document[page_index]
            pages_seen += 1
            height = float(page.rect.height)
            try:
                blocks = page.get_text("dict", sort=True).get("blocks") or []
            except Exception:
                continue
            page_values: set[str] = set()
            for block in blocks:
                if block.get("type", 0) != 0:
                    continue
                text, _ = _block_text(block)
                bbox = tuple(float(value) for value in block.get("bbox") or (0, 0, 0, 0))
                if not text or not (bbox[1] <= height * 0.09 or bbox[3] >= height * 0.91):
                    continue
                value = re.sub(r"\d+", "#", normalize_line(text))
                if 2 <= len(value) <= 80:
                    page_values.add(value)
            counts.update(page_values)
        threshold = max(3, math.ceil(pages_seen * 0.25))
        self._margin_noise = {value for value, count in counts.items() if count >= threshold}
        if self.profile_cache_path:
            self.profile_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.profile_cache_path.write_text(
                json.dumps(
                    {
                        "source_fingerprint": self.source_fingerprint,
                        "sampled_pages": pages_seen,
                        "margin_noise": sorted(self._margin_noise),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return self._margin_noise

    def _analyze_page(self, page: Any, table_count: int) -> PageAnalysis:
        try:
            blocks = page.get_text("dict", sort=True).get("blocks") or []
        except Exception:
            blocks = []
        text_chars = sum(len(_block_text(block)[0]) for block in blocks if block.get("type", 0) == 0)
        coverage = _image_coverage(page)
        columns = _estimate_columns(blocks, float(page.rect.width))
        issues: list[str] = []
        scanned = text_chars < 40 and coverage >= 0.35
        if scanned:
            issues.append("scanned_or_missing_text_layer")
        if columns > 1:
            issues.append("multi_column_layout")
        if table_count > 1:
            issues.append("complex_tables")
        route = "pymupdf"
        if self.mode == "docling":
            route = "docling_ocr" if scanned else "docling"
        elif self.mode == "auto":
            if scanned:
                route = "docling_ocr"
            elif columns > 1 or table_count > 2:
                route = "docling"
        score = 1.0 - (0.45 if text_chars < 40 else 0.0)
        score -= 0.1 if columns > 1 else 0.0
        score -= 0.1 if table_count > 2 else 0.0
        return PageAnalysis(
            page=page.number + 1,
            route=route,
            text_chars=text_chars,
            image_coverage=round(coverage, 4),
            table_count=table_count,
            column_count=columns,
            quality_score=round(max(0.0, score), 4),
            issues=tuple(issues),
        )

    def _parse_pymupdf_page(
        self,
        page: Any,
        analysis: PageAnalysis,
        table_payloads: list[tuple[tuple[float, float, float, float], str]],
    ) -> ParsedPage:
        table_bboxes = [bbox for bbox, _ in table_payloads]
        margin_noise = self._margin_noise or set()
        try:
            blocks = page.get_text("dict", sort=True).get("blocks") or []
        except Exception:
            blocks = []
        sizes = [
            _block_text(block)[1]
            for block in blocks
            if block.get("type", 0) == 0 and len(_block_text(block)[0]) >= 20
        ]
        body_size = median(sizes) if sizes else 10.0
        rendered: list[str] = []
        locators: list[SourceLocator] = []
        seen_text: set[str] = set()
        for block in blocks:
            if block.get("type", 0) != 0:
                continue
            text, size = _block_text(block)
            bbox = tuple(float(value) for value in block.get("bbox") or (0, 0, 0, 0))
            if not text:
                continue
            margin_key = re.sub(r"\d+", "#", normalize_line(text))
            if margin_key in margin_noise:
                continue
            if BOILERPLATE_LINE_RE.match(normalize_line(text)):
                continue
            if bbox[1] >= float(page.rect.height) * 0.92 and re.fullmatch(
                r"[-\s0-9IVXLCDMivxlcdm]+",
                text,
            ):
                continue
            if any(bbox_overlap_ratio(bbox, table_bbox) >= 0.35 for table_bbox in table_bboxes):
                continue
            normalized = normalize_line(text)
            if normalized in seen_text:
                continue
            seen_text.add(normalized)
            value = re.sub(r"[ \t]+", " ", text).strip()
            if size >= body_size * 1.35 and len(value) <= 80:
                value = f"### {value.replace(chr(10), ' ')}"
            rendered.append(value)
            artifact_kind = (
                "caption"
                if re.match(r"^(?:Figure|Fig\.?|\u56fe|\u8868)\s*[0-9\u4e00-\u9fff-]+", text)
                else "text_block"
            )
            locators.append(
                SourceLocator(
                    artifact_id=_artifact_id(
                        self.source_fingerprint, page.number + 1, artifact_kind, bbox, text
                    ),
                    page=page.number + 1,
                    kind=artifact_kind,
                    bbox=bbox,
                    text=text,
                    parser="pymupdf",
                    confidence=1.0,
                )
            )

        locators.extend(self._extract_image_locators(page))
        for bbox, markdown in table_payloads:
            rendered.append(markdown)
            locators.append(
                SourceLocator(
                    artifact_id=_artifact_id(
                        self.source_fingerprint, page.number + 1, "table", bbox, markdown
                    ),
                    page=page.number + 1,
                    kind="table",
                    bbox=bbox,
                    text=markdown,
                    parser="pymupdf",
                    confidence=0.95,
                )
            )

        markdown = "\n\n".join(rendered).strip()
        issues = list(analysis.issues)
        ratio = garbled_ratio(markdown)
        duplicate_ratio = duplicate_line_ratio(markdown.splitlines())
        score = analysis.quality_score
        if ratio > 0.02:
            issues.append("garbled_text")
            score -= min(0.4, ratio * 2)
        if duplicate_ratio > 0.25:
            issues.append("high_duplicate_ratio")
            score -= 0.15
        if len(markdown) < 40:
            issues.append("insufficient_content")
            score -= 0.35
        final_analysis = PageAnalysis(
            page=analysis.page,
            route=analysis.route,
            text_chars=len(markdown),
            image_coverage=analysis.image_coverage,
            table_count=analysis.table_count,
            column_count=analysis.column_count,
            quality_score=round(max(0.0, score), 4),
            issues=tuple(sorted(set(issues))),
        )
        return ParsedPage(
            page=page.number + 1,
            markdown=markdown,
            parser="pymupdf",
            analysis=final_analysis,
            locators=tuple(locators),
        )

    def _extract_image_locators(self, page: Any) -> list[SourceLocator]:
        locators: list[SourceLocator] = []
        try:
            images = page.get_images(full=True)
        except Exception:
            images = []
        seen: set[tuple[int, tuple[float, float, float, float]]] = set()
        for image in images:
            xref = int(image[0])
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            for rect in rects:
                bbox = tuple(float(value) for value in rect)
                key = (xref, bbox)
                if key in seen:
                    continue
                seen.add(key)
                artifact_id = _artifact_id(
                    self.source_fingerprint,
                    page.number + 1,
                    "figure",
                    bbox,
                    f"xref:{xref}",
                )
                asset_path = None
                if self.artifact_dir:
                    try:
                        payload = page.parent.extract_image(xref)
                        extension = str(payload.get("ext") or "png")
                        target = self.artifact_dir / f"{artifact_id}.{extension}"
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            target.write_bytes(payload["image"])
                        asset_path = str(target)
                    except Exception:
                        asset_path = None
                locators.append(
                    SourceLocator(
                        artifact_id=artifact_id,
                        page=page.number + 1,
                        kind="figure",
                        bbox=bbox,
                        text="",
                        parser="pymupdf",
                        confidence=1.0,
                        asset_path=asset_path,
                    )
                )
        return locators

    def _parse_docling_page(
        self,
        page_number: int,
        *,
        do_ocr: bool,
        page_bbox: tuple[float, float, float, float],
    ) -> ParsedPage:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.pipeline.legacy_standard_pdf_pipeline import LegacyStandardPdfPipeline

        converter = self._docling_converters.get(do_ocr)
        if converter is None:
            options = PdfPipelineOptions(
                do_ocr=do_ocr,
                do_table_structure=True,
                layout_batch_size=1,
                table_batch_size=1,
                queue_max_size=1,
            )
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=options,
                        pipeline_cls=LegacyStandardPdfPipeline,
                    )
                }
            )
            self._docling_converters[do_ocr] = converter
        result = converter.convert(str(self.source_path), page_range=(page_number, page_number))
        markdown = result.document.export_to_markdown().strip()
        parser = "docling_ocr" if do_ocr else "docling"
        bbox = page_bbox
        locator = SourceLocator(
            artifact_id=_artifact_id(
                self.source_fingerprint, page_number, "page_layout", bbox, markdown
            ),
            page=page_number,
            kind="page_layout",
            bbox=bbox,
            text=markdown,
            parser=parser,
            confidence=0.8 if do_ocr else 0.9,
        )
        score = 0.9 if len(markdown) >= 40 else 0.2
        issues = () if len(markdown) >= 40 else ("insufficient_content",)
        return ParsedPage(
            page=page_number,
            markdown=markdown,
            parser=parser,
            analysis=PageAnalysis(
                page=page_number,
                route=parser,
                text_chars=len(markdown),
                image_coverage=0.0,
                table_count=markdown.count("\n|"),
                column_count=1,
                quality_score=score,
                issues=issues,
            ),
            locators=(locator,),
        )

    def parse_range(self, page_start: int, page_end: int) -> tuple[str, dict[str, Any]]:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        document = fitz.open(str(self.source_path))
        self._build_margin_noise(document)
        pages: list[ParsedPage] = []
        try:
            for page_number in range(page_start, page_end + 1):
                page = document[page_number - 1]
                table_payloads = _table_payloads(page)
                analysis = self._analyze_page(page, len(table_payloads))
                parsed: ParsedPage | None = None
                fallback_error: str | None = None
                if analysis.route in {"docling", "docling_ocr"}:
                    if self._docling_unavailable_reason:
                        fallback_error = self._docling_unavailable_reason
                    else:
                        try:
                            parsed = self._parse_docling_page(
                                page_number,
                                do_ocr=analysis.route == "docling_ocr",
                                page_bbox=tuple(float(value) for value in page.rect),
                            )
                            image_locators = self._extract_image_locators(page)
                            parsed = ParsedPage(
                                page=parsed.page,
                                markdown=parsed.markdown,
                                parser=parsed.parser,
                                analysis=PageAnalysis(
                                    page=parsed.analysis.page,
                                    route=parsed.analysis.route,
                                    text_chars=parsed.analysis.text_chars,
                                    image_coverage=analysis.image_coverage,
                                    table_count=max(
                                        parsed.analysis.table_count,
                                        analysis.table_count,
                                    ),
                                    column_count=analysis.column_count,
                                    quality_score=parsed.analysis.quality_score,
                                    issues=tuple(
                                        sorted(
                                            set(
                                                [
                                                    *analysis.issues,
                                                    *parsed.analysis.issues,
                                                ]
                                            )
                                        )
                                    ),
                                ),
                                locators=tuple([*parsed.locators, *image_locators]),
                            )
                        except Exception as exc:
                            fallback_error = f"{type(exc).__name__}: {exc}"
                            self._docling_unavailable_reason = fallback_error
                if parsed is None:
                    parsed = self._parse_pymupdf_page(page, analysis, table_payloads)
                    if fallback_error:
                        parsed = ParsedPage(
                            page=parsed.page,
                            markdown=parsed.markdown,
                            parser="pymupdf_fallback",
                            analysis=PageAnalysis(
                                page=parsed.analysis.page,
                                route="pymupdf_fallback",
                                text_chars=parsed.analysis.text_chars,
                                image_coverage=parsed.analysis.image_coverage,
                                table_count=parsed.analysis.table_count,
                                column_count=parsed.analysis.column_count,
                                quality_score=parsed.analysis.quality_score,
                                issues=tuple(
                                    sorted(set([*parsed.analysis.issues, "docling_fallback"]))
                                ),
                            ),
                            locators=parsed.locators,
                        )
                pages.append(parsed)
        finally:
            document.close()

        markdown_pages = [
            f"<!-- PDF page {page.page} -->\n{page.markdown}"
            for page in pages
            if page.markdown
        ]
        analyses = [asdict(page.analysis) for page in pages]
        locators = [asdict(locator) for page in pages for locator in page.locators]
        blocking_pages = [
            item["page"]
            for item in analyses
            if item["quality_score"] < 0.35 or "insufficient_content" in item["issues"]
        ]
        report = {
            "page_start": page_start,
            "page_end": page_end,
            "pages": analyses,
            "locators": locators,
            "artifact_counts": dict(
                Counter(str(locator.get("kind") or "unknown") for locator in locators)
            ),
            "docling_unavailable_reason": self._docling_unavailable_reason,
            "parser_counts": dict(Counter(page.parser for page in pages)),
            "blocking_pages": blocking_pages,
            "checks": {
                "all_pages_have_content": all(bool(page.markdown) for page in pages),
                "no_blocking_pages": not blocking_pages,
            },
        }
        return "\n\n".join(markdown_pages), report


def find_evidence_locators(
    locators: Iterable[dict[str, Any]],
    evidence: str,
    *,
    page_start: int | None = None,
    page_end: int | None = None,
) -> list[dict[str, Any]]:
    needle = normalize_line(evidence)
    if not needle:
        return []
    candidates: list[tuple[dict[str, Any], str]] = []
    for locator in locators:
        page = int(locator.get("page") or 0)
        if page_start is not None and page < page_start:
            continue
        if page_end is not None and page > page_end:
            continue
        haystack = normalize_line(str(locator.get("text") or ""))
        if not haystack:
            continue
        candidates.append((locator, haystack))
        if needle in haystack or (len(needle) >= 24 and haystack in needle):
            return [
                {
                    "artifact_id": locator.get("artifact_id"),
                    "page": page,
                    "kind": locator.get("kind"),
                    "bbox": locator.get("bbox"),
                    "parser": locator.get("parser"),
                    "confidence": locator.get("confidence"),
                    "asset_path": locator.get("asset_path"),
                }
            ]

    combined = ""
    ranges: list[tuple[int, int, dict[str, Any]]] = []
    for locator, text in candidates:
        start = len(combined)
        combined += text
        ranges.append((start, len(combined), locator))
    position = combined.find(needle)
    if position >= 0:
        end = position + len(needle)
        return [
            {
                "artifact_id": locator.get("artifact_id"),
                "page": locator.get("page"),
                "kind": locator.get("kind"),
                "bbox": locator.get("bbox"),
                "parser": locator.get("parser"),
                "confidence": locator.get("confidence"),
                "asset_path": locator.get("asset_path"),
            }
            for start, stop, locator in ranges
            if stop > position and start < end
        ][:8]

    scored = []
    for locator, text in candidates:
        score = SequenceMatcher(None, needle, text).ratio()
        if score >= 0.55:
            scored.append((score, locator))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "artifact_id": locator.get("artifact_id"),
            "page": locator.get("page"),
            "kind": locator.get("kind"),
            "bbox": locator.get("bbox"),
            "parser": locator.get("parser"),
            "confidence": round(min(float(locator.get("confidence") or 0), score), 4),
            "asset_path": locator.get("asset_path"),
        }
        for score, locator in scored[:3]
    ]
