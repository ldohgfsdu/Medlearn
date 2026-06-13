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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from textbook_identity import INTERNAL_MEDICINE_10, get_textbook_identity
from textbook_pipeline.ingestion_contract import (
    ADAPTER_VERSION,
    KNOWLEDGE_POINTS_DEPRECATED,
    SECTION_STATUSES,
    TERMINAL_SECTION_STATUSES,
)
from textbook_pipeline.knowledge_node_adapter import (
    build_provenance,
    finalize_knowledge_rows,
    is_valid_node_row,
    load_v4_payload,
    v4_payload_to_knowledge_rows,
)
from textbook_pipeline.upload_to_supabase import upsert_knowledge_nodes

MANIFEST_PATH = PROJECT_ROOT / "manifests" / "internal_medicine_ingestion.yaml"
STATE_PATH = PROJECT_ROOT / "state" / "knowledge_ingestion.yaml"
CATALOG_PATH = PROJECT_ROOT / "scripts" / "catalog.internal-medicine.json"
PDF_PATH = PROJECT_ROOT / "textbook" / "内科学（第10版）.pdf"
V3_SCRIPT = SCRIPT_DIR / "pipeline_v3_extract.py"
V3_OUTPUT_DIR = PROJECT_ROOT / "generated" / "pipeline_v3"
GENERATED_ROOT = PROJECT_ROOT / "generated" / "knowledge_nodes"
TEXTBOOK_ID = "internal-medicine-10"
PDF_STEM = PDF_PATH.stem


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


