#!/usr/bin/env python3
"""Benchmark vision prompt latency across DPI settings.

Measures image tokenization cost (prompt_eval) for medlearn-qwen3.5:9b without
running full extraction prompts.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = PROJECT_ROOT / "textbook" / "内科学（第10版）.pdf"
OUTPUT_DIR = PROJECT_ROOT / "generated" / "vision_compare"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_VISION_MODEL", "medlearn-qwen3.5:9b")

PROMPT = (
    "从图片中识别疾病名称，只返回 JSON："
    '{"disease_name": ""}'
)


def render_page(pdf_path: Path, page_num: int, dpi: int, output_dir: Path) -> Path:
    import pymupdf as fitz

    doc = fitz.open(str(pdf_path))
    try:
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=dpi)
        output_path = output_dir / f"page_{page_num:04d}_dpi{dpi}.png"
        pix.save(str(output_path))
        return output_path
    finally:
        doc.close()


def image_to_base64(image_path: Path) -> str:
    with open(image_path, "rb") as handle:
        return base64.b64encode(handle.read()).decode("utf-8")


def unload_model(model: str) -> None:
    try:
        requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=30,
        )
    except Exception:
        pass


def call_vision(
    image_path: Path,
    *,
    think: bool | None,
    use_no_think_suffix: bool,
    num_predict: int,
) -> dict[str, Any]:
    prompt = PROMPT + ("\n/no_think" if use_no_think_suffix else "")
    payload: dict[str, Any] = {
        "model": MODEL,
        "stream": False,
        "format": "json",
        "keep_alive": "5m",
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_to_base64(image_path)],
            }
        ],
        "options": {
            "temperature": 0.1,
            "num_ctx": 16384,
            "num_gpu": 999,
            "num_predict": num_predict,
        },
    }
    if think is not None:
        payload["think"] = think

    started = time.time()
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=900)
    wall = time.time() - started
    response.raise_for_status()
    result = response.json()

    prompt_eval_ns = result.get("prompt_eval_duration") or 0
    eval_ns = result.get("eval_duration") or 0
    message = result.get("message", {})
    thinking = message.get("thinking", "") or ""
    content = message.get("content", "") or ""

    return {
        "wall_seconds": round(wall, 2),
        "prompt_eval_seconds": round(prompt_eval_ns / 1e9, 2),
        "eval_seconds": round(eval_ns / 1e9, 2),
        "prompt_tokens": result.get("prompt_eval_count", 0),
        "output_tokens": result.get("eval_count", 0),
        "thinking_chars": len(thinking),
        "content_chars": len(content),
        "done_reason": result.get("done_reason", ""),
        "think_setting": think,
        "no_think_suffix": use_no_think_suffix,
        "num_predict": num_predict,
        "image_bytes": image_path.stat().st_size,
        "image_path": str(image_path),
        "content_preview": content[:120],
        "thinking_preview": thinking[:120],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark vision DPI and think settings")
    parser.add_argument("--page", type=int, default=77)
    parser.add_argument("--dpis", type=str, default="100,200")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR))
    args = parser.parse_args()

    if not PDF_PATH.exists():
        print(f"PDF not found: {PDF_PATH}")
        return 1

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    dpis = [int(item.strip()) for item in args.dpis.split(",") if item.strip()]

    print(f"Model: {MODEL}")
    print(f"Page: {args.page}")
    print(f"DPIs: {dpis}")

    unload_model("medlearn-qwen3:8b")

    dpi_results: list[dict[str, Any]] = []
    for dpi in dpis:
        image_path = render_page(PDF_PATH, args.page, dpi, output_dir)
        print(f"\n=== DPI {dpi} ({image_path.name}, {image_path.stat().st_size // 1024} KB) ===")
        result = call_vision(
            image_path,
            think=False,
            use_no_think_suffix=False,
            num_predict=128,
        )
        result["dpi"] = dpi
        dpi_results.append(result)
        print(
            f"prompt_tokens={result['prompt_tokens']} "
            f"prompt_eval={result['prompt_eval_seconds']}s "
            f"eval={result['eval_seconds']}s "
            f"wall={result['wall_seconds']}s "
            f"thinking_chars={result['thinking_chars']}"
        )

    print("\n=== Think mode check @ DPI 100 ===")
    image_100 = output_dir / f"page_{args.page:04d}_dpi100.png"
    if not image_100.exists():
        image_100 = render_page(PDF_PATH, args.page, 100, output_dir)

    think_cases = [
        ("think_false_api", {"think": False, "use_no_think_suffix": False, "num_predict": 128}),
        ("no_think_suffix", {"think": None, "use_no_think_suffix": True, "num_predict": 128}),
        ("default", {"think": None, "use_no_think_suffix": False, "num_predict": 128}),
    ]
    think_results: list[dict[str, Any]] = []
    for label, cfg in think_cases:
        print(f"\n--- {label} ---")
        result = call_vision(image_100, **cfg)
        result["label"] = label
        think_results.append(result)
        print(
            f"thinking_chars={result['thinking_chars']} "
            f"content_chars={result['content_chars']} "
            f"output_tokens={result['output_tokens']} "
            f"wall={result['wall_seconds']}s"
        )

    report = {
        "model": MODEL,
        "page": args.page,
        "dpi_results": dpi_results,
        "think_results": think_results,
    }
    report_path = output_dir / f"dpi_benchmark_page_{args.page:04d}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())