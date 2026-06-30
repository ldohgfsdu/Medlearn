#!/usr/bin/env python
"""Train a small Qwen3 LoRA adapter for MedLearn extraction."""
from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
    set_seed,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "training" / "sft_train.jsonl"
DEFAULT_MODEL = "Qwen/Qwen3-0.6B"
DEFAULT_OUTPUT = PROJECT_ROOT / "training" / "checkpoints" / "qwen3-0.6b-medlearn-lora"
DEFAULT_REPORT = PROJECT_ROOT / "training" / "reports" / "qwen3-0.6b-medlearn-lora.json"
ASSISTANT_MARKER = "<|im_start|>assistant\n"
END_MARKER = "<|im_end|>"


def read_rows(path: Path) -> list[dict[str, str]]:
    rows = []
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this training command")

    os.environ.setdefault(
        "HF_HOME",
        str(PROJECT_ROOT / ".models" / "huggingface"),
    )
    set_seed(args.seed)

    rows = read_rows(args.dataset.resolve())
    train_rows, validation_rows = split_rows(
        rows,
        seed=args.seed,
        validation_ratio=args.validation_ratio,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, lora_config)

    def tokenize(batch: dict[str, list[str]]) -> dict[str, list[list[int]]]:
        tokenized = {"input_ids": [], "attention_mask": [], "labels": []}
        for text in batch["text"]:
            prompt, completion = text.split(ASSISTANT_MARKER, 1)
            prompt += ASSISTANT_MARKER
            completion = completion.split(END_MARKER, 1)[0].strip() + END_MARKER

            prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            completion_ids = tokenizer(completion, add_special_tokens=False)["input_ids"]

            max_completion = min(len(completion_ids), args.max_length // 2)
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
        gradient_accumulation_steps=8,
        learning_rate=args.learning_rate,
        warmup_ratio=0.05,
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        logging_steps=2,
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
    trainer.save_model(str(args.output_dir / "final"))
    tokenizer.save_pretrained(str(args.output_dir / "final"))

    report = {
        "base_model": args.model,
        "dataset": str(args.dataset.resolve()),
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "max_length": args.max_length,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "train_metrics": train_result.metrics,
        "eval_metrics": eval_result,
        "gpu": torch.cuda.get_device_name(0),
        "adapter_dir": str((args.output_dir / "final").resolve()),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
