#!/usr/bin/env python
"""5-10 step QLoRA smoke test for RTX 3080 10GB.

Validates: HF load → 4bit → LoRA → backward → save adapter.
Does NOT merge, export GGUF, or touch Ollama.
All paths default to F:\\ml-train.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Force caches onto F drive before heavy imports.
TRAIN_ROOT = Path(os.environ.get("MEDLEARN_TRAIN_ROOT", r"F:\ml-train"))
os.environ.setdefault("HF_HOME", str(TRAIN_ROOT / "hf-cache"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(TRAIN_ROOT / "hf-cache"))
os.environ.setdefault("TORCH_HOME", str(TRAIN_ROOT / "torch-cache"))
os.environ.setdefault("TEMP", str(TRAIN_ROOT / "tmp"))
os.environ.setdefault("TMP", str(TRAIN_ROOT / "tmp"))

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

DEFAULT_MODEL = r"F:\ml-train\models\Qwen3-8B"
DEFAULT_DATA = TRAIN_ROOT / "training" / "sft_train.jsonl"
DEFAULT_OUTPUT = TRAIN_ROOT / "training" / "lora-smoke"
DEFAULT_REPORT = TRAIN_ROOT / "training" / "qlora_smoke_report.json"

LORA_TARGET_MODULES = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QLoRA smoke test (5-10 steps)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--max-seq-length", type=int, default=1536)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    return parser.parse_args()


def gb(bytes_val: int | float) -> float:
    return round(bytes_val / 1024**3, 3)


def build_report(**fields: object) -> dict[str, object]:
    return {
        "task": "qlora_smoke_test",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        **fields,
    }


def save_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def verify_adapter_files(output_dir: Path) -> dict[str, object]:
    config = output_dir / "adapter_config.json"
    weights = output_dir / "adapter_model.safetensors"
    bin_weights = output_dir / "adapter_model.bin"
    return {
        "adapter_config_exists": config.exists(),
        "adapter_safetensors_exists": weights.exists(),
        "adapter_bin_exists": bin_weights.exists(),
        "adapter_saved": config.exists() and (weights.exists() or bin_weights.exists()),
        "files": sorted(p.name for p in output_dir.glob("*") if p.is_file()),
    }


def main() -> int:
    args = parse_args()
    report: dict[str, object] = build_report(
        model=args.model,
        data=str(args.data),
        output_dir=str(args.output_dir),
        max_steps=args.max_steps,
        train_root=str(TRAIN_ROOT),
    )

    if not torch.cuda.is_available():
        report["success"] = False
        report["blockers"] = ["torch.cuda.is_available() is False"]
        save_report(args.report, report)
        print("BLOCKED: CUDA not available")
        return 1

    report["gpu_name"] = torch.cuda.get_device_name(0)
    report["vram_total_gb"] = gb(torch.cuda.get_device_properties(0).total_memory)

    if not args.data.exists():
        report["success"] = False
        report["blockers"] = [f"dataset missing: {args.data}"]
        save_report(args.report, report)
        print(f"BLOCKED: dataset missing: {args.data}")
        return 1

    losses: list[float] = []
    started = time.time()

    try:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

        print(f"[*] Loading tokenizer: {args.model}")
        tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        print("[*] Loading model in 4-bit...")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )
        report["load_in_4bit"] = True
        report["vram_after_load_gb"] = gb(torch.cuda.max_memory_allocated())

        model = prepare_model_for_kbit_training(model)
        lora_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            target_modules=LORA_TARGET_MODULES,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

        dataset = load_dataset("json", data_files=str(args.data), split="train")
        report["train_samples"] = len(dataset)

        args.output_dir.mkdir(parents=True, exist_ok=True)
        training_args = SFTConfig(
            output_dir=str(args.output_dir),
            max_steps=args.max_steps,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            learning_rate=args.learning_rate,
            warmup_ratio=0.03,
            logging_steps=1,
            save_steps=args.max_steps,
            save_total_limit=1,
            bf16=True,
            optim="paged_adamw_8bit",
            max_length=args.max_seq_length,
            dataset_text_field="text",
            report_to="none",
            gradient_checkpointing=True,
            dataloader_pin_memory=False,
        )

        def on_log(logs: dict[str, object]) -> None:
            if "loss" in logs:
                losses.append(float(logs["loss"]))

        print(f"[*] Training {args.max_steps} steps on {len(dataset)} samples...")
        trainer = SFTTrainer(
            model=model,
            processing_class=tokenizer,
            train_dataset=dataset,
            args=training_args,
        )
        train_result = trainer.train()
        trainer.save_model(str(args.output_dir))

        report["vram_peak_gb"] = gb(torch.cuda.max_memory_allocated())
        report["train_runtime_sec"] = round(time.time() - started, 2)
        report["train_loss"] = float(train_result.training_loss) if train_result.training_loss else None
        report["step_losses"] = losses
        report["adapter_check"] = verify_adapter_files(args.output_dir)

        vram_ok = report["vram_peak_gb"] <= 9.7
        adapter_ok = report["adapter_check"]["adapter_saved"]
        report["success"] = bool(vram_ok and adapter_ok and report["load_in_4bit"])
        report["checks"] = {
            "load_in_4bit": report["load_in_4bit"],
            "vram_under_9_7gb": vram_ok,
            "training_completed": True,
            "adapter_saved": adapter_ok,
        }
        if not vram_ok:
            report.setdefault("warnings", []).append(
                f"VRAM peak {report['vram_peak_gb']}GB exceeds 9.7GB threshold"
            )

        save_report(args.report, report)
        print("=" * 60)
        print(f"success          : {report['success']}")
        print(f"vram_peak_gb     : {report['vram_peak_gb']}")
        print(f"vram_after_load  : {report['vram_after_load_gb']}")
        print(f"train_loss       : {report['train_loss']}")
        print(f"adapter_saved    : {adapter_ok}")
        print(f"report           : {args.report}")
        print("=" * 60)
        return 0 if report["success"] else 1

    except Exception as exc:
        report["success"] = False
        report["error"] = str(exc)
        report["traceback"] = traceback.format_exc()
        report["vram_peak_gb"] = gb(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else None
        save_report(args.report, report)
        print(f"FAILED: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())