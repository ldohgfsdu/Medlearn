#!/usr/bin/env python
"""Smoke LoRA training for Stage 3 full nodes-only schema (continues from Stage 2)."""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

import torch
from datasets import Dataset
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
    set_seed,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = (
    PROJECT_ROOT
    / "training"
    / "curriculum"
    / "sft_v2_nodes_curriculum"
    / "stage3_full_nodes_only"
    / "train.jsonl"
)
DEFAULT_BASE_MODEL = PROJECT_ROOT / ".models" / "modelscope" / "Qwen" / "Qwen3-0___6B"
DEFAULT_BASE_ADAPTER = (
    PROJECT_ROOT
    / "training"
    / "checkpoints"
    / "qwen3-0.6b-medlearn-lora-nodes-v2-smoke"
    / "stage2_evidence_content_distill"
    / "final"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "training"
    / "checkpoints"
    / "qwen3-0.6b-medlearn-lora-nodes-v2-smoke"
    / "stage3_full_nodes_only"
)
DEFAULT_REPORT = PROJECT_ROOT / "training" / "reports" / "stage3_full_nodes_only_train.json"
ASSISTANT_MARKER = "<|im_start|>assistant\n"
END_MARKER = "<|im_end|>"

PROTECTED_PATHS = (
    PROJECT_ROOT / "training" / "checkpoints" / "qwen3-0.6b-medlearn-lora" / "final",
    PROJECT_ROOT
    / "training"
    / "checkpoints"
    / "qwen3-0.6b-medlearn-lora-nodes-v2-smoke"
    / "stage1_evidence_copy"
    / "final",
    PROJECT_ROOT
    / "training"
    / "checkpoints"
    / "qwen3-0.6b-medlearn-lora-nodes-v2-smoke"
    / "stage2_evidence_content_distill"
    / "final",
)


def read_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            text = str(item.get("text") or "").strip()
            if text:
                rows.append({"text": text, "id": str(item.get("id") or "")})
    if len(rows) < 20:
        raise RuntimeError(f"Need at least 20 training rows, found {len(rows)}")
    return rows


def split_rows(
    rows: list[dict[str, str]],
    *,
    seed: int,
    validation_ratio: float,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    validation_size = max(8, round(len(shuffled) * validation_ratio))
    validation_size = min(validation_size, len(shuffled) - 1)
    return shuffled[validation_size:], shuffled[:validation_size]


def assert_output_safe(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    for protected in PROTECTED_PATHS:
        if resolved == protected.resolve():
            raise RuntimeError(f"Refusing to overwrite protected adapter path: {protected}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Train Stage 3 full nodes-only smoke LoRA")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--base-model", type=Path, default=DEFAULT_BASE_MODEL)
    parser.add_argument("--base-adapter", type=Path, default=DEFAULT_BASE_ADAPTER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-length", type=int, default=3072)
    parser.add_argument(
        "--completion-reserve-ratio",
        type=float,
        default=0.65,
        help="Fraction of max_length reserved for assistant completion.",
    )
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument(
        "--training-round",
        type=int,
        default=1,
        help="Smoke training round label for reports (e.g. 2 for remediation).",
    )
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this training command")
    if not args.base_adapter.exists():
        raise RuntimeError(f"Stage 2 adapter not found: {args.base_adapter}")
    assert_output_safe(args.output_dir / "final")

    os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".models" / "huggingface"))
    set_seed(args.seed)

    rows = read_rows(args.dataset.resolve())
    train_rows, validation_rows = split_rows(
        rows,
        seed=args.seed,
        validation_ratio=args.validation_ratio,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        str(args.base_model),
        use_fast=True,
        local_files_only=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        str(args.base_model),
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
        local_files_only=True,
    )
    model.config.use_cache = False
    model = PeftModel.from_pretrained(model, str(args.base_adapter), is_trainable=True)
    model.train()
    model.enable_input_require_grads()
    for name, param in model.named_parameters():
        if "lora_" in name:
            param.requires_grad = True
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    if trainable == 0:
        raise RuntimeError("No trainable LoRA parameters found after loading Stage 2 adapter")
    model.gradient_checkpointing_enable()

    def tokenize(batch: dict[str, list[str]]) -> dict[str, list[list[int]]]:
        tokenized = {"input_ids": [], "attention_mask": [], "labels": []}
        for text in batch["text"]:
            prompt, completion = text.split(ASSISTANT_MARKER, 1)
            prompt += ASSISTANT_MARKER
            completion = completion.split(END_MARKER, 1)[0].strip() + END_MARKER

            prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            completion_ids = tokenizer(completion, add_special_tokens=False)["input_ids"]

            max_completion = min(
                len(completion_ids),
                int(args.max_length * args.completion_reserve_ratio),
            )
            completion_ids = completion_ids[:max_completion]
            prompt_budget = args.max_length - len(completion_ids)
            if len(prompt_ids) > prompt_budget:
                prefix_size = min(384, max(0, prompt_budget // 3))
                suffix_size = prompt_budget - prefix_size
                prompt_ids = prompt_ids[:prefix_size] + prompt_ids[-suffix_size:]

            input_ids = prompt_ids + completion_ids
            tokenized["input_ids"].append(input_ids)
            tokenized["attention_mask"].append([1] * len(input_ids))
            tokenized["labels"].append([-100] * len(prompt_ids) + completion_ids)
        return tokenized

    train_dataset = Dataset.from_list(train_rows).map(
        tokenize,
        batched=True,
        remove_columns=["text", "id"],
    )
    validation_dataset = Dataset.from_list(validation_rows).map(
        tokenize,
        batched=True,
        remove_columns=["text", "id"],
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=0.05,
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        logging_steps=5,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        fp16=True,
        gradient_checkpointing=True,
        report_to=[],
        dataloader_num_workers=0,
        remove_unused_columns=True,
        seed=args.seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer=tokenizer,
            model=model,
            label_pad_token_id=-100,
            pad_to_multiple_of=8,
        ),
    )
    train_result = trainer.train()
    eval_result = trainer.evaluate()
    final_dir = args.output_dir / "final"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))

    report = {
        "stage": "stage3_full_nodes_only",
        "training_round": args.training_round,
        "base_model": str(args.base_model.resolve()),
        "base_adapter": str(args.base_adapter.resolve()),
        "dataset": str(args.dataset.resolve()),
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "max_length": args.max_length,
        "completion_reserve_ratio": args.completion_reserve_ratio,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "effective_batch_size": args.gradient_accumulation_steps,
        "train_metrics": train_result.metrics,
        "eval_metrics": eval_result,
        "gpu": torch.cuda.get_device_name(0),
        "adapter_dir": str(final_dir.resolve()),
        "protected_paths_not_overwritten": [str(path) for path in PROTECTED_PATHS],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()