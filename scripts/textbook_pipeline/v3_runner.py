"""In-process V3 pipeline runner (avoids subprocess overhead)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from pipeline_v3_extract import MedlearnPipeline, split_markdown
from textbook_pipeline.extraction_quality import is_extractable_chunk
from textbook_pipeline.ingestion_contract import resolve_pdf_parser_mode


def build_pipeline(
    *,
    section_start: int,
    section_limit: int,
    output_dir: Path,
    source_pdf: Path,
    max_chars: int = 2800,
) -> MedlearnPipeline:
    return MedlearnPipeline(
        source_path=source_pdf,
        output_dir=output_dir,
        model=os.getenv("OLLAMA_MODEL", "medlearn-qwen3:8b"),
        ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        max_chars=max_chars,
        num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "4096")),
        limit=None,
        subject=source_pdf.stem,
        section_limit=section_limit,
        section_start=section_start,
        pdf_parser_mode=resolve_pdf_parser_mode(),
    )


def count_extractable_chunks(markdown: str, max_chars: int) -> int:
    chunks = split_markdown(markdown, max_chars)
    return sum(1 for chunk in chunks if is_extractable_chunk(chunk.content))


def extraction_cache_stats(pipeline: MedlearnPipeline, markdown: str) -> dict[str, Any]:
    chunks = [
        chunk
        for chunk in split_markdown(markdown, pipeline.max_chars)
        if is_extractable_chunk(chunk.content)
    ]
    total = len(chunks)
    cached = 0
    raw_nodes = 0
    if pipeline.cache_path.exists():
        import json

        cache = json.loads(pipeline.cache_path.read_text(encoding="utf-8"))
        cached_keys = set((cache.get("chunks") or {}).keys())
        cached = sum(1 for chunk in chunks if str(chunk.index) in cached_keys)
        raw_nodes = sum(
            len(result.get("nodes") or [])
            for result in (cache.get("chunks") or {}).values()
        )
    built = 0
    if pipeline.scoped_output_path(".nodes.json").exists():
        import json

        built = len(
            json.loads(pipeline.scoped_output_path(".nodes.json").read_text(encoding="utf-8")).get(
                "nodes", []
            )
        )
    return {
        "total_chunks": total,
        "cached_chunks": cached,
        "raw_nodes": raw_nodes,
        "built_nodes": built,
        "complete": total > 0 and cached >= total,
    }


def rebuild_nodes(pipeline: MedlearnPipeline) -> list[dict[str, Any]]:
    return pipeline.rebuild_from_cache()


def run_section_extract(
    pipeline: MedlearnPipeline,
    *,
    force_parse: bool = False,
    no_resume: bool = False,
) -> list[dict[str, Any]]:
    total_started = time.perf_counter()
    timings: dict[str, float] = {}
    stats = None
    if pipeline.markdown_path.exists() and not force_parse:
        started = time.perf_counter()
        markdown = pipeline.markdown_path.read_text(encoding="utf-8")
        stats = extraction_cache_stats(pipeline, markdown)
        timings["cache_stats"] = round(time.perf_counter() - started, 3)
        if stats["complete"] and not no_resume:
            print(
                f"[v3] cache complete ({stats['cached_chunks']}/{stats['total_chunks']} chunks) "
                f"— rebuild only (built={stats['built_nodes']}, raw={stats['raw_nodes']})"
            )
            started = time.perf_counter()
            rows = pipeline.rebuild_from_cache()
            timings["rebuild_from_cache"] = round(time.perf_counter() - started, 3)
            timings["total"] = round(time.perf_counter() - total_started, 3)
            setattr(pipeline, "last_run_timings", timings)
            return rows

    started = time.perf_counter()
    markdown = pipeline.read_source(force=force_parse)
    timings["read_source"] = round(time.perf_counter() - started, 3)
    started = time.perf_counter()
    all_chunks = split_markdown(markdown, pipeline.max_chars)
    chunks = [chunk for chunk in all_chunks if is_extractable_chunk(chunk.content)]
    timings["split_filter_chunks"] = round(time.perf_counter() - started, 3)
    if not chunks:
        raise RuntimeError("No extractable chunks after quality filter")
    skipped = len(all_chunks) - len(chunks)
    if skipped:
        print(f"[v3] skipped {skipped} low-value chunks")

    started = time.perf_counter()
    cache = pipeline.extract(chunks, resume=not no_resume)
    timings["llm_extract"] = round(time.perf_counter() - started, 3)
    started = time.perf_counter()
    cache = pipeline.enrich_cache_with_source(cache)
    pipeline.cache_path.write_text(
        __import__("json").dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    timings["enrich_write_cache"] = round(time.perf_counter() - started, 3)
    started = time.perf_counter()
    rows = pipeline.build_rows(cache)
    timings["build_rows"] = round(time.perf_counter() - started, 3)
    started = time.perf_counter()
    pipeline.write_outputs(rows)
    timings["write_outputs"] = round(time.perf_counter() - started, 3)
    timings["total"] = round(time.perf_counter() - total_started, 3)
    setattr(pipeline, "last_run_timings", timings)
    return rows
