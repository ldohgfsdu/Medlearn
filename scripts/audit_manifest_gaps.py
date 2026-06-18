#!/usr/bin/env python3
"""Audit gaps between PDF TOC, app catalog, and ingestion manifest."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from ingest_knowledge import iter_manifest_sections, resolve_catalog_section_range

PART_RE = re.compile(r"第[一二三四五六七八九十百零\d]+篇")
CHAPTER_RE = re.compile(r"第[一二三四五六七八九十百零\d]+章")


def norm(text: str) -> str:
    return re.sub(r"[\s\-－—]", "", (text or "").strip())


def load_pdf_chapters_by_part() -> dict[str, list[str]]:
    pdf_cat = json.loads(
        (PROJECT_ROOT / "generated/pipeline_v3/内科学（第10版）.catalog.json").read_text(
            encoding="utf-8"
        )
    )
    parts: dict[str, list[str]] = defaultdict(list)
    for entry in pdf_cat["toc_entries"]:
        if not entry.get("is_content"):
            continue
        headings = entry.get("headings", [])
        part = next((h for h in headings if PART_RE.search(h)), None)
        if not part:
            continue
        title = entry["title"]
        if CHAPTER_RE.search(title) and "篇" not in title:
            if title not in parts[part]:
                parts[part].append(title)
    return parts


def main() -> None:
    manifest = yaml.safe_load(
        (PROJECT_ROOT / "manifests/internal_medicine_ingestion.yaml").read_text(encoding="utf-8")
    )
    app_cat = json.loads(
        (PROJECT_ROOT / "scripts/catalog.internal-medicine.json").read_text(encoding="utf-8")
    )
    pdf_parts = load_pdf_chapters_by_part()

    manifest_map: dict[str, list[dict]] = {}
    for part in manifest.get("parts", []):
        manifest_map[part["title"]] = part.get("sections", [])

    app_map: dict[str, list[str]] = {}
    for chapter in app_cat["chapters"]:
        part_title = chapter["chapterTitle"]
        app_map[part_title] = []
        for sec in chapter["sections"]:
            if sec.get("parentChapter"):
                continue
            app_map[part_title].append(sec["title"])

    print("=" * 60)
    print("内科学第10版 · 入库覆盖审计")
    print("=" * 60)

    total_pdf = sum(len(v) for v in pdf_parts.values())
    total_manifest = sum(len(v) for v in manifest_map.values())
    verified = sum(
        1
        for part in manifest_map.values()
        for sec in part
        if sec.get("status") == "verified"
    )

    print(f"\n全书 PDF 目录章数: {total_pdf} (+ 第一篇绪论)")
    print(f"Manifest 登记章数: {total_manifest} (verified: {verified})")

    print("\n--- 按篇明细 ---")
    for part_title in sorted(pdf_parts):
        pdf_chapters = pdf_parts[part_title]
        manifest_secs = manifest_map.get(part_title, [])
        manifest_titles = [s["title"] for s in manifest_secs]
        manifest_norm = {norm(t) for t in manifest_titles}

        missing_from_manifest = [c for c in pdf_chapters if norm(c) not in manifest_norm]
        verified_secs = [s for s in manifest_secs if s.get("status") == "verified"]

        print(f"\n{part_title}")
        print(f"  教材章数: {len(pdf_chapters)}")
        print(f"  manifest: {len(manifest_secs)} 条 | verified: {len(verified_secs)}")
        if missing_from_manifest:
            print(f"  未登记 ({len(missing_from_manifest)}):")
            for ch in missing_from_manifest:
                print(f"    · {ch}")

    print("\n--- App catalog 有、manifest 无 ---")
    for part_title, app_secs in app_map.items():
        manifest_norm = {norm(s["title"]) for s in manifest_map.get(part_title, [])}
        missing = [t for t in app_secs if norm(t) not in manifest_norm]
        if missing:
            print(f"\n{part_title}")
            for item in missing:
                print(f"  · {item}")

    print("\n--- Manifest 条目能否在 PDF 定位 ---")
    for item in iter_manifest_sections(manifest):
        try:
            resolve_catalog_section_range(item["part_title"], item["section_title"])
            status = "OK"
        except Exception as exc:
            status = f"FAIL ({exc})"
        sec_status = item["section_ref"].get("status", "?")
        print(f"  [{sec_status:10}] {item['section_title'][:40]:40} -> {status}")

    print("\n--- 第四~九篇 manifest 状态 ---")
    for part in manifest.get("parts", []):
        if part["title"].startswith(("第四篇", "第五篇", "第六篇", "第七篇", "第八篇", "第九篇")):
            n = len(pdf_parts.get(part["title"], []))
            listed = len(part.get("sections", []))
            print(f"  {part['title']}: 教材 {n} 章, manifest 登记 {listed} 章")


if __name__ == "__main__":
    main()