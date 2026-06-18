#!/usr/bin/env python3
"""Full pipeline closure verification (P0 + P1 + P2 checks)."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from textbook_pipeline.ingestion_contract import (
    DEFAULT_EMBED_MODEL,
    EMBED_DIMENSION,
    PRODUCTION_PDF_PARSER,
    resolve_pdf_parser_mode,
)
from verify_p0_smoke import (
    check_local_normalized_caches,
    check_remote_db,
    check_state_manifest_consistency,
)

CONTRACT_PATH = SCRIPT_DIR / "textbook_pipeline" / "ingestion_contract.py"
V3_RUNNER_PATH = SCRIPT_DIR / "textbook_pipeline" / "v3_runner.py"
PIPELINE_V3_PATH = SCRIPT_DIR / "pipeline_v3_extract.py"
INGEST_PATH = SCRIPT_DIR / "ingest_knowledge.py"
GUIDE_PATH = PROJECT_ROOT / "docs" / "PDF_EXTRACTION_GUIDE.md"
INDEX_PATH = PROJECT_ROOT / "docs" / "PIPELINE_INDEX.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def check_parser_consistency() -> dict[str, Any]:
    issues: list[str] = []
    contract = _read(CONTRACT_PATH)
    v3_runner = _read(V3_RUNNER_PATH)
    pipeline = _read(PIPELINE_V3_PATH)

    if PRODUCTION_PDF_PARSER not in contract:
        issues.append("ingestion_contract missing PRODUCTION_PDF_PARSER")
    if "resolve_pdf_parser_mode" not in v3_runner:
        issues.append("v3_runner does not use resolve_pdf_parser_mode")
    if "--use-docling" not in pipeline:
        issues.append("pipeline_v3_extract missing --use-docling flag")
    if resolve_pdf_parser_mode() != "auto":
        issues.append("default parser is not auto")
    return {
        "default_parser": PRODUCTION_PDF_PARSER,
        "adaptive_default": resolve_pdf_parser_mode() == "auto",
        "issues": issues,
    }


def check_book_id_cli() -> dict[str, Any]:
    issues: list[str] = []
    ingest = _read(INGEST_PATH)
    if "--book-id" not in ingest or "configure_ingestion" not in ingest:
        issues.append("ingest_knowledge missing --book-id or configure_ingestion")
    try:
        result = subprocess.run(
            [sys.executable, str(INGEST_PATH), "--book-id", "internal-medicine-10", "status"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            issues.append(f"status --book-id failed: {result.stderr[:200]}")
        elif "internal-medicine-10" not in result.stdout:
            issues.append("status output missing book id")
    except Exception as exc:
        issues.append(f"status --book-id error: {exc}")
    return {"issues": issues}


def check_embedding_contract() -> dict[str, Any]:
    issues: list[str] = []
    upload = _read(SCRIPT_DIR / "textbook_pipeline" / "upload_to_supabase.py")
    if DEFAULT_EMBED_MODEL != "bge-m3":
        issues.append(f"unexpected DEFAULT_EMBED_MODEL: {DEFAULT_EMBED_MODEL}")
    if "_embed_rows_ollama" not in upload:
        issues.append("upload_to_supabase missing Ollama embed path")
    if EMBED_DIMENSION != 1024:
        issues.append(f"unexpected EMBED_DIMENSION: {EMBED_DIMENSION}")
    return {
        "default_embed_model": DEFAULT_EMBED_MODEL,
        "embed_dimension": EMBED_DIMENSION,
        "issues": issues,
    }


def check_docs_and_deprecation() -> dict[str, Any]:
    issues: list[str] = []
    guide = _read(GUIDE_PATH)
    index = _read(INDEX_PATH)
    for cmd in (
        "ingest_knowledge.py --book-id",
        "verify_pipeline_closure.py",
        "backfill-p0",
    ):
        if cmd not in guide and cmd not in index:
            issues.append(f"docs missing command reference: {cmd}")
    for path, marker in (
        (SCRIPT_DIR / "ingest_final.py", "DEPRECATED"),
        (SCRIPT_DIR / "run_optimized_pipeline.py", "EXPERIMENTAL"),
        (SCRIPT_DIR / "textbook_parser.py", "DEMO ONLY"),
    ):
        if path.exists():
            if marker not in _read(path):
                issues.append(f"{path.name} missing {marker} header")
        elif f"`scripts/{path.name}` | {marker}" not in index:
            issues.append(f"{path.name} missing and not marked {marker} in pipeline index")
    if "H:/Ollama" in _read(SCRIPT_DIR / "Modelfile.medlearn-qwen3"):
        issues.append("Modelfile still has machine-specific H:/ path")
    return {"issues": issues}


def check_coverage_gate() -> dict[str, Any]:
    issues: list[str] = []
    spec = importlib.util.spec_from_file_location(
        "extraction_quality",
        SCRIPT_DIR / "textbook_pipeline" / "extraction_quality.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    low = module.assess_chunk_coverage(10, 1)
    ok = module.assess_chunk_coverage(10, 8)
    tiny = module.assess_chunk_coverage(2, 2)
    if low.get("passed"):
        issues.append("coverage gate should reject 1/10 chunks")
    if not ok.get("passed"):
        issues.append("coverage gate should accept 8/10 chunks")
    if not tiny.get("passed"):
        issues.append("coverage gate should accept 2/2 tiny sections")
    return {"low_passed": low.get("passed"), "ok_passed": ok.get("passed"), "issues": issues}


def check_catalog_preflight() -> dict[str, Any]:
    issues: list[str] = []
    catalog_path = PROJECT_ROOT / "generated" / "pipeline_v3" / "内科学（第10版）.catalog.json"
    if not catalog_path.exists():
        issues.append("PDF catalog missing — run: ingest_knowledge.py catalog")
    else:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not payload.get("units"):
            issues.append("PDF catalog has no units (missing bookmarks?)")
    return {"catalog_exists": catalog_path.exists(), "issues": issues}


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Pipeline closure verification")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "p0_smoke": {
            "local_caches": check_local_normalized_caches(),
            "state_manifest": check_state_manifest_consistency(),
            "remote_db": check_remote_db(),
        },
        "p1_parser": check_parser_consistency(),
        "p1_book_id": check_book_id_cli(),
        "p1_embedding": check_embedding_contract(),
        "p1_docs": check_docs_and_deprecation(),
        "p2_coverage": check_coverage_gate(),
        "p2_catalog": check_catalog_preflight(),
    }

    all_issues: list[str] = []
    for section in report.values():
        if isinstance(section, dict):
            if "issues" in section:
                all_issues.extend(section.get("issues") or [])
            for nested in section.values():
                if isinstance(nested, dict) and nested.get("issues"):
                    all_issues.extend(nested["issues"])

    report["passed"] = len(all_issues) == 0
    report["issue_count"] = len(all_issues)
    report["issues"] = all_issues

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=== Pipeline Closure Verification ===")
        for name, section in report.items():
            if name in {"passed", "issue_count", "issues"}:
                continue
            print(f"\n[{name}]")
            if not isinstance(section, dict):
                continue
            for key, value in section.items():
                if key == "issues":
                    continue
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        if sub_key != "issues":
                            print(f"    {sub_key}: {sub_value}")
                    for issue in value.get("issues") or []:
                        print(f"    ISSUE: {issue}")
                else:
                    print(f"  {key}: {value}")
            for issue in section.get("issues") or []:
                print(f"  ISSUE: {issue}")
        if all_issues:
            print("\n[all_issues]")
            for issue in all_issues:
                print(f"  ISSUE: {issue}")
        print(f"\nResult: {'PASS' if report['passed'] else 'FAIL'} ({len(all_issues)} issues)")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
