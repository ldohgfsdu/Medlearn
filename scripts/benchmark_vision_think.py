#!/usr/bin/env python3
from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

IMAGE = Path(__file__).resolve().parents[1] / "generated" / "vision_compare" / "page_0077_dpi100.png"
URL = "http://127.0.0.1:11434/api/chat"
MODEL = "medlearn-qwen3.5:9b"
PROMPT = '从图片中识别疾病名称，只返回 JSON：{"disease_name": ""}'


def run(label: str, *, think: bool | None, suffix_no_think: bool) -> None:
    prompt = PROMPT + ("\n/no_think" if suffix_no_think else "")
    payload: dict = {
        "model": MODEL,
        "stream": False,
        "format": "json",
        "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(IMAGE.read_bytes()).decode()]}],
        "options": {"num_predict": 128, "temperature": 0.1},
    }
    if think is not None:
        payload["think"] = think
    started = time.time()
    response = requests.post(URL, json=payload, timeout=300)
    wall = time.time() - started
    data = response.json()
    message = data.get("message", {})
    thinking = message.get("thinking") or ""
    content = message.get("content") or ""
    print(
        f"{label}: status={response.status_code} wall={wall:.1f}s "
        f"thinking_chars={len(thinking)} content_chars={len(content)} "
        f"out_tokens={data.get('eval_count', 0)}"
    )


def main() -> int:
    run("think_false_api", think=False, suffix_no_think=False)
    run("no_think_suffix", think=None, suffix_no_think=True)
    run("default", think=None, suffix_no_think=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())