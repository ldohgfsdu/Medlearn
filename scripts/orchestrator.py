#!/usr/bin/env python3
"""Manifest-driven ingestion orchestrator.

Delegates to scripts/ingest_knowledge.py instead of simulating progress.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INGEST = PROJECT_ROOT / "scripts" / "ingest_knowledge.py"
EXPORT_DISPLAY_CONTRACTS = PROJECT_ROOT / "scripts" / "export_ev1_display_contracts_ts.py"
EXPORT_SOURCE_QA_QUEUE = PROJECT_ROOT / "scripts" / "export-ev1-source-qa-queue.mjs"
AUDIT_EV1_KNOWLEDGE_QUALITY = PROJECT_ROOT / "scripts" / "audit-ev1-knowledge-quality.mjs"

INGEST_COMMANDS = {
    "status",
    "catalog",
    "sync-manifest",
    "audit-gaps",
    "extract",
    "upload",
    "run-next",
    "run-parts",
    "convert-v4",
    "rebuild-cache",
    "backfill-p0",
    "ev1-convert-ready",
    "ev1-release-gate",
    "ev1-artifact-audit",
    "ev1-display-contract",
    "ev1-display-quality-report",
    "ev1-run-batch",
    "ev1-reverify-candidates",
    "ev1-candidate-quality-report",
}

ORCHESTRATOR_COMMANDS = {
    "audit-app-knowledge-quality",
    "export-display-contracts",
    "build-app-knowledge-bundle",
    "reverify-app-knowledge-bundle",
}

SUPPORTED_COMMANDS = INGEST_COMMANDS | ORCHESTRATOR_COMMANDS


def _call(args: list[str]) -> int:
    print(f"[*] orchestrator -> {' '.join(args)}", flush=True)
    return subprocess.call(args, cwd=PROJECT_ROOT)


def _run_app_knowledge_bundle(extra: list[str]) -> int:
    gate = _call([sys.executable, str(INGEST), "ev1-release-gate", *extra])
    if gate != 0:
        return gate

    display = _call([sys.executable, str(INGEST), "ev1-display-contract", *extra])
    if display != 0:
        return display

    display_quality = _call(
        [sys.executable, str(INGEST), "ev1-display-quality-report", "--strict", "--pretty", *extra]
    )
    if display_quality != 0:
        return display_quality

    return _call([sys.executable, str(EXPORT_DISPLAY_CONTRACTS)])


def _audit_app_knowledge_quality(extra: list[str]) -> int:
    source_qa = _call(["node", str(EXPORT_SOURCE_QA_QUEUE), "--all", "--pretty"])
    if source_qa != 0:
        return source_qa

    audit_args = ["node", str(AUDIT_EV1_KNOWLEDGE_QUALITY), "--pretty", "--strict"]
    return _call([*audit_args, *extra])


def _reverify_app_knowledge_bundle(extra: list[str]) -> int:
    reverify = _call([sys.executable, str(INGEST), "ev1-reverify-candidates", *extra])
    if reverify != 0:
        return reverify

    quality = _call([sys.executable, str(INGEST), "ev1-candidate-quality-report", "--strict", "--pretty"])
    if quality != 0:
        return quality

    convert = _call([sys.executable, str(INGEST), "ev1-convert-ready", "--continue-on-error"])
    if convert != 0:
        return convert

    bundle = _run_app_knowledge_bundle([])
    if bundle != 0:
        return bundle

    return _audit_app_knowledge_quality([])


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "run-next"
    extra = sys.argv[2:]

    if command not in SUPPORTED_COMMANDS:
        print(f"Unsupported command: {command}")
        print(f"Allowed: {', '.join(sorted(SUPPORTED_COMMANDS))}")
        return 1

    if command == "export-display-contracts":
        return _call([sys.executable, str(EXPORT_DISPLAY_CONTRACTS), *extra])

    if command == "build-app-knowledge-bundle":
        return _run_app_knowledge_bundle(extra)

    if command == "audit-app-knowledge-quality":
        return _audit_app_knowledge_quality(extra)

    if command == "reverify-app-knowledge-bundle":
        return _reverify_app_knowledge_bundle(extra)

    args = [sys.executable, str(INGEST), command, *extra]
    if command == "run-next" and "--upload" not in extra:
        args.append("--upload")
    return _call(args)


if __name__ == "__main__":
    raise SystemExit(main())
