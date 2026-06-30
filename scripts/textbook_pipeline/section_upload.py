"""Upload section-level artifacts: document_chunks and causal_chains."""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from textbook_pipeline.upload_to_supabase import (
    CHUNK_BATCH_SIZE,
    _embed_rows,
    _get_client,
    _split_text,
    _upsert_batches,
)

CHAIN_NODE_TYPES = frozenset({"disease", "mechanism", "symptom", "exam"})
CHAIN_RELATIONS = frozenset({
    "causes",
    "characteristic_of",
    "treated_by",
    "complication_of",
    "associated_with",
    "diagnosis",
    "diagnosed_by",
    "manifests_as",
})


def _chunk_content_for_node(
    row: dict[str, Any],
    *,
    extraction_cache: dict[str, Any] | None,
) -> str:
    source_span = row.get("source_span") or {}
    if isinstance(source_span, dict):
        evidence = str(source_span.get("evidence") or "").strip()
        if len(evidence) >= 40:
            return evidence

    chunk_index = None
    if isinstance(source_span, dict):
        raw_index = source_span.get("chunk_index")
        if raw_index is not None and str(raw_index).strip() != "":
            chunk_index = str(raw_index)

    if extraction_cache and chunk_index is not None:
        chunk_result = (extraction_cache.get("chunks") or {}).get(chunk_index)
        if isinstance(chunk_result, dict):
            cached_content = str(chunk_result.get("content") or "").strip()
            if len(cached_content) >= 40:
                return cached_content

    content = str(row.get("content") or "").strip()
    if content:
        return content

    sections = row.get("structured_sections") or []
    if isinstance(sections, list) and sections:
        first = sections[0]
        if isinstance(first, dict):
            section_content = str(first.get("content") or "").strip()
            if section_content:
                return section_content
    return ""