def upload_rows_idempotent(rows: List[Dict[str, Any]], part_title: str, section_title: str) -> Dict[str, Any]:
    expected_ids = {row["id"] for row in rows}
    before_count, before_ids = remote_nodes_for_section(part_title, section_title)
    upsert_knowledge_nodes(rows)

    stale_ids = [node_id for node_id in before_ids if node_id not in expected_ids]
    if stale_ids:
        client = get_supabase_client()
        client.table("knowledge_nodes").delete().in_("id", stale_ids).execute()

    after_count, after_ids = remote_nodes_for_section(part_title, section_title)

    return {
        "before_count": before_count,
        "after_count": after_count,
        "uploaded": len(rows),
        "expected_ids": len(expected_ids),
        "stale_removed": len(stale_ids),
        "idempotent": after_count == len(expected_ids),
        "delta": after_count - before_count,
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


def load_normalized_cache(part_title: str, section_title: str) -> Optional[List[Dict[str, Any]]]:
    cache_path = normalized_cache_path(part_title, section_title)
    if not cache_path.exists():
        return None
    payload = load_json(cache_path)
    return payload.get("nodes") or []


def filter_valid_rows(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    valid = [row for row in rows if is_valid_node_row(row)]
    return valid, len(rows) - len(valid)


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


def normalize_catalog_title(title: str) -> str:
    return re.sub(r"\s+", "", (title or "").strip())


def part_in_catalog_headings(part_title: str, headings: List[str]) -> bool:
    norm_part = normalize_catalog_title(part_title)
    return part_title in headings or any(
        normalize_catalog_title(heading) == norm_part for heading in headings
    )


def resolve_catalog_section_range(part_title: str, section_title: str) -> Tuple[int, int]:
    catalog = ensure_v3_catalog()
    units = catalog.get("units", [])
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


def prepare_ollama_gpu() -> None:
    """Ensure Ollama is reachable and warm up the extraction model."""
    model = os.environ.get("OLLAMA_MODEL", "medlearn-qwen3:8b")
    keep_alive = os.environ.get("OLLAMA_KEEP_ALIVE", "10m")

    if not _ollama_api_ready():
        print("[ingest] Ollama API unreachable; clearing stale llama-server if any")
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/IM", "llama-server.exe"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
        if not _ollama_api_ready(timeout=15.0):
            print("[ingest] Ollama still unavailable — extract will likely fail")
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
        print(f"[ingest] Ollama warmed up ({model})")
    except Exception as exc:
        print(f"[ingest] Ollama warmup skipped: {exc}")


def v3_extraction_cache_path(section_start: int, section_limit: int) -> Path:
    return V3_OUTPUT_DIR / (
        f"{PDF_STEM}{v3_scope_tag(section_start, section_limit)}.extraction.json"
    )


def rebuild_v3_nodes(part_title: str, section_title: str) -> Path:
    section_start, section_limit = resolve_catalog_section_range(part_title, section_title)
    cache_path = v3_extraction_cache_path(section_start, section_limit)
    if not cache_path.exists():
        raise FileNotFoundError(f"No V3 extraction cache: {cache_path}")

    cmd = [
        sys.executable,
        str(V3_SCRIPT),
        str(PDF_PATH),
        "--output-dir",
        str(V3_OUTPUT_DIR),
        "--section-start",
        str(section_start),
        "--section-limit",
        str(section_limit),
        "--rebuild-only",
    ]
    print(f"[ingest] Rebuilding nodes from cache: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
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
        raise RuntimeError(f"V3 rebuild failed (exit {result.returncode})")

    nodes_path = v3_nodes_path(section_start, section_limit)
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


def run_v3_extract(part_title: str, section_title: str) -> Path:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    prepare_ollama_gpu()
    section_start, section_limit = resolve_catalog_section_range(part_title, section_title)
    nodes_path = v3_nodes_path(section_start, section_limit)
    cache_path = v3_extraction_cache_path(section_start, section_limit)

    if cache_path.exists() and (
        not nodes_path.exists()
        or len((load_json(nodes_path).get("nodes") or [])) == 0
    ):
        cache = load_json(cache_path)
        raw_nodes = sum(
            len(result.get("nodes") or [])
            for result in (cache.get("chunks") or {}).values()
        )
        if raw_nodes:
            print(
                f"[ingest] Found LLM cache with {raw_nodes} raw nodes; rebuilding outputs"
            )
            return rebuild_v3_nodes(part_title, section_title)

    cmd = [
        sys.executable,
        str(V3_SCRIPT),
        str(PDF_PATH),
        "--output-dir",
        str(V3_OUTPUT_DIR),
        "--section-start",
        str(section_start),
        "--section-limit",
        str(section_limit),
        "--pymupdf-only",
        "--max-chars",
        "2800",
    ]
    print(
        f"[ingest] Catalog range: units {section_start}..{section_start + section_limit - 1} "
        f"({section_limit} unit(s))"
    )
    print(f"[ingest] Running V3 extract: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
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
        raise RuntimeError(f"V3 extract failed (exit {result.returncode})")

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
            return rebuild_v3_nodes(part_title, section_title)
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
    rows, dropped = filter_valid_rows(raw_rows)
    if dropped:
        print(f"[ingest] Filtered {dropped} invalid nodes")
    return finalize_knowledge_rows(rows, identity, provenance=provenance)


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
    prod = state.get("production_status") or {}

    print("=== Knowledge Ingestion Status ===")
    print()
    print("--- Layered production status ---")
    print(f"Architecture:              {prod.get('architecture', 'accepted')}")
    print(f"Contract:                  {prod.get('contract', 'v4_accepted')}")
    print(f"Upload pipeline:           {prod.get('upload_pipeline', 'smoke-tested')}")
    print(f"Real extraction pipeline:  {prod.get('real_extraction_pipeline', 'pending')}")
    print(f"Production ingestion:      {prod.get('production_ingestion', 'not_accepted')}")
    print(f"App integration:           {prod.get('app_integration', 'db_query_ready_ui_pending')}")
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
    except Exception as exc:
        print(f"Remote nodes: unavailable ({exc})")

    gate = state.get("real_llm_gate") or {}
    checklist = gate.get("checklist") or {}
    if checklist:
        print("\n--- Real LLM gate checklist (section 1) ---")
        for key, value in checklist.items():
            mark = "ok" if value is True else ("fail" if value is False else str(value))
            print(f"  {key}: {mark}")

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


def cmd_extract(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    state = load_state()
    target = parse_section_args(args, manifest)
    part_title = target["part_title"]
    section_title = target["section_title"]

    set_section_status(manifest, part_title, section_title, "extracting")
    state["current_section"] = f"{part_title}/{section_title}"
    state["last_error"] = None
    save_state(state)

    try:
        if args.source:
            source_path = Path(args.source)
            if not source_path.is_absolute():
                source_path = PROJECT_ROOT / source_path
            rows = normalize_v4_source(part_title, section_title, source_path)
            pipeline_version = "v4"
            source_for_cache = source_path
        else:
            nodes_path = run_v3_extract(part_title, section_title)
            rows = normalize_v3_nodes(part_title, section_title, nodes_path)
            pipeline_version = "v3"
            source_for_cache = nodes_path

        cache_path = write_normalized_cache(
            part_title,
            section_title,
            rows,
            source_path=source_for_cache,
            pipeline_version=pipeline_version,
        )
        if not rows:
            raise RuntimeError(summarize_v3_failure(part_title, section_title))
        set_section_status(manifest, part_title, section_title, "extracted", node_count=len(rows))
        state["current_section"] = f"{part_title}/{section_title}"
        save_state(state)
        print(f"[extract] {part_title} / {section_title}: {len(rows)} nodes → {cache_path}")
        return 0
    except Exception as exc:
        set_section_status(manifest, part_title, section_title, "failed", error=str(exc))
        state["last_error"] = str(exc)
        save_state(state)
        print(f"[extract] FAILED {part_title} / {section_title}: {exc}", file=sys.stderr)
        return 1


def cmd_upload(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    state = load_state()
    target = parse_section_args(args, manifest)
    part_title = target["part_title"]
    section_title = target["section_title"]

    rows = load_normalized_cache(part_title, section_title)
    if not rows and args.source:
        source_path = Path(args.source)
        if not source_path.is_absolute():
            source_path = PROJECT_ROOT / source_path
        rows = normalize_v4_source(part_title, section_title, source_path)
        write_normalized_cache(part_title, section_title, rows, source_path=source_path)

    if not rows:
        print(f"No normalized cache for {part_title} / {section_title}. Run extract first.")
        return 1

    set_section_status(manifest, part_title, section_title, "uploading")
    state["current_section"] = f"{part_title}/{section_title}"
    save_state(state)

    try:
        result = upload_rows_idempotent(rows, part_title, section_title)
        print(
            f"[upload] remote {result['before_count']}→{result['after_count']} "
            f"(delta={result['delta']}, expected={result['expected_ids']})"
        )
        if not result["idempotent"]:
            raise RuntimeError(
                f"Idempotency check failed: remote={result['after_count']} "
                f"expected={result['expected_ids']}"
            )

        set_section_status(
            manifest,
            part_title,
            section_title,
            "uploaded",
            node_count=len(rows),
            remote_count=result["after_count"],
        )

        _, remote_ids = remote_nodes_for_section(part_title, section_title)
        expected_ids = {row["id"] for row in rows}
        missing = expected_ids - set(remote_ids)
        if missing and not args.skip_verify:
            raise RuntimeError(f"Verify failed: {len(missing)} expected IDs missing remotely")

        set_section_status(
            manifest,
            part_title,
            section_title,
            "verified",
            node_count=len(rows),
            remote_count=result["after_count"],
        )
        state["last_upload_count"] = len(rows)
        state["last_remote_count"] = result["after_count"]
        state["last_completed_section"] = f"{part_title}/{section_title}"
        state["last_error"] = None
        save_state(state)
        print(f"[upload] verified: {part_title} / {section_title} ({result['after_count']} remote nodes)")
        return 0
    except Exception as exc:
        set_section_status(manifest, part_title, section_title, "failed", error=str(exc))
        state["last_error"] = str(exc)
        save_state(state)
        print(f"[upload] FAILED {part_title} / {section_title}: {exc}", file=sys.stderr)
        return 1


def cmd_run_parts(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    target_parts = set(args.parts or [])
    if not target_parts:
        raise ValueError("run-parts requires at least one --part")

    processed = 0
    failed = 0
    for item in iter_manifest_sections(manifest):
        if item["part_title"] not in target_parts:
            continue
        part_title = item["part_title"]
        section_title = item["section_title"]
        if is_section_done(item["section_ref"]):
            print(f"[run-parts] skip verified: {part_title} / {section_title}")
            continue

        print(f"[run-parts] === {part_title} / {section_title} ===")
        args.part = part_title
        args.section = section_title
        args.source = None

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified knowledge ingestion (production)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show manifest + remote status")
    sub.add_parser("catalog", help="Ensure cache directories and PDF catalog")

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
    p_parts.add_argument("--source", help="V4 JSON for extract step")

    return parser


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "status": cmd_status,
        "catalog": cmd_catalog,
        "extract": cmd_extract,
        "upload": cmd_upload,
        "run-next": cmd_run_next,
        "run-parts": cmd_run_parts,
        "convert-v4": cmd_convert_v4,
        "rebuild-cache": cmd_rebuild_cache,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())