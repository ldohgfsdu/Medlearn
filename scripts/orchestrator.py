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


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "run-next"
    extra = sys.argv[2:]

    allowed = {"status", "catalog", "extract", "upload", "run-next", "convert-v4"}
    if command not in allowed:
        print(f"Unsupported command: {command}")
        print(f"Allowed: {', '.join(sorted(allowed))}")
        return 1

    args = [sys.executable, str(INGEST), command, *extra]
    if command == "run-next" and "--upload" not in extra:
        args.append("--upload")
    print(f"[*] orchestrator -> {' '.join(args)}")
    return subprocess.call(args, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())