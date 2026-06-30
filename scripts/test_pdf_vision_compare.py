#!/usr/bin/env python3
"""PDF 视觉解析对比测试：medlearn-qwen3:8b vs medlearn-qwen3.5:9b

用法：
  python scripts/test_pdf_vision_compare.py --pages 77,81,85
  python scripts/test_pdf_vision_compare.py --pages 77 --dpi 100
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = PROJECT_ROOT / "textbook" / "内科学（第10版）.pdf"
OUTPUT_DIR = PROJECT_ROOT / "generated" / "vision_compare"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

PAGE_TYPES = {
    77: "text",
    81: "table",
    85: "mixed",
}


def _node_count(extraction_result: dict[str, Any]) -> int:
    data = extraction_result.get("data")
    if isinstance(data, dict):
        nodes = data.get("nodes", [])
        if isinstance(nodes, list):
            return len(nodes)
    nodes = extraction_result.get("nodes", 0)
    return nodes if isinstance(nodes, int) else 0


def decide_text_first_route(
    page_type: str,
    text_result: dict[str, Any],
    vision_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply the benchmark-backed text-first routing policy."""
    text_nodes = _node_count(text_result)
    text_json_valid = bool(text_result.get("json_valid", False))
    vision_nodes = _node_count(vision_result or {})
    vision_json_valid = bool((vision_result or {}).get("json_valid", False))
    quality_notes: list[str] = []

    if text_json_valid and text_nodes > 0:
        if vision_result is None:
            quality_notes.append("vision_skipped_text_success")
        elif vision_json_valid and vision_nodes > text_nodes:
            quality_notes.append("needs_quality_review")
        elif not vision_json_valid:
            quality_notes.append("vision_json_failed_ignored")
        if page_type == "table":
            quality_notes.append("table_page_not_automatic_vision")
        return {
            "selected_route": "text",
            "fallback_reason": "",
            "text_nodes": text_nodes,
            "text_json_valid": text_json_valid,
            "vision_nodes": vision_nodes,
            "vision_json_valid": vision_json_valid,
            "quality_notes": quality_notes,
        }

    fallback_reason = "text_json_invalid" if not text_json_valid else "text_nodes_zero"
    quality_notes.append(
        "fallback_improved"
        if vision_json_valid and vision_nodes > 0
        else "fallback_not_improved"
    )
    return {
        "selected_route": "vision",
        "fallback_reason": fallback_reason,
        "text_nodes": text_nodes,
        "text_json_valid": text_json_valid,
        "vision_nodes": vision_nodes,
        "vision_json_valid": vision_json_valid,
        "quality_notes": quality_notes,
    }


def page_to_image(pdf_path: Path, page_num: int, output_dir: Path, dpi: int = 100) -> Path:
    """Convert PDF page to PNG image using pymupdf."""
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


def get_image_info(image_path: Path) -> dict[str, Any]:
    """Get image dimensions and file size."""
    from PIL import Image

    with Image.open(image_path) as img:
        width, height = img.size
    return {
        "width": width,
        "height": height,
        "size_bytes": image_path.stat().st_size,
    }


def extract_text_from_page(pdf_path: Path, page_num: int) -> str:
    """Extract text from PDF page using pymupdf."""
    import pymupdf as fitz

    doc = fitz.open(str(pdf_path))
    try:
        page = doc[page_num - 1]
        return page.get_text()
    finally:
        doc.close()


def _unload_model(model: str) -> None:
    """Remove a model from VRAM before loading another on limited GPUs."""
    import requests

    try:
        requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=30,
        )
        time.sleep(2)
    except Exception:
        pass


