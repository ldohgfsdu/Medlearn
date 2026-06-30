#!/usr/bin/env python3
"""Incremental textbook database build manifest for the respiratory scope.

This script keeps electronic textbook availability anchored on section/chunk
artifacts. Knowledge nodes are treated as optional enhancement artifacts that can
be reused when unchanged, but are not required for the textbook tree layer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NODES_PATH = PROJECT_ROOT / "generated" / "respiratory_knowledge_nodes.json"
DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "generated" / "respiratory_document_chunks.json"
DEFAULT_UPLOAD_RESULT_PATH = PROJECT_ROOT / "generated" / "respiratory_upload_result.json"
DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT / "generated" / "manifests" / "textbook_build_manifest.json"
)
DEFAULT_REPORT_PATH = PROJECT_ROOT / "generated" / "textbook_build_report.md"

BOOK_ID = "internal-medicine-10"
TEXTBOOK_TITLE = "内科学第10版"
RESPIRATORY_PART_TITLE = "第二篇 呼吸系统疾病"
SECTION_TABLE = "chapter_sections"
CHUNK_TABLE = "document_chunks"
NODE_PROMPT_CONTRACT = "knowledge_nodes_optional:v1:text-first:num_predict=4096"
MODEL_CONFIG = {
    "text": {
        "think": False,
        "temperature": 0,
        "num_predict": 4096,
    },
    "vision": {
        "think": False,
        "temperature": 0,
        "num_predict": 2048,
        "dpi": 100,
        "route": "fallback_only",
    },
    "knowledge_nodes": {
        "optional": True,
        "source": "existing_normalized_artifact",
    },
}


@dataclass
class SectionBuildInput:
    section_id: str
    section_title: str
    page_start: int
    page_end: int
    chunks: list[dict[str, Any]] = field(default_factory=list)
    nodes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def page_range(self) -> str:
        if self.page_start == self.page_end:
            return str(self.page_start)
        return f"{self.page_start}-{self.page_end}"


@dataclass
class SectionBuildResult:
    section_id: str
    section_title: str
    page_range: str
    section_text_hash: str
    chunk_hash: str
    node_prompt_hash: str
    embedding_status: str
    node_status: str
    last_built_at: str
    skipped_reason: str | None
    chunk_count: int
    node_count: int
    chunks_created: int
    chunks_reused: int
    embeddings_created: int
    embeddings_reused: int
    nodes_created: int
    nodes_reused: int
    duration_seconds: float

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_title": self.section_title,
            "page_range": self.page_range,
            "section_text_hash": self.section_text_hash,
            "chunk_hash": self.chunk_hash,
            "node_prompt_hash": self.node_prompt_hash,
            "embedding_status": self.embedding_status,
            "node_status": self.node_status,
            "last_built_at": self.last_built_at,
            "skipped_reason": self.skipped_reason,
            "chunk_count": self.chunk_count,
            "node_count": self.node_count,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def short_hash(value: Any) -> str:
    return stable_hash(value)[:20]


def normalize_rows(payload: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def as_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def page_range_from_rows(rows: list[dict[str, Any]]) -> tuple[int, int]:
    starts: list[int] = []
    ends: list[int] = []
    for row in rows:
        span = row.get("source_span") if isinstance(row.get("source_span"), dict) else {}
        page_start = row.get("page_number") or span.get("page_start")
        page_end = span.get("page_end") or row.get("page_number") or page_start
        if page_start is not None:
            starts.append(as_int(page_start))
        if page_end is not None:
            ends.append(as_int(page_end))
    starts = [value for value in starts if value > 0]
    ends = [value for value in ends if value > 0]
    if not starts and not ends:
        return (0, 0)
    return (min(starts or ends), max(ends or starts))


def section_sort_key(section: SectionBuildInput) -> tuple[int, str]:
    return (section.page_start or 999_999, section.section_title)


def section_id_for(order_index: int) -> str:
    return f"respiratory-{order_index:02d}"


def build_catalog(
    chunks: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    *,
    part_title: str = RESPIRATORY_PART_TITLE,
) -> list[SectionBuildInput]:
    """Build the respiratory textbook section catalog from chunks first.

    document_chunks are the first-layer source. Nodes are attached only as an
    optional enhancement for detail pages and reuse accounting.
    """
    by_title: dict[str, SectionBuildInput] = {}

    chunk_groups: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        if str(chunk.get("chapter") or "") != part_title:
            continue
        title = str(chunk.get("section") or "").strip()
        if not title:
            continue
        chunk_groups.setdefault(title, []).append(chunk)

    node_groups: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        if str(node.get("chapter") or "") != part_title:
            continue
        title = str(node.get("sub_chapter") or "").strip()
        if not title:
            continue
        node_groups.setdefault(title, []).append(node)

    all_titles = sorted(set(chunk_groups) | set(node_groups))
    provisional: list[SectionBuildInput] = []
    for title in all_titles:
        section_chunks = sorted(
            chunk_groups.get(title, []),
            key=lambda row: (as_int(row.get("page_number")), as_int(row.get("chunk_index"))),
        )
        section_nodes = sorted(
            node_groups.get(title, []),
            key=lambda row: (
                as_int((row.get("source_span") or {}).get("page_start")),
                str(row.get("id") or ""),
            ),
        )
        page_start, page_end = page_range_from_rows(section_chunks + section_nodes)
        provisional.append(
            SectionBuildInput(
                section_id="",
                section_title=title,
                page_start=page_start,
                page_end=page_end,
                chunks=section_chunks,
                nodes=section_nodes,
            )
        )

    sections = sorted(provisional, key=section_sort_key)
    for index, section in enumerate(sections, start=1):
        section.section_id = section_id_for(index)
    return sections


def extract_section_text(section: SectionBuildInput) -> tuple[str, str]:
    """Return section text and its hash, preferring document_chunks."""
    if section.chunks:
        parts = [str(chunk.get("content") or "").strip() for chunk in section.chunks]
        source = "document_chunks"
    else:
        parts = []
        for node in section.nodes:
            span = node.get("source_span") if isinstance(node.get("source_span"), dict) else {}
            evidence = str(span.get("evidence") or node.get("content") or "").strip()
            if evidence:
                parts.append(evidence)
        source = "knowledge_nodes_fallback"
    text = "\n\n".join(part for part in parts if part)
    return text, stable_hash({"source": source, "text": text})


def split_text(text: str, *, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            paragraph_break = text.rfind("\n\n", start, end)
            sentence_break = max(text.rfind("。", start, end), text.rfind(".", start, end))
            break_at = paragraph_break if paragraph_break > start + max_chars // 2 else sentence_break
            if break_at > start + max_chars // 2:
                end = break_at + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_chunks(section: SectionBuildInput, section_text: str) -> list[dict[str, Any]]:
    if section.chunks:
        return [
            {
                "document_name": chunk.get("document_name") or BOOK_ID,
                "chunk_index": chunk.get("chunk_index"),
                "content": chunk.get("content"),
                "page_number": chunk.get("page_number"),
                "chapter": chunk.get("chapter") or RESPIRATORY_PART_TITLE,
                "section": chunk.get("section") or section.section_title,
                "related_node_id": chunk.get("related_node_id"),
                "metadata": chunk.get("metadata") or {},
            }
            for chunk in section.chunks
        ]

    base_index = section.page_start * 100_000 if section.page_start else 0
    rows: list[dict[str, Any]] = []
    for offset, content in enumerate(split_text(section_text)):
        rows.append(
            {
                "document_name": BOOK_ID,
                "chunk_index": base_index + offset,
                "content": content,
                "page_number": section.page_start or None,
                "chapter": RESPIRATORY_PART_TITLE,
                "section": section.section_title,
                "related_node_id": None,
                "metadata": {
                    "section_id": section.section_id,
                    "page_range": section.page_range,
                    "pipeline": "textbook_database_build",
                    "source": "section_text",
                },
            }
        )
    return rows


def chunk_hash(chunks: list[dict[str, Any]]) -> str:
    normalized = [
        {
            "chunk_index": row.get("chunk_index"),
            "content": row.get("content"),
            "page_number": row.get("page_number"),
            "section": row.get("section"),
            "related_node_id": row.get("related_node_id"),
        }
        for row in chunks
    ]
    return stable_hash(normalized)


def node_prompt_hash(section_text_hash: str, model_config_hash: str) -> str:
    return stable_hash(
        {
            "contract": NODE_PROMPT_CONTRACT,
            "section_text_hash": section_text_hash,
            "model_config_hash": model_config_hash,
        }
    )


def manifest_sections_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(section.get("section_id")): section
        for section in manifest.get("sections", [])
        if isinstance(section, dict) and section.get("section_id")
    }


def upload_result_embedded(upload_result: dict[str, Any], total_chunks: int) -> bool:
    embedded = as_int(upload_result.get("chunks_embedded"), 0)
    uploaded = as_int(upload_result.get("chunks_uploaded"), 0)
    return total_chunks > 0 and embedded >= total_chunks and uploaded >= total_chunks


def embed_chunks(
    *,
    chunk_count: int,
    chunk_hash_value: str,
    previous: dict[str, Any] | None,
    upload_result: dict[str, Any],
    total_chunks: int,
) -> tuple[str, int, int]:
    if chunk_count <= 0:
        return ("no_chunks", 0, 0)
    if previous and previous.get("chunk_hash") == chunk_hash_value:
        previous_status = str(previous.get("embedding_status") or "")
        if previous_status.startswith("reused") or previous_status.startswith("created"):
            return ("reused_manifest", 0, chunk_count)
    if upload_result_embedded(upload_result, total_chunks):
        return ("reused_existing_db", 0, chunk_count)
    return ("pending_embedding", chunk_count, 0)


def extract_knowledge_nodes_optional(
    *,
    node_count: int,
    prompt_hash: str,
    previous: dict[str, Any] | None,
    previous_model_hash: str | None,
    model_config_hash: str,
) -> tuple[str, int, int]:
    if node_count <= 0:
        return ("optional_not_run", 0, 0)
    if (
        previous
        and previous.get("node_prompt_hash") == prompt_hash
        and previous_model_hash == model_config_hash
    ):
        return ("reused_manifest", 0, node_count)
    return ("reused_existing_artifact", 0, node_count)


def build_section_result(
    section: SectionBuildInput,
    *,
    previous: dict[str, Any] | None,
    previous_model_hash: str | None,
    model_config_hash: str,
    upload_result: dict[str, Any],
    total_chunks: int,
    built_at: str,
) -> SectionBuildResult:
    started = time.perf_counter()
    _section_text, section_text_hash = extract_section_text(section)
    chunk_rows = build_chunks(section, _section_text)
    chunk_hash_value = chunk_hash(chunk_rows)
    prompt_hash = node_prompt_hash(section_text_hash, model_config_hash)

    text_unchanged = bool(previous and previous.get("section_text_hash") == section_text_hash)
    chunks_unchanged = bool(previous and previous.get("chunk_hash") == chunk_hash_value)

    embedding_status, embeddings_created, embeddings_reused = embed_chunks(
        chunk_count=len(chunk_rows),
        chunk_hash_value=chunk_hash_value,
        previous=previous,
        upload_result=upload_result,
        total_chunks=total_chunks,
    )
    node_status, nodes_created, nodes_reused = extract_knowledge_nodes_optional(
        node_count=len(section.nodes),
        prompt_hash=prompt_hash,
        previous=previous,
        previous_model_hash=previous_model_hash,
        model_config_hash=model_config_hash,
    )

    skip_reasons: list[str] = []
    if text_unchanged:
        skip_reasons.append("unchanged_section_text")
    if chunks_unchanged:
        skip_reasons.append("unchanged_chunks")
    if embeddings_reused and not embeddings_created:
        skip_reasons.append("embedding_exists")
    if node_status.startswith("reused") and not nodes_created:
        skip_reasons.append("unchanged_node_prompt_or_existing_nodes")

    chunks_created = 0 if chunks_unchanged else len(chunk_rows)
    chunks_reused = len(chunk_rows) if chunks_unchanged else 0

    return SectionBuildResult(
        section_id=section.section_id,
        section_title=section.section_title,
        page_range=section.page_range,
        section_text_hash=section_text_hash,
        chunk_hash=chunk_hash_value,
        node_prompt_hash=prompt_hash,
        embedding_status=embedding_status,
        node_status=node_status,
        last_built_at=built_at,
        skipped_reason=", ".join(skip_reasons) if skip_reasons else None,
        chunk_count=len(chunk_rows),
        node_count=len(section.nodes),
        chunks_created=chunks_created,
        chunks_reused=chunks_reused,
        embeddings_created=embeddings_created,
        embeddings_reused=embeddings_reused,
        nodes_created=nodes_created,
        nodes_reused=nodes_reused,
        duration_seconds=time.perf_counter() - started,
    )


def upload_textbook_db(results: list[SectionBuildResult]) -> dict[str, Any]:
    """Document the DB step without expanding writes beyond accepted artifacts."""
    return {
        "mode": "reuse_existing_artifacts",
        "textbook_sections_table": SECTION_TABLE,
        "document_chunks_table": CHUNK_TABLE,
        "sections_available": len(results),
        "chunks_available": sum(result.chunk_count for result in results),
        "reason": "incremental build only; no destructive DB rewrite",
    }


def validate_textbook_tree(results: list[SectionBuildResult], *, expected_sections: int) -> list[str]:
    failures: list[str] = []
    if len(results) != expected_sections:
        failures.append(f"expected {expected_sections} sections, got {len(results)}")
    for result in results:
        if result.chunk_count <= 0:
            failures.append(f"{result.section_id} has no chunks")
        if not result.page_range or result.page_range == "0":
            failures.append(f"{result.section_id} has no page range")
    return failures


def build_report(
    *,
    results: list[SectionBuildResult],
    total_duration: float,
    failures: list[str],
    upload_summary: dict[str, Any],
    manifest_path: Path,
) -> str:
    sections_total = len(results)
    sections_skipped = sum(1 for result in results if is_section_fully_skipped(result))
    sections_built = sections_total - sections_skipped
    slowest = sorted(results, key=lambda result: result.duration_seconds, reverse=True)[:5]

    lines = [
        "# Textbook Build Report",
        "",
        f"- generated_at: `{utc_now()}`",
        f"- book_id: `{BOOK_ID}`",
        f"- textbook: `{TEXTBOOK_TITLE}`",
        f"- scope: `{RESPIRATORY_PART_TITLE}`",
        f"- manifest: `{manifest_path.as_posix()}`",
        f"- sections_total: `{sections_total}`",
        f"- sections_built: `{sections_built}`",
        f"- sections_skipped: `{sections_skipped}`",
        f"- chunks_created: `{sum(result.chunks_created for result in results)}`",
        f"- chunks_reused: `{sum(result.chunks_reused for result in results)}`",
        f"- embeddings_created: `{sum(result.embeddings_created for result in results)}`",
        f"- embeddings_reused: `{sum(result.embeddings_reused for result in results)}`",
        f"- nodes_created: `{sum(result.nodes_created for result in results)}`",
        f"- nodes_reused: `{sum(result.nodes_reused for result in results)}`",
        f"- total_duration: `{total_duration:.3f}s`",
        "",
        "## Pipeline",
        "",
        "1. build_catalog",
        "2. extract_section_text",
        "3. build_chunks",
        "4. embed_chunks",
        "5. extract_knowledge_nodes_optional",
        "6. upload_textbook_db",
        "7. validate_textbook_tree",
        "",
        "## Routing / Model Config",
        "",
        "- Text: `think=false`, `temperature=0`, `num_predict=4096`",
        "- Vision: `think=false`, `temperature=0`, `num_predict=2048`, `100 DPI`, fallback only",
        "- Knowledge nodes: optional enhancement layer; existing nodes reused when prompt/model hash is unchanged.",
        "",
        "## Database Layer",
        "",
        f"- textbook_sections layer: `{SECTION_TABLE}`",
        f"- document chunks layer: `{CHUNK_TABLE}`",
        f"- upload_textbook_db mode: `{upload_summary.get('mode')}`",
        f"- upload_textbook_db reason: {upload_summary.get('reason')}",
        "",
        "## Slowest Sections",
        "",
        "| section_id | section_title | duration | chunks | nodes | skipped_reason |",
        "|---|---|---:|---:|---:|---|",
    ]
    for result in slowest:
        lines.append(
            "| "
            + " | ".join(
                [
                    result.section_id,
                    result.section_title,
                    f"{result.duration_seconds:.4f}s",
                    str(result.chunk_count),
                    str(result.node_count),
                    result.skipped_reason or "",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Sections", ""])
    lines.extend(
        [
            "| section_id | section_title | page_range | chunks | nodes | embedding_status | node_status | skipped_reason |",
            "|---|---|---:|---:|---:|---|---|---|",
        ]
    )
    for result in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    result.section_id,
                    result.section_title,
                    result.page_range,
                    str(result.chunk_count),
                    str(result.node_count),
                    result.embedding_status,
                    result.node_status,
                    result.skipped_reason or "",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Failures", ""])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Scope Notes",
            "",
            "- This build does not expand AI, wrong-question, Feynman, search, graph, or UI features.",
            "- `knowledge_nodes` are reused as an enhancement layer and are not treated as a prerequisite for textbook section/chunk availability.",
            "- `causal_chains` and related graph expansion are intentionally out of scope.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_build(args: argparse.Namespace) -> dict[str, Any]:
    start = time.perf_counter()
    nodes = normalize_rows(load_json(args.nodes_path, {}), "nodes")
    chunks = normalize_rows(load_json(args.chunks_path, {}), "chunks")
    upload_result = load_json(args.upload_result_path, {})
    previous_manifest = load_json(args.manifest_path, {})
    previous_sections = manifest_sections_by_id(previous_manifest)
    previous_model_hash = previous_manifest.get("model_config_hash")
    model_config_hash = stable_hash(MODEL_CONFIG)
    built_at = utc_now()

    sections = build_catalog(chunks, nodes, part_title=args.part_title)
    results = [
        build_section_result(
            section,
            previous=previous_sections.get(section.section_id),
            previous_model_hash=previous_model_hash,
            model_config_hash=model_config_hash,
            upload_result=upload_result,
            total_chunks=len(chunks),
            built_at=built_at,
        )
        for section in sections
    ]

    upload_summary = upload_textbook_db(results)
    failures = validate_textbook_tree(results, expected_sections=args.expected_sections)
    if not chunks:
        failures.append(f"missing chunks artifact: {args.chunks_path}")
    if not nodes:
        failures.append(f"missing optional nodes artifact: {args.nodes_path}")

    total_duration = time.perf_counter() - start
    manifest = {
        "schema_version": 1,
        "book_id": BOOK_ID,
        "textbook": TEXTBOOK_TITLE,
        "scope": args.part_title,
        "textbook_sections_table": SECTION_TABLE,
        "document_chunks_table": CHUNK_TABLE,
        "node_layer": "optional_enhancement",
        "model_config": MODEL_CONFIG,
        "model_config_hash": model_config_hash,
        "generated_at": built_at,
        "sections": [result.manifest_entry() for result in results],
    }
    save_json(args.manifest_path, manifest)
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(
        build_report(
            results=results,
            total_duration=total_duration,
            failures=failures,
            upload_summary=upload_summary,
            manifest_path=args.manifest_path,
        ),
        encoding="utf-8",
    )
    return {
        "manifest_path": str(args.manifest_path),
        "report_path": str(args.report_path),
        "sections_total": len(results),
        "sections_skipped": sum(1 for result in results if is_section_fully_skipped(result)),
        "failures": failures,
    }


def is_section_fully_skipped(result: SectionBuildResult) -> bool:
    reasons = set(
        reason.strip()
        for reason in (result.skipped_reason or "").split(",")
        if reason.strip()
    )
    return {
        "unchanged_section_text",
        "unchanged_chunks",
        "embedding_exists",
        "unchanged_node_prompt_or_existing_nodes",
    }.issubset(reasons)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build incremental textbook DB manifest/report for respiratory sections."
    )
    parser.add_argument("--nodes-path", type=Path, default=DEFAULT_NODES_PATH)
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--upload-result-path", type=Path, default=DEFAULT_UPLOAD_RESULT_PATH)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--part-title", default=RESPIRATORY_PART_TITLE)
    parser.add_argument("--expected-sections", type=int, default=17)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    result = run_build(parse_args(argv))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
