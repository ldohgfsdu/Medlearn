#!/usr/bin/env python
"""Training environment smoke check.

Gate before any QLoRA work. Writes report to F:\\ml-train\\training by default.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REPORT_DIR = Path(
    os.environ.get("MEDLEARN_TRAIN_ROOT", r"F:\ml-train\training")
)


def check_package(name: str) -> dict[str, str]:
    try:
        module = __import__(name)
        version = getattr(module, "__version__", "unknown")
        return {"status": "ok", "version": str(version)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "missing", "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check QLoRA training environment")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
    )
    args = parser.parse_args()
    report_path = args.report_dir / "env_check_report.json"

    report: dict[str, object] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ready_for_training": False,
        "blockers": [],
        "warnings": [],
        "train_root": str(DEFAULT_REPORT_DIR.parent),
    }

    torch_info = check_package("torch")
    report["torch"] = torch_info

    if torch_info["status"] != "ok":
        report["blockers"].append("torch not installed")
    else:
        import torch

        cuda_available = torch.cuda.is_available()
        report["cuda_available"] = cuda_available
        report["torch_version"] = torch.__version__

        if not cuda_available:
            report["blockers"].append(
                "torch.cuda.is_available() is False — install CUDA-enabled PyTorch"
            )
        else:
            device = torch.cuda.get_device_name(0)
            total_gb = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
            report["gpu_name"] = device
            report["vram_gb"] = total_gb
            if total_gb < 9.5:
                report["warnings"].append(
                    f"VRAM {total_gb}GB is tight for QLoRA 8B; keep max_seq_length <= 1536"
                )

    for package in ("transformers", "datasets", "peft", "trl", "bitsandbytes", "accelerate"):
        info = check_package(package)
        report[package] = info
        if info["status"] != "ok":
            report["warnings"].append(f"{package} not installed")

    if not report["blockers"]:
        report["ready_for_training"] = True
        report["next_step"] = "Run 5-10 step fake QLoRA smoke test on F:\\ml-train"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Training environment check")
    print("=" * 60)
    print(f"ready_for_training : {report['ready_for_training']}")
    if report.get("gpu_name"):
        print(f"gpu                : {report['gpu_name']}")
        print(f"vram_gb            : {report['vram_gb']}")
    print(f"cuda_available     : {report.get('cuda_available', False)}")
    if report["blockers"]:
        print("\nBlockers:")
        for item in report["blockers"]:
            print(f"  - {item}")
    if report["warnings"]:
        print("\nWarnings:")
        for item in report["warnings"]:
            print(f"  - {item}")
    print(f"\nReport saved: {report_path}")
    return 0 if report["ready_for_training"] else 1


if __name__ == "__main__":
    raise SystemExit(main())