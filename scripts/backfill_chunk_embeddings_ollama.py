#!/usr/bin/env python3
"""Backfill missing chunk embeddings from Ollama; dry-run unless --apply."""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


EXPECTED_DIMENSION = 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--document-name", action="append", default=[])
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def fetch_rows(session, rest_url, headers, document_names, limit):
    params = {
        "select": "id,document_name,content",
        "embedding": "is.null",
        "order": "id.asc",
        "limit": str(limit),
    }
    if document_names:
        quoted = ",".join(json.dumps(name, ensure_ascii=False) for name in document_names)
        params["document_name"] = f"in.({quoted})"
    response = session.get(
        f"{rest_url}/document_chunks",
        headers={**headers, "Prefer": "count=exact"},
        params=params,
        timeout=60,
    )
    response.raise_for_status()
    print(f"matching_rows={response.headers.get('Content-Range', 'unknown')}")
    return response.json()


def embed(session, ollama_url, model, texts):
    response = session.post(
        f"{ollama_url}/api/embed",
        json={"model": model, "input": texts},
        timeout=300,
    )
    response.raise_for_status()
    vectors = response.json().get("embeddings", [])
    if len(vectors) != len(texts):
        raise RuntimeError(f"Expected {len(texts)} vectors, received {len(vectors)}")
    for vector in vectors:
        if len(vector) != EXPECTED_DIMENSION:
            raise RuntimeError(
                f"Expected {EXPECTED_DIMENSION} dimensions, received {len(vector)}"
            )
        norm = math.sqrt(sum(float(value) ** 2 for value in vector))
        if not math.isfinite(norm) or norm < 1e-6:
            raise RuntimeError(f"Invalid embedding norm: {norm}")
    return vectors


def update_row(session, rest_url, headers, row_id, vector):
    response = session.patch(
        f"{rest_url}/document_chunks",
        headers={**headers, "Prefer": "return=minimal"},
        params={"id": f"eq.{row_id}", "embedding": "is.null"},
        json={"embedding": vector},
        timeout=60,
    )
    response.raise_for_status()


def main() -> int:
    args = parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    supabase_url = required_env("SUPABASE_URL").rstrip("/")
    service_key = required_env("SUPABASE_SERVICE_ROLE_KEY")
    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
    rest_url = f"{supabase_url}/rest/v1"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    mode = "APPLY" if args.apply else "DRY_RUN"
    print(f"mode={mode}")
    print(f"model={model}")
    print(f"limit={args.limit}")
    print(f"documents={args.document_name or ['ALL']}")

    session = requests.Session()
    rows = fetch_rows(
        session, rest_url, headers, args.document_name, args.limit
    )
    print(f"fetched_rows={len(rows)}")
    if not rows:
        return 0

    processed = 0
    for start in range(0, len(rows), args.batch_size):
        batch = rows[start : start + args.batch_size]
        vectors = embed(session, ollama_url, model, [row["content"] for row in batch])
        if args.apply:
            for row, vector in zip(batch, vectors):
                update_row(session, rest_url, headers, row["id"], vector)
        processed += len(batch)
        print(f"processed={processed}/{len(rows)}")
        time.sleep(0.05)

    print(f"completed mode={mode} rows={processed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
