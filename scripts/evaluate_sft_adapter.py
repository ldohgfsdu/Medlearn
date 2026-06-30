#!/usr/bin/env python
"""Backward-compatible entry point for MedLearn SFT adapter evaluation."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_SCRIPT = PROJECT_ROOT / "training" / "evaluate_sft_adapter.py"

spec = importlib.util.spec_from_file_location("training_evaluate_sft_adapter", TRAINING_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load evaluation script at {TRAINING_SCRIPT}")

module = importlib.util.module_from_spec(spec)
sys.modules["training_evaluate_sft_adapter"] = module
spec.loader.exec_module(module)

if __name__ == "__main__":
    module.main()