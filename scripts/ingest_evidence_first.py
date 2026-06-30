#!/usr/bin/env python3
"""EV1 Evidence-First Pipeline — CLI entry point.

Phase 0+1 only: deterministic evidence artifact extraction.
No LLM calls. No knowledge_nodes. No Supabase upload.

Usage:
  python scripts/ingest_evidence_first.py --book-id internal-medicine-10 --dry-run
  python scripts/ingest_evidence_first.py --part "第四篇 消化系统疾病" --section "第四章 胃炎"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from textbook_identity import resolve_ingestion_context
from textbook_pipeline.evidence_artifact import EvidenceArtifact
from textbook_pipeline.evidence_extractor import (
    extract_section_evidence,
    load_evidence_cache,
    write_evidence_cache,
)


EVIDENCE_DIR = PROJECT_ROOT / "generated" / "evidence"


def section_cache_path(
    textbook_id: str,
    part_title: str,
    section_title: str,
) -> Path:
    """Path to evidence cache for a section."""
    safe_part = part_title.replace("/", "_").replace(" ", "_")
    safe_section = section_title.replace("/", "_").replace(" ", "_")
    return EVIDENCE_DIR / textbook_id / f"{safe_part}__{safe_section}.evidence.json"


def iter_manifest_sections(manifest: dict):
    """Yield (part_title, section_title, section_ref) from manifest."""
    for part in manifest.get("parts", []):
        part_title = str(part.get("title") or "").strip()
        for section in part.get("sections", []):
            section_title = str(section.get("title") or "").strip()
            yield part_title, section_title, section


def load_manifest(ctx) -> dict:
    """Load manifest YAML."""
    import yaml

    if not ctx.manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {ctx.manifest_path}")
    with open(ctx.manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_catalog(ctx) -> list[dict]:
    """Load PDF catalog JSON."""
    catalog_path = ctx.v3_output_dir / f"{ctx.pdf_stem}.catalog.json"
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog not found: {catalog_path}")
    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("units", [])


def resolve_section_page_range(
    catalog_units: list[dict],
    part_title: str,
    section_title: str,
) -> tuple[int, int]:
    """Find page range for a section from catalog units.

    Handles both:
    - Direct section match (e.g. "第一节 | 急性胃炎")
    - Chapter-level match spanning multiple sections (e.g. "第四章 胃炎" → 400-404)
    """
    import re

    def normalize(s: str) -> str:
        return re.sub(r"[\s\-－—]", "", s.strip())

    norm_section = normalize(section_title)
    norm_part = normalize(part_title)

    # Try exact match on section title
    for unit in catalog_units:
        unit_title = normalize(str(unit.get("title", "")))
        if unit_title == norm_section:
            return int(unit["page_start"]), int(unit["page_end"])

    # Chapter-level match: find all units whose headings contain the section title
    # This handles "第四章 胃炎" spanning multiple sub-sections
    chapter_re = re.compile(r"第[一二三四五六七八九十百零\d]+章")
    if chapter_re.search(section_title):
        matching_units = []
        for unit in catalog_units:
            headings = unit.get("headings") or []
            if any(section_title in h for h in headings):
                matching_units.append(unit)
        if matching_units:
            page_start = min(int(u["page_start"]) for u in matching_units)
            page_end = max(int(u["page_end"]) for u in matching_units)
            return page_start, page_end

    # Fallback: try part title match for "绪论" or part-level sections
    for unit in catalog_units:
        unit_title = normalize(str(unit.get("title", "")))
        if unit_title == norm_part:
            return int(unit["page_start"]), int(unit["page_end"])

    raise RuntimeError(
        f"Section not found in catalog: {part_title} / {section_title}"
    )


def print_artifact_summary(artifacts: list[EvidenceArtifact]) -> None:
    """Print a summary table of extracted artifacts."""
    from collections import Counter

    type_counts = Counter(a.artifact_type for a in artifacts)
    page_range = (
        min(a.page_start for a in artifacts),
        max(a.page_end for a in artifacts),
    ) if artifacts else (0, 0)

    print(f"\n  Total artifacts: {len(artifacts)}")
    print(f"  Page range: {page_range[0]}-{page_range[1]}")
    print(f"  Types: {dict(type_counts)}")

    # Show first few artifacts
    print("\n  First 5 artifacts:")
    for art in artifacts[:5]:
        preview = art.raw_text[:80].replace("\n", " ")
        print(f"    [{art.source_order:3d}] p{art.page_start} "
              f"{art.artifact_type:<12} {art.source_heading[:20]:<20} "
              f"{preview}...")

    if len(artifacts) > 5:
        print(f"    ... and {len(artifacts) - 5} more")


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract evidence artifacts for a section."""
    ctx = resolve_ingestion_context(args.book_id, PROJECT_ROOT)
    manifest = load_manifest(ctx)

    # Find target section
    target_part = args.part
    target_section = args.section

    if not target_part or not target_section:
        print("Error: --part and --section are required")
        return 1

    # Resolve page range from catalog
    catalog_units = load_catalog(ctx)
    try:
        page_start, page_end = resolve_section_page_range(
            catalog_units, target_part, target_section
        )
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1

    print(f"Section: {target_part} / {target_section}")
    print(f"Pages: {page_start}-{page_end}")
    print(f"PDF: {ctx.pdf_path}")

    # Check cache
    cache_path = section_cache_path(ctx.book_id, target_part, target_section)
    if cache_path.exists() and not getattr(args, 'force', False):
        print(f"Cache exists: {cache_path}")
        artifacts = load_evidence_cache(cache_path)
        print_artifact_summary(artifacts)
        return 0

    # Extract
    print("\nExtracting evidence artifacts...")
    start = time.time()

    artifacts = extract_section_evidence(
        pdf_path=ctx.pdf_path,
        textbook_id=ctx.book_id,
        book_id=ctx.book_id,
        part_title=target_part,
        section_title=target_section,
        page_start=page_start,
        page_end=page_end,
    )

    elapsed = time.time() - start
    print(f"Extraction completed in {elapsed:.1f}s")

    # Print summary
    print_artifact_summary(artifacts)

    # Write cache (unless --dry-run)
    if not args.dry_run:
        write_evidence_cache(artifacts, cache_path)
        print(f"\nCache written: {cache_path}")
    else:
        print("\n[dry-run] Cache not written")

    # Verification
    print("\n--- Verification ---")
    issues = []
    for art in artifacts:
        if not art.page_start or art.page_start < page_start:
            issues.append(f"  Artifact {art.id}: page_start={art.page_start} < section start {page_start}")
        if art.page_end > page_end:
            issues.append(f"  Artifact {art.id}: page_end={art.page_end} > section end {page_end}")
        if not art.raw_text.strip():
            issues.append(f"  Artifact {art.id}: empty raw_text")
        if art.artifact_type not in {"text_block", "table", "figure", "caption"}:
            issues.append(f"  Artifact {art.id}: invalid type {art.artifact_type}")

    if issues:
        print(f"  Issues found: {len(issues)}")
        for issue in issues[:10]:
            print(issue)
    else:
        print("  All checks passed [OK]")

    # ID stability check
    if not args.dry_run and cache_path.exists():
        artifacts2 = load_evidence_cache(cache_path)
        ids1 = [a.id for a in artifacts]
        ids2 = [a.id for a in artifacts2]
        if ids1 == ids2:
            print("  ID stability: [OK] (re-load produces same IDs)")
        else:
            print("  ID stability: [FAIL] (IDs changed on re-load!)")

    return 0


