#!/usr/bin/env python3
"""Scan PDF for table-heavy pages where PyMuPDF text quality is poor."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import pymupdf as fitz

from textbook_pipeline.adaptive_pdf_parser import AdaptivePdfParser, garbled_ratio


def scan_pdf(pdf_path: Path, page_start: int | None, page_end: int | None) -> list[dict]:
    parser = AdaptivePdfParser(pdf_path, mode="pymupdf")
    doc = fitz.open(str(pdf_path))
    results: list[dict] = []
    try:
        start = (page_start or 1) - 1
        end = page_end or len(doc)
        for i in range(start, min(end, len(doc))):
            page = doc[i]
            pn = i + 1
            try:
                table_count = len(page.find_tables().tables)
            except Exception:
                table_count = 0
            _, report = parser.parse_range(pn, pn)
            page_info = report["pages"][0] if report.get("pages") else {}
            raw_text = page.get_text()
            results.append(
                {
                    "page": pn,
                    "raw_text_chars": len(raw_text.strip()),
                    "markdown_chars": page_info.get("text_chars", 0),
                    "table_count": table_count,
                    "quality_score": page_info.get("quality_score", 0),
                    "issues": list(page_info.get("issues") or []),
                    "garbled_ratio": round(garbled_ratio(raw_text), 3),
                    "blocking": pn in (report.get("blocking_pages") or []),
                    "route": page_info.get("route"),
                }
            )
    finally:
        doc.close()
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, default=PROJECT_ROOT / "textbook" / "内科学（第10版）.pdf")
    ap.add_argument("--start", type=int, default=60)
    ap.add_argument("--end", type=int, default=120)
    ap.add_argument("--out", type=Path, default=PROJECT_ROOT / "generated" / "vision_compare" / "table_scan.json")
    args = ap.parse_args()

    results = scan_pdf(args.pdf, args.start, args.end)
    table_pages = [r for r in results if r["table_count"] >= 1]
    bad = [
        r
        for r in table_pages
        if r["blocking"]
        or r["quality_score"] < 0.55
        or "garbled_text" in r["issues"]
        or "insufficient_content" in r["issues"]
        or "complex_tables" in r["issues"]
    ]
    bad.sort(key=lambda x: (x["quality_score"], -x["table_count"]))

    payload = {
        "range": [args.start, args.end],
        "total_pages": len(results),
        "table_pages": len(table_pages),
        "candidates": bad[:25],
        "all_table_pages": sorted(table_pages, key=lambda x: (-x["table_count"], x["page"])),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Scanned pages {args.start}-{args.end}: {len(table_pages)} with tables, {len(bad)} candidates")
    print("\nTop candidates for vision compare:")
    for item in bad[:10]:
        print(
            f"  p{item['page']:>3}  tables={item['table_count']}  "
            f"quality={item['quality_score']:.2f}  md_chars={item['markdown_chars']}  "
            f"issues={item['issues']}"
        )


if __name__ == "__main__":
    main()