#!/usr/bin/env python3
"""P0 smoke checks for PDF knowledge pipeline reference integrity."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from textbook_pipeline.knowledge_node_adapter import needs_reference_repair

GENERATED_ROOT = PROJECT_ROOT / "generated" / "knowledge_nodes"
MANIFEST_PATH = PROJECT_ROOT / "manifests" / "internal_medicine_ingestion.yaml"
STATE_PATH = PROJECT_ROOT / "state" / "knowledge_ingestion.yaml"
TEXTBOOK_ID = "internal-medicine-10"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def iter_verified_sections(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for part in manifest.get("parts", []):
        part_title = str(part.get("title") or "").strip()
        for section in part.get("sections", []):
            if str(section.get("status") or "") == "verified":
                sections.append((part_title, str(section.get("title") or "").strip()))
    return sections


def check_local_normalized_caches() -> dict[str, Any]:
    manifest = load_yaml(MANIFEST_PATH)
    verified = iter_verified_sections(manifest)
    cache_dir = GENERATED_ROOT / TEXTBOOK_ID

    issues: list[str] = []
    checked = 0
    with_v3_refs = 0

    for part_title, section_title in verified:
        key = (
            f"{part_title.replace(' ', '_')}"
            f"__{section_title.replace(' ', '_')}"
        )
        # slugify match ingest_knowledge slugify
        import re

        def slugify(text: str) -> str:
            cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", (text or "").strip())
            return cleaned.strip("_") or "section"

        cache_path = cache_dir / f"{slugify(part_title)}__{slugify(section_title)}.normalized.json"
        if not cache_path.exists():
            issues.append(f"missing normalized cache: {part_title} / {section_title}")
            continue
        payload = load_json(cache_path)
        rows = payload.get("nodes") or []
        checked += 1
        if needs_reference_repair(rows):
            with_v3_refs += 1
            issues.append(f"v3 refs in cache (needs re-upload): {part_title} / {section_title}")

    return {
        "verified_sections": len(verified),
        "checked_caches": checked,
        "caches_with_v3_refs": with_v3_refs,
        "issues": issues,
    }


def check_state_manifest_consistency() -> dict[str, Any]:
    manifest = load_yaml(MANIFEST_PATH)
    state = load_yaml(STATE_PATH)
    verified = iter_verified_sections(manifest)
    issues: list[str] = []

    extraction = state.get("extraction") or {}
    production = state.get("production_ingestion") or {}

    if extraction.get("verified_section_count") != len(verified):
        issues.append(
            f"state extraction.verified_section_count={extraction.get('verified_section_count')} "
            f"!= manifest verified={len(verified)}"
        )
    if production.get("status") == "not_accepted":
        issues.append("production_ingestion.status still not_accepted")

    return {
        "manifest_verified": len(verified),
        "state_verified": extraction.get("verified_section_count"),
        "production_status": production.get("status"),
        "issues": issues,
    }


def check_remote_db() -> dict[str, Any]:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("EXPO_PUBLIC_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
    )
    if not url or not key:
        return {"skipped": True, "reason": "missing SUPABASE credentials"}

    try:
        from supabase import create_client

        client = create_client(url, key)
        issues: list[str] = []

        nodes: list[dict[str, Any]] = []
        page_size = 1000
        offset = 0
        while True:
            nodes_resp = (
                client.table("knowledge_nodes")
                .select("id, related_nodes, causal_links")
                .eq("book_id", TEXTBOOK_ID)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = nodes_resp.data or []
            nodes.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        node_ids = {row["id"] for row in nodes}

        v3_in_nodes = [
            row["id"] for row in nodes if str(row.get("id", "")).startswith("v3-")
        ]
        if v3_in_nodes:
            issues.append(f"knowledge_nodes contains {len(v3_in_nodes)} v3-* primary ids")

        orphan_related = 0
        orphan_targets = 0
        for row in nodes:
            for ref in row.get("related_nodes") or []:
                ref_s = str(ref)
                if ref_s.startswith("v3-"):
                    orphan_related += 1
                elif ref_s not in node_ids:
                    orphan_related += 1
            for link in row.get("causal_links") or []:
                if not isinstance(link, dict):
                    continue
                target_id = str(link.get("target_id") or "")
                if target_id.startswith("v3-") or (
                    target_id and target_id not in node_ids
                ):
                    orphan_targets += 1

        chunks_resp = (
            client.table("document_chunks")
            .select("id", count="exact")
            .eq("document_name", TEXTBOOK_ID)
            .execute()
        )
        chunk_count = chunks_resp.count or 0
        if chunk_count == 0:
            issues.append("document_chunks is empty for internal-medicine-10")

        chains_resp = (
            client.table("causal_chains")
            .select("id", count="exact")
            .eq("source", "pipeline_v3")
            .execute()
        )
        chain_count = chains_resp.count or 0
        if chain_count == 0:
            issues.append("causal_chains has no pipeline_v3 rows")

        manifest = load_yaml(MANIFEST_PATH)
        verified = iter_verified_sections(manifest)
        sections_without_chunks = 0
        for part_title, section_title in verified[:5]:
            probe = (
                client.table("knowledge_nodes")
                .select("id")
                .eq("book_id", TEXTBOOK_ID)
                .eq("chapter", part_title)
                .eq("sub_chapter", section_title)
                .limit(1)
                .execute()
            )
            if not probe.data:
                continue
            node_id = probe.data[0]["id"]
            chunk_probe = (
                client.table("document_chunks")
                .select("id", count="exact")
                .eq("related_node_id", node_id)
                .execute()
            )
            if (chunk_probe.count or 0) == 0:
                sections_without_chunks += 1

        if sections_without_chunks:
            issues.append(
                f"sampled verified sections missing chunks: {sections_without_chunks}/5"
            )
        if orphan_related:
            issues.append(f"orphan related_nodes references: {orphan_related}")
        if orphan_targets:
            issues.append(f"orphan causal_links.target_id references: {orphan_targets}")

        return {
            "skipped": False,
            "node_count": len(nodes),
            "v3_primary_ids": len(v3_in_nodes),
            "orphan_related_refs": orphan_related,
            "orphan_causal_targets": orphan_targets,
            "document_chunks": chunk_count,
            "causal_chains_v3": chain_count,
            "issues": issues,
        }
    except Exception as exc:
        return {
            "skipped": False,
            "issues": [f"remote DB verification failed: {type(exc).__name__}: {exc}"],
        }


def build_report(*, include_remote: bool = False) -> dict[str, Any]:
    remote_db: dict[str, Any]
    if include_remote:
        remote_db = check_remote_db()
    else:
        remote_db = {
            "skipped": True,
            "reason": "remote verification not requested; pass --remote to enable",
        }

    report: dict[str, Any] = {
        "local_caches": check_local_normalized_caches(),
        "state_manifest": check_state_manifest_consistency(),
        "remote_db": remote_db,
    }
    all_issues: list[str] = []
    for section in report.values():
        if isinstance(section, dict):
            all_issues.extend(section.get("issues") or [])

    report["passed"] = len(all_issues) == 0
    report["issue_count"] = len(all_issues)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="P0 smoke verification")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Load .env and verify Supabase state (network access required)",
    )
    args = parser.parse_args()

    if args.remote:
        try:
            from dotenv import load_dotenv

            load_dotenv(PROJECT_ROOT / ".env")
        except ImportError:
            pass

    report = build_report(include_remote=args.remote)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=== P0 Smoke Verification ===")
        for name, section in report.items():
            if not isinstance(section, dict):
                continue
            print(f"\n[{name}]")
            for key, value in section.items():
                if key != "issues":
                    print(f"  {key}: {value}")
            for issue in section.get("issues") or []:
                print(f"  ISSUE: {issue}")
        print(
            f"\nResult: {'PASS' if report['passed'] else 'FAIL'} "
            f"({report['issue_count']} issues)"
        )

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