def image_to_base64(image_path: Path) -> str:
    """Convert image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _parse_json_response(content: str) -> tuple[dict[str, Any], bool]:
    """Parse JSON from LLM response. Returns (data, is_valid_json)."""
    import re

    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    # Try direct parse
    try:
        return json.loads(cleaned), True
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip()), True
        except json.JSONDecodeError:
            pass

    # Try finding JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start : end + 1]), True
        except json.JSONDecodeError:
            pass

    return {"error": "JSON parse failed", "raw": content}, False


def _extract_ollama_metrics(result: dict[str, Any]) -> dict[str, Any]:
    """Extract timing and token metrics from Ollama response."""
    return {
        "prompt_eval_count": result.get("prompt_eval_count", 0),
        "prompt_eval_duration_s": result.get("prompt_eval_duration", 0) / 1e9,
        "eval_count": result.get("eval_count", 0),
        "eval_duration_s": result.get("eval_duration", 0) / 1e9,
        "total_duration_s": result.get("total_duration", 0) / 1e9,
        "load_duration_s": result.get("load_duration", 0) / 1e9,
        "done_reason": result.get("done_reason", ""),
    }


def call_ollama_text(text: str, model: str = "medlearn-qwen3:8b") -> dict[str, Any]:
    """Call Ollama with text-only input."""
    import requests

    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "think": False,
        "keep_alive": "5m",
        "messages": [{"role": "user", "content": EXTRACTION_PROMPT.format(input_text=text)}],
        "options": {
            "temperature": 0,
            "num_ctx": 8192,
            "num_gpu": 999,
            "num_predict": 4096,  # Text model generates fast, allow more output
        },
    }

    start = time.time()
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=600)
    wall_time = time.time() - start

    response.raise_for_status()
    result = response.json()
    content = result["message"]["content"]
    thinking = result["message"].get("thinking", "")
    data, json_valid = _parse_json_response(content)
    metrics = _extract_ollama_metrics(result)

    if not content and thinking:
        data = {"error": "thinking_overflow", "thinking": thinking[:500]}
        json_valid = False

    return {
        "data": data,
        "json_valid": json_valid,
        "wall_time_s": wall_time,
        "raw": content,
        "thinking": thinking,
        **metrics,
    }


def call_ollama_vision(image_path: Path, model: str = "medlearn-qwen3.5:9b") -> dict[str, Any]:
    """Call Ollama with image input (vision model). think:false via API."""
    import requests

    image_b64 = image_to_base64(image_path)

    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "think": False,
        "keep_alive": "5m",
        "messages": [
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(input_text="[见图片]"),
                "images": [image_b64],
            }
        ],
        "options": {
            "temperature": 0,
            "num_ctx": 8192,
            "num_gpu": 999,
            "num_predict": 2048,
        },
    }

    start = time.time()
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=900)
    wall_time = time.time() - start

    response.raise_for_status()
    result = response.json()
    content = result["message"]["content"]
    thinking = result["message"].get("thinking", "")
    data, json_valid = _parse_json_response(content)
    metrics = _extract_ollama_metrics(result)

    if not content and thinking:
        data = {"error": "thinking_overflow", "thinking": thinking[:500]}
        json_valid = False

    return {
        "data": data,
        "json_valid": json_valid,
        "wall_time_s": wall_time,
        "raw": content,
        "thinking": thinking,
        **metrics,
    }


EXTRACTION_PROMPT = """你是医学教材知识抽取器。从以下内容中提取知识点，输出 JSON。

要求：
1. 每个知识点包含 title、type、parent_entity、aspect、content、evidence
2. 如果有表格，保留表格结构
3. 如果有药物/治疗方案，归入对应疾病
4. 只输出 JSON，不要额外解释

输出格式：
{{"nodes":[{{"title":"...","type":"disease|treatment|symptom","parent_entity":"...","aspect":"...","content":"...","evidence":"..."}}],"edges":[]}}