def cmd_synthesize(args: argparse.Namespace) -> int:
    """Synthesize items from evidence artifacts (Phase 4: full chapter candidate cache)."""
    from textbook_pipeline.evidence_synthesis import (
        SynthesizedItem,
        synthesize_artifacts,
        write_synthesis_cache,
    )
    from textbook_pipeline.evidence_verifier import verify_items

    ctx = resolve_ingestion_context(args.book_id, PROJECT_ROOT)

    # Load evidence cache
    cache_path = section_cache_path(ctx.book_id, args.part, args.section)
    if not cache_path.exists():
        print(f"Error: Evidence cache not found: {cache_path}")
        print("Run 'extract' first.")
        return 1

    artifacts = load_evidence_cache(cache_path)
    print(f"Loaded {len(artifacts)} artifacts from cache")

    # Filter to text_block only (skip tables for now)
    text_artifacts = [a for a in artifacts if a.artifact_type == "text_block"]
    table_artifacts = [a for a in artifacts if a.artifact_type == "table"]
    print(f"Text block: {len(text_artifacts)}, Table: {len(table_artifacts)}")

    # Determine max_artifacts
    max_artifacts = getattr(args, 'max_artifacts', 0)
    if max_artifacts > 0:
        selected = text_artifacts[:max_artifacts]
        print(f"Selected for synthesis: {len(selected)} (limited)")
    else:
        selected = text_artifacts
        print(f"Selected for synthesis: {len(selected)} (full chapter)")
    print()

    # Synthesize
    print("--- Synthesis ---")
    items, metrics = synthesize_artifacts(
        selected,
        model=getattr(args, 'model', 'medlearn-qwen3:8b'),
    )

    print(f"\nSynthesized {len(items)} items from {len(selected)} artifacts")

    # Verify
    print("\n--- Verification ---")
    page_start = min(a.page_start for a in artifacts) if artifacts else 0
    page_end = max(a.page_end for a in artifacts) if artifacts else 9999
    results, counts = verify_items(
        items,
        artifacts,
        section_page_start=page_start,
        section_page_end=page_end,
    )

    print(f"  Pass:          {counts['pass']}")
    print(f"  Needs review:  {counts['needs_review']}")
    print(f"  Rejected:      {counts['rejected']}")

    # Coverage report
    print("\n--- Coverage Report ---")
    artifact_ids_with_items = {item.artifact_id for item in items}
    artifact_ids_all = {a.id for a in selected}
    covered = len(artifact_ids_with_items)
    uncovered = len(artifact_ids_all) - covered
    print(f"  Artifacts with items: {covered}/{len(selected)} ({covered/len(selected)*100:.1f}%)")
    print(f"  Artifacts without items: {uncovered}/{len(selected)} ({uncovered/len(selected)*100:.1f}%)")
    print(f"  Table artifacts (not synthesized): {len(table_artifacts)}")

    # Needs review breakdown
    needs_review_items = [item for item in items if item.verification_state == "needs_review"]
    if needs_review_items:
        print(f"\n--- Needs Review Breakdown ({len(needs_review_items)} items) ---")
        reasons: dict[str, int] = {}
        for item in needs_review_items:
            for note in item.verification_notes:
                reason = note.split(":")[0] if ":" in note else note
                reasons[reason] = reasons.get(reason, 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")

    # Write candidate cache (unless dry-run)
    if not getattr(args, 'dry_run', False):
        # Write synthesis cache
        synth_path = cache_path.with_suffix('.synthesis.json')
        write_synthesis_cache(items, metrics, synth_path)
        print(f"\nSynthesis cache: {synth_path}")

        # Write candidate cache
        candidate_dir = PROJECT_ROOT / "generated" / "evidence_candidates" / args.book_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        safe_part = args.part.replace("/", "_").replace(" ", "_")
        safe_section = args.section.replace("/", "_").replace(" ", "_")
        candidate_path = candidate_dir / f"{safe_part}__{safe_section}.candidate.json"

        candidate_payload = {
            "version": "ev1-candidate-0.1.0",
            "book_id": args.book_id,
            "part_title": args.part,
            "section_title": args.section,
            "page_start": page_start,
            "page_end": page_end,
            "generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "artifacts": {
                "total": len(artifacts),
                "text_block": len(text_artifacts),
                "table": len(table_artifacts),
            },
            "items": {
                "total": len(items),
                "pass": counts["pass"],
                "needs_review": counts["needs_review"],
                "rejected": counts["rejected"],
            },
            "coverage": {
                "artifacts_with_items": covered,
                "artifacts_without_items": uncovered,
                "coverage_rate": covered / len(selected) if selected else 0,
            },
            "candidate_items": [item.to_dict() for item in items],
        }

        with open(candidate_path, "w", encoding="utf-8") as f:
            import json
            json.dump(candidate_payload, f, ensure_ascii=False, indent=2)
        print(f"Candidate cache: {candidate_path}")
    else:
        print("\n[dry-run] Caches not written")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List available sections in manifest."""
    ctx = resolve_ingestion_context(args.book_id, PROJECT_ROOT)
    manifest = load_manifest(ctx)

    print(f"Textbook: {args.book_id}")
    print(f"Manifest: {ctx.manifest_path}\n")

    for part_title, section_title, section_ref in iter_manifest_sections(manifest):
        status = section_ref.get("status", "unknown")
        print(f"  [{status:>12}] {part_title} / {section_title}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EV1 Evidence-First Pipeline (Phase 0+1)"
    )
    parser.add_argument(
        "--book-id",
        default="internal-medicine-10",
        help="Textbook canonical id",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # extract
    p_extract = sub.add_parser("extract", help="Extract evidence artifacts for a section")
    p_extract.add_argument("--part", required=True, help="Part title")
    p_extract.add_argument("--section", required=True, help="Section title")
    p_extract.add_argument("--dry-run", action="store_true", help="Don't write cache")
    p_extract.add_argument("--force", action="store_true", help="Re-extract even if cache exists")

    # synthesize
    p_synth = sub.add_parser("synthesize", help="Synthesize items from evidence artifacts")
    p_synth.add_argument("--part", required=True, help="Part title")
    p_synth.add_argument("--section", required=True, help="Section title")
    p_synth.add_argument("--max-artifacts", type=int, default=10, help="Max artifacts to process")
    p_synth.add_argument("--model", default="medlearn-qwen3:8b", help="LLM model")
    p_synth.add_argument("--dry-run", action="store_true", help="Don't write synthesis cache")

    # list
    sub.add_parser("list", help="List manifest sections")

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
        "extract": cmd_extract,
        "synthesize": cmd_synthesize,
        "list": cmd_list,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
