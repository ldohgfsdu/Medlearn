#!/usr/bin/env python3
"""
Unified knowledge ingestion CLI — production contract.

Single write path:
  V3 / V4 / convert-v4 → knowledge_node_adapter → knowledge_nodes

Section lifecycle (manifest):
  pending → extracting → extracted → uploading → uploaded → verified
  Any step failure → failed (run-next retries failed sections)

Normalized cache (mandatory):
  generated/knowledge_nodes/{textbook_id}/{part_slug}__{section_slug}.normalized.json

knowledge_points is DEPRECATED — never written by this CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from textbook_identity import (
    INTERNAL_MEDICINE_10,
    IngestionContext,
    get_textbook_identity,
    resolve_ingestion_context,
)
from textbook_pipeline.ingestion_contract import (
    PRODUCTION_PDF_PARSER,
    resolve_pdf_parser_mode,
)
from textbook_pipeline.ingestion_contract import (
    ADAPTER_VERSION,
    KNOWLEDGE_POINTS_DEPRECATED,
    SECTION_STATUSES,
    TERMINAL_SECTION_STATUSES,
)
from textbook_pipeline.knowledge_node_adapter import (
    build_provenance,
    build_v3_to_kn_map,
    finalize_knowledge_rows,
    is_valid_node_row,
    load_v4_payload,
    needs_reference_repair,
    repair_row_references,
    v4_payload_to_knowledge_rows,
)
from textbook_pipeline.section_upload import upload_section_artifacts
from textbook_pipeline.extraction_quality import (
    assess_chunk_coverage,
    assess_rows_with_guardrails,
    enrich_row_content,
)
from textbook_pipeline.node_guardrails import (
    build_chunk_source_map,
    extract_section_entity,
    filter_guarded_rows,
)
from textbook_pipeline.upload_to_supabase import upsert_knowledge_nodes
from textbook_pipeline.v3_runner import build_pipeline, run_section_extract

MANIFEST_PATH = PROJECT_ROOT / "manifests" / "internal_medicine_ingestion.yaml"
STATE_PATH = PROJECT_ROOT / "state" / "knowledge_ingestion.yaml"
CATALOG_PATH = PROJECT_ROOT / "scripts" / "catalog.internal-medicine.json"
PDF_PATH = PROJECT_ROOT / "textbook" / "内科学（第10版）.pdf"
V3_SCRIPT = SCRIPT_DIR / "pipeline_v3_extract.py"
V3_OUTPUT_DIR = PROJECT_ROOT / "generated" / "pipeline_v3"
GENERATED_ROOT = PROJECT_ROOT / "generated" / "knowledge_nodes"
EV1_NORMALIZED_ROOT = PROJECT_ROOT / "generated" / "knowledge_nodes_ev1"
EV1_DISPLAY_CONTRACT_ROOT = PROJECT_ROOT / "generated" / "ev1_display_contracts"
TEXTBOOK_ID = "internal-medicine-10"
PDF_STEM = PDF_PATH.stem
_INGESTION_CTX: Optional[IngestionContext] = None
_LAST_V3_TIMINGS: Dict[str, float] = {}


def configure_ingestion(book_id: str = "internal-medicine-10") -> IngestionContext:
    """Bind module paths to a textbook ingestion context."""
    global _INGESTION_CTX, TEXTBOOK_ID, PDF_PATH, MANIFEST_PATH, CATALOG_PATH
    global V3_OUTPUT_DIR, GENERATED_ROOT, EV1_NORMALIZED_ROOT, PDF_STEM

    ctx = resolve_ingestion_context(book_id, PROJECT_ROOT)
    _INGESTION_CTX = ctx
    TEXTBOOK_ID = ctx.book_id
    PDF_PATH = ctx.pdf_path
    MANIFEST_PATH = ctx.manifest_path
    CATALOG_PATH = ctx.catalog_path
    V3_OUTPUT_DIR = ctx.v3_output_dir
    GENERATED_ROOT = ctx.generated_root
    EV1_NORMALIZED_ROOT = PROJECT_ROOT / "generated" / "knowledge_nodes_ev1"
    PDF_STEM = ctx.pdf_stem
    return ctx


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_yaml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", (text or "").strip())
    return cleaned.strip("_") or "section"


def section_cache_key(part_title: str, section_title: str) -> str:
    return f"{slugify(part_title)}__{slugify(section_title)}"


def normalized_cache_path(part_title: str, section_title: str) -> Path:
    return GENERATED_ROOT / TEXTBOOK_ID / f"{section_cache_key(part_title, section_title)}.normalized.json"


def ev1_normalized_cache_path(part_title: str, section_title: str) -> Path:
    return EV1_NORMALIZED_ROOT / TEXTBOOK_ID / f"{section_cache_key(part_title, section_title)}.normalized.json"


def iter_manifest_sections(manifest: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    for part in manifest.get("parts", []):
        part_title = str(part.get("title") or "").strip()
        for section in part.get("sections", []):
            section_title = str(section.get("title") or "").strip()
            yield {
                "part_title": part_title,
                "section_title": section_title,
                "section_ref": section,
                "part_ref": part,
            }


def resolve_section(
    manifest: Dict[str, Any],
    *,
    part_title: Optional[str] = None,
    section_title: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for item in iter_manifest_sections(manifest):
        if section_title and item["section_title"] != section_title:
            continue
        if part_title and item["part_title"] != part_title:
            continue
        matches.append(item)
    if not matches:
        return None
    if len(matches) > 1 and not part_title:
        titles = ", ".join(f"{m['part_title']}/{m['section_title']}" for m in matches)
        raise ValueError(f"Ambiguous section '{section_title}'. Specify --part. Matches: {titles}")
    return matches[0]


def section_status(section_ref: Dict[str, Any]) -> str:
    return str(section_ref.get("status") or "pending")


def is_section_done(section_ref: Dict[str, Any]) -> bool:
    return section_status(section_ref) in TERMINAL_SECTION_STATUSES


def set_section_status(
    manifest: Dict[str, Any],
    part_title: str,
    section_title: str,
    status: str,
    *,
    error: Optional[str] = None,
    node_count: Optional[int] = None,
    remote_count: Optional[int] = None,
    quality_metrics: Optional[Dict[str, Any]] = None,
) -> None:
    if status not in SECTION_STATUSES:
        raise ValueError(f"Invalid section status: {status}")
    target = resolve_section(manifest, part_title=part_title, section_title=section_title)
    if not target:
        raise KeyError(f"Section not found: {part_title} / {section_title}")

    section_ref = target["section_ref"]
    section_ref["status"] = status
    section_ref["updated_at"] = utc_now()
    if error is not None:
        section_ref["last_error"] = error
    if node_count is not None:
        section_ref["node_count"] = node_count
    if remote_count is not None:
        section_ref["remote_count"] = remote_count
    if quality_metrics is not None:
        section_ref["quality_metrics"] = quality_metrics
    if status == "verified":
        section_ref["completed_at"] = utc_now()
        section_ref.pop("last_error", None)
    manifest["updated_at"] = utc_now()
    save_yaml(MANIFEST_PATH, manifest)


def next_runnable_section(manifest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for item in iter_manifest_sections(manifest):
        if section_status(item["section_ref"]) == "failed":
            return item
    for item in iter_manifest_sections(manifest):
        if not is_section_done(item["section_ref"]):
            return item
    return None


def sync_state_from_manifest(state: Dict[str, Any], manifest: Dict[str, Any]) -> None:
    verified_count = sum(
        1
        for item in iter_manifest_sections(manifest)
        if section_status(item["section_ref"]) == "verified"
    )
    next_pending = next_runnable_section(manifest)
    extraction = state.setdefault("extraction", {})
    extraction["verified_section_count"] = verified_count
    extraction["status"] = f"verified_{verified_count}_chapters"
    if next_pending:
        extraction["next_pending_section"] = (
            f"{next_pending['part_title']}/{next_pending['section_title']}"
        )
    else:
        extraction["next_pending_section"] = None


def load_manifest() -> Dict[str, Any]:
    manifest = load_yaml(MANIFEST_PATH)
    if not manifest:
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")
    return manifest


def load_state() -> Dict[str, Any]:
    state = load_yaml(STATE_PATH)
    if not state:
        state = {
            "textbook_id": TEXTBOOK_ID,
            "adapter_version": ADAPTER_VERSION,
            "knowledge_points_deprecated": KNOWLEDGE_POINTS_DEPRECATED,
            "current_section": None,
            "last_error": None,
            "last_upload_count": None,
            "last_remote_count": None,
            "updated_at": utc_now(),
        }
    return state


def save_state(state: Dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    save_yaml(STATE_PATH, state)


def seconds_since(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def record_performance(
    state: Dict[str, Any],
    *,
    part_title: str,
    section_title: str,
    stage: str,
    timings: Dict[str, float],
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    record: Dict[str, Any] = {
        "section": f"{part_title}/{section_title}",
        "stage": stage,
        "timings_sec": timings,
        "recorded_at": utc_now(),
    }
    if extra:
        record["extra"] = extra
    performance = state.setdefault("performance", {})
    performance["last_section"] = record
    history = list(performance.get("history") or [])
    history.append(record)
    performance["history"] = history[-20:]


def get_supabase_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL") or os.environ.get("EXPO_PUBLIC_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("EXPO_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY in environment")
    return create_client(url, key)


def remote_nodes_for_section(part_title: str, section_title: str) -> Tuple[int, List[str]]:
    client = get_supabase_client()
    resp = (
        client.table("knowledge_nodes")
        .select("id")
        .eq("book_id", TEXTBOOK_ID)
        .eq("chapter", part_title)
        .eq("sub_chapter", section_title)
        .execute()
    )
    rows = resp.data or []
    return len(rows), [row["id"] for row in rows]


def _section_extraction_cache(part_title: str, section_title: str) -> Optional[Dict[str, Any]]:
    try:
        pipeline = _v3_pipeline_for_section(part_title, section_title)
        if not pipeline.cache_path.exists():
            return None
        cache = load_json(pipeline.cache_path)
        return pipeline.enrich_cache_with_source(cache)
    except Exception:
        return None


def _v3_to_kn_map_for_section(
    part_title: str,
    section_title: str,
) -> Dict[str, str]:
    identity = get_textbook_identity(TEXTBOOK_ID)
    provenance = build_provenance(
        identity=identity,
        part_title=part_title,
        section_title=section_title,
        source_pdf=str(PDF_PATH),
        pipeline_version="v3",
        created_from="upload_repair",
    )
    section_start, section_limit = resolve_catalog_section_range(part_title, section_title)
    nodes_path = v3_nodes_path(section_start, section_limit)
    if nodes_path.exists():
        raw_rows = load_json(nodes_path).get("nodes") or []
        return build_v3_to_kn_map(raw_rows, identity, provenance=provenance)
    return build_v3_to_kn_map([], identity, provenance=provenance)


def ensure_upload_ready_rows(
    rows: List[Dict[str, Any]],
    part_title: str,
    section_title: str,
) -> List[Dict[str, Any]]:
    """Repair legacy v3-* references before upload."""
    if not needs_reference_repair(rows):
        return rows

    has_legacy_primary_ids = any(
        str(row.get("id") or "").startswith("v3-") for row in rows
    )
    if has_legacy_primary_ids:
        section_start, _section_limit = resolve_catalog_section_range(part_title, section_title)
        nodes_path = v3_nodes_path(section_start, _section_limit)
        if nodes_path.exists():
            print(f"[upload] repairing references via re-normalize: {nodes_path.name}")
            repaired = normalize_v3_nodes(part_title, section_title, nodes_path)
            write_normalized_cache(
                part_title,
                section_title,
                repaired,
                source_path=nodes_path,
                pipeline_version="v3",
            )
            return repaired

    v3_to_kn = _v3_to_kn_map_for_section(part_title, section_title)
    print(f"[upload] repairing edge references in-place ({len(v3_to_kn)} legacy ids)")
    repaired = repair_row_references(rows, v3_to_kn=v3_to_kn)
    write_normalized_cache(
        part_title,
        section_title,
        repaired,
        source_path=None,
        pipeline_version="v3",
    )
    return repaired


def upload_rows_idempotent(rows: List[Dict[str, Any]], part_title: str, section_title: str) -> Dict[str, Any]:
    timings: Dict[str, float] = {}
    started = time.perf_counter()
    rows = ensure_upload_ready_rows(rows, part_title, section_title)
    timings["prepare_rows"] = seconds_since(started)

    expected_ids = {row["id"] for row in rows}
    started = time.perf_counter()
    before_count, before_ids = remote_nodes_for_section(part_title, section_title)
    timings["remote_before"] = seconds_since(started)

    started = time.perf_counter()
    upsert_knowledge_nodes(rows)
    timings["upsert_nodes"] = seconds_since(started)

    started = time.perf_counter()
    section_start, _section_limit = resolve_catalog_section_range(part_title, section_title)
    artifact_result = upload_section_artifacts(
        rows,
        book_id=TEXTBOOK_ID,
        part_title=part_title,
        section_title=section_title,
        section_unit_index=section_start,
        extraction_cache=_section_extraction_cache(part_title, section_title),
        embed_chunks=True,
        verbose=True,
    )
    timings["upload_artifacts"] = seconds_since(started)

    started = time.perf_counter()
    stale_ids = [node_id for node_id in before_ids if node_id not in expected_ids]
    if stale_ids:
        client = get_supabase_client()
        client.table("knowledge_nodes").delete().in_("id", stale_ids).execute()
    timings["cleanup_stale"] = seconds_since(started)

    started = time.perf_counter()
    after_count, after_ids = remote_nodes_for_section(part_title, section_title)
    timings["remote_after"] = seconds_since(started)
    timings["total"] = round(sum(timings.values()), 3)

    return {
        "before_count": before_count,
        "after_count": after_count,
        "after_ids": after_ids,
        "uploaded": len(rows),
        "expected_ids": len(expected_ids),
        "stale_removed": len(stale_ids),
        "idempotent": after_count == len(expected_ids),
        "delta": after_count - before_count,
        "chunks_uploaded": artifact_result.get("chunks", 0),
        "chunks_embedded": artifact_result.get("embedded", 0),
        "causal_chains_uploaded": artifact_result.get("causal_chains", 0),
        "timings_sec": timings,
        "artifact_timings_sec": artifact_result.get("timings_sec") or {},
    }


def write_normalized_cache(
    part_title: str,
    section_title: str,
    rows: List[Dict[str, Any]],
    *,
    source_path: Optional[Path] = None,
    pipeline_version: str = "v4",
) -> Path:
    cache_path = normalized_cache_path(part_title, section_title)
    payload = {
        "textbook_id": TEXTBOOK_ID,
        "part_title": part_title,
        "section_title": section_title,
        "pipeline_version": pipeline_version,
        "adapter_version": ADAPTER_VERSION,
        "source_path": str(source_path) if source_path else None,
        "node_count": len(rows),
        "generated_at": utc_now(),
        "nodes": rows,
    }
    save_json(cache_path, payload)
    return cache_path


def write_ev1_normalized_cache(
    part_title: str,
    section_title: str,
    rows: List[Dict[str, Any]],
    *,
    source_path: Path,
    conversion_summary: Dict[str, Any],
) -> Path:
    cache_path = ev1_normalized_cache_path(part_title, section_title)
    payload = {
        "textbook_id": TEXTBOOK_ID,
        "part_title": part_title,
        "section_title": section_title,
        "pipeline_version": "ev1_candidate_to_knowledge_node",
        "adapter_version": ADAPTER_VERSION,
        "source_path": str(source_path),
        "node_count": len(rows),
        "conversion_summary": conversion_summary,
        "generated_at": utc_now(),
        "nodes": rows,
    }
    save_json(cache_path, payload)
    return cache_path


def load_normalized_cache(part_title: str, section_title: str) -> Optional[List[Dict[str, Any]]]:
    cache_path = normalized_cache_path(part_title, section_title)
    if not cache_path.exists():
        return None
    payload = load_json(cache_path)
    return payload.get("nodes") or []


def filter_valid_rows(
    rows: List[Dict[str, Any]],
    *,
    section_title: str | None = None,
    extraction_cache: Dict[str, Any] | None = None,
    section_markdown: str = "",
) -> Tuple[List[Dict[str, Any]], int]:
    valid = [row for row in rows if is_valid_node_row(row)]
    dropped = len(rows) - len(valid)
    if not section_title:
        return valid, dropped

    section_entity = extract_section_entity(section_title)
    guarded, rejected = filter_guarded_rows(
        valid,
        section_entity=section_entity,
        chunk_source_map=build_chunk_source_map(extraction_cache),
        section_markdown=section_markdown,
    )
    if rejected:
        sample = ", ".join(
            f"{item.get('title')}({item.get('reason')})" for item in rejected[:5]
        )
        print(
            f"[ingest] Guardrails rejected {len(rejected)} nodes"
            + (f": {sample}" if sample else "")
        )
    return guarded, dropped + len(rejected)


def ensure_v3_catalog() -> Dict[str, Any]:
    catalog_path = V3_OUTPUT_DIR / f"{PDF_STEM}.catalog.json"
    if catalog_path.exists():
        return load_json(catalog_path)

    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    cmd = [sys.executable, str(V3_SCRIPT), str(PDF_PATH), "--catalog-only"]
    print(f"[ingest] Building PDF catalog: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"catalog-only failed (exit {result.returncode})")
    return load_json(catalog_path)


CHAPTER_NUM_RE = re.compile(r"^(第[一二三四五六七八九十百零\d]+章)")
CHAPTER_TITLE_RE = re.compile(r"第[一二三四五六七八九十百零\d]+章")


def normalize_catalog_title(title: str) -> str:
    return re.sub(r"[\s\-－—]", "", (title or "").strip())


def chapter_number_prefix(title: str) -> str | None:
    match = CHAPTER_NUM_RE.match((title or "").strip())
    return match.group(1) if match else None


def pdf_chapter_titles_for_part(part_title: str) -> list[str]:
    catalog = ensure_v3_catalog()
    titles: list[str] = []
    norm_part = normalize_catalog_title(part_title)
    for entry in catalog.get("toc_entries", []):
        if not entry.get("is_content"):
            continue
        headings = entry.get("headings") or []
        if not part_in_catalog_headings(part_title, headings):
            continue
        title = str(entry.get("title") or "").strip()
        if title == "绪论" and norm_part == normalize_catalog_title(part_title):
            titles.append(title)
        elif CHAPTER_TITLE_RE.search(title) and "篇" not in title:
            titles.append(title)
    return titles


def _title_keywords(title: str) -> set[str]:
    cleaned = re.sub(r"^第[一二三四五六七八九十百零\d]+章", "", title or "")
    cleaned = re.sub(r"[\s\-－—、，。；;（）()]", "", cleaned)
    if len(cleaned) <= 1:
        return set()
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def resolve_pdf_section_title_with_confidence(
    part_title: str,
    section_title: str,
) -> Tuple[str, int, str]:
    """Map manifest section title to PDF bookmark title with confidence score."""
    pdf_titles = pdf_chapter_titles_for_part(part_title)
    norm_section = normalize_catalog_title(section_title)
    for pdf_title in pdf_titles:
        if normalize_catalog_title(pdf_title) == norm_section:
            return pdf_title, 100, "exact"

    wanted_keywords = _title_keywords(section_title)
    if wanted_keywords:
        best_title = section_title
        best_score = 0
        for pdf_title in pdf_titles:
            overlap = len(wanted_keywords & _title_keywords(pdf_title))
            if overlap > best_score:
                best_score = overlap
                best_title = pdf_title
        if best_score >= 2:
            return best_title, best_score, "keyword"

    wanted_num = chapter_number_prefix(section_title)
    if wanted_num:
        same_num = [pdf_title for pdf_title in pdf_titles if pdf_title.startswith(wanted_num)]
        if len(same_num) == 1:
            return same_num[0], 1, "chapter_number"
    return section_title, 0, "unchanged"


def resolve_pdf_section_title(part_title: str, section_title: str) -> str:
    resolved, score, method = resolve_pdf_section_title_with_confidence(part_title, section_title)
    if score < 2 and method != "exact":
        print(
            f"[catalog] WARN low-confidence title mapping ({method}, score={score}): "
            f"{section_title} -> {resolved}"
        )
    return resolved


def section_quality_metrics(
    part_title: str,
    section_title: str,
    *,
    quality_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved, score, method = resolve_pdf_section_title_with_confidence(part_title, section_title)
    metrics: Dict[str, Any] = {
        "pdf_parser": resolve_pdf_parser_mode(),
        "catalog_mapping": {
            "manifest_title": section_title,
            "resolved_title": resolved,
            "score": score,
            "method": method,
        },
    }
    try:
        pipeline = _v3_pipeline_for_section(part_title, section_title)
        if pipeline.parse_report_path.exists():
            parse_report = load_json(pipeline.parse_report_path)
            metrics["parser_units"] = parse_report.get("total_units")
            metrics["parser_fallback_units"] = parse_report.get("fallback_units")
            metrics["parser_page_counts"] = parse_report.get("page_parser_counts")
            metrics["parser_blocking_pages"] = parse_report.get("blocking_pages")
    except Exception:
        pass
    if quality_report:
        metrics["chunk_coverage"] = quality_report.get("chunk_coverage")
        metrics["guardrails"] = (quality_report.get("guardrails") or {}).get("metrics")
    return metrics


def part_in_catalog_headings(part_title: str, headings: List[str]) -> bool:
    norm_part = normalize_catalog_title(part_title)
    return part_title in headings or any(
        normalize_catalog_title(heading) == norm_part for heading in headings
    )


def resolve_catalog_section_range(part_title: str, section_title: str) -> Tuple[int, int]:
    catalog = ensure_v3_catalog()
    units = catalog.get("units", [])
    section_title = resolve_pdf_section_title(part_title, section_title)
    norm_section = normalize_catalog_title(section_title)
    norm_part = normalize_catalog_title(part_title)

    if norm_section in {normalize_catalog_title("绪论"), norm_part}:
        for unit in units:
            if normalize_catalog_title(str(unit.get("title") or "")) == norm_part:
                return int(unit["index"]), 1

    chapter_units: List[Dict[str, Any]] = []
    for unit in units:
        headings = unit.get("headings") or []
        if not part_in_catalog_headings(part_title, headings):
            continue
        if normalize_catalog_title(str(unit.get("title") or "")) == norm_section:
            return int(unit["index"]), 1
        if any(normalize_catalog_title(heading) == norm_section for heading in headings):
            chapter_units.append(unit)

    if chapter_units:
        indices = sorted(int(unit["index"]) for unit in chapter_units)
        start = indices[0]
        if indices != list(range(start, start + len(indices))):
            raise RuntimeError(
                f"Non-contiguous catalog units for {part_title} / {section_title}: {indices}"
            )
        return start, len(indices)

    raise RuntimeError(f"Section not found in PDF catalog: {part_title} / {section_title}")


def find_catalog_unit_index(part_title: str, section_title: str) -> int:
    start, _limit = resolve_catalog_section_range(part_title, section_title)
    return start


def v3_scope_tag(section_start: int, section_limit: int) -> str:
    return f".s{section_start}.l{section_limit}"


def v3_nodes_path(section_start: int, section_limit: int) -> Path:
    return V3_OUTPUT_DIR / f"{PDF_STEM}{v3_scope_tag(section_start, section_limit)}.nodes.json"


def _ollama_api_ready(timeout: float = 5.0) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=timeout) as resp:
            json.loads(resp.read().decode("utf-8"))
        return True
    except Exception:
        return False


def ensure_ollama_server() -> bool:
    """Start the local Ollama service when the API is down."""
    if _ollama_api_ready():
        return True

    candidates = [
        Path(os.environ.get("OLLAMA_EXE", "")),
        PROJECT_ROOT.parent / "Ollama" / "ollama.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
    ]
    ollama_exe = next((path for path in candidates if path and path.exists()), None)
    if ollama_exe is None:
        print("[ingest] Ollama executable not found — set OLLAMA_EXE if needed")
        return False

    print(f"[ingest] Starting Ollama: {ollama_exe}")
    subprocess.Popen(
        [str(ollama_exe), "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(12):
        time.sleep(2)
        if _ollama_api_ready(timeout=3.0):
            print("[ingest] Ollama API is ready")
            return True
    print("[ingest] Ollama failed to become ready")
    return False


def prepare_ollama_gpu() -> None:
    """Ensure Ollama is reachable and warm up the extraction model."""
    model = os.environ.get("OLLAMA_MODEL", "medlearn-qwen3:8b")
    keep_alive = os.environ.get("OLLAMA_KEEP_ALIVE", "10m")

    if not ensure_ollama_server():
        print("[ingest] Ollama unavailable — extract will likely fail")
        return

    try:
        import urllib.request

        warmup_payload = json.dumps(
            {
                "model": model,
                "stream": False,
                "keep_alive": keep_alive,
                "messages": [{"role": "user", "content": "回复 OK"}],
                "options": {
                    "num_ctx": 512,
                    "num_gpu": int(os.environ.get("OLLAMA_NUM_GPU", "999")),
                },
            }
        ).encode("utf-8")
        warmup_req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=warmup_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(warmup_req, timeout=120)
        os.environ["OLLAMA_SKIP_WARMUP"] = "1"
        print(f"[ingest] Ollama warmed up ({model})")
    except Exception as exc:
        print(f"[ingest] Ollama warmup skipped: {exc}")


def v3_extraction_cache_path(section_start: int, section_limit: int) -> Path:
    return V3_OUTPUT_DIR / (
        f"{PDF_STEM}{v3_scope_tag(section_start, section_limit)}.extraction.json"
    )


def _v3_pipeline_for_section(part_title: str, section_title: str):
    section_start, section_limit = resolve_catalog_section_range(part_title, section_title)
    return build_pipeline(
        section_start=section_start,
        section_limit=section_limit,
        output_dir=V3_OUTPUT_DIR,
        source_pdf=PDF_PATH,
    )


def rebuild_v3_nodes(part_title: str, section_title: str) -> Path:
    pipeline = _v3_pipeline_for_section(part_title, section_title)
    if not pipeline.cache_path.exists():
        raise FileNotFoundError(f"No V3 extraction cache: {pipeline.cache_path}")
    print(f"[ingest] Rebuilding nodes in-process from {pipeline.cache_path.name}")
    pipeline.rebuild_from_cache()
    nodes_path = v3_nodes_path(pipeline.section_start, pipeline.section_limit or 1)
    if not nodes_path.exists():
        raise FileNotFoundError(f"No V3 nodes output after rebuild: {nodes_path}")
    return nodes_path


def summarize_v3_failure(part_title: str, section_title: str) -> str:
    try:
        section_start, section_limit = resolve_catalog_section_range(
            part_title, section_title
        )
    except Exception as exc:
        return f"V3 extract produced 0 nodes ({exc})"

    cache_path = v3_extraction_cache_path(section_start, section_limit)
    nodes_path = v3_nodes_path(section_start, section_limit)
    if not cache_path.exists():
        return (
            "V3 extract produced 0 nodes (no LLM cache — check Ollama logs / chunk errors)"
        )

    cache = load_json(cache_path)
    chunk_count = len(cache.get("chunks") or {})
    raw_nodes = sum(
        len(result.get("nodes") or [])
        for result in (cache.get("chunks") or {}).values()
    )
    built_nodes = 0
    if nodes_path.exists():
        built_nodes = len((load_json(nodes_path).get("nodes") or []))

    if raw_nodes and built_nodes == 0:
        return (
            f"V3 extract produced 0 nodes after filtering "
            f"(raw={raw_nodes}, chunks={chunk_count}) — try rebuild-from-cache"
        )
    if chunk_count and raw_nodes == 0:
        return (
            f"V3 extract produced 0 nodes (LLM returned empty for {chunk_count} chunks)"
        )
    return (
        f"V3 extract produced 0 nodes (chunks={chunk_count}, raw={raw_nodes}, built={built_nodes})"
    )


def run_v3_extract(
    part_title: str,
    section_title: str,
    *,
    prepare_ollama: bool = True,
) -> Path:
    global _LAST_V3_TIMINGS
    _LAST_V3_TIMINGS = {}
    total_started = time.perf_counter()
    timings: Dict[str, float] = {}
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    if prepare_ollama:
        started = time.perf_counter()
        prepare_ollama_gpu()
        timings["prepare_ollama"] = seconds_since(started)
    started = time.perf_counter()
    section_start, section_limit = resolve_catalog_section_range(part_title, section_title)
    timings["resolve_catalog_range"] = seconds_since(started)
    nodes_path = v3_nodes_path(section_start, section_limit)
    cache_path = v3_extraction_cache_path(section_start, section_limit)

    started = time.perf_counter()
    pipeline = _v3_pipeline_for_section(part_title, section_title)
    timings["build_pipeline"] = seconds_since(started)

    if cache_path.exists() and (
        not nodes_path.exists()
        or len((load_json(nodes_path).get("nodes") or [])) == 0
    ):
        from textbook_pipeline.v3_runner import extraction_cache_stats

        cache = load_json(cache_path)
        raw_nodes = sum(
            len(result.get("nodes") or [])
            for result in (cache.get("chunks") or {}).values()
        )
        cache_complete = False
        if pipeline.markdown_path.exists():
            markdown = pipeline.markdown_path.read_text(encoding="utf-8")
            stats = extraction_cache_stats(pipeline, markdown)
            cache_complete = bool(stats.get("complete"))
            if raw_nodes and not cache_complete:
                print(
                    f"[ingest] Partial LLM cache ({stats['cached_chunks']}/"
                    f"{stats['total_chunks']} chunks); resuming extraction"
                )
        if raw_nodes and cache_complete:
            print(
                f"[ingest] Found complete LLM cache with {raw_nodes} raw nodes; "
                "rebuilding outputs"
            )
            started = time.perf_counter()
            rebuilt = rebuild_v3_nodes(part_title, section_title)
            timings["rebuild_nodes"] = seconds_since(started)
            timings["total"] = seconds_since(total_started)
            _LAST_V3_TIMINGS = timings
            return rebuilt

    print(
        f"[ingest] Catalog range: units {section_start}..{section_start + section_limit - 1} "
        f"({section_limit} unit(s))"
    )
    print("[ingest] Running V3 extract in-process (pymupdf-only, max-chars=2800)")
    started = time.perf_counter()
    run_section_extract(pipeline, force_parse=False, no_resume=False)
    timings["run_section_extract"] = seconds_since(started)
    for key, value in (getattr(pipeline, "last_run_timings", {}) or {}).items():
        timings[f"runner.{key}"] = value

    if not nodes_path.exists():
        raise FileNotFoundError(f"No V3 nodes output: {nodes_path}")

    if len((load_json(nodes_path).get("nodes") or [])) == 0 and cache_path.exists():
        cache = load_json(cache_path)
        raw_nodes = sum(
            len(result.get("nodes") or [])
            for result in (cache.get("chunks") or {}).values()
        )
        if raw_nodes:
            print(
                f"[ingest] Extract finished with 0 atomic nodes but raw={raw_nodes}; rebuilding"
            )
            started = time.perf_counter()
            rebuilt = rebuild_v3_nodes(part_title, section_title)
            timings["rebuild_nodes"] = seconds_since(started)
            timings["total"] = seconds_since(total_started)
            _LAST_V3_TIMINGS = timings
            return rebuilt
    timings["total"] = seconds_since(total_started)
    _LAST_V3_TIMINGS = timings
    return nodes_path


def normalize_v3_nodes(
    part_title: str,
    section_title: str,
    nodes_path: Path,
    *,
    pipeline_version: str = "v3",
) -> List[Dict[str, Any]]:
    identity = get_textbook_identity(TEXTBOOK_ID)
    payload = load_json(nodes_path)
    raw_rows = payload.get("nodes") or []
    pipeline = _v3_pipeline_for_section(part_title, section_title)
    extraction_cache = (
        load_json(pipeline.cache_path) if pipeline.cache_path.exists() else None
    )
    if extraction_cache:
        extraction_cache = pipeline.enrich_cache_with_source(extraction_cache)
    section_markdown = (
        pipeline.markdown_path.read_text(encoding="utf-8")
        if pipeline.markdown_path.exists()
        else ""
    )
    provenance = build_provenance(
        identity=identity,
        part_title=part_title,
        section_title=section_title,
        source_pdf=str(PDF_PATH),
        pipeline_version=pipeline_version,
        created_from=str(nodes_path),
    )
    for row in raw_rows:
        if row.get("chapter") and row.get("chapter") != part_title:
            source_span = row.get("source_span") or {}
            if isinstance(source_span, dict):
                source_span["pdf_part_title"] = row["chapter"]
                row["source_span"] = source_span
        row["chapter"] = part_title
        row["sub_chapter"] = section_title
    rows, dropped = filter_valid_rows(
        raw_rows,
        section_title=section_title,
        extraction_cache=extraction_cache,
        section_markdown=section_markdown,
    )
    if dropped:
        print(f"[ingest] Filtered {dropped} invalid/unsafe nodes")
    enriched = [enrich_row_content(row) for row in rows]
    return finalize_knowledge_rows(enriched, identity, provenance=provenance)


def normalize_v3_nodes_preserve(
    part_title: str,
    section_title: str,
    nodes_path: Path,
    *,
    pipeline_version: str = "v3",
) -> List[Dict[str, Any]]:
    """Normalize V3 nodes without guardrail re-filtering (P0 backfill recovery)."""
    identity = get_textbook_identity(TEXTBOOK_ID)
    payload = load_json(nodes_path)
    raw_rows = payload.get("nodes") or []
    provenance = build_provenance(
        identity=identity,
        part_title=part_title,
        section_title=section_title,
        source_pdf=str(PDF_PATH),
        pipeline_version=pipeline_version,
        created_from=str(nodes_path),
    )
    for row in raw_rows:
        if row.get("chapter") and row.get("chapter") != part_title:
            source_span = row.get("source_span") or {}
            if isinstance(source_span, dict):
                source_span["pdf_part_title"] = row["chapter"]
                row["source_span"] = source_span
        row["chapter"] = part_title
        row["sub_chapter"] = section_title
    valid = [row for row in raw_rows if is_valid_node_row(row)]
    enriched = [enrich_row_content(row) for row in valid]
    return finalize_knowledge_rows(enriched, identity, provenance=provenance)


def recover_section_rows_from_v3(
    part_title: str,
    section_title: str,
) -> Optional[List[Dict[str, Any]]]:
    try:
        section_start, section_limit = resolve_catalog_section_range(part_title, section_title)
    except Exception:
        return None
    nodes_path = v3_nodes_path(section_start, section_limit)
    if not nodes_path.exists():
        return None
    rows = normalize_v3_nodes_preserve(part_title, section_title, nodes_path)
    if not rows:
        return None
    write_normalized_cache(
        part_title,
        section_title,
        rows,
        source_path=nodes_path,
        pipeline_version="v3",
    )
    return rows


def evaluate_section_quality(
    rows: List[Dict[str, Any]],
    *,
    part_title: str,
    section_title: str,
) -> Dict[str, Any]:
    chunk_cov: Dict[str, Any] = {}
    section_markdown = ""
    chunk_source_map: Dict[str, str] = {}
    try:
        pipeline = _v3_pipeline_for_section(part_title, section_title)
        if pipeline.markdown_path.exists():
            from textbook_pipeline.v3_runner import extraction_cache_stats

            section_markdown = pipeline.markdown_path.read_text(encoding="utf-8")
            chunk_stats = extraction_cache_stats(pipeline, section_markdown)
            chunk_cov = assess_chunk_coverage(
                chunk_stats["total_chunks"],
                chunk_stats["cached_chunks"],
            )
        if pipeline.cache_path.exists():
            extraction_cache = load_json(pipeline.cache_path)
            extraction_cache = pipeline.enrich_cache_with_source(extraction_cache)
            chunk_source_map = build_chunk_source_map(extraction_cache)
    except Exception as exc:
        chunk_cov = {"error": str(exc)}

    report = assess_rows_with_guardrails(
        rows,
        section_entity=extract_section_entity(section_title),
        chunk_source_map=chunk_source_map,
        section_markdown=section_markdown,
    )
    report["chunk_coverage"] = chunk_cov
    if chunk_cov and not chunk_cov.get("passed", True):
        report["passed"] = False
        reasons = list(report.get("reasons") or [])
        reasons.append("low_chunk_coverage")
        report["reasons"] = reasons
    return report


def normalize_v4_source(
    part_title: str,
    section_title: str,
    source_path: Path,
) -> List[Dict[str, Any]]:
    identity = get_textbook_identity(TEXTBOOK_ID)
    nodes = load_v4_payload(source_path)
    rows = v4_payload_to_knowledge_rows(
        nodes,
        textbook_id=TEXTBOOK_ID,
        subject=identity.subject_name,
        textbook=identity.display_name,
        chapter=part_title,
        sub_chapter=section_title,
        source_pdf=str(PDF_PATH),
    )
    rows, dropped = filter_valid_rows(rows)
    if dropped:
        print(f"[ingest] Filtered {dropped} invalid nodes from V4 source")
    return rows


def parse_section_args(args: argparse.Namespace, manifest: Dict[str, Any]) -> Dict[str, Any]:
    part_title = getattr(args, "part", None)
    section_title = getattr(args, "section", None) or getattr(args, "chapter", None)
    if section_title:
        resolved = resolve_section(manifest, part_title=part_title, section_title=section_title)
        if not resolved:
            raise KeyError(f"Section not in manifest: {section_title}")
        return resolved
    resolved = next_runnable_section(manifest)
    if not resolved:
        raise RuntimeError("No runnable section in manifest")
    return resolved


def _ollama_ready() -> tuple[bool, str]:
    import urllib.request

    model = os.environ.get("OLLAMA_MODEL", "medlearn-qwen3:8b")
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        names = [item.get("name", "") for item in payload.get("models", [])]
        if not names:
            return False, f"Ollama running but no models installed (want {model})"
        if any(model in name or name.startswith(model.split(":")[0]) for name in names):
            return True, model
        return False, f"Ollama up; missing {model}. Have: {', '.join(names)}"
    except Exception as exc:
        return False, f"Ollama unavailable: {exc}"


def cmd_status(_args: argparse.Namespace) -> int:
    manifest = load_manifest()
    state = load_state()
    sections = list(iter_manifest_sections(manifest))
    total = len(sections)
    verified = sum(1 for item in sections if section_status(item["section_ref"]) == "verified")
    failed = sum(1 for item in sections if section_status(item["section_ref"]) == "failed")
    next_sec = next_runnable_section(manifest)
    ollama_ok, ollama_detail = _ollama_ready()
    legacy_prod = state.get("production_status") or {}
    extraction = state.get("extraction") or {}
    production = state.get("production_ingestion") or {}
    app_integration = state.get("app_integration") or {}

    print("=== Knowledge Ingestion Status ===")
    print()
    print("--- Layered production status ---")
    print(
        f"Extraction:                "
        f"{extraction.get('status', legacy_prod.get('real_extraction_pipeline', 'pending'))}"
    )
    print(
        f"Verified sections:         "
        f"{extraction.get('verified_section_count', verified)}"
    )
    print(
        f"Production ingestion:      "
        f"{production.get('status', legacy_prod.get('production_ingestion', 'not_accepted'))}"
    )
    print(
        f"Upload pipeline:           "
        f"{production.get('upload_pipeline', legacy_prod.get('upload_pipeline', 'smoke-tested'))}"
    )
    print(
        f"App integration:           "
        f"{app_integration.get('status', legacy_prod.get('app_integration', 'db_query_ready_ui_pending'))}"
    )
    if production.get("p0_backfill_completed"):
        print(
            f"P0 backfill:               "
            f"{production.get('p0_backfill_sections', 0)} sections"
        )
    print()
    print(f"Textbook:     {TEXTBOOK_ID}")
    print(f"Adapter:      {ADAPTER_VERSION}")
    print(f"Manifest:     {MANIFEST_PATH}")
    print(f"PDF:          {'OK' if PDF_PATH.exists() else 'MISSING'}")
    print(f"Ollama:       {'OK' if ollama_ok else 'NOT READY'} ({ollama_detail})")
    print(f"Sections:     {verified}/{total} manifest-verified, {failed} failed")
    if next_sec:
        print(
            f"Next section: {next_sec['part_title']} / {next_sec['section_title']} "
            f"[{section_status(next_sec['section_ref'])}]"
        )
    else:
        print("Next section: (all verified)")
    print(f"State file:   {STATE_PATH}")
    print(f"Last error:   {state.get('last_error') or 'none'}")
    print(f"Cache root:   {GENERATED_ROOT / TEXTBOOK_ID}")
    print(f"knowledge_points deprecated: {KNOWLEDGE_POINTS_DEPRECATED}")

    try:
        client = get_supabase_client()
        resp = client.table("knowledge_nodes").select("id", count="exact").eq("book_id", TEXTBOOK_ID).execute()
        print(f"Remote nodes: {resp.count} (book_id={TEXTBOOK_ID})")
        chunks_resp = (
            client.table("document_chunks")
            .select("id", count="exact")
            .eq("document_name", TEXTBOOK_ID)
            .execute()
        )
        chains_resp = (
            client.table("causal_chains")
            .select("id", count="exact")
            .eq("source", "pipeline_v3")
            .execute()
        )
        print(f"Remote chunks: {chunks_resp.count} (document_name={TEXTBOOK_ID})")
        print(f"Remote causal_chains: {chains_resp.count} (source=pipeline_v3)")
    except Exception as exc:
        print(f"Remote nodes: unavailable ({exc})")

    gate = state.get("real_llm_gate") or {}
    checklist = gate.get("checklist") or {}
    if checklist:
        print("\n--- Real LLM gate checklist (section 1) ---")
        for key, value in checklist.items():
            mark = "ok" if value is True else ("fail" if value is False else str(value))
            print(f"  {key}: {mark}")

    last_perf = ((state.get("performance") or {}).get("last_section") or {})
    if last_perf:
        print("\n--- Last performance sample ---")
        print(f"  section: {last_perf.get('section')}")
        print(f"  stage:   {last_perf.get('stage')}")
        timings = last_perf.get("timings_sec") or {}
        for key, value in sorted(
            timings.items(),
            key=lambda item: float(item[1]) if isinstance(item[1], (int, float)) else 0.0,
            reverse=True,
        )[:10]:
            print(f"  {key}: {value}s")

    print("\n--- Section breakdown ---")
    for item in sections:
        part = item["part_title"]
        section = item["section_title"]
        ref = item["section_ref"]
        st = section_status(ref)
        nc = ref.get("node_count", "-")
        cache = "cached" if normalized_cache_path(part, section).exists() else "no-cache"
        print(f"  [{st:12}] {part} / {section}  nodes={nc}  {cache}")
    return 0


def cmd_catalog(_args: argparse.Namespace) -> int:
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    (GENERATED_ROOT / TEXTBOOK_ID).mkdir(parents=True, exist_ok=True)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CATALOG_PATH.exists():
        catalog = load_json(CATALOG_PATH)
        chapter_count = len(catalog.get("chapters", []))
        print(f"[catalog] App catalog: {chapter_count} parts in {CATALOG_PATH.name}")
    if PDF_PATH.exists():
        ensure_v3_catalog()
        print(f"[catalog] PDF catalog ready under {V3_OUTPUT_DIR}")
    else:
        print(f"[catalog] PDF missing — skipped PDF catalog build ({PDF_PATH})")
    print(f"[catalog] Normalized cache dir: {GENERATED_ROOT / TEXTBOOK_ID}")
    return 0


def section_has_normalized_cache(part_title: str, section_title: str) -> bool:
    rows = load_normalized_cache(part_title, section_title)
    return bool(rows)


def _ev1_safe_cache_names(part_title: str, section_title: str) -> Tuple[str, str]:
    safe_part = part_title.replace("/", "_").replace(" ", "_")
    safe_section = section_title.replace("/", "_").replace(" ", "_")
    return safe_part, safe_section


def _ev1_evidence_cache_path(part_title: str, section_title: str) -> Path:
    safe_part, safe_section = _ev1_safe_cache_names(part_title, section_title)
    return GENERATED_ROOT / TEXTBOOK_ID / f"{safe_part}__{safe_section}.evidence.json"


def _ev1_candidate_cache_path(part_title: str, section_title: str) -> Path:
    safe_part, safe_section = _ev1_safe_cache_names(part_title, section_title)
    return (
        PROJECT_ROOT
        / "generated"
        / "evidence_candidates"
        / TEXTBOOK_ID
        / f"{safe_part}__{safe_section}.candidate.json"
    )


def _write_ev1_normalized_from_candidate(
    *,
    ctx: IngestionContext,
    candidate_payload: Dict[str, Any],
    candidate_path: Path,
    part_title: str,
    section_title: str,
) -> Path:
    from textbook_pipeline.evidence_to_knowledge import (
        candidate_cache_to_knowledge_rows,
    )

    rows, summary = candidate_cache_to_knowledge_rows(
        candidate_payload,
        ctx.identity,
        source_pdf=str(PDF_PATH.relative_to(PROJECT_ROOT)),
        candidate_path=candidate_path,
        blocked_artifact_ids=_ev1_audit_blocked_artifact_ids(),
    )
    if not rows:
        raise RuntimeError("EV1 candidate conversion produced zero normalized rows")
    output_path = write_ev1_normalized_cache(
        part_title,
        section_title,
        rows,
        source_path=candidate_path,
        conversion_summary=summary,
    )
    print(
        "[ev1] Normalized EV1 cache: "
        f"{output_path.relative_to(PROJECT_ROOT)} "
        f"(converted={summary['converted']}, "
        f"skipped_needs_review={summary['skipped_needs_review']}, "
        f"skipped_rejected={summary['skipped_rejected']}, "
        f"skipped_artifact_audit={summary.get('skipped_artifact_audit', 0)})"
    )
    return output_path


def _load_ev1_registry() -> Dict[str, Any]:
    registry_path = PROJECT_ROOT / "generated" / "evidence_candidates" / TEXTBOOK_ID / "_registry.json"
    if not registry_path.exists():
        raise FileNotFoundError(f"EV1 registry not found: {registry_path}")
    return load_json(registry_path)


def _ev1_audit_blocked_artifact_ids() -> set[str]:
    """Artifacts that must not produce organized EV1 conclusions."""
    audit_path = PROJECT_ROOT / "generated" / "ev1_artifact_audit.json"
    if not audit_path.exists():
        return set()
    try:
        report = load_json(audit_path)
    except Exception:
        return set()
    blocked: set[str] = set()
    for section in report.get("sections") or []:
        for warning in section.get("warnings") or []:
            if warning.get("type") != "missing_figure_context_warning":
                continue
            artifact_id = str(warning.get("artifact_id") or "").strip()
            if artifact_id:
                blocked.add(artifact_id)
    return blocked


def cmd_ev1_convert_ready(args: argparse.Namespace) -> int:
    """Convert all ready EV1 candidate caches into isolated normalized caches."""
    ctx = configure_ingestion(getattr(args, "book_id", "internal-medicine-10"))
    registry = _load_ev1_registry()
    converted = 0
    skipped = 0
    failed = 0

    for key, entry in sorted((registry.get("sections") or {}).items()):
        if entry.get("candidate_status") != "ready_candidate":
            print(f"[ev1-convert-ready] skip not-ready: {key}")
            skipped += 1
            continue
        part_title = str(entry.get("part_title") or "")
        section_title = str(entry.get("section_title") or "")
        output_path = entry.get("output_path")
        candidate_path = PROJECT_ROOT / output_path if output_path else _ev1_candidate_cache_path(part_title, section_title)
        if not candidate_path.exists():
            print(f"[ev1-convert-ready] FAIL missing candidate: {candidate_path}", file=sys.stderr)
            failed += 1
            if not getattr(args, "continue_on_error", False):
                return 1
            continue
        try:
            payload = load_json(candidate_path)
            _write_ev1_normalized_from_candidate(
                ctx=ctx,
                candidate_payload=payload,
                candidate_path=candidate_path,
                part_title=part_title,
                section_title=section_title,
            )
            converted += 1
        except Exception as exc:
            print(f"[ev1-convert-ready] FAIL {key}: {exc}", file=sys.stderr)
            failed += 1
            if not getattr(args, "continue_on_error", False):
                return 1

    print(f"[ev1-convert-ready] done: converted={converted} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 1


def cmd_ev1_release_gate(args: argparse.Namespace) -> int:
    """Validate EV1 normalized caches before any production upload discussion."""
    from textbook_pipeline.evidence_release_gate import (
        summarize_gate_results,
        validate_ev1_normalized_payload,
    )

    ctx = configure_ingestion(getattr(args, "book_id", "internal-medicine-10"))
    root = EV1_NORMALIZED_ROOT / TEXTBOOK_ID
    if not root.exists():
        print(f"[ev1-release-gate] no EV1 normalized cache dir: {root}", file=sys.stderr)
        return 1

    paths = sorted(root.glob("*.normalized.json"))
    if getattr(args, "section", None):
        wanted = section_cache_key(getattr(args, "part", "") or "", args.section)
        paths = [path for path in paths if path.name == f"{wanted}.normalized.json"]
    results = []
    blocked_artifact_ids = _ev1_audit_blocked_artifact_ids()
    for path in paths:
        payload = load_json(path)
        result = validate_ev1_normalized_payload(
            payload,
            path=path.relative_to(PROJECT_ROOT),
            identity=ctx.identity,
            blocked_artifact_ids=blocked_artifact_ids,
        )
        results.append(result)

    summary = summarize_gate_results(results)
    report = {
        "generated_at": utc_now(),
        "book_id": TEXTBOOK_ID,
        "summary": summary,
        "results": [result.to_dict() for result in results],
    }
    report_path = PROJECT_ROOT / "generated" / "ev1_release_gate.json"
    save_json(report_path, report)

    print(
        "[ev1-release-gate] "
        f"sections={summary['sections']} passed={summary['passed_sections']} "
        f"failed={summary['failed_sections']} nodes={summary['total_nodes']}"
    )
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.section}: nodes={result.node_count}")
        for error in result.errors[:5]:
            print(f"    error: {error}")
        for warning in result.warnings[:3]:
            print(f"    warn: {warning}")
    print(f"[ev1-release-gate] report: {report_path.relative_to(PROJECT_ROOT)}")
    return 0 if summary["passed"] else 1


def cmd_ev1_display_contract(args: argparse.Namespace) -> int:
    """Build frontend-facing EV1 display contracts from isolated normalized caches."""
    from textbook_pipeline.evidence_display_contract import (
        DisplayContractOptions,
        build_display_contract_payload,
    )

    _ctx = configure_ingestion(getattr(args, "book_id", "internal-medicine-10"))
    normalized_root = EV1_NORMALIZED_ROOT / TEXTBOOK_ID
    output_root = EV1_DISPLAY_CONTRACT_ROOT / TEXTBOOK_ID
    output_root.mkdir(parents=True, exist_ok=True)

    if not normalized_root.exists():
        print(f"[ev1-display-contract] no EV1 normalized cache dir: {normalized_root}", file=sys.stderr)
        return 1

    paths = sorted(normalized_root.glob("*.normalized.json"))
    if getattr(args, "section", None):
        wanted = section_cache_key(getattr(args, "part", "") or "", args.section)
        paths = [path for path in paths if path.name == f"{wanted}.normalized.json"]

    registry: dict[str, Any] = {}
    try:
        registry = _load_ev1_registry()
    except FileNotFoundError:
        registry = {}

    candidate_by_key: dict[str, Path] = {}
    for key, entry in (registry.get("sections") or {}).items():
        output_path = entry.get("output_path")
        if output_path:
            candidate_by_key[section_cache_key(entry.get("part_title") or "", entry.get("section_title") or "")] = (
                PROJECT_ROOT / output_path
            )

    written = 0
    total_nodes = 0
    options = DisplayContractOptions(
        merge_adjacent_same_heading=not getattr(args, "no_merge", False),
        include_evidence_only=not getattr(args, "organized_only", False),
    )
    for normalized_path in paths:
        normalized_payload = load_json(normalized_path)
        key = section_cache_key(
            normalized_payload.get("part_title") or "",
            normalized_payload.get("section_title") or "",
        )
        candidate_payload = None
        candidate_path = candidate_by_key.get(key)
        if candidate_path and candidate_path.exists():
            candidate_payload = load_json(candidate_path)
        contract = build_display_contract_payload(
            normalized_payload,
            candidate_payload=candidate_payload,
            options=options,
        )
        output_path = output_root / normalized_path.name.replace(".normalized.json", ".display_contract.json")
        save_json(output_path, contract)
        written += 1
        total_nodes += int(contract.get("node_count") or 0)

    report = {
        "generated_at": utc_now(),
        "book_id": TEXTBOOK_ID,
        "contracts": written,
        "nodes": total_nodes,
        "output_root": str(output_root.relative_to(PROJECT_ROOT)),
        "merge_adjacent_same_heading": options.merge_adjacent_same_heading,
        "include_evidence_only": options.include_evidence_only,
    }
    report_path = PROJECT_ROOT / "generated" / "ev1_display_contract_report.json"
    save_json(report_path, report)
    print(
        "[ev1-display-contract] "
        f"contracts={written} nodes={total_nodes} output={output_root.relative_to(PROJECT_ROOT)}"
    )
    print(f"[ev1-display-contract] report: {report_path.relative_to(PROJECT_ROOT)}")
    return 0


def _write_ev1_artifact_audit_markdown(report: Dict[str, Any], path: Path) -> None:
    lines = [
        "# EV1 Artifact Audit",
        "",
        f"Generated: {report['generated_at']}",
        f"Book: {report['book_id']}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    summary = report.get("summary") or {}
    for key in (
        "sections",
        "total_artifacts",
        "text_block",
        "table",
        "caption_like_text",
        "list_like_text",
        "pdf_image_blocks",
        "warnings",
    ):
        lines.append(f"| {key} | {summary.get(key, 0)} |")

    lines.extend(["", "## Sections", ""])
    for section in report.get("sections") or []:
        sec_summary = section.get("summary") or {}
        lines.extend([
            f"### {section.get('section')}",
            "",
            f"- Artifacts: {sec_summary.get('total_artifacts', 0)}",
            f"- Tables: {sec_summary.get('table', 0)}",
            f"- Caption-like text: {sec_summary.get('caption_like_text', 0)}",
            f"- List-like text: {sec_summary.get('list_like_text', 0)}",
            f"- PDF image blocks: {sec_summary.get('pdf_image_blocks', 0)}",
            f"- Warnings: {sec_summary.get('warnings', 0)}",
        ])
        for warning in (section.get("warnings") or [])[:8]:
            lines.append(
                f"  - [{warning.get('severity')}] p{warning.get('page')}: "
                f"{warning.get('type')} - {warning.get('message')}"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def cmd_ev1_artifact_audit(args: argparse.Namespace) -> int:
    """Audit EV1 evidence artifacts for table/list/figure-caption risks."""
    from textbook_pipeline.evidence_artifact_audit import audit_artifacts
    from textbook_pipeline.evidence_extractor import load_evidence_cache

    configure_ingestion(getattr(args, "book_id", "internal-medicine-10"))
    evidence_root = GENERATED_ROOT / TEXTBOOK_ID
    if not evidence_root.exists():
        print(f"[ev1-artifact-audit] evidence cache dir not found: {evidence_root}", file=sys.stderr)
        return 1

    paths = sorted(evidence_root.glob("*.evidence.json"))
    if getattr(args, "section", None):
        wanted = section_cache_key(getattr(args, "part", "") or "", args.section)
        paths = [path for path in paths if path.name == f"{wanted}.evidence.json"]
    if not paths:
        print("[ev1-artifact-audit] no evidence caches matched", file=sys.stderr)
        return 1

    sections: list[dict[str, Any]] = []
    total_summary: Dict[str, int] = {
        "sections": 0,
        "total_artifacts": 0,
        "text_block": 0,
        "table": 0,
        "caption_like_text": 0,
        "list_like_text": 0,
        "pdf_image_blocks": 0,
        "warnings": 0,
    }
    for path in paths:
        artifacts = load_evidence_cache(path)
        audit = audit_artifacts(artifacts, pdf_path=PDF_PATH)
        section_name = path.stem.removesuffix(".evidence")
        section_report = {
            "evidence_path": str(path.relative_to(PROJECT_ROOT)),
            "section": section_name,
            **audit,
        }
        sections.append(section_report)
        sec_summary = audit.get("summary") or {}
        total_summary["sections"] += 1
        for key in total_summary:
            if key == "sections":
                continue
            total_summary[key] += int(sec_summary.get(key) or 0)

    report = {
        "generated_at": utc_now(),
        "book_id": TEXTBOOK_ID,
        "summary": total_summary,
        "sections": sections,
    }
    report_path = PROJECT_ROOT / "generated" / "ev1_artifact_audit.json"
    markdown_path = PROJECT_ROOT / "generated" / "ev1_artifact_audit.md"
    save_json(report_path, report)
    _write_ev1_artifact_audit_markdown(report, markdown_path)

    print(
        "[ev1-artifact-audit] "
        f"sections={total_summary['sections']} artifacts={total_summary['total_artifacts']} "
        f"tables={total_summary['table']} images={total_summary['pdf_image_blocks']} "
        f"warnings={total_summary['warnings']}"
    )
    for section in sections:
        sec_summary = section.get("summary") or {}
        print(
            f"  {section['section']}: "
            f"tables={sec_summary.get('table', 0)} "
            f"caption_like={sec_summary.get('caption_like_text', 0)} "
            f"lists={sec_summary.get('list_like_text', 0)} "
            f"images={sec_summary.get('pdf_image_blocks', 0)} "
            f"warnings={sec_summary.get('warnings', 0)}"
        )
    print(f"[ev1-artifact-audit] report: {report_path.relative_to(PROJECT_ROOT)}")
    print(f"[ev1-artifact-audit] markdown: {markdown_path.relative_to(PROJECT_ROOT)}")
    return 0


def cmd_ev1_run_batch(args: argparse.Namespace) -> int:
    """Run EV1 candidate extraction over manifest sections, then audit/convert/gate."""
    manifest = load_manifest()
    state = load_state()
    target_part = getattr(args, "part", None)
    force = getattr(args, "force_reextract", False)
    max_rejected_rate = float(getattr(args, "max_rejected_rate", 0.30))
    limit = int(getattr(args, "limit", 0) or 0)

    sections = [
        item for item in iter_manifest_sections(manifest)
        if not target_part or item["part_title"] == target_part
    ]
    if limit > 0:
        sections = sections[:limit]

    processed = 0
    skipped = 0
    failed = 0
    review_flagged = 0
    paused = False

    print(
        f"[ev1-run-batch] sections={len(sections)} "
        f"part={target_part or 'ALL'} force={force}"
    )

    for index, item in enumerate(sections, start=1):
        part_title = item["part_title"]
        section_title = item["section_title"]
        candidate_path = _ev1_candidate_cache_path(part_title, section_title)
        label = f"{part_title} / {section_title}"

        if candidate_path.exists() and not force:
            print(f"[ev1-run-batch] [{index}/{len(sections)}] skip cached: {label}")
            skipped += 1
            continue

        print(f"[ev1-run-batch] [{index}/{len(sections)}] run: {label}")
        child_args = argparse.Namespace(**vars(args))
        child_args.part = part_title
        child_args.section = section_title
        child_args.chapter = section_title
        child_args.pipeline = "evidence-first"
        child_args.dry_run = False
        child_args.write_cache = True
        child_args.write_normalized_cache = False
        child_args.force_reextract = force

        code = _cmd_extract_evidence_first(child_args, manifest, state, part_title, section_title)
        if code != 0:
            failed += 1
            print(f"[ev1-run-batch] FAIL extraction: {label}", file=sys.stderr)
            if not getattr(args, "continue_on_error", False):
                paused = True
                break
            continue

        processed += 1
        try:
            candidate_payload = load_json(candidate_path)
            item_total = int((candidate_payload.get("items") or {}).get("total") or 0)
            rejected = int((candidate_payload.get("items") or {}).get("rejected") or 0)
            rejected_rate = rejected / item_total if item_total else 0.0
            candidate_status = candidate_payload.get("candidate_status")
            if candidate_status != "ready_candidate":
                review_flagged += 1
                print(
                    f"[ev1-run-batch] review-flagged: {label} "
                    f"status={candidate_status} rejected_rate={rejected_rate:.1%}"
                )
            if rejected_rate > max_rejected_rate:
                print(
                    f"[ev1-run-batch] PAUSE quality gate: {label} "
                    f"status={candidate_status} rejected_rate={rejected_rate:.1%}",
                    file=sys.stderr,
                )
                failed += 1
                if not getattr(args, "continue_on_error", False):
                    paused = True
                    break
        except Exception as exc:
            failed += 1
            print(f"[ev1-run-batch] FAIL candidate inspection: {label}: {exc}", file=sys.stderr)
            if not getattr(args, "continue_on_error", False):
                paused = True
                break

    print(
        f"[ev1-run-batch] extraction phase: processed={processed} "
        f"skipped={skipped} review_flagged={review_flagged} failed={failed} paused={paused}"
    )
    if paused:
        return 1

    if getattr(args, "skip_post_gates", False):
        print("[ev1-run-batch] post gates skipped")
        return 0 if failed == 0 else 1

    audit_args = argparse.Namespace(**vars(args))
    audit_args.section = None
    audit_args.part = None
    if cmd_ev1_artifact_audit(audit_args) != 0:
        return 1

    convert_args = argparse.Namespace(**vars(args))
    if cmd_ev1_convert_ready(convert_args) != 0:
        return 1

    gate_args = argparse.Namespace(**vars(args))
    gate_args.section = None
    gate_args.part = None
    if cmd_ev1_release_gate(gate_args) != 0:
        return 1

    print("[ev1-run-batch] DONE")
    return 0 if failed == 0 else 1


def _update_ev1_registry(
    *,
    book_id: str,
    part_title: str,
    section_title: str,
    page_start: int,
    page_end: int,
    artifacts: int,
    items: int,
    counts: Dict[str, int],
    coverage_rate: float,
    candidate_status: str,
    candidate_path: Path,
) -> None:
    """Update EV1 candidate registry with section results."""
    registry_dir = PROJECT_ROOT / "generated" / "evidence_candidates" / book_id
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / "_registry.json"

    # Load existing registry or create new
    if registry_path.exists():
        registry = load_json(registry_path)
    else:
        registry = {"version": "ev1-registry-0.1.0", "book_id": book_id, "sections": {}}

    # Key by part/section
    key = f"{part_title} / {section_title}"
    registry["sections"][key] = {
        "part_title": part_title,
        "section_title": section_title,
        "page_start": page_start,
        "page_end": page_end,
        "artifact_count": artifacts,
        "item_count": items,
        "pass": counts["pass"],
        "needs_review": counts["needs_review"],
        "rejected": counts["rejected"],
        "coverage": coverage_rate,
        "candidate_status": candidate_status,
        "output_path": str(candidate_path.relative_to(PROJECT_ROOT)),
        "generated_at": utc_now(),
        "pipeline_version": "ev1-0.1.0",
    }
    registry["updated_at"] = utc_now()

    save_json(registry_path, registry)
    print(f"[ev1] Registry updated: {registry_path.name}")


def _cmd_extract_evidence_first(
    args: argparse.Namespace,
    manifest: Dict[str, Any],
    state: Dict[str, Any],
    part_title: str,
    section_title: str,
) -> int:
    """EV1 evidence-first pipeline (dry-run only)."""
    from textbook_pipeline.evidence_extractor import (
        extract_section_evidence,
        load_evidence_cache,
        write_evidence_cache,
    )
    from textbook_pipeline.evidence_synthesis import (
        synthesize_artifacts,
        write_synthesis_cache,
    )
    from textbook_pipeline.evidence_verifier import verify_items

    ctx = configure_ingestion(getattr(args, "book_id", "internal-medicine-10"))
    write_normalized = getattr(args, "write_normalized_cache", False)

    # Resolve page range from catalog units
    catalog = ensure_v3_catalog()
    section_start, section_limit = resolve_catalog_section_range(
        part_title, section_title
    )
    units = catalog.get("units", [])
    page_start = units[section_start]["page_start"] if section_start < len(units) else 0
    page_end = units[section_start + section_limit - 1]["page_end"] if section_start + section_limit - 1 < len(units) else 0

    print(f"[ev1] Section: {part_title} / {section_title}")
    print(f"[ev1] Pages: {page_start}-{page_end}")
    if write_normalized:
        print("[ev1] Mode: write-normalized-cache (EV1 isolated cache, no manifest/upload changes)")
    elif getattr(args, "write_cache", False):
        print("[ev1] Mode: write-cache (candidate only, no manifest/upload changes)")
    else:
        print("[ev1] Mode: dry-run (no manifest/cache/upload changes)")

    candidate_path = _ev1_candidate_cache_path(part_title, section_title)
    if write_normalized and candidate_path.exists() and not getattr(args, "force_reextract", False):
        candidate_payload = load_json(candidate_path)
        print(f"[ev1] Using cached candidate: {candidate_path.name}")
        try:
            _write_ev1_normalized_from_candidate(
                ctx=ctx,
                candidate_payload=candidate_payload,
                candidate_path=candidate_path,
                part_title=part_title,
                section_title=section_title,
            )
        except Exception as exc:
            print(f"[ev1] FAILED normalized conversion: {exc}", file=sys.stderr)
            return 1
        print("[ev1] DONE (--write-normalized-cache, no manifest/upload changes)")
        return 0

    # Phase 1: Evidence extraction
    evidence_path = _ev1_evidence_cache_path(part_title, section_title)

    if evidence_path.exists() and not getattr(args, "force_reextract", False):
        print(f"[ev1] Using cached evidence: {evidence_path.name}")
        artifacts = load_evidence_cache(evidence_path)
    else:
        print("[ev1] Extracting evidence artifacts...")
        artifacts = extract_section_evidence(
            pdf_path=PDF_PATH,
            textbook_id=TEXTBOOK_ID,
            book_id=TEXTBOOK_ID,
            part_title=part_title,
            section_title=section_title,
            page_start=page_start,
            page_end=page_end,
        )
        write_evidence_cache(artifacts, evidence_path)
        print(f"[ev1] Evidence cache: {evidence_path.name}")

    text_arts = [a for a in artifacts if a.artifact_type == "text_block"]
    table_arts = [a for a in artifacts if a.artifact_type == "table"]
    print(f"[ev1] Artifacts: {len(artifacts)} total, {len(text_arts)} text, {len(table_arts)} table")

    # Phase 2: Synthesis
    synth_path = evidence_path.with_suffix(".synthesis.json")
    if getattr(args, "force_reextract", False) and synth_path.exists():
        synth_path.unlink()
    print("[ev1] Synthesizing items...")
    items, metrics = synthesize_artifacts(
        text_arts,
        checkpoint_path=synth_path,
        resume=not getattr(args, "force_reextract", False),
        verbose=not getattr(args, "quiet", False),
    )

    print(f"[ev1] Items: {len(items)} synthesized")

    # Phase 3: Verification
    results, counts = verify_items(
        items, artifacts,
        section_page_start=page_start,
        section_page_end=page_end,
    )

    print(f"[ev1] Verification: pass={counts['pass']} needs_review={counts['needs_review']} rejected={counts['rejected']}")

    # Coverage
    artifact_ids_with_items = {item.artifact_id for item in items}
    covered = len(artifact_ids_with_items)
    coverage_rate = covered / len(text_arts) if text_arts else 0
    rejected_rate = counts["rejected"] / len(items) if items else 0
    print(f"[ev1] Coverage: {covered}/{len(text_arts)} text artifacts ({coverage_rate*100:.1f}%)")

    # Quality gate: candidate_status
    candidate_status = "ready_candidate"
    if coverage_rate < 0.95 or rejected_rate > 0.02:
        candidate_status = "needs_pipeline_review"
    print(f"[ev1] Quality gate: {candidate_status}")

    # Write final synthesis cache with verification states.
    write_synthesis_cache(items, metrics, synth_path)

    # Write candidate cache (only with --write-cache / --write-normalized-cache)
    write_cache = getattr(args, "write_cache", False)
    should_write_candidate = write_cache or write_normalized

    candidate_payload = {
        "version": "ev1-candidate-0.1.0",
        "book_id": TEXTBOOK_ID,
        "part_title": part_title,
        "section_title": section_title,
        "page_start": page_start,
        "page_end": page_end,
        "generated_at": utc_now(),
        "pipeline_version": "ev1-0.1.0",
        "candidate_status": candidate_status,
        "artifacts": {"total": len(artifacts), "text_block": len(text_arts), "table": len(table_arts)},
        "items": {"total": len(items), "pass": counts["pass"], "needs_review": counts["needs_review"], "rejected": counts["rejected"]},
        "coverage": {"artifacts_with_items": covered, "artifacts_without_items": len(text_arts) - covered, "coverage_rate": coverage_rate},
        "candidate_items": [item.to_dict() for item in items],
    }

    if should_write_candidate:
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        save_json(candidate_path, candidate_payload)
        print(f"[ev1] Candidate cache: {candidate_path.name}")

        # Update registry
        _update_ev1_registry(
            book_id=TEXTBOOK_ID,
            part_title=part_title,
            section_title=section_title,
            page_start=page_start,
            page_end=page_end,
            artifacts=len(artifacts),
            items=len(items),
            counts=counts,
            coverage_rate=coverage_rate,
            candidate_status=candidate_status,
            candidate_path=candidate_path,
        )
        if write_normalized:
            try:
                _write_ev1_normalized_from_candidate(
                    ctx=ctx,
                    candidate_payload=candidate_payload,
                    candidate_path=candidate_path,
                    part_title=part_title,
                    section_title=section_title,
                )
            except Exception as exc:
                print(f"[ev1] FAILED normalized conversion: {exc}", file=sys.stderr)
                return 1
            print("[ev1] DONE (--write-normalized-cache, no manifest/upload changes)")
        else:
            print(f"[ev1] DONE (--write-cache)")
    else:
        print(f"[ev1] Candidate cache: {candidate_path.name} (not written, use --write-cache)")
        print(f"[ev1] DONE (dry-run)")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    state = load_state()
    total_started = time.perf_counter()
    timings: Dict[str, float] = {}
    target = parse_section_args(args, manifest)
    part_title = target["part_title"]
    section_title = target["section_title"]
    section_ref = target["section_ref"]
    current_status = section_status(section_ref)

    # EV1 evidence-first pipeline
    pipeline = getattr(args, "pipeline", "v3") or "v3"
    if pipeline == "evidence-first":
        if (
            not getattr(args, "dry_run", False)
            and not getattr(args, "write_cache", False)
            and not getattr(args, "write_normalized_cache", False)
        ):
            print(
                "[extract] ERROR: --pipeline evidence-first requires "
                "--dry-run, --write-cache, or --write-normalized-cache",
                file=sys.stderr,
            )
            return 1
        return _cmd_extract_evidence_first(
            args, manifest, state, part_title, section_title
        )

    if (
        not getattr(args, "force_reextract", False)
        and not getattr(args, "source", None)
        and current_status in {"extracted", "uploading", "uploaded", "verified"}
        and section_has_normalized_cache(part_title, section_title)
    ):
        print(
            f"[extract] skip (cached): {part_title} / {section_title} "
            f"[{current_status}] — use --force-reextract to rerun LLM"
        )
        return 0

    set_section_status(manifest, part_title, section_title, "extracting")
    state["current_section"] = f"{part_title}/{section_title}"
    state["last_error"] = None
    save_state(state)

    try:
        if args.source:
            started = time.perf_counter()
            source_path = Path(args.source)
            if not source_path.is_absolute():
                source_path = PROJECT_ROOT / source_path
            rows = normalize_v4_source(part_title, section_title, source_path)
            timings["normalize_source"] = seconds_since(started)
            pipeline_version = "v4"
            source_for_cache = source_path
        else:
            started = time.perf_counter()
            nodes_path = run_v3_extract(
                part_title,
                section_title,
                prepare_ollama=getattr(args, "prepare_ollama", True),
            )
            timings["extract_source"] = seconds_since(started)
            for key, value in _LAST_V3_TIMINGS.items():
                timings[f"extract.{key}"] = value
            started = time.perf_counter()
            rows = normalize_v3_nodes(part_title, section_title, nodes_path)
            timings["normalize_source"] = seconds_since(started)
            pipeline_version = "v3"
            source_for_cache = nodes_path

        started = time.perf_counter()
        quality = evaluate_section_quality(rows, part_title=part_title, section_title=section_title)
        timings["quality_gate"] = seconds_since(started)
        if not rows:
            raise RuntimeError(summarize_v3_failure(part_title, section_title))
        if not quality.get("passed"):
            reasons = ", ".join(quality.get("reasons") or ["quality_gate"])
            metrics = quality.get("metrics") or {}
            raise RuntimeError(
                f"Quality gate failed ({reasons}); metrics={metrics}"
            )

        started = time.perf_counter()
        cache_path = write_normalized_cache(
            part_title,
            section_title,
            rows,
            source_path=source_for_cache,
            pipeline_version=pipeline_version,
        )
        timings["write_cache"] = seconds_since(started)
        print(
            f"[extract] quality OK: nodes={len(rows)} "
            f"metrics={quality.get('metrics')}"
        )
        started = time.perf_counter()
        quality_metrics = section_quality_metrics(
            part_title,
            section_title,
            quality_report=quality,
        )
        set_section_status(
            manifest,
            part_title,
            section_title,
            "extracted",
            node_count=len(rows),
            quality_metrics=quality_metrics,
        )
        timings["status_update"] = seconds_since(started)
        state["current_section"] = f"{part_title}/{section_title}"
        timings["total"] = seconds_since(total_started)
        record_performance(
            state,
            part_title=part_title,
            section_title=section_title,
            stage="extract",
            timings=timings,
            extra={
                "pipeline_version": pipeline_version,
                "node_count": len(rows),
                "cache_path": str(cache_path),
            },
        )
        save_state(state)
        print(f"[extract] timings_sec={timings}")
        print(f"[extract] {part_title} / {section_title}: {len(rows)} nodes → {cache_path}")
        return 0
    except Exception as exc:
        set_section_status(manifest, part_title, section_title, "failed", error=str(exc))
        state["last_error"] = str(exc)
        timings["total"] = seconds_since(total_started)
        record_performance(
            state,
            part_title=part_title,
            section_title=section_title,
            stage="extract_failed",
            timings=timings,
            extra={"error": str(exc)},
        )
        save_state(state)
        print(f"[extract] FAILED {part_title} / {section_title}: {exc}", file=sys.stderr)
        return 1


def cmd_upload(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    state = load_state()
    total_started = time.perf_counter()
    timings: Dict[str, float] = {}
    target = parse_section_args(args, manifest)
    part_title = target["part_title"]
    section_title = target["section_title"]

    started = time.perf_counter()
    rows = load_normalized_cache(part_title, section_title)
    if not rows and args.source:
        source_path = Path(args.source)
        if not source_path.is_absolute():
            source_path = PROJECT_ROOT / source_path
        rows = normalize_v4_source(part_title, section_title, source_path)
        write_normalized_cache(part_title, section_title, rows, source_path=source_path)
    timings["load_cache"] = seconds_since(started)

    if not rows:
        print(f"No normalized cache for {part_title} / {section_title}. Run extract first.")
        return 1

    set_section_status(manifest, part_title, section_title, "uploading")
    state["current_section"] = f"{part_title}/{section_title}"
    save_state(state)

    try:
        started = time.perf_counter()
        result = upload_rows_idempotent(rows, part_title, section_title)
        timings["upload_idempotent"] = seconds_since(started)
        for key, value in (result.get("timings_sec") or {}).items():
            timings[f"upload.{key}"] = value
        for key, value in (result.get("artifact_timings_sec") or {}).items():
            timings[f"artifact.{key}"] = value
        print(
            f"[upload] remote {result['before_count']}→{result['after_count']} "
            f"(delta={result['delta']}, expected={result['expected_ids']}, "
            f"chunks={result.get('chunks_uploaded', 0)}, "
            f"causal_chains={result.get('causal_chains_uploaded', 0)})"
        )
        if not result["idempotent"]:
            raise RuntimeError(
                f"Idempotency check failed: remote={result['after_count']} "
                f"expected={result['expected_ids']}"
            )

        started = time.perf_counter()
        set_section_status(
            manifest,
            part_title,
            section_title,
            "uploaded",
            node_count=len(rows),
            remote_count=result["after_count"],
        )
        timings["status_uploaded"] = seconds_since(started)

        remote_ids = result.get("after_ids") or []
        timings["verify_remote_ids"] = 0.0
        expected_ids = {row["id"] for row in rows}
        missing = expected_ids - set(remote_ids)
        if missing and not args.skip_verify:
            raise RuntimeError(f"Verify failed: {len(missing)} expected IDs missing remotely")

        started = time.perf_counter()
        set_section_status(
            manifest,
            part_title,
            section_title,
            "verified",
            node_count=len(rows),
            remote_count=result["after_count"],
        )
        timings["status_verified"] = seconds_since(started)
        state["last_upload_count"] = len(rows)
        state["last_remote_count"] = result["after_count"]
        state["last_completed_section"] = f"{part_title}/{section_title}"
        state["last_error"] = None
        sync_state_from_manifest(state, manifest)
        timings["total"] = seconds_since(total_started)
        record_performance(
            state,
            part_title=part_title,
            section_title=section_title,
            stage="upload",
            timings=timings,
            extra={
                "node_count": len(rows),
                "remote_count": result["after_count"],
                "chunks_uploaded": result.get("chunks_uploaded", 0),
                "chunks_embedded": result.get("chunks_embedded", 0),
                "causal_chains_uploaded": result.get("causal_chains_uploaded", 0),
            },
        )
        save_state(state)
        print(f"[upload] timings_sec={timings}")
        print(f"[upload] verified: {part_title} / {section_title} ({result['after_count']} remote nodes)")
        return 0
    except Exception as exc:
        set_section_status(manifest, part_title, section_title, "failed", error=str(exc))
        state["last_error"] = str(exc)
        timings["total"] = seconds_since(total_started)
        record_performance(
            state,
            part_title=part_title,
            section_title=section_title,
            stage="upload_failed",
            timings=timings,
            extra={"error": str(exc), "node_count": len(rows)},
        )
        save_state(state)
        print(f"[upload] FAILED {part_title} / {section_title}: {exc}", file=sys.stderr)
        return 1


def cmd_run_parts(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    target_parts = set(args.parts or [])
    if not target_parts:
        raise ValueError("run-parts requires at least one --part")

    needs_llm = any(
        item["part_title"] in target_parts
        and not is_section_done(item["section_ref"])
        and not getattr(args, "source", None)
        for item in iter_manifest_sections(manifest)
    )
    if needs_llm:
        prepare_ollama_gpu()

    processed = 0
    failed = 0
    for item in iter_manifest_sections(manifest):
        if item["part_title"] not in target_parts:
            continue
        part_title = item["part_title"]
        section_title = item["section_title"]
        section_ref = item["section_ref"]
        status = section_status(section_ref)

        if is_section_done(section_ref):
            print(f"[run-parts] skip verified: {part_title} / {section_title}")
            continue

        if (
            status in {"extracted", "uploading", "uploaded"}
            and section_has_normalized_cache(part_title, section_title)
            and not getattr(args, "force_reextract", False)
        ):
            if args.upload:
                print(f"[run-parts] upload-only: {part_title} / {section_title}")
                args.part = part_title
                args.section = section_title
                args.source = None
                args.skip_verify = False
                if cmd_upload(args) != 0:
                    failed += 1
                    if not args.continue_on_error:
                        return 1
                    continue
                processed += 1
            else:
                print(f"[run-parts] skip extracted: {part_title} / {section_title}")
            continue

        print(f"[run-parts] === {part_title} / {section_title} ===")
        args.part = part_title
        args.section = section_title
        args.source = None
        args.prepare_ollama = False
        args.force_reextract = getattr(args, "force_reextract", False)

        if cmd_extract(args) != 0:
            failed += 1
            if not args.continue_on_error:
                return 1
            continue

        if args.upload:
            args.skip_verify = False
            if cmd_upload(args) != 0:
                failed += 1
                if not args.continue_on_error:
                    return 1
                continue

        processed += 1

    print(f"[run-parts] done: processed={processed}, failed={failed}")
    return 1 if failed else 0


def cmd_run_next(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    target = next_runnable_section(manifest)
    if not target:
        print("[run-next] All sections verified.")
        return 0

    part_title = target["part_title"]
    section_title = target["section_title"]
    status = section_status(target["section_ref"])
    print(f"[run-next] {part_title} / {section_title} (was: {status})")

    if status in {"extracted", "uploading", "uploaded", "failed"}:
        cache_rows = load_normalized_cache(part_title, section_title)
        if cache_rows:
            print(f"[run-next] Using cached normalized nodes ({len(cache_rows)})")
            if args.upload:
                args.section = section_title
                args.part = part_title
                args.source = None
                args.skip_verify = False
                return cmd_upload(args)
            print("[run-next] Cache exists — pass --upload to upload without re-extract.")
            return 0

    args.section = section_title
    args.part = part_title
    if cmd_extract(args) != 0:
        return 1
    if args.upload:
        args.source = None
        args.skip_verify = False
        return cmd_upload(args)
    return 0


def cmd_rebuild_cache(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    state = load_state()
    part_title = args.part
    section_title = args.section
    if not resolve_section(manifest, part_title=part_title, section_title=section_title):
        raise KeyError(f"Section not in manifest: {part_title} / {section_title}")

    try:
        nodes_path = rebuild_v3_nodes(part_title, section_title)
        rows = normalize_v3_nodes(part_title, section_title, nodes_path)
        cache_path = write_normalized_cache(
            part_title,
            section_title,
            rows,
            source_path=nodes_path,
            pipeline_version="v3",
        )
        if not rows:
            raise RuntimeError(summarize_v3_failure(part_title, section_title))
        set_section_status(
            manifest, part_title, section_title, "extracted", node_count=len(rows)
        )
        state["current_section"] = f"{part_title}/{section_title}"
        state["last_error"] = None
        save_state(state)
        print(f"[rebuild-cache] {part_title} / {section_title}: {len(rows)} nodes → {cache_path}")
        if args.upload:
            args.source = None
            args.skip_verify = False
            return cmd_upload(args)
        return 0
    except Exception as exc:
        set_section_status(manifest, part_title, section_title, "failed", error=str(exc))
        state["last_error"] = str(exc)
        save_state(state)
        print(f"[rebuild-cache] FAILED {part_title} / {section_title}: {exc}", file=sys.stderr)
        return 1


def cmd_sync_manifest(_args: argparse.Namespace) -> int:
    script = SCRIPT_DIR / "sync_manifest_from_catalog.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode
    return 0


def cmd_audit_gaps(_args: argparse.Namespace) -> int:
    script = SCRIPT_DIR / "audit_manifest_gaps.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(PROJECT_ROOT))
    return result.returncode


def cmd_convert_v4(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path

    part_title = args.part
    section_title = args.section or args.chapter
    if not part_title or not section_title:
        raise ValueError("convert-v4 requires --part and --section")

    rows = normalize_v4_source(part_title, section_title, input_path)
    cache_path = write_normalized_cache(part_title, section_title, rows, source_path=input_path)

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = PROJECT_ROOT / output_path
        save_json(output_path, {"nodes": rows, "part_title": part_title, "section_title": section_title})
        print(f"[convert-v4] extra output → {output_path}")

    print(f"[convert-v4] {len(rows)} nodes → {cache_path}")
    set_section_status(manifest, part_title, section_title, "extracted", node_count=len(rows))

    if args.upload:
        args.source = None
        args.skip_verify = False
        return cmd_upload(args)
    return 0


def cmd_backfill_p0(args: argparse.Namespace) -> int:
    """Re-upload verified sections from normalized cache (no LLM / no new extract)."""
    manifest = load_manifest()
    state = load_state()
    processed = 0
    failed = 0
    skipped = 0

    for item in iter_manifest_sections(manifest):
        part_title = item["part_title"]
        section_title = item["section_title"]
        section_ref = item["section_ref"]
        if str(section_ref.get("status") or "") != "verified":
            continue

        rows = load_normalized_cache(part_title, section_title)
        if not rows:
            rows = recover_section_rows_from_v3(part_title, section_title)
            if not rows:
                print(f"[backfill-p0] skip (no cache/v3): {part_title} / {section_title}")
                skipped += 1
                continue
            print(f"[backfill-p0] recovered {len(rows)} nodes from V3 cache")

        if needs_reference_repair(rows):
            rows = ensure_upload_ready_rows(rows, part_title, section_title)
        elif len(rows) < 1:
            recovered = recover_section_rows_from_v3(part_title, section_title)
            if recovered:
                rows = recovered
                print(
                    f"[backfill-p0] recovered empty cache: {part_title} / {section_title} "
                    f"({len(rows)} nodes)"
                )

        try:
            result = upload_rows_idempotent(rows, part_title, section_title)
            print(
                f"[backfill-p0] OK {part_title} / {section_title}: "
                f"nodes={result['after_count']} chunks={result.get('chunks_uploaded', 0)} "
                f"chains={result.get('causal_chains_uploaded', 0)}"
            )
            processed += 1
        except Exception as exc:
            failed += 1
            print(
                f"[backfill-p0] FAIL {part_title} / {section_title}: {exc}",
                file=sys.stderr,
            )
            if not getattr(args, "continue_on_error", False):
                state["last_error"] = str(exc)
                save_state(state)
                return 1

    state["production_ingestion"] = {
        **(state.get("production_ingestion") or {}),
        "status": "accepted_if_db_verified",
        "p0_backfill_completed": processed > 0,
        "p0_backfill_sections": processed,
    }
    sync_state_from_manifest(state, manifest)
    state["last_error"] = None if failed == 0 else state.get("last_error")
    save_state(state)
    print(
        f"[backfill-p0] done: processed={processed} failed={failed} skipped={skipped}"
    )
    return 0 if failed == 0 else 1


def add_book_id_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--book-id",
        default="internal-medicine-10",
        help="Textbook canonical id (default: internal-medicine-10)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified knowledge ingestion (production)")
    add_book_id_arg(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show manifest + remote status")
    sub.add_parser("catalog", help="Ensure cache directories and PDF catalog")
    sub.add_parser("sync-manifest", help="Rebuild manifest + app catalog from PDF TOC")

    p_audit = sub.add_parser("audit-gaps", help="Report manifest vs PDF catalog gaps")

    p_rebuild = sub.add_parser(
        "rebuild-cache",
        help="Rebuild V3 nodes from existing .extraction.json without calling Ollama",
    )
    p_rebuild.add_argument("--section", required=True)
    p_rebuild.add_argument("--part", required=True)
    p_rebuild.add_argument("--upload", action="store_true")

    for name in ("extract", "upload", "run-next"):
        cmd = sub.add_parser(name, help=f"{name} one manifest section")
        cmd.add_argument("--section", help="Section title, e.g. 第一章 总论")
        cmd.add_argument("--chapter", help="Alias for --section")
        cmd.add_argument("--part", help="Part title, e.g. 第一篇 呼吸系统疾病")
        if name == "extract":
            cmd.add_argument("--source", help="V4 JSON path (skip V3 LLM extract)")
            cmd.add_argument(
                "--force-reextract",
                action="store_true",
                help="Ignore normalized cache and rerun LLM",
            )
            cmd.add_argument(
                "--pipeline",
                choices=["v3", "evidence-first"],
                default="v3",
                help=(
                    "Extraction pipeline (default: v3). evidence-first requires "
                    "--dry-run, --write-cache, or --write-normalized-cache"
                ),
            )
            cmd.add_argument(
                "--dry-run",
                action="store_true",
                help="Dry-run mode (required for evidence-first without --write-cache)",
            )
            cmd.add_argument(
                "--write-cache",
                action="store_true",
                help="Write EV1 candidate cache (evidence-first only, no upload/manifest changes)",
            )
            cmd.add_argument(
                "--write-normalized-cache",
                action="store_true",
                help="Convert EV1 candidate to normalized cache (evidence-first only, no upload)",
            )
        if name == "upload":
            cmd.add_argument("--source", help="Re-normalize from V4 JSON before upload")
            cmd.add_argument("--skip-verify", action="store_true")
        if name == "run-next":
            cmd.add_argument("--upload", action="store_true")
            cmd.add_argument("--source", help="V4 JSON for extract step")

    p_cv4 = sub.add_parser("convert-v4", help="Convert V4 JSON → normalized cache")
    p_cv4.add_argument("--input", required=True)
    p_cv4.add_argument("--output", help="Optional extra output path")
    p_cv4.add_argument("--part", required=True)
    p_cv4.add_argument("--section", required=True)
    p_cv4.add_argument("--upload", action="store_true")

    p_parts = sub.add_parser("run-parts", help="Extract/upload all sections in given parts")
    p_parts.add_argument(
        "--part",
        dest="parts",
        action="append",
        required=True,
        help="Part title (repeatable), e.g. --part '第一篇 绪论'",
    )
    p_parts.add_argument("--upload", action="store_true")
    p_parts.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep going after a section fails",
    )
    p_parts.add_argument(
        "--force-reextract",
        action="store_true",
        help="Rerun LLM even when normalized cache exists",
    )
    p_parts.add_argument("--source", help="V4 JSON for extract step")

    p_backfill = sub.add_parser(
        "backfill-p0",
        help="Re-upload verified sections from cache (repair refs + chunks + causal_chains)",
    )
    p_backfill.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep going after a section upload fails",
    )

    p_ev1_convert = sub.add_parser(
        "ev1-convert-ready",
        help="Convert ready EV1 candidate caches to isolated normalized caches",
    )
    p_ev1_convert.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep going after one candidate conversion fails",
    )

    p_ev1_gate = sub.add_parser(
        "ev1-release-gate",
        help="Validate EV1 isolated normalized caches before production upload",
    )
    p_ev1_gate.add_argument("--section", help="Optional section title filter")
    p_ev1_gate.add_argument("--part", help="Part title for --section filter")

    p_ev1_audit = sub.add_parser(
        "ev1-artifact-audit",
        help="Audit EV1 evidence artifacts for table/list/figure-caption risks",
    )
    p_ev1_audit.add_argument("--section", help="Optional section title filter")
    p_ev1_audit.add_argument("--part", help="Part title for --section filter")

    p_ev1_display = sub.add_parser(
        "ev1-display-contract",
        help="Build frontend-facing EV1 display contracts from normalized caches",
    )
    p_ev1_display.add_argument("--section", help="Optional section title filter")
    p_ev1_display.add_argument("--part", help="Part title for --section filter")
    p_ev1_display.add_argument(
        "--no-merge",
        action="store_true",
        help="Disable adjacent same-heading display merges",
    )
    p_ev1_display.add_argument(
        "--organized-only",
        action="store_true",
        help="Do not append evidence-only fallback nodes from candidate caches",
    )

    p_ev1_batch = sub.add_parser(
        "ev1-run-batch",
        help="Run EV1 candidate extraction over manifest sections, then audit/convert/gate",
    )
    p_ev1_batch.add_argument("--part", help="Optional part title filter")
    p_ev1_batch.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of manifest sections to process",
    )
    p_ev1_batch.add_argument(
        "--force-reextract",
        action="store_true",
        help="Rerun EV1 extraction even when candidate cache exists",
    )
    p_ev1_batch.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue after extraction or quality failures",
    )
    p_ev1_batch.add_argument(
        "--max-rejected-rate",
        type=float,
        default=0.30,
        help="Pause when one section exceeds this rejected-item rate (default: 0.30)",
    )
    p_ev1_batch.add_argument(
        "--skip-post-gates",
        action="store_true",
        help="Only run extraction; skip artifact audit, conversion, and release gate",
    )
    p_ev1_batch.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce per-artifact synthesis logging during long EV1 runs",
    )

    return parser


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    parser = build_parser()
    args = parser.parse_args()
    configure_ingestion(getattr(args, "book_id", "internal-medicine-10"))
    handlers = {
        "status": cmd_status,
        "catalog": cmd_catalog,
        "sync-manifest": cmd_sync_manifest,
        "audit-gaps": cmd_audit_gaps,
        "extract": cmd_extract,
        "upload": cmd_upload,
        "run-next": cmd_run_next,
        "run-parts": cmd_run_parts,
        "convert-v4": cmd_convert_v4,
        "rebuild-cache": cmd_rebuild_cache,
        "backfill-p0": cmd_backfill_p0,
        "ev1-convert-ready": cmd_ev1_convert_ready,
        "ev1-release-gate": cmd_ev1_release_gate,
        "ev1-artifact-audit": cmd_ev1_artifact_audit,
        "ev1-display-contract": cmd_ev1_display_contract,
        "ev1-run-batch": cmd_ev1_run_batch,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
