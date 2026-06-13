"""Medlearn Pipeline v3: Docling -> Ollama/Qwen -> cache -> knowledge map."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from textbook_identity import CANONICAL_TEXTBOOK_ID, INTERNAL_MEDICINE_10


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "textbook" / "内科学（第10版）.pdf"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "generated" / "pipeline_v3"
os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".cache" / "huggingface"))
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


def resolve_book_id(source_path: Path) -> str:
    if source_path.stem in {"内科学（第10版）", CANONICAL_TEXTBOOK_ID}:
        return CANONICAL_TEXTBOOK_ID
    return source_path.stem


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
    if len(text) <= max_chars:
        return [text]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(
                paragraph[start : start + max_chars]
                for start in range(0, len(paragraph), max_chars)
            )
            continue
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def extract_json(content: str) -> dict[str, Any]:
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise
        result = json.loads(content[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("Ollama response must be a JSON object")
    return result


def make_standalone(text: str, parent_entity: str) -> str:
    text = text.strip()
    if not text or not parent_entity or parent_entity in text:
        return text
    return f"{parent_entity}：{text}"


def identify_node_entity(title: str, content: str, aspect: str) -> NodeEntityResult:
    """Identify a title-derived medical subject and confirm it in raw content."""
    title = title.strip()
    content = content.strip()
    if not title:
        return NodeEntityResult(None, "title_missing")

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
    if candidate not in content:
        return NodeEntityResult(None, "entity_not_confirmed_in_content")
    return NodeEntityResult(candidate, "confirmed_in_title_and_content")


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
        pymupdf_only: bool = False,
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
        self.pymupdf_only = pymupdf_only or os.getenv("MEDLEARN_PDF_PARSER") == "pymupdf"
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
        try:
            total_pages = document.page_count
            raw_toc = document.get_toc()
        finally:
            document.close()
        if not raw_toc:
            raise RuntimeError(
                "PDF 没有可用书签目录；为避免错分章节，已停止提取。"
                "需要先增加目录页 OCR 识别。"
            )

        entries, units = build_catalog_units(raw_toc, total_pages)
        if not units:
            raise RuntimeError("书签存在，但未识别到篇、章、节等正文目录项")
        payload = {
            "subject": self.subject,
            "source": str(self.source_path),
            "total_pages": total_pages,
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
        converter = None
        if not self.pymupdf_only:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.document_converter import DocumentConverter
                from docling.document_converter import PdfFormatOption
                from docling.pipeline.legacy_standard_pdf_pipeline import (
                    LegacyStandardPdfPipeline,
                )
            except ImportError as exc:
                raise RuntimeError(
                    "缺少 docling，请运行: pip install -r scripts/requirements.txt"
                ) from exc
            pipeline_options = PdfPipelineOptions(
                do_ocr=False,
                do_table_structure=True,
                layout_batch_size=1,
                table_batch_size=1,
                queue_max_size=1,
            )
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options,
                        pipeline_cls=LegacyStandardPdfPipeline,
                    )
                }
            )
        documents: list[str] = []
        parse_units: list[dict[str, Any]] = []
        parser_mode = "pymupdf" if self.pymupdf_only else "docling"
        print(f"[*] {parser_mode} 按目录解析 {len(selected)} 个分页单元")
        for position, unit in enumerate(selected, start=1):
            parser = parser_mode
            error: str | None = None
            if self.pymupdf_only:
                markdown = self.read_unit_with_pymupdf(unit)
                if len(markdown) < 40:
                    raise RuntimeError(
                        f"目录单元 p{unit.page_start}-{unit.page_end} PyMuPDF 解析过短"
                    )
            else:
                try:
                    result = converter.convert(
                        str(self.source_path),
                        page_range=(unit.page_start, unit.page_end),
                    )
                    markdown = result.document.export_to_markdown().strip()
                    if len(markdown) < 40:
                        raise RuntimeError("Docling 返回内容过短")
                except Exception as exc:
                    parser = "pymupdf_fallback"
                    error = f"{type(exc).__name__}: {exc}"
                    markdown = self.read_unit_with_pymupdf(unit)
                    if len(markdown) < 40:
                        raise RuntimeError(
                            f"目录单元 p{unit.page_start}-{unit.page_end} 解析失败: {error}"
                        ) from exc
                    print(
                        f"  [!] Docling 失败，已回退 PyMuPDF: "
                        f"p{unit.page_start}-{unit.page_end}"
                    )
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
                    "parser": parser,
                    "characters": len(markdown),
                    "error": error,
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
            "docling_units": sum(
                unit["parser"] == "docling" for unit in parse_units
            ),
            "fallback_units": sum(
                unit["parser"] == "pymupdf_fallback" for unit in parse_units
            ),
            "units": parse_units,
            "checks": {
                "all_units_have_content": all(
                    unit["characters"] >= 40 for unit in parse_units
                ),
                "all_units_used_docling": all(
                    unit["parser"] == "docling" for unit in parse_units
                ),
            },
        }
        self.parse_report_path.write_text(
            json.dumps(parse_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return combined

    def read_unit_with_pymupdf(self, unit: CatalogUnit) -> str:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        document = fitz.open(str(self.source_path))
        pages: list[str] = []
        try:
            for page_number in range(unit.page_start - 1, unit.page_end):
                page = document[page_number]
                text = page.get_text("text", sort=True).strip()
                tables_markdown: list[str] = []
                try:
                    tables = page.find_tables().tables
                except Exception:
                    tables = []
                for table in tables:
                    try:
                        tables_markdown.append(table.to_markdown())
                    except Exception:
                        continue
                page_content = "\n\n".join(
                    value for value in [text, *tables_markdown] if value
                )
                if page_content:
                    pages.append(f"<!-- PDF page {page_number + 1} -->\n{page_content}")
        finally:
            document.close()
        return "\n\n".join(pages)

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
2. 每个节点必须是一个原子知识块；parent_entity 用具体疾病/药物/机制名。
3. title 与 content 均须包含 parent_entity；不能以“该病、其、上述”开头。
4. aspect 填原文面向；evidence 填最短原文依据；无依据则不生成。
5. edges.relation 用 causes、characteristic_of、treated_by、complication_of、associated_with。
6. 只输出合法 JSON。

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
            "messages": [{"role": "user", "content": prompt}],
            "options": {
                "temperature": 0.1,
                "num_ctx": min(self.num_ctx, 4096),
                "num_gpu": int(os.getenv("OLLAMA_NUM_GPU", "999")),
            },
        }
        response = requests.post(
            f"{self.ollama_url}/api/chat", json=payload, timeout=180
        )
        response.raise_for_status()
        return extract_json(response.json()["message"]["content"])

    def call_ollama(self, chunk: MarkdownChunk, retries: int = 2) -> dict[str, Any]:
        import requests

        content = chunk.content[: self.max_content_chars_for_ctx()]
        prompt = self.build_extraction_prompt(chunk, content)
        last_exc: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                return self.call_ollama_once(prompt)
            except requests.HTTPError as exc:
                last_exc = exc
                status = exc.response.status_code if exc.response is not None else None
                # Context overflow returns 400 — smaller input helps; same payload won't.
                if status == 400 and len(content) > 1500:
                    content = content[: max(1200, len(content) // 2)]
                    prompt = self.build_extraction_prompt(chunk, content)
                    print(f"  [!] 块 {chunk.index} 上下文过长，截断至 {len(content)} 字重试")
                    continue
                if status in {400, 500}:
                    raise RuntimeError(f"Ollama 调用失败: {exc}") from exc
            except (requests.RequestException, KeyError, json.JSONDecodeError, ValueError) as exc:
                last_exc = exc
            if attempt < retries:
                time.sleep(attempt)
        raise RuntimeError(f"Ollama 调用失败（重试 {retries} 次）: {last_exc}") from last_exc

    def extract(self, chunks: list[MarkdownChunk], resume: bool = True) -> dict[str, Any]:
        cache: dict[str, Any] = {"subject": self.subject, "chunks": {}}
        if resume and self.cache_path.exists():
            cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            cache.setdefault("chunks", {})

        selected = chunks[: self.limit] if self.limit else chunks
        print(f"[*] 共 {len(chunks)} 个语义块，本次处理 {len(selected)} 个")
        for position, chunk in enumerate(selected, start=1):
            key = str(chunk.index)
            if key in cache["chunks"]:
                print(f"  [=] {position}/{len(selected)} 块 {chunk.index} 已缓存")
                continue
            try:
                data = self.call_ollama(chunk)
                cache["chunks"][key] = {
                    "headings": chunk.headings,
                    "nodes": data.get("nodes", []),
                    "edges": data.get("edges", []),
                }
                self.cache_path.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(
                    f"  [+] {position}/{len(selected)} 块 {chunk.index}: "
                    f"{len(data.get('nodes', []))} 个节点"
                )
            except RuntimeError as exc:
                print(f"  [!] 块 {chunk.index} 跳过: {exc}")
        return cache

    def build_rows(self, cache: dict[str, Any]) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str | None, str], dict[str, Any]] = {}
        pending_edges: list[tuple[str, str | None, dict[str, Any]]] = []

        for chunk_index, result in cache.get("chunks", {}).items():
            headings = result.get("headings") or []
            chapter, sub_chapter = resolve_map_hierarchy(headings)
            for raw in result.get("nodes") or []:
                title = str(raw.get("title", "")).strip()
                raw_content = str(raw.get("content", "")).strip()
                parent_entity = str(raw.get("parent_entity", "")).strip()
                aspect = str(raw.get("aspect", "")).strip()
                evidence = str(raw.get("evidence", "")).strip()
                node_entity = identify_node_entity(title, raw_content, aspect)
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
                key = (chapter, sub_chapter, title)
                node_type = str(raw.get("type", "concept"))
                tags = [str(tag) for tag in raw.get("tags", []) if str(tag) in VINDICATE_TAGS]
                row = merged.setdefault(
                    key,
                    {
                        "id": stable_id(self.subject, chapter, sub_chapter or "", title),
                        "order_num": len(merged),
                        "level": 3,
                        "type": node_type if node_type in ALLOWED_TYPES else "concept",
                        "title": title,
                        "subject": self.subject,
                        "chapter": chapter,
                        "sub_chapter": sub_chapter,
                        "knowledge_path": [p for p in [self.subject, chapter, sub_chapter, title] if p],
                        "content": content,
                        "key_points": [],
                        "structured_sections": [
                            {"title": aspect or "知识要点", "content": content}
                        ],
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
                            "evidence": evidence,
                        },
                        "version": "3.0",
                    },
                )
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

        for chapter, sub_chapter, edge in pending_edges:
            source_title = str(edge.get("source", "")).strip()
            target_title = str(edge.get("target", "")).strip()
            source = merged.get((chapter, sub_chapter, source_title))
            target = merged.get((chapter, sub_chapter, target_title))
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
        parent_path = parent_entity in title and parent_entity in content
        node_path = bool(
            node_entity and node_entity in title and node_entity in content
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
        quality = {
            "subject": self.subject,
            "total_nodes": len(rows),
            "standalone_nodes": sum(bool(row.get("standalone")) for row in rows),
            "nodes_with_evidence": sum(
                bool((row.get("source_span") or {}).get("evidence")) for row in rows
            ),
            "nodes_with_explicit_relationships": sum(
                bool(row.get("related_nodes")) for row in rows
            ),
            "parsing": {
                "total_units": parse_report.get("total_units"),
                "docling_units": parse_report.get("docling_units"),
                "fallback_units": parse_report.get("fallback_units"),
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
                "all_content_names_parent": all(
                    str((row.get("source_span") or {}).get("parent_entity") or "")
                    in str(row.get("content") or "")
                    for row in rows
                ),
                "no_context_dependent_opening": all(
                    not CONTEXT_DEPENDENT_RE.match(str(row.get("content") or ""))
                    for row in rows
                ),
            },
        }
        quality_path.write_text(
            json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return nodes_path, preview_path, quality_path

    def upload(self, rows: list[dict[str, Any]], batch_size: int = 100) -> None:
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

    def run(
        self,
        upload: bool,
        force_parse: bool,
        no_resume: bool,
        catalog_only: bool,
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
        markdown = self.read_source(force=force_parse)
        chunks = split_markdown(markdown, self.max_chars)
        cache = self.extract(chunks, resume=not no_resume)
        rows = self.build_rows(cache)
        nodes_path, preview_path, quality_path = self.write_outputs(rows)
        print(f"[+] 节点缓存: {nodes_path}（{len(rows)} 个节点）")
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
            self.upload(rows)
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
    parser.add_argument("--force-parse", action="store_true", help="重新解析 PDF")
    parser.add_argument("--no-resume", action="store_true", help="忽略已有 LLM 抽取缓存")
    parser.add_argument(
        "--pymupdf-only",
        action="store_true",
        help="跳过 Docling，仅用 PyMuPDF 解析（低内存环境推荐）",
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
        pymupdf_only=args.pymupdf_only,
    )
    pipeline.run(args.upload, args.force_parse, args.no_resume, args.catalog_only)


if __name__ == "__main__":
    main()
