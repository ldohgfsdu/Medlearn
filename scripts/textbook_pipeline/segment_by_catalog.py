"""
Catalog-based segmenter: split textbook pages into segments by catalog sections.

Supports hierarchical TOC matching (parent → child) and fuzzy similarity.
pageEnd is computed from next-sibling or parent boundary (NOT the next page).
"""
from __future__ import annotations
import json
import hashlib
import re
from difflib import SequenceMatcher
from pathlib import Path
from textbook_pipeline.atomic_io import atomic_write_jsonl

# ── Helpers ────────────────────────────────────────────────────────────

def _normalize_strict(s: str) -> str:
    return re.sub(r'\s+', '', s)

def _normalize_fuzzy(s: str) -> str:
    s = _normalize_strict(s)
    s = re.sub(r'[（(].*?[)）]', '', s)
    s = re.sub(r'^第[一二三四五六七八九十百千万零\d]+[章节篇]|^第\d+章', '', s)
    return s.lower()

def _make_alias_set(aliases: list[str] | None) -> set[str]:
    return {_normalize_strict(a) for a in (aliases or [])}

def _match_toc(toc: list[dict], section: dict) -> tuple[dict | None, str]:
    strict_title = _normalize_strict(section["title"])
    fuzzy_title = _normalize_fuzzy(section["title"])
    alias_set = _make_alias_set(section.get("aliases"))

    # 1. Strict: exact match or alias match
    for entry in toc:
        t_strict = _normalize_strict(entry["title"])
        if t_strict == strict_title or t_strict in alias_set:
            return entry, "strict"

    # 2. Fuzzy: normalized text equality
    for entry in toc:
        t_fuzzy = _normalize_fuzzy(entry["title"])
        if t_fuzzy and fuzzy_title and t_fuzzy == fuzzy_title:
            return entry, "fuzzy"

    # 3. Similarity: SequenceMatcher ratio >= 0.85
    for entry in toc:
        t_fuzzy = _normalize_fuzzy(entry["title"])
        if t_fuzzy and fuzzy_title:
            ratio = SequenceMatcher(None, fuzzy_title, t_fuzzy).ratio()
            if ratio >= 0.85:
                return entry, "fuzzy"

    # 4. Hierarchical: find a parent TOC entry that contains this section's core title
    core_title = _normalize_fuzzy(section["title"])
    if core_title:
        for entry in toc:
            t_strict = _normalize_strict(entry["title"])
            t_norm = _normalize_fuzzy(entry["title"])
            # Parent entry should be shorter, meaningful length, and match a prefix
            if t_norm and len(t_norm) >= 4 and len(core_title) - len(t_norm) >= 4:
                if core_title.startswith(t_norm):
                    return entry, "hierarchical"

    return None, "missing"


def _compute_page_ranges(segments: list[dict], total_pages: int) -> None:
    """Assign pageStart and pageEnd using next-sibling logic."""
    for i, seg in enumerate(segments):
        if seg["found"] and seg["tocPage"] is not None:
            seg["pageStart"] = seg["tocPage"]
        else:
            seg["pageStart"] = None

    for i, seg in enumerate(segments):
        if seg["pageStart"] is None:
            continue
        # Find next sibling with a pageStart
        j = i + 1
        while j < len(segments):
            if segments[j]["pageStart"] is not None:
                seg["pageEnd"] = segments[j]["pageStart"] - 1
                break
            j += 1
        if seg.get("pageEnd") is None:
            seg["pageEnd"] = total_pages
        # Guard: pageEnd must not be less than pageStart (handles same-page segments)
        seg["pageEnd"] = max(seg["pageStart"], seg.get("pageEnd", seg["pageStart"]))


def _extract_text_for_segment(pages: list[dict], pageStart: int | None, pageEnd: int | None) -> str:
    if pageStart is None or pageEnd is None:
        return ""
    texts = []
    for p in pages:
        if pageStart <= p["page_number"] <= pageEnd:
            texts.append(p["text"])
    return "\n".join(texts)


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]


# ── Main ───────────────────────────────────────────────────────────────

def segment_by_catalog(
    catalog: dict,
    pages: list[dict],
    toc: list[dict],
    total_pages: int,
) -> list[dict]:
    segments = []
    for ch in catalog.get("chapters", []):
        for sec in ch.get("sections", []):
            toc_entry, match_type = _match_toc(toc, sec)
            seg_id = _normalize_strict(sec["title"])[:20]
            
            # 构建分段数据
            segment = {
                "segmentId":     seg_id,
                "chapter":       ch["chapterTitle"],
                "sectionTitle":  sec["title"],
                "aliases":       sec.get("aliases", []),
                "found":         toc_entry is not None,
                "method":        "toc" if toc_entry else "missing",
                "matchType":     match_type,
                "confidence":    1.0 if match_type == "strict" else (0.8 if match_type == "fuzzy" else (0.7 if match_type == "hierarchical" else 0.0)),
                "tocTitle":      toc_entry["title"] if toc_entry else None,
                "tocPage":       toc_entry["page"] if toc_entry else None,
                "tocLevel":      toc_entry["level"] if toc_entry else None,
                "pageStart":     toc_entry["page"] if toc_entry else None,
                "pageEnd":       None,
                "text":          None,
                "textHash":      None,
            }
            
            # 添加"附"条目标记
            if sec.get("isAppendix"):
                segment["isAppendix"] = True
                segment["parentChapter"] = sec.get("parentChapter", "")
            
            # 添加独立疾病章节标记
            if sec.get("standalone"):
                segment["standalone"] = True
            
            segments.append(segment)

    _compute_page_ranges(segments, total_pages)

    for seg in segments:
        if seg["pageStart"] is not None:
            text = _extract_text_for_segment(pages, seg["pageStart"], seg["pageEnd"])
            seg["text"] = text
            seg["textHash"] = _text_hash(text) if text else None
        else:
            seg["textHash"] = None

    return segments


def run_segment(
    catalog_path: str,
    pages_path: str,
    toc_path: str,
    out_path: str,
    total_pages: int | None = None,
) -> list[dict]:
    try:
        catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid catalog JSON: {catalog_path}: {e}") from e

    try:
        pages = [json.loads(l) for l in Path(pages_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid pages JSONL: {pages_path}: {e}") from e

    toc = json.loads(Path(toc_path).read_text(encoding="utf-8"))

    if total_pages is None:
        total_pages = max(p["page_number"] for p in pages) if pages else 0

    segments = segment_by_catalog(catalog, pages, toc, total_pages)
    atomic_write_jsonl(out_path, segments)
    return segments
