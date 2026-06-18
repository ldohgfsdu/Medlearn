"""Medlearn Pipeline v3: Docling -> Ollama/Qwen -> cache -> knowledge map."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from textbook_identity import CANONICAL_TEXTBOOK_ID, INTERNAL_MEDICINE_10
from textbook_pipeline.adaptive_pdf_parser import (
    AdaptivePdfParser,
    find_evidence_locators,
    infer_toc_from_layout,
    page_window_toc,
    structure_aware_split,
)
from textbook_pipeline.ingestion_contract import (
    resolve_pdf_parser_mode,
)
from textbook_pipeline.node_guardrails import (
    MAX_NODES_PER_CHUNK,
    assess_guardrails,
    build_chunk_source_map,
    canonicalize_aspect_label,
    evidence_supported_by_source,
    extract_section_entity,
    is_cross_disease_expansion,
    looks_self_referential_evidence,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "textbook" / "内科学（第10版）.pdf"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "generated" / "pipeline_v3"
os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".models" / "huggingface"))
ALLOWED_TYPES = {"concept", "mechanism", "disease", "symptom", "treatment", "exam"}
VINDICATE_TAGS = {"V", "I", "N", "D", "I2", "C", "A", "T", "E"}
PART_RE = re.compile(r"第[一二三四五六七八九十百零〇\d]+篇")
CHAPTER_RE = re.compile(r"第[一二三四五六七八九十百零〇\d]+章")
CONTEXT_DEPENDENT_RE = re.compile(r"^(该病|本病|其|上述|前者|后者|这种情况)")
ENTITY_ASPECT_SUFFIXES = (
    "实验室和其他辅助检查",
    "病因和发病机制",
    "诊断与鉴别诊断",
    "个体化治疗方案",
    "靶器官损害",
    "临床表现",
    "临床分型",
    "治疗原则",
    "诊断原则",
    "药物选择",
    "发病机制",
    "病理机制",
    "危险因素",
    "流行病学",
    "鉴别诊断",
    "并发症",
    "实验室检查",
    "辅助检查",
    "定义",
    "概念",
    "病因",
    "病理",
    "诊断",
    "检查",
    "治疗",
    "预后",
    "预防",
)
NON_ENTITY_TERMS = frozenset(ENTITY_ASPECT_SUFFIXES)
ENTITY_CONFLICT_RE = re.compile(r".{2,}(?:与|和|及|、|/).{2,}")
EXPLICIT_DISEASE_DEFINITION_RE = re.compile(
    r"(?P<name>[\u4e00-\u9fffA-Za-z0-9-]{2,30}(?:肺炎|疾病|病|癌|瘤|综合征))"
    r"\s*[（(][^）)]{1,100}[）)]\s*是"
)
UMBRELLA_DISEASE_ENTITIES = frozenset({"肺炎", "细菌性肺炎"})


def resolve_book_id(source_path: Path) -> str:
    if source_path.stem in {"内科学（第10版）", CANONICAL_TEXTBOOK_ID}:
        return CANONICAL_TEXTBOOK_ID
    return source_path.stem


def recover_explicit_disease_entity(parent_entity: str, source_text: str) -> str:
    if parent_entity not in UMBRELLA_DISEASE_ENTITIES:
        return parent_entity
    matches = list(EXPLICIT_DISEASE_DEFINITION_RE.finditer(source_text or ""))
    names = list(dict.fromkeys(match.group("name") for match in matches))
    return names[0] if len(names) == 1 else parent_entity


@dataclass
class MarkdownChunk:
    index: int
    headings: list[str]
    content: str


@dataclass
class CatalogUnit:
    index: int
    title: str
    level: int
    page_start: int
    page_end: int
    headings: list[str]


@dataclass(frozen=True)
class NodeEntityResult:
    entity: str | None
    reason: str


def stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"v3-{digest}"


def resolve_map_hierarchy(headings: list[str]) -> tuple[str, str | None]:
    """Map Markdown headings to the app's part/chapter tree contract."""
    clean = [heading.strip() for heading in headings if heading.strip()]
    part = next((h for h in reversed(clean) if PART_RE.search(h)), None)
    chapter = next((h for h in reversed(clean) if CHAPTER_RE.search(h)), None)

    if not part:
        part = clean[0] if clean else "基础/概论"
    if not chapter:
        candidates = [h for h in clean if h != part]
        chapter = candidates[0] if candidates else None
    return part, chapter


def resolve_catalog_page_range(
    units: list[dict[str, Any]],
    headings: list[str],
) -> tuple[int | None, int | None]:
    normalized = [str(value).strip() for value in headings if str(value).strip()]
    if not normalized:
        return None, None

    best: dict[str, Any] | None = None
    best_score = -1
    for unit in units:
        unit_headings = [
            str(value).strip()
            for value in (unit.get("headings") or [])
            if str(value).strip()
        ]
        score = 0
        for left, right in zip(reversed(normalized), reversed(unit_headings)):
            if left != right:
                break
            score += 1
        if score > best_score:
            best = unit
            best_score = score

    if not best or best_score <= 0:
        return None, None
    return best.get("page_start"), best.get("page_end")


def clean_toc_title(title: str) -> str:
    return re.sub(r"[\x00-\x1f]+", "", title).strip()


def is_content_heading(title: str) -> bool:
    return bool(
        PART_RE.search(title)
        or CHAPTER_RE.search(title)
        or re.search(r"第[一二三四五六七八九十百零〇\d]+节", title)
        or title in {"绪论", "总论", "概论"}
    )


def build_catalog_units(
    raw_toc: list[list[Any]], total_pages: int
) -> tuple[list[dict[str, Any]], list[CatalogUnit]]:
    entries: list[dict[str, Any]] = []
    stack: list[str] = []
    content_started = False
    content_start_page: int | None = None
    for raw_level, raw_title, raw_page in raw_toc:
        title = clean_toc_title(str(raw_title))
        level = max(1, int(raw_level))
        page = min(max(1, int(raw_page)), total_pages)
        if not title:
            continue
        if is_content_heading(title):
            content_started = True
            if content_start_page is None:
                content_start_page = page
        del stack[level - 1 :]
        while len(stack) < level - 1:
            stack.append("")
        stack.append(title)
        entries.append(
            {
                "level": level,
                "title": title,
                "page": page,
                "headings": [value for value in stack if value],
                "is_content": content_started,
                "page_is_in_content_range": (
                    content_start_page is not None and page >= content_start_page
                ),
            }
        )

    content_entries = [
        entry
        for entry in entries
        if entry["is_content"] and entry["page_is_in_content_range"]
    ]
    by_page: dict[int, dict[str, Any]] = {}
    for entry in content_entries:
        current = by_page.get(entry["page"])
        if current is None or entry["level"] >= current["level"]:
            by_page[entry["page"]] = entry

    page_entries = [by_page[page] for page in sorted(by_page)]
    units: list[CatalogUnit] = []
    for index, entry in enumerate(page_entries):
        next_page = (
            page_entries[index + 1]["page"]
            if index + 1 < len(page_entries)
            else total_pages + 1
        )
        page_end = max(entry["page"], next_page - 1)
        units.append(
            CatalogUnit(
                index=index,
                title=entry["title"],
                level=entry["level"],
                page_start=entry["page"],
                page_end=min(page_end, total_pages),
                headings=entry["headings"],
            )
        )
    return entries, units


