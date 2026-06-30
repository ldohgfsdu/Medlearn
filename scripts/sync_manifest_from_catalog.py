#!/usr/bin/env python3
"""Sync ingestion manifest and app catalog from PDF bookmark TOC."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "manifests" / "internal_medicine_ingestion.yaml"
APP_CATALOG_PATH = PROJECT_ROOT / "scripts" / "catalog.internal-medicine.json"
APP_CATALOG_CONSTANTS_PATH = PROJECT_ROOT / "constants" / "catalog.internal-medicine.json"
PDF_CATALOG_PATH = PROJECT_ROOT / "generated" / "pipeline_v3" / "内科学（第10版）.catalog.json"
NORMALIZED_ROOT = PROJECT_ROOT / "generated" / "knowledge_nodes" / "internal-medicine-10"

PART_RE = re.compile(r"第[一二三四五六七八九十百零\d]+篇")
CHAPTER_RE = re.compile(r"第[一二三四五六七八九十百零\d]+章")
SECTION_UNIT_RE = re.compile(r"^第[一二三四五六七八九十百零\d]+节")
CHAPTER_NUM_RE = re.compile(r"^(第[一二三四五六七八九十百零\d]+章)")
SECTION_UNIT_TITLE_RE = re.compile(r"^第[一二三四五六七八九十百零\d]+节\s*[|｜]\s*(.+)$")


def extract_chapter_label(chapter_title: str) -> str:
    return re.sub(r"^第[一二三四五六七八九十百零\d]+章\s*", "", (chapter_title or "").strip()).strip()


def extract_section_unit_entity(unit_title: str) -> str:
    match = SECTION_UNIT_TITLE_RE.match((unit_title or "").strip())
    return match.group(1).strip() if match else (unit_title or "").strip()


def split_disease_group(entity: str) -> list[str]:
    parts = [part.strip() for part in entity.replace("与", "、").split("、") if part.strip()]
    return parts if len(parts) > 1 else [entity]


def derive_subsections(unit_title: str, chapter_title: str) -> list[dict[str, str]]:
    entity = extract_section_unit_entity(unit_title)
    if "概述" in entity or "总论" in entity:
        return [{"title": extract_chapter_label(chapter_title)}]
    return [{"title": title} for title in split_disease_group(entity)]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(text: str) -> str:
    return re.sub(r"[\s\-－—]", "", (text or "").strip())


def chapter_num(title: str) -> str | None:
    match = CHAPTER_NUM_RE.match((title or "").strip())
    return match.group(1) if match else None


def load_pdf_parts() -> dict[str, list[dict[str, Any]]]:
    """Build 篇 -> 章 -> 节 skeleton from PDF bookmark TOC."""
    payload = json.loads(PDF_CATALOG_PATH.read_text(encoding="utf-8"))
    parts: dict[str, list[dict[str, Any]]] = {}

    def ensure_chapter(part_title: str, chapter_title: str) -> dict[str, Any]:
        parts.setdefault(part_title, [])
        for chapter in parts[part_title]:
            if chapter["title"] == chapter_title:
                return chapter
        chapter = {"title": chapter_title, "units": []}
        parts[part_title].append(chapter)
        return chapter

    for entry in payload.get("toc_entries", []):
        if not entry.get("is_content"):
            continue
        headings = entry.get("headings", [])
        part = next((h for h in headings if PART_RE.search(h)), None)
        if not part:
            continue
        title = str(entry.get("title") or "").strip()
        level = int(entry.get("level") or 1)

        if level == 1 and PART_RE.search(title) and "绪论" in title:
            ensure_chapter(title, "绪论")
            continue

        if title == "绪论":
            ensure_chapter(part, "绪论")
            continue

        if level == 2 and CHAPTER_RE.search(title) and "篇" not in title:
            ensure_chapter(part, title)
            continue

        if level == 3 and SECTION_UNIT_RE.search(title):
            chapter_title = next(
                (h for h in headings if CHAPTER_RE.search(h) and "篇" not in h),
                None,
            )
            if not chapter_title:
                continue
            chapter = ensure_chapter(part, chapter_title)
            units = chapter.setdefault("units", [])
            if title not in {unit["title"] for unit in units}:
                units.append(
                    {
                        "title": title,
                        "subsections": derive_subsections(title, chapter_title),
                    }
                )

    return parts


def index_existing_sections(manifest: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for part in manifest.get("parts", []):
        part_title = part["title"]
        for section in part.get("sections", []):
            title = section["title"]
            indexed[(part_title, norm(title))] = section
            num = chapter_num(title)
            if num:
                indexed[(part_title, f"num:{num}")] = section
    return indexed


def normalized_cache_path(part_title: str, section_title: str) -> Path:
    slug = lambda text: re.sub(r"[^\w\u4e00-\u9fff]+", "_", (text or "").strip()).strip("_") or "section"
    key = f"{slug(part_title)}__{slug(section_title)}"
    return NORMALIZED_ROOT / f"{key}.normalized.json"


def status_from_normalized_cache(part_title: str, section_title: str) -> dict[str, Any] | None:
    cache_path = normalized_cache_path(part_title, section_title)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    nodes = payload.get("nodes") or []
    if not nodes:
        return None
    return {
        "title": section_title,
        "status": "extracted",
        "node_count": len(nodes),
    }


def carry_forward_section(
    part_title: str,
    section_title: str,
    indexed: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    old = indexed.get((part_title, norm(section_title)))
    if old is None:
        num = chapter_num(section_title)
        if num:
            old = indexed.get((part_title, f"num:{num}"))
    if old:
        carried = {k: v for k, v in old.items() if k != "title"}
        carried["title"] = section_title
        return carried
    cached = status_from_normalized_cache(part_title, section_title)
    if cached:
        return cached
    return {"title": section_title, "status": "pending"}


def build_manifest(pdf_parts: dict[str, list[dict[str, Any]]], existing: dict[str, Any]) -> dict[str, Any]:
    indexed = index_existing_sections(existing)
    parts: list[dict[str, Any]] = []

    ordered_parts = ["第一篇 绪论"] + sorted(
        [p for p in pdf_parts if p != "第一篇 绪论"],
        key=lambda name: list("一二三四五六七八九十").index(name[1]) if len(name) > 1 and name[1] in "一二三四五六七八九十" else 99,
    )

    for part_title in ordered_parts:
        if part_title not in pdf_parts:
            continue
        sections = [
            carry_forward_section(part_title, chapter["title"], indexed)
            for chapter in pdf_parts[part_title]
        ]
        verified = sum(1 for sec in sections if sec.get("status") == "verified")
        total = len(sections)
        if verified == total and total:
            part_status = "verified"
        elif verified:
            part_status = "in_progress"
        else:
            part_status = "pending"
        parts.append({"title": part_title, "status": part_status, "sections": sections})

    return {
        "schema_version": 1,
        "book_id": existing.get("book_id", "internal-medicine-10"),
        "display_name": existing.get("display_name", "内科学（第10版）"),
        "source_pdf": existing.get("source_pdf", "textbook/内科学（第10版）.pdf"),
        "pipeline": existing.get("pipeline", "pipeline_v3"),
        "output_dir": existing.get("output_dir", "generated/pipeline_v3"),
        "status": existing.get("status", "in_progress"),
        "last_run": existing.get("last_run"),
        "parts": parts,
        "updated_at": utc_now(),
    }


def build_app_catalog(pdf_parts: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    chapters = []
    ordered_parts = ["第一篇 绪论"] + sorted(
        [p for p in pdf_parts if p != "第一篇 绪论"],
        key=lambda name: list("一二三四五六七八九十").index(name[1]) if len(name) > 1 and name[1] in "一二三四五六七八九十" else 99,
    )
    for part_title in ordered_parts:
        if part_title not in pdf_parts:
            continue
        sections = []
        for chapter in pdf_parts[part_title]:
            item: dict[str, Any] = {"title": chapter["title"]}
            units = chapter.get("units") or []
            if units:
                item["units"] = [
                    {
                        "title": unit["title"],
                        **(
                            {"subsections": [{"title": sub["title"]} for sub in unit.get("subsections") or []]}
                            if unit.get("subsections")
                            else {}
                        ),
                    }
                    for unit in units
                ]
            sections.append(item)
        chapters.append({"chapterTitle": part_title, "sections": sections})
    return {
        "bookId": "internal-medicine-10",
        "title": "内科学（第10版）",
        "chapters": chapters,
    }


def main() -> int:
    if not PDF_CATALOG_PATH.exists():
        raise FileNotFoundError(f"Missing PDF catalog: {PDF_CATALOG_PATH}")

    pdf_parts = load_pdf_parts()
    existing = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}

    manifest = build_manifest(pdf_parts, existing)
    app_catalog = build_app_catalog(pdf_parts)

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, allow_unicode=True, sort_keys=False)

    catalog_text = json.dumps(app_catalog, ensure_ascii=False, indent=2) + "\n"
    APP_CATALOG_PATH.write_text(catalog_text, encoding="utf-8")
    APP_CATALOG_CONSTANTS_PATH.write_text(catalog_text, encoding="utf-8")

    total_sections = sum(len(p["sections"]) for p in manifest["parts"])
    total_units = sum(
        len(section.get("units") or [])
        for part in app_catalog["chapters"]
        for section in part["sections"]
    )
    verified = sum(
        1
        for p in manifest["parts"]
        for s in p["sections"]
        if s.get("status") == "verified"
    )
    print(f"[sync] manifest -> {MANIFEST_PATH}")
    print(f"[sync] app catalog -> {APP_CATALOG_PATH}")
    print(
        f"[sync] parts={len(manifest['parts'])}, chapters={total_sections}, "
        f"units={total_units}, verified={verified}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())