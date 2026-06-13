"""Upload textbook pipeline output to Supabase."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from textbook_identity import INTERNAL_MEDICINE_10, TextbookIdentity
from textbook_pipeline.metadata import PIPELINE_VERSION

NODE_BATCH_SIZE = 300
CHUNK_BATCH_SIZE = 100
EMBED_BATCH_SIZE = 20
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-large-zh-v1.5")
EMBED_DIMENSION = 1024


def _resolve_textbook_identity(book_id: str) -> TextbookIdentity | None:
    candidates = {
        INTERNAL_MEDICINE_10.canonical_id,
        INTERNAL_MEDICINE_10.display_name,
        INTERNAL_MEDICINE_10.subject_name,
        INTERNAL_MEDICINE_10.source_filename,
        Path(INTERNAL_MEDICINE_10.source_filename).stem,
        *INTERNAL_MEDICINE_10.aliases,
    }
    return INTERNAL_MEDICINE_10 if book_id in candidates else None


def _create_supabase_client(url: str, key: str):
    import importlib

    module = importlib.import_module("supabase")
    create_client = getattr(module, "create_client", None)
    if create_client is None:
        raise ImportError(
            "The Supabase Python SDK is not available. Install it with: pip install supabase"
        )
    return create_client(url, key)


def _get_client():
    url = os.environ.get("SUPABASE_URL") or os.environ.get("EXPO_PUBLIC_SUPABASE_URL", "")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
    )
    if not url or not key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY before uploading. "
            "Do not use the anon key for pipeline writes."
        )
    return _create_supabase_client(url, key)


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    return [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _split_text(text: str, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    """Split text on paragraph/sentence boundaries while keeping small overlap."""
    cleaned = re.sub(r"[ \t]+", " ", text or "").strip()
    if not cleaned:
        return []

    units = [
        unit.strip()
        for unit in re.split(r"(?<=[。！？；\n])", cleaned)
        if unit.strip()
    ]
    chunks: list[str] = []
    current = ""

    for unit in units:
        if len(unit) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            step = max_chars - overlap
            for start in range(0, len(unit), step):
                piece = unit[start : start + max_chars].strip()
                if piece:
                    chunks.append(piece)
            continue

        candidate = f"{current}{unit}"
        if current and len(candidate) > max_chars:
            chunks.append(current)
            prefix = current[-overlap:] if overlap else ""
            combined = f"{prefix}{unit}".strip()
            if len(combined) <= max_chars:
                current = combined
            else:
                current = unit
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def _build_related_nodes(nodes: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Connect nearby nodes in the same chapter and section."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        key = node.get("chapter", "")
        groups.setdefault(key, []).append(node)

    related: dict[str, list[str]] = {}
    for group in groups.values():
        ordered = sorted(
            group,
            key=lambda item: (
                item.get("order_num", item.get("orderNum", 0)) or 0,
                item.get("title", ""),
            ),
        )
        ids = [item["id"] for item in ordered]
        for index, node_id in enumerate(ids):
            related[node_id] = (
                ids[max(0, index - 4) : index] + ids[index + 1 : index + 5]
            )
    return related


def _node_rows(
    nodes: list[dict[str, Any]],
    book_id: str,
    textbook_name: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    related = _build_related_nodes(nodes)
    segment_to_node: dict[str, str] = {}
    rows: list[dict[str, Any]] = []

    for index, node in enumerate(nodes):
        source_span = node.get("sourceSpan") or node.get("source_span") or {}
        segment_id = source_span.get("segmentId")
        if segment_id and segment_id not in segment_to_node:
            segment_to_node[segment_id] = node["id"]

        existing_related = node.get("related_nodes") or node.get("relatedNodes") or []
        linked_ids = list(dict.fromkeys([*existing_related, *related.get(node["id"], [])]))
        rows.append(
            {
                "id": node["id"],
                "order_num": node.get("order_num", node.get("orderNum", index)),
                "level": node.get("level", 3),
                "title": node["title"],
                "type": node.get("type", "concept"),
                "subject": node.get("subject") or textbook_name or book_id,
                "chapter": node.get("chapter") or "",
                "sub_chapter": node.get("sub_chapter") or node.get("subChapter"),
                "content": node.get("content"),
                "key_points": node.get("key_points") or node.get("keyPoints") or [],
                "causal_links": node.get("causal_links") or node.get("causalLinks") or [],
                "related_nodes": linked_ids,
                "tags": node.get("tags") or [],
                "source": "textbook_pipeline",
                "book_id": book_id,
                "textbook": textbook_name or book_id,
                "node_source": node.get("nodeSource") or node.get("node_source"),
                "inferred": bool(node.get("inferred", False)),
                "source_span": source_span,
                "structured_sections": (
                    node.get("structured_sections")
                    or node.get("structuredSections")
                    or []
                ),
                "version": PIPELINE_VERSION,
            }
        )
    return rows, segment_to_node


def _chunk_rows(
    segments: list[dict[str, Any]],
    book_id: str,
    segment_to_node: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    chunk_index = 0
    for segment in segments:
        segment_id = segment.get("segmentId", "")
        for text in _split_text(segment.get("text", "")):
            rows.append(
                {
                    "document_name": book_id,
                    "chunk_index": chunk_index,
                    "content": text,
                    "page_number": segment.get("pageStart"),
                    "chapter": segment.get("chapter"),
                    "section": segment.get("sectionTitle"),
                    "related_node_id": segment_to_node.get(segment_id),
                    "metadata": {
                        "segment_id": segment_id,
                        "page_start": segment.get("pageStart"),
                        "page_end": segment.get("pageEnd"),
                        "text_hash": segment.get("textHash"),
                        "confidence": segment.get("confidence"),
                    },
                }
            )
            chunk_index += 1
    return rows


def _embed_rows(rows: list[dict[str, Any]], verbose: bool = False) -> int:
    api_key = os.environ.get("SILICONFLOW_KEY")
    if not api_key:
        if verbose:
            print("  No SILICONFLOW_KEY; chunks will be uploaded without vectors.")
        return 0

    import requests

    embedded = 0
    for start in range(0, len(rows), EMBED_BATCH_SIZE):
        batch = rows[start : start + EMBED_BATCH_SIZE]
        response = requests.post(
            "https://api.siliconflow.cn/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": EMBED_MODEL, "input": [row["content"] for row in batch]},
            timeout=90,
        )
        response.raise_for_status()
        data = sorted(response.json().get("data", []), key=lambda item: item["index"])
        if len(data) != len(batch):
            raise RuntimeError("Embedding API returned an unexpected item count.")
        for row, item in zip(batch, data):
            embedding = item.get("embedding")
            if not embedding or len(embedding) != EMBED_DIMENSION:
                raise RuntimeError(
                    f"Expected {EMBED_DIMENSION}-dimension embeddings from {EMBED_MODEL}."
                )
            row["embedding"] = embedding
            embedded += 1
        if verbose:
            print(f"  Embedded {embedded}/{len(rows)} chunks")
    return embedded


def _upsert_batches(client, table: str, rows: list[dict[str, Any]], batch_size: int) -> int:
    uploaded = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        result = client.table(table).upsert(batch).execute()
        uploaded += len(result.data or batch)
    return uploaded


def upload_textbook(
    nodes_path: str,
    segments_path: str,
    book_id: str,
    verbose: bool = False,
) -> dict[str, int]:
    """Upload nodes, source chunks, node links, and optional embeddings."""
    payload = json.loads(Path(nodes_path).read_text(encoding="utf-8"))
    nodes = payload.get("nodes", [])
    segments = _read_jsonl(segments_path)
    if not nodes:
        return {"nodes": 0, "chunks": 0, "embedded": 0}
    if not segments:
        raise RuntimeError(
            "segments.jsonl is missing or empty; run the segment stage before upload."
        )

    identity = _resolve_textbook_identity(book_id)
    canonical_book_id = identity.canonical_id if identity else book_id
    textbook_name = identity.display_name if identity else book_id

    node_rows, segment_to_node = _node_rows(
        nodes,
        canonical_book_id,
        textbook_name,
    )
    chunk_rows = _chunk_rows(segments, canonical_book_id, segment_to_node)
    embedded = _embed_rows(chunk_rows, verbose)

    client = _get_client()
    client.table("document_chunks").delete().eq(
        "document_name",
        canonical_book_id,
    ).execute()
    uploaded_nodes = _upsert_batches(
        client, "knowledge_nodes", node_rows, NODE_BATCH_SIZE
    )
    uploaded_chunks = _upsert_batches(
        client, "document_chunks", chunk_rows, CHUNK_BATCH_SIZE
    )

    if verbose:
        print(
            f"  Uploaded {uploaded_nodes} nodes, {uploaded_chunks} chunks, "
            f"{embedded} vectors."
        )
    return {
        "nodes": uploaded_nodes,
        "chunks": uploaded_chunks,
        "embedded": embedded,
    }


def upsert_knowledge_nodes(rows: list[dict[str, Any]], batch_size: int = 100) -> int:
    """Idempotent upsert into knowledge_nodes by primary key (id)."""
    if not rows:
        return 0
    return _upsert_batches(_get_client(), "knowledge_nodes", rows, batch_size)


def upload_nodes(nodes_path: str, book_id: str, verbose: bool = False) -> int:
    """Backward-compatible node-only upload."""
    payload = json.loads(Path(nodes_path).read_text(encoding="utf-8"))
    identity = _resolve_textbook_identity(book_id)
    canonical_book_id = identity.canonical_id if identity else book_id
    textbook_name = identity.display_name if identity else book_id
    rows, _ = _node_rows(
        payload.get("nodes", []),
        canonical_book_id,
        textbook_name,
    )
    if not rows:
        return 0
    uploaded = _upsert_batches(_get_client(), "knowledge_nodes", rows, NODE_BATCH_SIZE)
    if verbose:
        print(f"  Uploaded {uploaded} nodes.")
    return uploaded


def create_pipeline_run(
    book_id: str,
    source_file: str,
    status: str,
    stages: dict,
    started_at: str | None = None,
    error_message: str | None = None,
) -> dict | None:
    client = _get_client()
    identity = _resolve_textbook_identity(book_id)
    canonical_book_id = identity.canonical_id if identity else book_id
    row = {
        "book_id": canonical_book_id,
        "source_file": source_file,
        "status": status,
        "pipeline_version": os.environ.get("PIPELINE_VERSION", PIPELINE_VERSION),
        "stages": stages,
        "started_at": started_at or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if error_message:
        row["error_message"] = error_message
    result = client.table("pipeline_runs").insert(row).execute()
    return result.data[0] if result.data else None


def create_pipeline_snapshot(
    run_id: str,
    book_id: str,
    out_dir: str,
    verbose: bool = False,
) -> dict | None:
    client = _get_client()
    identity = _resolve_textbook_identity(book_id)
    canonical_book_id = identity.canonical_id if identity else book_id
    out = Path(out_dir)
    nodes_path = out / "nodes.staging.json"
    segments_path = out / "segments.jsonl"
    validation_path = out / "validation-report.json"

    nodes_data = (
        json.loads(nodes_path.read_text(encoding="utf-8"))
        if nodes_path.exists()
        else {}
    )
    segments_data = _read_jsonl(segments_path)
    validation = (
        json.loads(validation_path.read_text(encoding="utf-8"))
        if validation_path.exists()
        else {}
    )
    row = {
        "run_id": run_id,
        "book_id": canonical_book_id,
        "total_nodes": len(nodes_data.get("nodes", [])),
        "total_segments": len(segments_data),
        "nodes_data": nodes_data,
        "segments_data": segments_data,
        "validation": validation,
    }
    result = client.table("pipeline_snapshots").insert(row).execute()
    if verbose:
        print(
            f"  Snapshot created: {row['total_nodes']} nodes, "
            f"{row['total_segments']} segments."
        )
    return result.data[0] if result.data else None