def split_markdown(markdown: str, max_chars: int) -> list[MarkdownChunk]:
    heading_stack: list[str] = []
    sections: list[tuple[list[str], str]] = []
    body: list[str] = []

    def flush() -> None:
        text = "\n".join(body).strip()
        if text:
            sections.append((heading_stack.copy(), text))
        body.clear()

    for line in markdown.splitlines():
        match = re.match(r"^(#{1,3})\s+(.+?)\s*$", line)
        if not match:
            body.append(line)
            continue
        flush()
        level = len(match.group(1))
        del heading_stack[level - 1 :]
        while len(heading_stack) < level - 1:
            heading_stack.append("")
        heading_stack.append(match.group(2).strip())
        body.append(line)
    flush()

    chunks: list[MarkdownChunk] = []
    for headings, section in sections:
        for piece in split_oversized_section(section, max_chars):
            if len(piece.strip()) >= 40:
                chunks.append(MarkdownChunk(len(chunks), headings, piece))
    return chunks


def split_oversized_section(text: str, max_chars: int) -> list[str]:
    return structure_aware_split(text, max_chars)


def repair_json_text(content: str) -> str:
    """Best-effort cleanup for common LLM JSON mistakes."""
    cleaned = content.strip()
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    cleaned = re.sub(r"//.*", "", cleaned)
    return cleaned


def salvage_nodes_from_json(content: str) -> dict[str, Any]:
    """Recover node objects when the outer JSON object is malformed."""
    nodes: list[dict[str, Any]] = []
    for match in re.finditer(
        r'\{[^{}]*"title"\s*:\s*"[^"]+?"[^{}]*"content"\s*:\s*"[^"]*?"[^{}]*\}',
        content,
        flags=re.DOTALL,
    ):
        try:
            node = json.loads(repair_json_text(match.group(0)))
        except json.JSONDecodeError:
            continue
        if isinstance(node, dict) and node.get("title"):
            nodes.append(node)
    if nodes:
        return {"nodes": nodes, "edges": []}
    raise ValueError("Unable to salvage nodes from malformed JSON")


def extract_json(content: str) -> dict[str, Any]:
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()
    candidates = [content]
    start, end = content.find("{"), content.rfind("}")
    if start >= 0 and end > start:
        candidates.append(content[start : end + 1])
    last_exc: json.JSONDecodeError | None = None
    for candidate in candidates:
        for variant in (candidate, repair_json_text(candidate)):
            try:
                result = json.loads(variant)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError as exc:
                last_exc = exc
    if last_exc is not None:
        try:
            return salvage_nodes_from_json(content)
        except ValueError:
            raise last_exc
    raise ValueError("Ollama response must be a JSON object")


def make_standalone(text: str, parent_entity: str) -> str:
    text = text.strip()
    if not text or not parent_entity or parent_entity in text:
        return text
    return f"{parent_entity}：{text}"


def entity_confirmed_in_text(entity: str, *texts: str) -> bool:
    """Return True when entity appears in any provided text blob."""
    entity = entity.strip()
    if not entity:
        return False
    return any(entity in (text or "") for text in texts)


def title_declares_entity(title: str, entity: str) -> bool:
    """Accept titles like '支气管哮喘的临床表现' or '慢性血栓栓塞性肺疾病'."""
    title = title.strip()
    entity = entity.strip()
    if not title or not entity:
        return False
    return title == entity or title.startswith(f"{entity}的")


def identify_node_entity(
    title: str,
    content: str,
    aspect: str,
    evidence: str = "",
) -> NodeEntityResult:
    """Identify a title-derived medical subject and confirm it in raw content."""
    title = title.strip()
    content = content.strip()
    evidence = evidence.strip()
    if not title:
        return NodeEntityResult(None, "title_missing")

    searchable = "\n".join(value for value in (content, evidence) if value)

    if title not in NON_ENTITY_TERMS and not CONTEXT_DEPENDENT_RE.match(title):
        if title in searchable or evidence:
            return NodeEntityResult(title, "confirmed_title_entity")

    suffixes = sorted(
        {value for value in (*ENTITY_ASPECT_SUFFIXES, aspect.strip()) if value},
        key=len,
        reverse=True,
    )
    candidate: str | None = None
    for suffix in suffixes:
        if title == suffix:
            return NodeEntityResult(None, "aspect_only_title")
        for marker in (f"的{suffix}", suffix):
            if title.endswith(marker) and len(title) > len(marker):
                candidate = title[: -len(marker)].strip(" ：:，,。；;")
                break
        if candidate:
            break

    if not candidate:
        return NodeEntityResult(None, "aspect_suffix_not_found")
    if candidate in NON_ENTITY_TERMS:
        return NodeEntityResult(None, "non_entity_candidate")
    if len(candidate) < 2 or CONTEXT_DEPENDENT_RE.match(candidate):
        return NodeEntityResult(None, "context_dependent_candidate")
    if ENTITY_CONFLICT_RE.fullmatch(candidate):
        return NodeEntityResult(None, "entity_conflict")
    if entity_confirmed_in_text(candidate, searchable) or title_declares_entity(
        title, candidate
    ):
        return NodeEntityResult(candidate, "confirmed_in_title_and_content")
    return NodeEntityResult(None, "entity_not_confirmed_in_content")