def build_section_document_chunks(
    rows: list[dict[str, Any]],
    *,
    book_id: str,
    part_title: str,
    section_title: str,
    section_unit_index: int,
    extraction_cache: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build document_chunks rows with related_node_id for each knowledge node."""
    chunk_rows: list[dict[str, Any]] = []
    base_index = max(1, int(section_unit_index)) * 100_000

    for offset, row in enumerate(rows):
        node_id = str(row.get("id") or "").strip()
        if not node_id:
            continue

        raw_content = _chunk_content_for_node(row, extraction_cache=extraction_cache)
        if not raw_content:
            continue

        source_span = row.get("source_span") or {}
        page_number = None
        source_chunk_index = offset
        if isinstance(source_span, dict):
            if source_span.get("page_start") is not None:
                page_number = source_span.get("page_start")
            if source_span.get("chunk_index") is not None:
                try:
                    source_chunk_index = int(source_span.get("chunk_index"))
                except (TypeError, ValueError):
                    source_chunk_index = offset

        split_parts = _split_text(raw_content, max_chars=1200, overlap=120)
        texts = split_parts or [raw_content]

        for piece_index, text in enumerate(texts):
            # offset is the per-section unique slot; avoids collisions when many
            # nodes share the same source chunk_index.
            chunk_rows.append(
                {
                    "document_name": book_id,
                    "chunk_index": base_index + offset * 20 + piece_index,
                    "content": text,
                    "page_number": page_number,
                    "chapter": part_title,
                    "section": section_title,
                    "related_node_id": node_id,
                    "metadata": {
                        "node_id": node_id,
                        "node_title": row.get("title"),
                        "node_type": row.get("type"),
                        "section_unit_index": section_unit_index,
                        "source_chunk_index": source_chunk_index,
                        "pipeline": "pipeline_v3",
                    },
                }
            )
    return chunk_rows


def _link_is_clinical_chain(
    link: dict[str, Any],
    *,
    title_to_type: dict[str, str],
) -> bool:
    relation = str(link.get("relation") or "").strip().lower()
    if relation in CHAIN_RELATIONS:
        return True

    from_title = normalized_title_key(str(link.get("from") or ""))
    to_title = normalized_title_key(str(link.get("to") or ""))
    from_type = title_to_type.get(from_title, "")
    to_type = title_to_type.get(to_title, "")
    return from_type in CHAIN_NODE_TYPES or to_type in CHAIN_NODE_TYPES


def normalized_title_key(title: str) -> str:
    return re.sub(r"\s+", "", (title or "").strip()).lower()


def build_section_causal_chains(
    rows: list[dict[str, Any]],
    *,
    book_id: str,
    part_title: str,
    section_title: str,
) -> list[dict[str, Any]]:
    """Aggregate section causal_links into one causal_chains row."""
    title_to_id = {
        normalized_title_key(str(row.get("title") or "")): str(row["id"])
        for row in rows
        if row.get("id")
    }
    title_to_type = {
        normalized_title_key(str(row.get("title") or "")): str(row.get("type") or "")
        for row in rows
        if row.get("title")
    }
    valid_ids = set(title_to_id.values())

    steps: list[dict[str, Any]] = []
    seen_steps: set[tuple[str, str, str]] = set()
    related_nodes: list[str] = []

    for row in rows:
        source_id = str(row.get("id") or "")
        for link in row.get("causal_links") or []:
            if not isinstance(link, dict):
                continue
            if not _link_is_clinical_chain(link, title_to_type=title_to_type):
                continue

            target_id = str(link.get("target_id") or "").strip()
            if target_id not in valid_ids:
                to_title = normalized_title_key(str(link.get("to") or ""))
                target_id = title_to_id.get(to_title, "")
            if not target_id or target_id not in valid_ids:
                continue

            from_title = str(link.get("from") or row.get("title") or "").strip()
            to_title = str(link.get("to") or "").strip()
            relation = str(link.get("relation") or "associated_with").strip()
            step_key = (from_title, to_title, relation)
            if step_key in seen_steps:
                continue
            seen_steps.add(step_key)

            steps.append(
                {
                    "from": from_title,
                    "to": to_title,
                    "relation": relation,
                    "source_id": source_id,
                    "target_id": target_id,
                }
            )
            related_nodes.extend([source_id, target_id])

    if not steps:
        return []

    digest = hashlib.sha256(
        f"{book_id}\0{part_title}\0{section_title}".encode("utf-8")
    ).hexdigest()[:20]
    return [
        {
            "id": f"cc-{digest}",
            "title": f"{section_title} - 因果推导链",
            "steps": steps,
            "related_nodes": list(dict.fromkeys(related_nodes)),
            "source": "pipeline_v3",
            "difficulty": 1,
        }
    ]


def upsert_section_document_chunks(
    chunk_rows: list[dict[str, Any]],
    *,
    node_ids: list[str],
    book_id: str | None = None,
    part_title: str | None = None,
    section_title: str | None = None,
    embed: bool = True,
    verbose: bool = False,
) -> dict[str, int]:
    total_started = time.perf_counter()
    timings: dict[str, float] = {}
    started = time.perf_counter()
    client = _get_client()
    if book_id and part_title and section_title:
        client.table("document_chunks").delete().eq(
            "document_name", book_id
        ).eq("chapter", part_title).eq("section", section_title).execute()
    elif node_ids:
        client.table("document_chunks").delete().in_("related_node_id", node_ids).execute()
    timings["delete_existing_chunks"] = round(time.perf_counter() - started, 3)

    embedded = 0
    if chunk_rows and embed:
        started = time.perf_counter()
        embedded = _embed_rows(chunk_rows, verbose=verbose)
        timings["embed_chunks"] = round(time.perf_counter() - started, 3)

    uploaded = 0
    if chunk_rows:
        started = time.perf_counter()
        uploaded = _upsert_batches(
            client, "document_chunks", chunk_rows, CHUNK_BATCH_SIZE
        )
        timings["upsert_chunks"] = round(time.perf_counter() - started, 3)
    timings["total"] = round(time.perf_counter() - total_started, 3)
    return {"chunks": uploaded, "embedded": embedded, "timings_sec": timings}


def upsert_section_causal_chains(chain_rows: list[dict[str, Any]]) -> int:
    if not chain_rows:
        return 0
    client = _get_client()
    return _upsert_batches(client, "causal_chains", chain_rows, batch_size=50)


def upload_section_artifacts(
    rows: list[dict[str, Any]],
    *,
    book_id: str,
    part_title: str,
    section_title: str,
    section_unit_index: int,
    extraction_cache: dict[str, Any] | None = None,
    embed_chunks: bool = True,
    verbose: bool = False,
) -> dict[str, Any]:
    """Upload document_chunks and causal_chains for one manifest section."""
    total_started = time.perf_counter()
    timings: dict[str, float] = {}
    started = time.perf_counter()
    node_ids = [str(row["id"]) for row in rows if row.get("id")]

    chunk_rows = build_section_document_chunks(
        rows,
        book_id=book_id,
        part_title=part_title,
        section_title=section_title,
        section_unit_index=section_unit_index,
        extraction_cache=extraction_cache,
    )
    timings["build_chunks"] = round(time.perf_counter() - started, 3)

    started = time.perf_counter()
    chunk_result = upsert_section_document_chunks(
        chunk_rows,
        node_ids=node_ids,
        book_id=book_id,
        part_title=part_title,
        section_title=section_title,
        embed=embed_chunks,
        verbose=verbose,
    )
    timings["upload_chunks_total"] = round(time.perf_counter() - started, 3)
    for key, value in (chunk_result.get("timings_sec") or {}).items():
        timings[f"chunks.{key}"] = value

    started = time.perf_counter()
    chain_rows = build_section_causal_chains(
        rows,
        book_id=book_id,
        part_title=part_title,
        section_title=section_title,
    )
    timings["build_chains"] = round(time.perf_counter() - started, 3)
    started = time.perf_counter()
    chains_uploaded = upsert_section_causal_chains(chain_rows)
    timings["upsert_chains"] = round(time.perf_counter() - started, 3)
    timings["total"] = round(time.perf_counter() - total_started, 3)

    return {
        "chunks": chunk_result["chunks"],
        "embedded": chunk_result["embedded"],
        "causal_chains": chains_uploaded,
        "node_ids": len(node_ids),
        "timings_sec": timings,
    }
