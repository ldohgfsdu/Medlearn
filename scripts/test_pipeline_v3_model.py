"""Smoke-test the local Medlearn Ollama model with UTF-8 medical text."""
from __future__ import annotations

import json

import requests


def main() -> None:
    prompt = (
        '原文：高血压可导致心、脑、肾等靶器官损害。'
        '请返回 JSON：{"nodes":[{"title":"疾病名称","type":"disease",'
        '"content":"原文结论"}]} /no_think'
    )
    response = requests.post(
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": "medlearn-qwen3:8b",
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.1, "num_ctx": 6144},
        },
        timeout=300,
    )
    response.raise_for_status()
    content = response.json()["message"]["content"]
    data = json.loads(content)
    assert data["nodes"][0]["title"] == "高血压", data
    print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