class MedlearnPipeline:
    def __init__(
        self,
        source_path: Path,
        output_dir: Path,
        model: str,
        ollama_url: str,
        max_chars: int,
        num_ctx: int,
        limit: int | None,
        subject: str | None,
        section_limit: int | None,
        section_start: int,
        pymupdf_only: bool | None = None,
        pdf_parser_mode: str | None = None,
    ) -> None:
        self.source_path = source_path.resolve()
        self.output_dir = output_dir.resolve()
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.max_chars = max_chars
        self.num_ctx = num_ctx
        self.limit = limit
        self.section_limit = section_limit
        self.section_start = section_start
        if pdf_parser_mode:
            self.pdf_parser_mode = pdf_parser_mode
        elif pymupdf_only is True:
            self.pdf_parser_mode = "pymupdf"
        elif pymupdf_only is False:
            self.pdf_parser_mode = "docling"
        else:
            self.pdf_parser_mode = resolve_pdf_parser_mode()
        self.pymupdf_only = self.pdf_parser_mode == "pymupdf"
        self.pdf_parser = AdaptivePdfParser(
            self.source_path,
            mode=self.pdf_parser_mode,
            profile_cache_path=(
                self.output_dir / f"{self.source_path.stem}.parser-profile.json"
            ),
            artifact_dir=(
                self.output_dir
                / "source-assets"
                / self.source_path.stem
            ),
        ) if self.source_path.suffix.lower() == ".pdf" else None
        self.subject = subject or self.source_path.stem
        self.book_id = resolve_book_id(self.source_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def section_scoped(self) -> bool:
        return self.section_limit is not None

    @property
    def scope_tag(self) -> str:
        if not self.section_scoped:
            return ""
        limit = self.section_limit or 1
        return f".s{self.section_start}.l{limit}"

    def scoped_output_path(self, suffix: str) -> Path:
        return self.output_dir / f"{self.source_path.stem}{self.scope_tag}{suffix}"

    @property
    def markdown_path(self) -> Path:
        return self.scoped_output_path(".md")

    @property
    def cache_path(self) -> Path:
        return self.scoped_output_path(".extraction.json")

    @property
    def catalog_path(self) -> Path:
        return self.output_dir / f"{self.source_path.stem}.catalog.json"

    @property
    def catalog_report_path(self) -> Path:
        return self.output_dir / f"{self.source_path.stem}.catalog-report.json"

    @property
    def parse_report_path(self) -> Path:
        return self.scoped_output_path(".parse-report.json")

    @property
    def source_artifacts_path(self) -> Path:
        return self.scoped_output_path(".source-artifacts.json")

    def build_catalog(self, force: bool = False) -> list[CatalogUnit]:
        if self.source_path.suffix.lower() == ".md":
            return []
        if self.catalog_path.exists() and not force:
            cached = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            return [CatalogUnit(**unit) for unit in cached.get("units", [])]

        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        document = fitz.open(str(self.source_path))
        catalog_source = "bookmarks"
        try:
            total_pages = document.page_count
            raw_toc = document.get_toc()
            if not raw_toc:
                raw_toc = infer_toc_from_layout(document)
                catalog_source = "layout_inference"
            if not raw_toc:
                raw_toc = page_window_toc(total_pages)
                catalog_source = "page_windows"
        finally:
            document.close()

        entries, units = build_catalog_units(raw_toc, total_pages)
        if not units and catalog_source == "page_windows":
            units = [
                CatalogUnit(
                    index=index,
                    title=str(title),
                    level=int(level),
                    page_start=int(page),
                    page_end=min(
                        total_pages,
                        int(raw_toc[index + 1][2]) - 1
                        if index + 1 < len(raw_toc)
                        else total_pages,
                    ),
                    headings=[str(title)],
                )
                for index, (level, title, page) in enumerate(raw_toc)
            ]
            entries = [
                {
                    "level": unit.level,
                    "title": unit.title,
                    "page": unit.page_start,
                    "headings": unit.headings,
                    "is_content": True,
                    "page_is_in_content_range": True,
                }
                for unit in units
            ]
        if not units:
            raw_toc = page_window_toc(total_pages)
            catalog_source = "page_windows"
            entries = []
            units = []
            for index, (level, title, page) in enumerate(raw_toc):
                page_end = (
                    int(raw_toc[index + 1][2]) - 1
                    if index + 1 < len(raw_toc)
                    else total_pages
                )
                unit = CatalogUnit(
                    index=index,
                    title=str(title),
                    level=int(level),
                    page_start=int(page),
                    page_end=page_end,
                    headings=[str(title)],
                )
                units.append(unit)
                entries.append(
                    {
                        "level": unit.level,
                        "title": unit.title,
                        "page": unit.page_start,
                        "headings": unit.headings,
                        "is_content": True,
                        "page_is_in_content_range": True,
                    }
                )
        payload = {
            "subject": self.subject,
            "source": str(self.source_path),
            "total_pages": total_pages,
            "catalog_source": catalog_source,
            "toc_entries": entries,
            "units": [
                {
                    "index": unit.index,
                    "title": unit.title,
                    "level": unit.level,
                    "page_start": unit.page_start,
                    "page_end": unit.page_end,
                    "headings": unit.headings,
                }
                for unit in units
            ],
        }
        self.catalog_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        covered_pages = {
            page
            for unit in units
            for page in range(unit.page_start, unit.page_end + 1)
        }
        report = {
            "subject": self.subject,
            "total_pages": total_pages,
            "raw_toc_entries": len(raw_toc),
            "clean_toc_entries": len(entries),
            "content_units": len(units),
            "catalog_source": catalog_source,
            "discarded_backward_toc_entries": sum(
                entry["is_content"] and not entry["page_is_in_content_range"]
                for entry in entries
            ),
            "content_page_start": units[0].page_start,
            "content_page_end": units[-1].page_end,
            "covered_content_pages": len(covered_pages),
            "overlapping_units": sum(
                units[index].page_start <= units[index - 1].page_end
                for index in range(1, len(units))
            ),
            "invalid_ranges": sum(
                unit.page_end < unit.page_start for unit in units
            ),
            "checks": {
                "has_toc": bool(raw_toc),
                "has_content_units": bool(units),
                "ranges_valid": all(
                    unit.page_start <= unit.page_end for unit in units
                ),
                "ranges_non_overlapping": all(
                    units[index].page_start > units[index - 1].page_end
                    for index in range(1, len(units))
                ),
            },
        }
        self.catalog_report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"[+] 目录识别: {len(entries)} 条书签，"
            f"{len(units)} 个正文分页单元"
        )
        return units

    def read_pdf_by_catalog(
        self, units: list[CatalogUnit], force: bool = False
    ) -> str:
        if self.markdown_path.exists() and not force:
            print(f"[*] 使用目录分段 Markdown 缓存: {self.markdown_path}")
            return self.markdown_path.read_text(encoding="utf-8")
        selected = units[self.section_start :]
        if self.section_limit:
            selected = selected[: self.section_limit]
        documents: list[str] = []
        parse_units: list[dict[str, Any]] = []
        all_locators: list[dict[str, Any]] = []
        parser_mode = self.pdf_parser_mode
        print(f"[*] {parser_mode} 按目录解析 {len(selected)} 个分页单元")
        for position, unit in enumerate(selected, start=1):
            if self.pdf_parser is None:
                raise RuntimeError("Adaptive PDF parser is unavailable for a non-PDF source")
            markdown, unit_report = self.pdf_parser.parse_range(
                unit.page_start,
                unit.page_end,
            )
            if len(markdown) < 40:
                raise RuntimeError(
                    f"目录单元 p{unit.page_start}-{unit.page_end} 解析过短"
                )
            all_locators.extend(unit_report.get("locators") or [])
            heading_lines = [
                f"{'#' * min(index + 1, 3)} {heading}"
                for index, heading in enumerate(unit.headings[-3:])
            ]
            documents.append("\n".join([*heading_lines, markdown]))
            parse_units.append(
                {
                    "catalog_index": unit.index,
                    "title": unit.title,
                    "page_start": unit.page_start,
                    "page_end": unit.page_end,
                    "parser": parser_mode,
                    "parser_counts": unit_report.get("parser_counts") or {},
                    "characters": len(markdown),
                    "blocking_pages": unit_report.get("blocking_pages") or [],
                    "pages": unit_report.get("pages") or [],
                }
            )
            print(
                f"  [+] {position}/{len(selected)} "
                f"p{unit.page_start}-{unit.page_end} {unit.title}"
            )
        combined = "\n\n".join(documents)
        self.markdown_path.write_text(combined, encoding="utf-8")
        parse_report = {
            "subject": self.subject,
            "total_units": len(parse_units),
            "parser_mode": parser_mode,
            "page_parser_counts": dict(
                sum(
                    (Counter(unit.get("parser_counts") or {}) for unit in parse_units),
                    Counter(),
                )
            ),
            "blocking_pages": sorted(
                {
                    page
                    for unit in parse_units
                    for page in (unit.get("blocking_pages") or [])
                }
            ),
            "artifact_counts": dict(
                Counter(str(locator.get("kind") or "unknown") for locator in all_locators)
            ),
            "units": parse_units,
            "checks": {
                "all_units_have_content": all(
                    unit["characters"] >= 40 for unit in parse_units
                ),
                "no_blocking_pages": not any(
                    unit.get("blocking_pages") for unit in parse_units
                ),
            },
        }
        parse_report["docling_units"] = sum(
            bool(
                {
                    "docling",
                    "docling_ocr",
                }
                & set((unit.get("parser_counts") or {}).keys())
            )
            for unit in parse_units
        )
        parse_report["fallback_units"] = sum(
            "pymupdf_fallback" in (unit.get("parser_counts") or {})
            for unit in parse_units
        )
        parse_report["checks"]["all_units_used_docling"] = bool(parse_units) and all(
            set((unit.get("parser_counts") or {}).keys())
            <= {"docling", "docling_ocr"}
            for unit in parse_units
        )
        self.parse_report_path.write_text(
            json.dumps(parse_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.source_artifacts_path.write_text(
            json.dumps(
                {
                    "source": str(self.source_path),
                    "parser_mode": parser_mode,
                    "locators": all_locators,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if not parse_report["checks"]["no_blocking_pages"]:
            raise RuntimeError(
                "PDF parsing quality gate failed for pages: "
                f"{parse_report['blocking_pages']}"
            )
        return combined

    def read_unit_with_pymupdf(self, unit: CatalogUnit) -> str:
        parser = AdaptivePdfParser(
            self.source_path,
            mode="pymupdf",
            profile_cache_path=(
                self.output_dir / f"{self.source_path.stem}.parser-profile.json"
            ),
            artifact_dir=(
                self.output_dir
                / "source-assets"
                / self.source_path.stem
            ),
        )
        markdown, _ = parser.parse_range(unit.page_start, unit.page_end)
        return markdown

    def read_source(self, force: bool = False) -> str:
        if self.source_path.suffix.lower() in {".md", ".markdown"}:
            return self.source_path.read_text(encoding="utf-8")
        units = self.build_catalog(force=force)
        return self.read_pdf_by_catalog(units, force=force)

    def max_content_chars_for_ctx(self) -> int:
        """Keep prompt + output inside num_ctx (4096 tokens ≈ chars for Chinese)."""
        ctx = min(self.num_ctx, 4096)
        reserved = 1900
        return max(1200, min(self.max_chars, ctx - reserved))

    def build_extraction_prompt(self, chunk: MarkdownChunk, content: str) -> str:
        path = " > ".join(filter(None, chunk.headings)) or "未识别"
        return f"""你是医学教材“原子知识块”抽取器。仅根据给定原文抽取，不补充原文外事实。

要求：
1. nodes.type 只能是 concept、mechanism、disease、symptom、treatment、exam。
2. 每个节点代表 parent_entity 的一个知识面向；疾病章节中 parent_entity 必须是章节疾病或明确疾病亚型。药物、术式、检查项目、治疗步骤不得成为独立 parent_entity，必须作为该疾病“治疗”或“诊断”节点中的枚举子项。
   原文若明确出现“X肺炎/X疾病是……”等命名疾病定义，parent_entity 必须保留 X 的完整疾病名，禁止上卷成“细菌性肺炎”“肺炎”等总类。
3. title 建议写“parent_entity + 的 + aspect”；content 首句必须写出 parent_entity 全称，不能用“该病、其、上述”。
4. aspect 填原文面向；evidence 必须是原文中的连续片段，禁止改写或编造。
5. 只抽取当前章节主体相关内容，禁止把一种治疗泛化到其他病种（如变应性鼻炎、过敏性结膜炎）。
6. 同一个 parent_entity + aspect 只能输出一个 node。治疗、诊断、检查中的 1.2.3.、①②③ 等枚举项必须保留在同一 node 的 content 或 key_points 中，禁止拆成并列 nodes。
7. 最多输出 {MAX_NODES_PER_CHUNK} 个 nodes；优先保留定义、机制、诊断、治疗主干。
8. edges.relation 用 causes、characteristic_of、treated_by、complication_of、associated_with。
9. 只输出合法 JSON，不要输出空 nodes。

JSON 格式：
{{
  "nodes": [{{"title": "主体的知识面向", "type": "disease", "parent_entity": "主体名", "aspect": "面向", "content": "含主体的结论", "evidence": "原文片段", "tags": []}}],
  "edges": [{{"source": "节点A", "target": "节点B", "relation": "causes"}}]
}}

章节路径：{path}
教材原文：
{content}
/no_think"""

    def call_ollama_once(self, prompt: str) -> dict[str, Any]:
        import requests

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "10m"),
            "messages": [{"role": "user", "content": prompt}],
            "options": {
                "temperature": 0.1,
                "num_ctx": min(self.num_ctx, 4096),
                "num_gpu": int(os.getenv("OLLAMA_NUM_GPU", "999")),
                "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "1024")),
            },
        }
        response = requests.post(
            f"{self.ollama_url}/api/chat", json=payload, timeout=180
        )
        response.raise_for_status()
        return extract_json(response.json()["message"]["content"])

    def warmup_ollama(self) -> None:
        import requests

        try:
            requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "10m"),
                    "messages": [{"role": "user", "content": "回复 OK"}],
                    "options": {
                        "num_ctx": 512,
                        "num_gpu": int(os.getenv("OLLAMA_NUM_GPU", "999")),
                    },
                },
                timeout=120,
            ).raise_for_status()
            print("[*] Ollama 模型已预热")
        except Exception as exc:
            print(f"[!] Ollama 预热失败（继续尝试提取）: {exc}")

    def build_compact_extraction_prompt(self, chunk: MarkdownChunk, content: str) -> str:
        path = " > ".join(filter(None, chunk.headings)) or "未识别"
        return f"""你是医学教材原子知识块抽取器。仅根据原文抽取，不补充原文外事实。
最多输出 6 个 nodes；每个节点必须含 parent_entity、aspect、evidence。
同一 parent_entity + aspect 只能有一个 node；枚举子项写入同一 content 或 key_points，禁止拆成并列 nodes。
疾病章节中的药物、术式、检查项目不得成为独立 parent_entity，必须归入章节疾病的治疗或诊断节点。
原文明确定义命名疾病时，parent_entity 必须使用完整疾病名，不得用章节总类替代。
content 首句必须写出 parent_entity 全称。只输出合法 JSON。

JSON 格式：
{{"nodes":[{{"title":"主体的知识面向","type":"disease","parent_entity":"主体名","aspect":"面向","content":"含主体的结论","evidence":"原文片段","tags":[]}}],"edges":[]}}

章节路径：{path}
教材原文：
{content}
/no_think"""

    def call_ollama(self, chunk: MarkdownChunk, retries: int = 3) -> dict[str, Any]:
        import requests

        content = chunk.content[: self.max_content_chars_for_ctx()]
        prompt = self.build_extraction_prompt(chunk, content)
        last_exc: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                data = self.call_ollama_once(prompt)
                if not data.get("nodes"):
                    raise ValueError("Ollama 返回空 nodes")
                return data
            except requests.HTTPError as exc:
                last_exc = exc
                status = exc.response.status_code if exc.response is not None else None
                if status == 400 and len(content) > 1200:
                    content = content[: max(1000, len(content) // 2)]
                    prompt = self.build_extraction_prompt(chunk, content)
                    print(f"  [!] 块 {chunk.index} 上下文过长，截断至 {len(content)} 字重试")
                    continue
                if status in {400, 500} and attempt < retries:
                    time.sleep(attempt * 2)
                    continue
                if status in {400, 500}:
                    raise RuntimeError(f"Ollama 调用失败: {exc}") from exc
            except (json.JSONDecodeError, ValueError) as exc:
                last_exc = exc
                if attempt < retries:
                    compact = chunk.content[: max(1000, len(content) // 2)]
                    prompt = self.build_compact_extraction_prompt(chunk, compact)
                    print(f"  [!] 块 {chunk.index} JSON/空结果，切换紧凑 prompt 重试")
                    continue
            except (requests.RequestException, KeyError) as exc:
                last_exc = exc
            if attempt < retries:
                time.sleep(attempt * 2)
        raise RuntimeError(f"Ollama 调用失败（重试 {retries} 次）: {last_exc}") from last_exc

    def _persist_chunk_result(
        self,
        cache: dict[str, Any],
        chunk: MarkdownChunk,
        data: dict[str, Any],
    ) -> None:
        cache["chunks"][str(chunk.index)] = {
            "headings": chunk.headings,
            "content": chunk.content,
            "nodes": (data.get("nodes", []) or [])[:MAX_NODES_PER_CHUNK],
            "edges": data.get("edges", []),
        }
        self.cache_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def extract(self, chunks: list[MarkdownChunk], resume: bool = True) -> dict[str, Any]:
        cache: dict[str, Any] = {"subject": self.subject, "chunks": {}}
        if resume and self.cache_path.exists():
            cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            cache.setdefault("chunks", {})

        selected = chunks[: self.limit] if self.limit else chunks
        if not selected:
            print("[*] 无可提取语义块")
            return cache
        print(f"[*] 共 {len(chunks)} 个语义块，本次处理 {len(selected)} 个")
        if not cache["chunks"] and not os.getenv("OLLAMA_SKIP_WARMUP"):
            self.warmup_ollama()

        pending: list[MarkdownChunk] = []
        for position, chunk in enumerate(selected, start=1):
            key = str(chunk.index)
            if key in cache["chunks"]:
                print(f"  [=] {position}/{len(selected)} 块 {chunk.index} 已缓存")
                continue
            pending.append(chunk)

        concurrency = max(1, int(os.getenv("OLLAMA_CONCURRENCY", "1")))
        failed: list[MarkdownChunk] = []

        if concurrency <= 1 or len(pending) <= 1:
            # Serial path (original behavior)
            for position, chunk in enumerate(pending, start=1):
                try:
                    data = self.call_ollama(chunk)
                    self._persist_chunk_result(cache, chunk, data)
                    print(
                        f"  [+] {len(selected) - len(pending) + position}/{len(selected)} "
                        f"块 {chunk.index}: {len(data.get('nodes', []))} 个节点"
                    )
                except RuntimeError as exc:
                    failed.append(chunk)
                    print(f"  [!] 块 {chunk.index} 跳过: {exc}")
        else:
            # Concurrent Ollama calls, ordered persistence
            from concurrent.futures import ThreadPoolExecutor, as_completed

            print(f"[*] 并发模式: concurrency={concurrency}, pending={len(pending)}")
            results: dict[int, dict[str, Any] | Exception] = {}
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                future_to_chunk = {
                    executor.submit(self.call_ollama, chunk): chunk
                    for chunk in pending
                }
                for future in as_completed(future_to_chunk):
                    chunk = future_to_chunk[future]
                    try:
                        results[chunk.index] = future.result()
                    except RuntimeError as exc:
                        results[chunk.index] = exc

            # Main thread: persist in chunk order to keep cache stable
            for position, chunk in enumerate(pending, start=1):
                result = results.get(chunk.index)
                if result is None:
                    failed.append(chunk)
                    print(f"  [!] 块 {chunk.index} 跳过: no result")
                elif isinstance(result, Exception):
                    failed.append(chunk)
                    print(f"  [!] 块 {chunk.index} 跳过: {result}")
                else:
                    self._persist_chunk_result(cache, chunk, result)
                    print(
                        f"  [+] {len(selected) - len(pending) + position}/{len(selected)} "
                        f"块 {chunk.index}: {len(result.get('nodes', []))} 个节点"
                    )

        if failed:
            print(f"[*] 对 {len(failed)} 个失败块做最终重试")
            for chunk in failed:
                try:
                    data = self.call_ollama(chunk, retries=2)
                    self._persist_chunk_result(cache, chunk, data)
                    print(
                        f"  [+] 重试成功 块 {chunk.index}: "
                        f"{len(data.get('nodes', []))} 个节点"
                    )
                except RuntimeError as exc:
                    print(f"  [!] 重试仍失败 块 {chunk.index}: {exc}")

        raw_nodes = sum(
            len(result.get("nodes") or [])
            for result in cache.get("chunks", {}).values()
        )
        print(
            f"[*] 提取缓存: {len(cache.get('chunks', {}))} 块, "
            f"原始节点 {raw_nodes}"
        )
        return cache

    def build_rows(self, cache: dict[str, Any]) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str | None, str, str], dict[str, Any]] = {}
        title_to_key: dict[
            tuple[str, str | None, str],
            tuple[str, str | None, str, str],
        ] = {}
        pending_edges: list[tuple[str, str | None, dict[str, Any]]] = []
        catalog_units: list[dict[str, Any]] = []
        source_locators: list[dict[str, Any]] = []
        if self.catalog_path.exists():
            catalog_payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            catalog_units = catalog_payload.get("units") or []
        if self.source_artifacts_path.exists():
            artifact_payload = json.loads(
                self.source_artifacts_path.read_text(encoding="utf-8")
            )
            source_locators = artifact_payload.get("locators") or []
        active_explicit_disease: str | None = None

        for chunk_index, result in cache.get("chunks", {}).items():
            headings = result.get("headings") or []
            chapter, sub_chapter = resolve_map_hierarchy(headings)
            page_start, page_end = resolve_catalog_page_range(catalog_units, headings)
            source_text = str(result.get("content") or "")
            section_entity = extract_section_entity(sub_chapter or "")
            for raw in (result.get("nodes") or [])[:MAX_NODES_PER_CHUNK]:
                title = str(raw.get("title", "")).strip()
                raw_content = str(raw.get("content", "")).strip()
                raw_parent_entity = str(raw.get("parent_entity", "")).strip()
                parent_entity = (
                    active_explicit_disease
                    if raw_parent_entity in UMBRELLA_DISEASE_ENTITIES
                    and active_explicit_disease
                    else raw_parent_entity
                )
                if parent_entity != raw_parent_entity:
                    title = title.replace(raw_parent_entity, parent_entity)
                    raw_content = raw_content.replace(
                        raw_parent_entity,
                        parent_entity,
                    )
                raw_aspect = str(raw.get("aspect", "")).strip()
                aspect = canonicalize_aspect_label(raw_aspect)
                evidence = str(raw.get("evidence", "")).strip()
                if is_cross_disease_expansion(
                    title, parent_entity, section_entity=section_entity
                ):
                    continue
                if source_text and not evidence_supported_by_source(evidence, source_text):
                    continue
                if not source_text:
                    continue
                if looks_self_referential_evidence(evidence, raw_content):
                    continue
                node_entity = identify_node_entity(
                    title, raw_content, aspect, evidence
                )
                content = make_standalone(
                    raw_content, node_entity.entity or parent_entity
                )
                if not self.is_atomic_node(
                    title,
                    content,
                    parent_entity,
                    aspect,
                    evidence,
                    node_entity.entity,
                ):
                    continue
                key = (chapter, sub_chapter, parent_entity, aspect)
                matched_locators = find_evidence_locators(
                    source_locators,
                    evidence,
                    page_start=page_start,
                    page_end=page_end,
                )
                group_title = f"{parent_entity}的{aspect}"
                title_to_key[(chapter, sub_chapter, title)] = key
                node_type = str(raw.get("type", "concept"))
                tags = [str(tag) for tag in raw.get("tags", []) if str(tag) in VINDICATE_TAGS]
                row = merged.setdefault(
                    key,
                    {
                        "id": stable_id(
                            self.subject,
                            chapter,
                            sub_chapter or "",
                            parent_entity,
                            aspect,
                        ),
                        "order_num": len(merged),
                        "level": 3,
                        "type": node_type if node_type in ALLOWED_TYPES else "concept",
                        "title": group_title,
                        "subject": self.subject,
                        "chapter": chapter,
                        "sub_chapter": sub_chapter,
                        "knowledge_path": [
                            p
                            for p in [
                                self.subject,
                                chapter,
                                sub_chapter,
                                group_title,
                            ]
                            if p
                        ],
                        "content": content,
                        "key_points": [],
                        "structured_sections": [],
                        "causal_links": [],
                        "related_nodes": [],
                        "tags": [],
                        "source": "pipeline_v3",
                        "book_id": self.book_id,
                        "textbook": self.subject,
                        "node_source": "llm_extracted",
                        "inferred": False,
                        "standalone": True,
                        "parent_chapter": parent_entity or sub_chapter,
                        "source_span": {
                            "chunk_index": int(chunk_index),
                            "headings": headings,
                            "parent_entity": parent_entity,
                            "aspect": aspect,
                            "raw_aspect": raw_aspect,
                            "evidence": evidence,
                            "evidence_items": [],
                            "source_locators": [],
                            "page_start": page_start,
                            "page_end": page_end,
                        },
                        "version": "3.0",
                    },
                )
                section = {"title": title, "content": content}
                if section not in row["structured_sections"]:
                    row["structured_sections"].append(section)
                evidence_items = row["source_span"]["evidence_items"]
                if evidence and evidence not in evidence_items:
                    evidence_items.append(evidence)
                row_locators = row["source_span"]["source_locators"]
                known_artifact_ids = {
                    locator.get("artifact_id") for locator in row_locators
                }
                for locator in matched_locators:
                    if locator.get("artifact_id") not in known_artifact_ids:
                        row_locators.append(locator)
                        known_artifact_ids.add(locator.get("artifact_id"))
                key_points = [
                    make_standalone(str(value), parent_entity)
                    for value in raw.get("key_points", [])
                    if str(value).strip()
                ]
                row["key_points"] = list(
                    dict.fromkeys([*row["key_points"], *key_points])
                )
                row["tags"] = list(dict.fromkeys([*row["tags"], *tags]))
            for edge in result.get("edges") or []:
                pending_edges.append((chapter, sub_chapter, edge))
            explicit_disease = recover_explicit_disease_entity(
                "细菌性肺炎",
                source_text,
            )
            if explicit_disease != "细菌性肺炎":
                active_explicit_disease = explicit_disease

        for row in merged.values():
            sections = row["structured_sections"]
            aspect = str((row.get("source_span") or {}).get("aspect") or "知识要点")
            if len(sections) == 1:
                row["content"] = sections[0]["content"]
                row["structured_sections"] = [
                    {"title": aspect, "content": sections[0]["content"]}
                ]
                continue
            row["content"] = "\n\n".join(
                f"{index}. {section['title']}\n{section['content']}"
                for index, section in enumerate(sections, start=1)
            )

        for chapter, sub_chapter, edge in pending_edges:
            source_title = str(edge.get("source", "")).strip()
            target_title = str(edge.get("target", "")).strip()
            source_key = title_to_key.get((chapter, sub_chapter, source_title))
            target_key = title_to_key.get((chapter, sub_chapter, target_title))
            source = merged.get(source_key) if source_key else None
            target = merged.get(target_key) if target_key else None
            if not source or not target or source["id"] == target["id"]:
                continue
            relation = str(edge.get("relation") or "associated_with")
            link = {
                "from": source["title"],
                "to": target["title"],
                "target_id": target["id"],
                "relation": relation,
            }
            if link not in source["causal_links"]:
                source["causal_links"].append(link)
            source["related_nodes"] = list(dict.fromkeys([*source["related_nodes"], target["id"]]))
            target["related_nodes"] = list(dict.fromkeys([*target["related_nodes"], source["id"]]))
        return list(merged.values())

    @staticmethod
    def is_atomic_node(
        title: str,
        content: str,
        parent_entity: str,
        aspect: str,
        evidence: str,
        node_entity: str | None,
    ) -> bool:
        if len(title) < 4 or len(content) < 15:
            return False
        if not parent_entity or not aspect or len(evidence) < 6:
            return False
        if CONTEXT_DEPENDENT_RE.match(title) or CONTEXT_DEPENDENT_RE.match(content):
            return False

        corpus = "\n".join(value for value in (title, content, evidence) if value)
        parent_in_title = entity_confirmed_in_text(parent_entity, title)
        parent_in_corpus = entity_confirmed_in_text(parent_entity, corpus)
        parent_path = parent_in_title and (
            parent_in_corpus
            or title_declares_entity(title, parent_entity)
            or title == parent_entity
        )
        node_path = bool(
            node_entity
            and entity_confirmed_in_text(node_entity, title)
            and entity_confirmed_in_text(node_entity, corpus)
        )
        return parent_path or node_path

    def write_outputs(self, rows: list[dict[str, Any]]) -> tuple[Path, Path, Path]:
        nodes_path = self.scoped_output_path(".nodes.json")
        preview_path = self.scoped_output_path(".map-preview.json")
        quality_path = self.scoped_output_path(".quality-report.json")
        nodes_path.write_text(
            json.dumps({"subject": self.subject, "nodes": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        parts: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for row in rows:
            part = parts.setdefault(row["chapter"] or "基础/概论", {})
            part.setdefault(row["sub_chapter"] or "直属知识点", []).append({
                "id": row["id"],
                "title": row["title"],
                "type": row["type"],
                "level": row["level"],
                "related_nodes": row["related_nodes"],
                "causal_links": row["causal_links"],
            })
        tree = [
            {
                "name": part_name,
                "chapters": [
                    {"name": chapter_name, "nodes": chapter_nodes}
                    for chapter_name, chapter_nodes in chapters.items()
                ],
            }
            for part_name, chapters in parts.items()
        ]
        preview_path.write_text(
            json.dumps(
                {"subject": self.subject, "total_nodes": len(rows), "tree": tree},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        parse_report = {}
        if self.parse_report_path.exists():
            parse_report = json.loads(
                self.parse_report_path.read_text(encoding="utf-8")
            )
        cache_payload = (
            json.loads(self.cache_path.read_text(encoding="utf-8"))
            if self.cache_path.exists()
            else None
        )
        section_title = ""
        if rows:
            section_title = str(rows[0].get("sub_chapter") or "")
        if not section_title and cache_payload:
            for result in (cache_payload.get("chunks") or {}).values():
                headings = result.get("headings") or []
                chapter_heading = next(
                    (value for value in reversed(headings) if CHAPTER_RE.search(str(value))),
                    "",
                )
                if chapter_heading:
                    section_title = str(chapter_heading)
                    break
        section_entity = extract_section_entity(section_title)
        guardrail_report = assess_guardrails(
            rows,
            section_entity=section_entity,
            chunk_source_map=build_chunk_source_map(cache_payload),
            section_markdown=(
                self.markdown_path.read_text(encoding="utf-8")
                if self.markdown_path.exists()
                else ""
            ),
        )
        nodes_with_source_locators = sum(
            bool((row.get("source_span") or {}).get("source_locators"))
            for row in rows
        )
        source_locator_coverage_ratio = (
            nodes_with_source_locators / len(rows) if rows else 0.0
        )
        quality = {
            "subject": self.subject,
            "total_nodes": len(rows),
            "standalone_nodes": sum(bool(row.get("standalone")) for row in rows),
            "nodes_with_evidence": sum(
                bool((row.get("source_span") or {}).get("evidence")) for row in rows
            ),
            "nodes_with_source_locators": nodes_with_source_locators,
            "source_locator_coverage_ratio": round(
                source_locator_coverage_ratio,
                4,
            ),
            "nodes_with_explicit_relationships": sum(
                bool(row.get("related_nodes")) for row in rows
            ),
            "guardrails": guardrail_report,
            "parsing": {
                "total_units": parse_report.get("total_units"),
                "docling_units": parse_report.get("docling_units"),
                "fallback_units": parse_report.get("fallback_units"),
                "parser_mode": parse_report.get("parser_mode"),
                "page_parser_counts": parse_report.get("page_parser_counts"),
                "blocking_pages": parse_report.get("blocking_pages"),
                "artifact_counts": parse_report.get("artifact_counts"),
                "all_units_used_docling": (
                    parse_report.get("checks", {}).get("all_units_used_docling")
                    if parse_report
                    else None
                ),
            },
            "checks": {
                "has_nodes": bool(rows),
                "all_parsed_units_have_content": (
                    parse_report.get("checks", {}).get(
                        "all_units_have_content", True
                    )
                ),
                "no_blocking_pdf_pages": (
                    parse_report.get("checks", {}).get(
                        "no_blocking_pages", True
                    )
                ),
                "all_level_3": all(row.get("level") == 3 for row in rows),
                "all_have_parent_entity": all(
                    bool((row.get("source_span") or {}).get("parent_entity")) for row in rows
                ),
                "all_have_aspect": all(
                    bool((row.get("source_span") or {}).get("aspect")) for row in rows
                ),
                "all_have_evidence": all(
                    bool((row.get("source_span") or {}).get("evidence")) for row in rows
                ),
                "all_evidence_located": all(
                    bool((row.get("source_span") or {}).get("source_locators"))
                    for row in rows
                ),
                "all_content_names_parent": all(
                    str((row.get("source_span") or {}).get("parent_entity") or "")
                    in str(row.get("content") or "")
                    for row in rows
                ),
                "no_context_dependent_opening": all(
                    not CONTEXT_DEPENDENT_RE.match(str(row.get("content") or ""))
                    for row in rows
                ),
                "guardrails_passed": guardrail_report.get("passed", False),
            },
        }
        quality_path.write_text(
            json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if rows and not guardrail_report.get("passed", False):
            reasons = ", ".join(guardrail_report.get("reasons") or ["guardrails"])
            raise RuntimeError(
                f"Quality guardrails failed ({reasons}); "
                f"metrics={guardrail_report.get('metrics')}"
            )
        return nodes_path, preview_path, quality_path

    def upload(
        self,
        rows: list[dict[str, Any]],
        *,
        replace_section: bool = False,
        batch_size: int = 100,
    ) -> None:
        from supabase import create_client

        from textbook_pipeline.knowledge_node_adapter import finalize_knowledge_rows

        identity = (
            INTERNAL_MEDICINE_10
            if self.book_id in {INTERNAL_MEDICINE_10.canonical_id, INTERNAL_MEDICINE_10.display_name, *INTERNAL_MEDICINE_10.aliases}
            else None
        )
        if identity is not None:
            rows = finalize_knowledge_rows(rows, identity)

        url = os.getenv("SUPABASE_URL") or os.getenv("EXPO_PUBLIC_SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError("上传需要 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY")
        client = create_client(url, key)
        print(f"[*] 批量写入 Supabase: {len(rows)} 个节点")
        for start in range(0, len(rows), batch_size):
            client.table("knowledge_nodes").upsert(
                rows[start : start + batch_size], on_conflict="id"
            ).execute()
            print(f"  [+] 已写入 {min(start + batch_size, len(rows))}/{len(rows)}")
        if replace_section:
            current_ids = {str(row["id"]) for row in rows}
            sub_chapters = {
                str(row.get("sub_chapter") or "").strip()
                for row in rows
                if str(row.get("sub_chapter") or "").strip()
            }
            if len(sub_chapters) != 1:
                raise RuntimeError("--replace-section 要求本次输出只包含一个章节")
            sub_chapter = next(iter(sub_chapters))
            response = (
                client.table("knowledge_nodes")
                .select("id")
                .eq("book_id", self.book_id)
                .eq("sub_chapter", sub_chapter)
                .eq("source", "pipeline_v3")
                .execute()
            )
            stale_ids = [
                str(item["id"])
                for item in (response.data or [])
                if str(item["id"]) not in current_ids
            ]
            for start in range(0, len(stale_ids), batch_size):
                batch = stale_ids[start : start + batch_size]
                (
                    client.table("knowledge_nodes")
                    .update({"content_class": "invalid", "disease_id": None})
                    .in_("id", batch)
                    .execute()
                )
            print(f"  [+] 已将同章节旧 pipeline_v3 节点标 invalid: {len(stale_ids)}")

    def enrich_cache_with_source(self, cache: dict[str, Any]) -> dict[str, Any]:
        if not self.markdown_path.exists():
            return cache
        markdown = self.markdown_path.read_text(encoding="utf-8")
        chunks = split_markdown(markdown, self.max_chars)
        content_by_index = {str(chunk.index): chunk.content for chunk in chunks}
        for key, result in (cache.get("chunks") or {}).items():
            if not isinstance(result, dict):
                continue
            if not str(result.get("content") or "").strip():
                result["content"] = content_by_index.get(str(key), "")
        return cache

    def rebuild_from_cache(self) -> list[dict[str, Any]]:
        if not self.cache_path.exists():
            raise FileNotFoundError(f"未找到提取缓存: {self.cache_path}")
        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        cache = self.enrich_cache_with_source(cache)
        rows = self.build_rows(cache)
        nodes_path, preview_path, quality_path = self.write_outputs(rows)
        raw_nodes = sum(
            len(result.get("nodes") or [])
            for result in cache.get("chunks", {}).values()
        )
        print(
            f"[+] 从缓存重建: {nodes_path}（原始 {raw_nodes} → 原子 {len(rows)}）"
        )
        print(f"[+] 地图预览: {preview_path}")
        print(f"[+] 原子性报告: {quality_path}")
        return rows

    def run(
        self,
        upload: bool,
        force_parse: bool,
        no_resume: bool,
        catalog_only: bool,
        rebuild_only: bool = False,
        replace_section: bool = False,
    ) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {self.source_path}")
        if catalog_only:
            if self.source_path.suffix.lower() in {".md", ".markdown"}:
                raise RuntimeError("--catalog-only 仅适用于 PDF")
            self.build_catalog(force=force_parse)
            print(f"[+] 目录清单: {self.catalog_path}")
            print(f"[+] 目录质量报告: {self.catalog_report_path}")
            return
        if rebuild_only:
            rows = self.rebuild_from_cache()
            quality_path = self.scoped_output_path(".quality-report.json")
        else:
            markdown = self.read_source(force=force_parse)
            chunks = split_markdown(markdown, self.max_chars)
            cache = self.extract(chunks, resume=not no_resume)
            rows = self.build_rows(cache)
            nodes_path, preview_path, quality_path = self.write_outputs(rows)
            raw_nodes = sum(
                len(result.get("nodes") or [])
                for result in cache.get("chunks", {}).values()
            )
            print(
                f"[+] 节点缓存: {nodes_path}（原始 {raw_nodes} → 原子 {len(rows)}）"
            )
            print(f"[+] 地图预览: {preview_path}")
            print(f"[+] 原子性报告: {quality_path}")
        if upload:
            report = json.loads(quality_path.read_text(encoding="utf-8"))
            failed_checks = [
                name for name, passed in report["checks"].items() if not passed
            ]
            if failed_checks:
                raise RuntimeError(
                    "质量门禁未通过，拒绝上传: " + ", ".join(failed_checks)
                )
            self.upload(rows, replace_section=replace_section)
            print("[+] Supabase 同步完成，知识地图可直接读取")
        else:
            print("[*] 未上传数据库；确认结果后添加 --upload")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Medlearn 知识提取 Pipeline v3")
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--subject", help="知识地图中的学科名称，默认使用文件名")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "medlearn-qwen3:8b"))
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument(
        "--max-chars",
        type=int,
        default=3200,
        help="语义块最大字符数（须适配 num_ctx=4096，默认 3200）",
    )
    parser.add_argument("--num-ctx", type=int, default=4096)
    parser.add_argument("--limit", type=int, help="仅处理前 N 个语义块")
    parser.add_argument("--section-limit", type=int, help="仅解析前 N 个目录分页单元")
    parser.add_argument("--section-start", type=int, default=0, help="从第 N 个目录分页单元开始")
    parser.add_argument("--catalog-only", action="store_true", help="仅识别并校验 PDF 目录")
    parser.add_argument("--upload", action="store_true", help="写入 Supabase knowledge_nodes")
    parser.add_argument(
        "--replace-section",
        action="store_true",
        help="上传后将同教材同章节的旧 pipeline_v3 节点标记为 invalid",
    )
    parser.add_argument("--force-parse", action="store_true", help="重新解析 PDF")
    parser.add_argument("--no-resume", action="store_true", help="忽略已有 LLM 抽取缓存")
    parser.add_argument(
        "--rebuild-only",
        action="store_true",
        help="仅从 .extraction.json 重建 nodes/quality，不调用 Ollama",
    )
    parser.add_argument(
        "--use-docling",
        action="store_true",
        help="强制使用 Docling 解析；默认按页面自动路由",
    )
    parser.add_argument(
        "--pdf-parser",
        choices=("auto", "pymupdf", "docling"),
        help="覆盖 PDF 解析模式；默认使用生产契约 auto",
    )
    return parser.parse_args()


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    args = parse_args()
    pipeline = MedlearnPipeline(
        source_path=args.source,
        output_dir=args.output_dir,
        model=args.model,
        ollama_url=args.ollama_url,
        max_chars=args.max_chars,
        num_ctx=args.num_ctx,
        limit=args.limit,
        subject=args.subject,
        section_limit=args.section_limit,
        section_start=args.section_start,
        pdf_parser_mode=(
            args.pdf_parser
            or resolve_pdf_parser_mode(cli_use_docling=args.use_docling)
        ),
    )
    pipeline.run(
        args.upload,
        args.force_parse,
        args.no_resume,
        args.catalog_only,
        args.rebuild_only,
        args.replace_section,
    )


if __name__ == "__main__":
    main()