---
{input_text}
"""


def compare_page(
    pdf_path: Path,
    page_num: int,
    output_dir: Path,
    dpi: int = 100,
    production_routing: bool = False,
) -> dict[str, Any]:
    """Compare text vs vision extraction for a single page."""
    page_type = PAGE_TYPES.get(page_num, "unknown")
    print(f"\n=== Page {page_num} ({page_type}) ===")

    # Extract text
    text = extract_text_from_page(pdf_path, page_num)
    print(f"Text length: {len(text)} chars")

    # Convert to image
    image_path = page_to_image(pdf_path, page_num, output_dir, dpi=dpi)
    img_info = get_image_info(image_path)
    print(f"Image: {img_info['width']}x{img_info['height']}, {img_info['size_bytes']//1024}KB, DPI={dpi}")

    # Text extraction (8b)
    _unload_model("medlearn-qwen3.5:9b")
    print("Running text extraction (medlearn-qwen3:8b)...")
    try:
        text_result = call_ollama_text(text, model="medlearn-qwen3:8b")
        text_nodes = len(text_result["data"].get("nodes", []))
        print(f"  Text: {text_nodes} nodes, {text_result['wall_time_s']:.1f}s, prompt={text_result['prompt_eval_count']}tok/{text_result['prompt_eval_duration_s']:.1f}s, gen={text_result['eval_count']}tok/{text_result['eval_duration_s']:.1f}s")
    except Exception as e:
        text_result = {"error": str(e), "wall_time_s": 0, "json_valid": False, "data": {}}
        text_nodes = 0
        print(f"  Text extraction failed: {e}")

    vision_result: dict[str, Any] | None
    if production_routing and text_result.get("json_valid", False) and text_nodes > 0:
        vision_result = None
        vision_nodes = 0
        print("Skipping vision extraction: text-first production route selected.")
    else:
        # Vision extraction (3.5-9b)
        _unload_model("medlearn-qwen3:8b")
        print("Running vision extraction (medlearn-qwen3.5:9b, think:false)...")
        try:
            vision_result = call_ollama_vision(image_path, model="medlearn-qwen3.5:9b")
            vision_nodes = len(vision_result["data"].get("nodes", []))
            has_thinking = bool(vision_result.get("thinking", ""))
            print(f"  Vision: {vision_nodes} nodes, {vision_result['wall_time_s']:.1f}s, prompt={vision_result['prompt_eval_count']}tok/{vision_result['prompt_eval_duration_s']:.1f}s, gen={vision_result['eval_count']}tok/{vision_result['eval_duration_s']:.1f}s, thinking={has_thinking}")
        except Exception as e:
            vision_result = {"error": str(e), "wall_time_s": 0, "json_valid": False, "data": {}}
            vision_nodes = 0
            print(f"  Vision extraction failed: {e}")

    route_decision = decide_text_first_route(page_type, text_result, vision_result)

    # Build result
    result = {
        "page": page_num,
        "page_type": page_type,
        "text_length": len(text),
        "dpi": dpi,
        "image_width": img_info["width"],
        "image_height": img_info["height"],
        "image_size_bytes": img_info["size_bytes"],
        "selected_route": route_decision["selected_route"],
        "fallback_reason": route_decision["fallback_reason"],
        "text_nodes": route_decision["text_nodes"],
        "text_json_valid": route_decision["text_json_valid"],
        "vision_nodes": route_decision["vision_nodes"],
        "vision_json_valid": route_decision["vision_json_valid"],
        "quality_notes": route_decision["quality_notes"],
        "text_extraction": {
            "model": "medlearn-qwen3:8b",
            "nodes": text_nodes,
            "json_valid": text_result.get("json_valid", False),
            "wall_time_s": text_result.get("wall_time_s", 0),
            "prompt_eval_count": text_result.get("prompt_eval_count", 0),
            "prompt_eval_duration_s": text_result.get("prompt_eval_duration_s", 0),
            "eval_count": text_result.get("eval_count", 0),
            "eval_duration_s": text_result.get("eval_duration_s", 0),
            "total_duration_s": text_result.get("total_duration_s", 0),
            "load_duration_s": text_result.get("load_duration_s", 0),
            "data": text_result.get("data"),
            "raw": text_result.get("raw", ""),
            "thinking": text_result.get("thinking", ""),
            "error": text_result.get("error"),
        },
        "vision_extraction": {
            "model": "medlearn-qwen3.5:9b",
            "nodes": vision_nodes,
            "json_valid": (vision_result or {}).get("json_valid", False),
            "wall_time_s": (vision_result or {}).get("wall_time_s", 0),
            "prompt_eval_count": (vision_result or {}).get("prompt_eval_count", 0),
            "prompt_eval_duration_s": (vision_result or {}).get("prompt_eval_duration_s", 0),
            "eval_count": (vision_result or {}).get("eval_count", 0),
            "eval_duration_s": (vision_result or {}).get("eval_duration_s", 0),
            "total_duration_s": (vision_result or {}).get("total_duration_s", 0),
            "load_duration_s": (vision_result or {}).get("load_duration_s", 0),
            "data": (vision_result or {}).get("data"),
            "raw": (vision_result or {}).get("raw", ""),
            "thinking": (vision_result or {}).get("thinking", ""),
            "error": (vision_result or {}).get("error"),
            "skipped": vision_result is None,
        },
        "image_path": str(image_path),
    }

    # Save individual page result
    page_result_path = output_dir / f"page_{page_num:04d}_result.json"
    with open(page_result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def print_summary(results: list[dict[str, Any]]) -> None:
    """Print benchmark summary table."""
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"{'Page':<6} {'Type':<8} {'Text':>6} {'T-Time':>8} {'T-Prompt':>10} {'Vision':>8} {'V-Time':>8} {'V-Prompt':>10} {'V-Thinking':>12} {'V-JSON':>8} {'Route':>8}")
    print("-" * 100)

    for r in results:
        te = r["text_extraction"]
        ve = r["vision_extraction"]
        print(
            f"{r['page']:<6} "
            f"{r['page_type']:<8} "
            f"{te['nodes']:>6} "
            f"{te['wall_time_s']:>7.1f}s "
            f"{te['prompt_eval_count']:>5}tok/{te['prompt_eval_duration_s']:.0f}s "
            f"{ve['nodes']:>8} "
            f"{ve['wall_time_s']:>7.1f}s "
            f"{ve['prompt_eval_count']:>5}tok/{ve['prompt_eval_duration_s']:.0f}s "
            f"{'YES' if ve.get('thinking') else 'NO':>12} "
            f"{'OK' if ve['json_valid'] else 'FAIL':>8} "
            f"{r.get('selected_route', '?'):>8}"
        )

    # Averages
    if results:
        avg_t_time = sum(r["text_extraction"]["wall_time_s"] for r in results) / len(results)
        avg_v_time = sum(r["vision_extraction"]["wall_time_s"] for r in results) / len(results)
        avg_v_prompt = sum(r["vision_extraction"]["prompt_eval_duration_s"] for r in results) / len(results)
        avg_v_eval = sum(r["vision_extraction"]["eval_duration_s"] for r in results) / len(results)
        v_json_ok = sum(1 for r in results if r["vision_extraction"]["json_valid"])
        v_thinking = sum(1 for r in results if r["vision_extraction"].get("thinking"))

        print("-" * 100)
        print(f"Averages: Text={avg_t_time:.1f}s  Vision={avg_v_time:.1f}s  (V-prompt={avg_v_prompt:.1f}s, V-eval={avg_v_eval:.1f}s)")
        print(f"Vision JSON valid: {v_json_ok}/{len(results)}  Thinking detected: {v_thinking}/{len(results)}")
        route_text = sum(1 for r in results if r.get("selected_route") == "text")
        route_vision = sum(1 for r in results if r.get("selected_route") == "vision")
        print(f"Selected route: text={route_text} vision={route_vision}")


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF vision comparison benchmark")
    parser.add_argument("--pages", type=str, required=True, help="Comma-separated page numbers")
    parser.add_argument("--dpi", type=int, default=100, help="Image DPI (default: 100)")
    parser.add_argument(
        "--production-routing",
        action="store_true",
        help="Skip vision when text JSON is valid and text nodes are present.",
    )
    args = parser.parse_args()

    if not PDF_PATH.exists():
        print(f"PDF not found: {PDF_PATH}")
        return 1

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    pages = [int(p.strip()) for p in args.pages.split(",")]
    print(f"Testing pages: {pages}, DPI: {args.dpi}")
    print(f"Output: {output_dir}")

    results = []
    for page in pages:
        try:
            result = compare_page(
                PDF_PATH,
                page,
                output_dir,
                dpi=args.dpi,
                production_routing=args.production_routing,
            )
            results.append(result)
        except Exception as e:
            print(f"Page {page} failed: {e}")
            import traceback
            traceback.print_exc()

    if results:
        print_summary(results)

        # Save summary
        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pages": pages,
            "dpi": args.dpi,
            "results": results,
        }
        summary_path = output_dir / f"summary_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\nSummary saved: {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
