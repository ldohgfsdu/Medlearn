#!/usr/bin/env python3
"""Step 2: asthma section pipeline chain (post-synthesis).
Usage: python scripts/rebuild_asthma_chain.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from textbook_identity import resolve_ingestion_context
from textbook_pipeline.evidence_to_knowledge import candidate_cache_to_knowledge_rows

PART = "第二篇 呼吸系统疾病"
SECTION = "第四章 支气管哮喘"
BOOK_ID = "internal-medicine-10"
SAFE_KEY = "第二篇_呼吸系统疾病__第四章_支气管哮喘"

CANDIDATE_DIR = ROOT / "generated" / "pipeline_v3" / "evidence_candidates" / BOOK_ID
CANDIDATE_PATH = CANDIDATE_DIR / f"{SAFE_KEY}.candidate.json"
if not CANDIDATE_PATH.exists():
    # Fall back to legacy pre-V3 candidate location for older sections.
    legacy = ROOT / "generated" / "evidence_candidates" / BOOK_ID / f"{SAFE_KEY}.candidate.json"
    if legacy.exists():
        CANDIDATE_PATH = legacy
NORMALIZED_DIR = ROOT / "generated" / "knowledge_nodes" / BOOK_ID
NORMALIZED_PATH = NORMALIZED_DIR / f"{SAFE_KEY}.normalized.json"
DISPLAY_CONTRACT_DIR = ROOT / "generated" / "display_contracts" / BOOK_ID

def main():
    # 1. Check candidate exists
    if not CANDIDATE_PATH.exists():
        print(f"ERROR: Candidate cache not found: {CANDIDATE_PATH}")
        print("Run 'ingest_evidence_first.py synthesize' first.")
        return 1

    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    print(f"Loaded candidate: {len(candidate.get('candidate_items', []))} items")

    # 2. Convert candidate → normalized
    ctx = resolve_ingestion_context(BOOK_ID, ROOT)
    blocked_ids = set()  # No blocked artifacts for asthma
    
    rows, summary = candidate_cache_to_knowledge_rows(
        candidate,
        ctx.identity,
        source_pdf="textbook/内科学（第10版）.pdf",
        candidate_path=CANDIDATE_PATH,
        blocked_artifact_ids=blocked_ids,
    )
    print(f"Converted: {summary['converted']}, "
          f"skipped_needs_review={summary['skipped_needs_review']}, "
          f"skipped_rejected={summary['skipped_rejected']}")

    if not rows:
        print("ERROR: Zero rows produced")
        return 1

    # Write normalized cache
    from ingest_knowledge import write_ev1_normalized_cache
    output_path = write_ev1_normalized_cache(
        PART, SECTION, rows,
        source_path=CANDIDATE_PATH,
        conversion_summary=summary,
    )
    print(f"Normalized: {output_path}")

    # 3. Build display contract
    from textbook_pipeline.evidence_display_contract import (
        DisplayContractOptions,
        build_display_contract_payload,
    )
    
    normalized = json.loads(NORMALIZED_PATH.read_text(encoding="utf-8"))
    options = DisplayContractOptions(
        merge_adjacent_same_heading=True,
        include_evidence_only=True,
    )
    dc_payload = build_display_contract_payload(
        normalized,
        candidate_payload=candidate,
        options=options,
    )
    
    DISPLAY_CONTRACT_DIR.mkdir(parents=True, exist_ok=True)
    dc_path = DISPLAY_CONTRACT_DIR / f"{SAFE_KEY}.display_contract.json"
    dc_path.write_text(
        json.dumps(dc_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Display contract: {dc_path} "
          f"(nodes={dc_payload.get('node_count', 0)})")

    # 4. Generate source locators
    print("\n--- Generating source locators ---")
    rc = subprocess.run(
        [sys.executable, str(SCRIPTS / "export_phase1_evidence_lineage.py")],
        cwd=ROOT,
        capture_output=True, text=True,
    )
    if rc.returncode != 0:
        print(f"WARNING: export_phase1_evidence_lineage failed: {rc.stderr[:500]}")
    else:
        print(rc.stdout.strip()[:500])

    # 5. Merge bundle + export TS
    print("\n--- Merging bundle ---")
    rc = subprocess.run(
        [sys.executable, str(SCRIPTS / "merge_phase1_locators_bundle.py")],
        cwd=ROOT,
        capture_output=True, text=True,
    )
    if rc.returncode != 0:
        print(f"WARNING: merge_phase1_locators_bundle failed: {rc.stderr[:500]}")
    else:
        print(rc.stdout.strip()[:1000])

    # 6. Export EV1 display contracts TS
    print("\n--- Exporting EV1 TS ---")
    rc = subprocess.run(
        [sys.executable, str(SCRIPTS / "export_ev1_display_contracts_ts.py")],
        cwd=ROOT,
        capture_output=True, text=True,
    )
    if rc.returncode != 0:
        print(f"WARNING: export_ev1_display_contracts_ts failed: {rc.stderr[:500]}")
    else:
        print(rc.stdout.strip()[:500])

    print("\n=== DONE ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
