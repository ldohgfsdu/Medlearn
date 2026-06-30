"""Read-only heading signal auditor for Document Tree v1.

Scans asthma (PDF 62-70) and tuberculosis (PDF 102-116) pages, extracts raw
block/line/span/char signals, classifies candidate markers, and emits an audit
report. Does NOT modify the existing extractor, UI, state, or remote data.

Usage:
    python -m scripts.textbook_pipeline.heading_signal_auditor
    python -m scripts.textbook_pipeline.heading_signal_auditor --twice  # stability

Output:
    generated/heading_audit/{scope}.audit.json
    generated/heading_audit/{scope}.stability.json  (with --twice)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PDF_PATH = Path("textbook/内科学（第10版）.pdf")
OUTPUT_DIR = Path("generated/heading_audit")

SCOPES: list[dict[str, Any]] = [
    {
        "scope_id": "asthma",
        "catalog_path": ["第二篇", "第四章 支气管哮喘"],
        "pdf_page_start_1based": 62,
        "pdf_page_end_1based": 70,
        "printed_page_start_label": "31",
        "printed_page_end_label": "39",
    },
    {
        "scope_id": "tuberculosis",
        "catalog_path": ["第二篇", "第八章 肺结核"],
        "pdf_page_start_1based": 102,
        "pdf_page_end_1based": 116,
        "printed_page_start_label": "71",
        "printed_page_end_label": "85",
    },
]

# ---------------------------------------------------------------------------
# Marker detection (per-scope proposed; font/size assist, marker prefix decides)
# ---------------------------------------------------------------------------

PART_RE = re.compile(r"^第[一二三四五六七八九十百零〇\d]+[篇章节]")
BRACKET_RE = re.compile(r"^【([^】]+)】")
CHINESE_PAREN_RE = re.compile(r"^（[一二三四五六七八九十百]+）")
ARABIC_DOT_RE = re.compile(r"^\d+\.\s")
ARABIC_PAREN_RE = re.compile(r"^（\d+）")
ARABIC_RIGHT_PAREN_RE = re.compile(r"^\d+）")
APPENDIX_RE = re.compile(r"^附[：:]")

# Separator characters that may split heading from body
SEPARATORS = {
    "\u2003": "EM_SPACE",
    "\u2002": "EN_SPACE",
    "\u2009": "THIN_SPACE",
    "\u200a": "HAIR_SPACE",
}

# Font buckets (proposed, pending human review)
PAGE_HEADER_FONTS = {"FZLTZHUNHK--GBK1-0"}
HEADING_FONTS = {"FZLTHK--GBK1-0", "FZZYSK1--GBK1-0", "FZLTZCHK--GBK1-0"}
BODY_FONTS = {"FZSSK--GBK1-0"}


def detect_marker(text: str) -> str | None:
    """Detect marker kind from text prefix. Returns None if no marker."""
    text = text.strip()
    if not text:
        return None
    if PART_RE.match(text):
        return "chapter"
    if BRACKET_RE.match(text):
        return "bracket"
    if APPENDIX_RE.match(text):
        return "appendix"
    if CHINESE_PAREN_RE.match(text):
        return "chinese_parenthetical"
    if ARABIC_DOT_RE.match(text):
        return "arabic_dot"
    if ARABIC_PAREN_RE.match(text):
        return "arabic_parenthetical"
    if ARABIC_RIGHT_PAREN_RE.match(text):
        return "arabic_right_parenthesis"
    return None


def is_page_header(line_info: dict[str, Any]) -> bool:
    """Check if a line is a page header (not a content heading)."""
    spans = line_info.get("spans", [])
    if not spans:
        return False
    first_font = spans[0].get("font", "")
    first_size = spans[0].get("size", 0)
    bbox = spans[0].get("bbox", [0, 999, 0, 0])
    y0 = bbox[1] if len(bbox) >= 2 else 999
    return (
        first_font in PAGE_HEADER_FONTS
        and first_size <= 9.0
        and y0 < 50.0
    )


def normalize_spans_for_fingerprint(spans: list[dict[str, Any]]) -> str:
    """Build a normalized JSON span array for SHA-256 fingerprinting.

    Uses repr() for floats to avoid str(float) ambiguity, and rounds to 2
    decimal places for bbox/size.
    """
    normalized = []
    for s in spans:
        normalized.append({
            "t": s.get("text", ""),
            "f": s.get("font", ""),
            "s": round(float(s.get("size", 0)), 2),
            "b": [round(float(x), 2) for x in s.get("bbox", [0, 0, 0, 0])],
        })
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def compute_raw_anchor(
    pdf_page: int,
    block_index: int,
    line_index: int | str,
    spans: list[dict[str, Any]],
) -> str:
    """Compute raw anchor string from pre-classification payload.

    Uses 128 bits (32 hex chars) of SHA-256 to satisfy the >=128-bit
    identifier requirement. `line_index` may be a string like "0-1" for
    merged multi-line headings (joint SourceAnchor).
    """
    payload = normalize_spans_for_fingerprint(spans)
    full_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"p{pdf_page}:b{block_index}:l{line_index}:{full_sha[:32]}"


def compute_full_anchor_id(
    textbook_version_id: str,
    scope_id: str,
    pdf_checksum: str,
    raw_anchor: str,
) -> str:
    """Compute full anchor ID including full PDF checksum binding.

    Retains the full source PDF SHA-256 (256 bits) so source binding is
    unambiguous; no truncation.
    """
    return f"dt:{textbook_version_id}:{scope_id}:{pdf_checksum}:{raw_anchor}"


# ---------------------------------------------------------------------------
# Page scanning
# ---------------------------------------------------------------------------

def scan_page(page, pdf_page_1based: int) -> list[dict[str, Any]]:
    """Scan a single page using rawdict for char-level bbox, return line records."""
    # Use rawdict for char-level detail
    raw = page.get_text("rawdict", sort=True)
    blocks = raw.get("blocks") or []
    lines_out: list[dict[str, Any]] = []

    for bi, block in enumerate(blocks):
        if block.get("type") != 0:
            continue
        for li, line in enumerate(block.get("lines", [])):
            spans_out = []
            for si, span in enumerate(line.get("spans", [])):
                span_text = "".join(
                    ch.get("c", "") for ch in span.get("chars", [])
                )
                if not span_text.strip() and not span_text:
                    continue
                # Collect separator chars
                sep_chars = []
                for ch in span.get("chars", []):
                    c = ch.get("c", "")
                    if c in SEPARATORS:
                        sep_chars.append({
                            "char": c,
                            "name": SEPARATORS[c],
                            "bbox": [round(float(x), 2) for x in ch.get("bbox", [0, 0, 0, 0])],
                        })
                spans_out.append({
                    "span_index": si,
                    "text": span_text,
                    "text_repr": repr(span_text),
                    "font": span.get("font", ""),
                    "size": round(float(span.get("size", 0)), 2),
                    "bbox": [round(float(x), 2) for x in span.get("bbox", [0, 0, 0, 0])],
                    "color": span.get("color", 0),
                    "flags": span.get("flags", 0),
                    "char_count": len(span.get("chars", [])),
                    "separators": sep_chars,
                })
            if not spans_out:
                continue
            line_text = "".join(s["text"] for s in spans_out)
            lines_out.append({
                "pdf_page": pdf_page_1based,
                "raw_block_index": bi,
                "raw_line_index": li,
                "line_text": line_text,
                "line_text_repr": repr(line_text),
                "spans": spans_out,
            })
    return lines_out


def classify_line(line_info: dict[str, Any]) -> dict[str, Any]:
    """Classify a line as page_header / heading_candidate / body / uncertain."""
    spans = line_info.get("spans", [])
    line_text = line_info.get("line_text", "").strip()
    if not spans:
        return {"classification": "empty", "marker": None, "reason": "no spans"}

    # Page header check
    if is_page_header(line_info):
        return {
            "classification": "page_header",
            "marker": None,
            "reason": "font+size+y0 match page header",
        }

    # Marker detection
    marker = detect_marker(line_text)

    # Font/size signals
    first_font = spans[0].get("font", "")
    first_size = spans[0].get("size", 0)
    font_bucket = (
        "heading" if first_font in HEADING_FONTS
        else "body" if first_font in BODY_FONTS
        else "page_header" if first_font in PAGE_HEADER_FONTS
        else "unknown"
    )

    # Separator analysis: find first U+2003 (EM SPACE) position in line_text
    em_space_pos = -1
    all_seps = []
    for s in spans:
        for sep in s.get("separators", []):
            all_seps.append(sep)
    # Find U+2003 in full line text
    for idx, ch in enumerate(line_text):
        if ch == "\u2003":
            em_space_pos = idx
            break

    # Body punctuation: colon/semicolon/period prove explanatory text, not heading
    has_body_punct = any(p in line_text for p in "：；。")

    # Split dispatch: heading/body boundary depends on marker kind.
    # - bracket 【…】: split at closing 】 (real PDF uses ordinary space after
    #   】, not U+2003; the closing bracket is the natural delimiter)
    # - chinese_parenthetical / arabic_dot / appendix: split at U+2003
    # - chapter: never split (U+2003 is trailing/internal in chapter titles)
    # - body font + U+2003 + body punct => numbered body, not a heading split
    # Key audit finding: U+2003 alone does NOT prove heading/body boundary.
    SPLITTABLE_MARKERS = {"chinese_parenthetical", "arabic_dot", "appendix"}
    is_heading_candidate = False
    split_position = None
    heading_text = line_text
    body_text = ""
    if marker:
        if font_bucket == "heading":
            is_heading_candidate = True
            if marker == "bracket":
                # Bracket headings: split at closing 】 — everything after is body.
                close_pos = line_text.find("】")
                if close_pos >= 0:
                    candidate_body = line_text[close_pos + 1:].strip()
                    if candidate_body:
                        split_position = close_pos + 1
                        heading_text = line_text[:close_pos + 1]
                        body_text = candidate_body
                    # else: bracket-only heading, no body
            elif marker in SPLITTABLE_MARKERS and em_space_pos >= 0:
                candidate_body = line_text[em_space_pos + 1:].strip()
                if candidate_body:
                    split_position = em_space_pos
                    heading_text = line_text[:em_space_pos].strip()
                    body_text = candidate_body
                # else: U+2003 is trailing/internal, no split
        elif font_bucket == "body":
            if not has_body_punct and em_space_pos >= 0 and len(line_text) <= 80:
                is_heading_candidate = True
                # body font + U+2003 + no punct: tentatively heading, but do NOT
                # split — body-font split is unsafe per audit finding.
            elif not has_body_punct and len(line_text) <= 40:
                is_heading_candidate = True  # tentative, needs font confirmation
            # else: body font + body punct or long text => body
        else:  # unknown font
            if em_space_pos >= 0:
                is_heading_candidate = True
            elif len(line_text) <= 60 and not has_body_punct:
                is_heading_candidate = True

    if not marker:
        classification = "body"
    elif is_heading_candidate:
        classification = "heading_candidate"
    else:
        classification = "body"

    return {
        "classification": classification,
        "marker": marker,
        "font_bucket": font_bucket,
        "first_font": first_font,
        "first_size": first_size,
        "em_space_position": em_space_pos,
        "all_separators": all_seps,
        "split_position": split_position,
        "heading_text": heading_text,
        "body_text": body_text,
        "line_length": len(line_text),
        "has_body_punct": has_body_punct,
        "has_sentence_punct": any(p in line_text for p in "。！？"),
        "_spans": spans,  # private; used by merge_chapter_continuations; stripped before output
    }


# ---------------------------------------------------------------------------
# Audit runner
# ---------------------------------------------------------------------------

def merge_chapter_continuations(
    classified: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge chapter title continuation lines within the same PDF block.

    Chapter titles may span multiple lines in the same block (e.g.
    '第四章\\u2003' on line 0, '支气管哮喘' on line 1, both 21pt FZLTZCHK).
    This merges continuation lines (same block, same font, same size, no
    marker, currently classified as body) into the chapter heading and
    produces a joint SourceAnchor with a line-range indicator 'l{first}-{last}'.

    The merged heading_text joins all parts with a single space; the
    raw_anchor fingerprint is computed from the combined spans of all
    merged lines so it is deterministic and stable.
    """
    merged: list[dict[str, Any]] = []
    skip: set[int] = set()
    for i, line in enumerate(classified):
        if i in skip:
            continue
        if not (
            line.get("marker") == "chapter"
            and line.get("classification") == "heading_candidate"
            and line.get("font_bucket") == "heading"
        ):
            merged.append(line)
            continue

        # Look ahead for continuation lines in the same block
        page = line["pdf_page"]
        block = line["raw_block_index"]
        font = line["first_font"]
        size = line["first_size"]
        combined_spans: list[dict[str, Any]] = list(line.get("_spans", []))
        first_text = line["heading_text"].rstrip("\u2003 ").rstrip()
        text_parts = [first_text]
        line_indices = [line["raw_line_index"]]
        j = i + 1
        while j < len(classified):
            nxt = classified[j]
            if (
                nxt["pdf_page"] == page
                and nxt["raw_block_index"] == block
                and nxt.get("first_font") == font
                and nxt.get("first_size") == size
                and nxt.get("marker") is None
                and nxt["classification"] == "body"
            ):
                combined_spans.extend(nxt.get("_spans", []))
                text_parts.append(nxt["heading_text"].strip())
                line_indices.append(nxt["raw_line_index"])
                skip.add(j)
                j += 1
            else:
                break

        if len(line_indices) <= 1:
            merged.append(line)
            continue

        # Build merged entry with joint SourceAnchor
        merged_text = " ".join(t for t in text_parts if t)
        line_range = f"{line_indices[0]}-{line_indices[-1]}"
        raw_anchor = compute_raw_anchor(page, block, line_range, combined_spans)
        # Rebuild anchor_id: dt:{version}:{scope}:{pdf_sha256}:{raw_anchor}
        aid_parts = line["anchor_id"].split(":", 4)
        full_id = f"{aid_parts[0]}:{aid_parts[1]}:{aid_parts[2]}:{aid_parts[3]}:{raw_anchor}"

        merged_line = dict(line)
        merged_line["raw_anchor"] = raw_anchor
        merged_line["anchor_id"] = full_id
        merged_line["heading_text"] = merged_text
        merged_line["raw_line_index"] = line_range
        merged_line["line_text_preview"] = merged_text[:80]
        merged_line["merged_from_lines"] = line_indices
        merged.append(merged_line)
    return merged


def run_audit(pdf_path: Path, scopes: list[dict[str, Any]]) -> dict[str, Any]:
    """Run audit on all scopes, return results dict."""
    import fitz  # PyMuPDF — lazy import so core logic tests run without it
    doc = fitz.open(str(pdf_path))
    pdf_checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    pymupdf_version = fitz.version[0]

    results: dict[str, Any] = {
        "meta": {
            "pdf_path": str(pdf_path),
            "pdf_sha256": pdf_checksum,
            "pymupdf_version": pymupdf_version,
            "sort_mode": "sort=True",
            "extraction_mode": "rawdict",
        },
        "scopes": {},
    }

    for scope in scopes:
        scope_id = scope["scope_id"]
        page_start = scope["pdf_page_start_1based"]
        page_end = scope["pdf_page_end_1based"]

        all_lines: list[dict[str, Any]] = []
        for pn in range(page_start, page_end + 1):
            page = doc[pn - 1]
            page_lines = scan_page(page, pn)
            all_lines.extend(page_lines)

        # Classify all lines
        classified: list[dict[str, Any]] = []
        for line_info in all_lines:
            cls = classify_line(line_info)
            raw_anchor = compute_raw_anchor(
                line_info["pdf_page"],
                line_info["raw_block_index"],
                line_info["raw_line_index"],
                line_info["spans"],
            )
            full_id = compute_full_anchor_id(
                "internal-medicine-10", scope_id, pdf_checksum, raw_anchor
            )
            classified.append({
                "raw_anchor": raw_anchor,
                "anchor_id": full_id,
                "pdf_page": line_info["pdf_page"],
                "raw_block_index": line_info["raw_block_index"],
                "raw_line_index": line_info["raw_line_index"],
                "line_text_preview": line_info["line_text"][:80],
                "classification": cls["classification"],
                "marker": cls["marker"],
                "font_bucket": cls.get("font_bucket"),
                "first_font": cls.get("first_font"),
                "first_size": cls.get("first_size"),
                "em_space_position": cls.get("em_space_position"),
                "split_position": cls.get("split_position"),
                "heading_text": cls.get("heading_text"),
                "body_text": cls.get("body_text"),
                "line_length": cls.get("line_length"),
                "has_body_punct": cls.get("has_body_punct"),
                "has_sentence_punct": cls.get("has_sentence_punct"),
                "separators_count": len(cls.get("all_separators", [])),
                "_spans": cls.get("_spans", line_info["spans"]),  # private; stripped after merge
            })

        # Merge chapter title continuation lines (same block, same font/size)
        classified = merge_chapter_continuations(classified)

        # Strip private _spans field before statistics and output
        for c in classified:
            c.pop("_spans", None)

        # Statistics
        marker_stats: Counter = Counter()
        font_stats: Counter = Counter()
        classification_stats: Counter = Counter()
        sep_patterns: Counter = Counter()
        ambiguous_blocks: list[dict[str, Any]] = []

        for c in classified:
            classification_stats[c["classification"]] += 1
            marker_stats[c["marker"] or "none"] += 1
            font_stats[c["first_font"] or "unknown"] += 1
            em_pos = c.get("em_space_position")
            if em_pos is not None and em_pos >= 0:
                sep_patterns["has_em_space"] += 1
            if c["separators_count"] > 0 and (em_pos is None or em_pos < 0):
                sep_patterns["has_other_sep_no_em_space"] += 1
            # Ambiguous: heading_candidate with non-heading font (unknown OR body)
            # body-font heading_candidate = genuinely ambiguous short text
            # (e.g. "（1） 治疗方案" — could be heading or numbered body)
            if c["classification"] == "heading_candidate" and c["font_bucket"] != "heading":
                ambiguous_blocks.append({
                    "raw_anchor": c["raw_anchor"],
                    "pdf_page": c["pdf_page"],
                    "line_text_preview": c["line_text_preview"],
                    "marker": c["marker"],
                    "first_font": c["first_font"],
                    "font_bucket": c["font_bucket"],
                    "has_body_punct": c.get("has_body_punct"),
                    "line_length": c.get("line_length"),
                    "reason": f"heading_candidate with {c['font_bucket']} font",
                })
            # Numbered body resolved: marker + body font + body punct => body
            # This is the key audit finding: U+2003 + marker does NOT prove heading.
            if c["marker"] and c["classification"] == "body":
                ambiguous_blocks.append({
                    "raw_anchor": c["raw_anchor"],
                    "pdf_page": c["pdf_page"],
                    "line_text_preview": c["line_text_preview"],
                    "marker": c["marker"],
                    "first_font": c["first_font"],
                    "has_body_punct": c.get("has_body_punct"),
                    "has_em_space": em_pos is not None and em_pos >= 0,
                    "reason": "numbered body resolved by body font + punctuation",
                })

        results["scopes"][scope_id] = {
            "scope_config": scope,
            "total_lines": len(classified),
            "classification_stats": dict(classification_stats),
            "marker_stats": dict(marker_stats),
            "font_stats": dict(font_stats),
            "separator_patterns": dict(sep_patterns),
            "ambiguous_blocks": ambiguous_blocks,
            "lines": classified,
        }

    doc.close()
    return results


def verify_golden_paths(results: dict[str, Any]) -> dict[str, Any]:
    """Verify 5 golden paths by matching each expected node to a distinct
    heading_candidate in strict source order.

    Each path defines `expected_nodes`: an ordered list of {marker, title_contains}.
    The verifier walks heading_candidates in source order and matches each
    expected node to the next candidate whose marker matches AND whose
    heading_text contains the expected title substring. All nodes must match
    in order; page headers must never be heading_candidates.
    """
    paths = [
        {
            "id": "T1",
            "scope": "asthma",
            "description": "第四章 → 【流行病学】",
            "expected_nodes": [
                {"marker": "chapter", "title_contains": "第四章"},
                {"marker": "bracket", "title_contains": "流行病学"},
            ],
        },
        {
            "id": "T2",
            "scope": "asthma",
            "description": "第四章 → 【病因和发病机制】 → （二）发病机制 → 1. 气道免疫-炎症机制",
            "expected_nodes": [
                {"marker": "chapter", "title_contains": "第四章"},
                {"marker": "bracket", "title_contains": "病因和发病机制"},
                {"marker": "chinese_parenthetical", "title_contains": "发病机制"},
                {"marker": "arabic_dot", "title_contains": "气道免疫"},
            ],
        },
        {
            "id": "T3",
            "scope": "asthma",
            "description": "第四章 → 【实验室和其他检查】 → （三）肺功能检查 → 3. 支气管舒张试验（BDT）",
            "expected_nodes": [
                {"marker": "chapter", "title_contains": "第四章"},
                {"marker": "bracket", "title_contains": "实验室和其他检查"},
                {"marker": "chinese_parenthetical", "title_contains": "肺功能检查"},
                {"marker": "arabic_dot", "title_contains": "支气管舒张试验"},
            ],
        },
        {
            "id": "T4",
            "scope": "tuberculosis",
            "description": "第八章 → 【结核病的分类标准】 → （二）活动性结核病 → 1. 按病变部位分类",
            "expected_nodes": [
                {"marker": "chapter", "title_contains": "第八章"},
                {"marker": "bracket", "title_contains": "结核病的分类标准"},
                {"marker": "chinese_parenthetical", "title_contains": "活动性结核病"},
                {"marker": "arabic_dot", "title_contains": "按病变部位分类"},
            ],
        },
        {
            "id": "T5",
            "scope": "tuberculosis",
            "description": "第八章 → 【结核病的化学治疗】 → （五）标准化学治疗方案 → 1. 初治活动性肺结核治疗方案",
            "expected_nodes": [
                {"marker": "chapter", "title_contains": "第八章"},
                {"marker": "bracket", "title_contains": "结核病的化学治疗"},
                {"marker": "chinese_parenthetical", "title_contains": "标准化学治疗方案"},
                {"marker": "arabic_dot", "title_contains": "初治活动性肺结核"},
            ],
        },
    ]
    verification = []
    for p in paths:
        scope_lines = results["scopes"][p["scope"]]["lines"]
        heading_candidates = [
            c for c in scope_lines
            if c["classification"] == "heading_candidate"
        ]
        page_headers_in_scope = [
            c for c in scope_lines
            if c["classification"] == "page_header"
        ]
        page_headers_clean = all(
            c["classification"] == "page_header" for c in page_headers_in_scope
        )

        # Match each expected node to the next heading_candidate in source order
        search_start = 0
        node_matches = []
        all_nodes_found = True
        for node in p["expected_nodes"]:
            matched = None
            for i in range(search_start, len(heading_candidates)):
                c = heading_candidates[i]
                if c["marker"] == node["marker"] and node["title_contains"] in c.get("heading_text", ""):
                    matched = c
                    search_start = i + 1  # next node must appear AFTER this one
                    break
            if matched is None:
                all_nodes_found = False
                node_matches.append({
                    "expected_marker": node["marker"],
                    "expected_title_contains": node["title_contains"],
                    "matched": False,
                })
            else:
                node_matches.append({
                    "expected_marker": node["marker"],
                    "expected_title_contains": node["title_contains"],
                    "matched": True,
                    "raw_anchor": matched["raw_anchor"],
                    "pdf_page": matched["pdf_page"],
                    "heading_text": matched.get("heading_text", "")[:80],
                })

        verification.append({
            "path_id": p["id"],
            "description": p["description"],
            "scope": p["scope"],
            "expected_node_count": len(p["expected_nodes"]),
            "matched_node_count": sum(1 for m in node_matches if m["matched"]),
            "node_matches": node_matches,
            "page_headers_detected": len(page_headers_in_scope),
            "page_headers_are_not_nodes": page_headers_clean,
            "passed": all_nodes_found and page_headers_clean,
        })
    return {"golden_paths": verification}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only heading signal auditor")
    parser.add_argument("--twice", action="store_true", help="Run twice to verify stability")
    parser.add_argument("--pdf", type=str, default=str(PDF_PATH), help="PDF path")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Auditing: {pdf_path}")
    results1 = run_audit(pdf_path, SCOPES)

    # Verify golden paths
    gp = verify_golden_paths(results1)
    results1["golden_path_verification"] = gp

    # Save audit results
    for scope_id, scope_data in results1["scopes"].items():
        out_path = OUTPUT_DIR / f"{scope_id}.audit.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(scope_data, f, ensure_ascii=False, indent=2)
        print(f"  {scope_id}: {scope_data['total_lines']} lines → {out_path}")

    # Save golden path verification
    gp_path = OUTPUT_DIR / "golden_paths.json"
    with open(gp_path, "w", encoding="utf-8") as f:
        json.dump(gp, f, ensure_ascii=False, indent=2)
    print(f"  golden paths → {gp_path}")

    # Print summary
    print("\n=== Audit Summary ===")
    for scope_id, scope_data in results1["scopes"].items():
        print(f"\n[{scope_id}]")
        print(f"  Total lines: {scope_data['total_lines']}")
        print(f"  Classification: {scope_data['classification_stats']}")
        print(f"  Markers: {scope_data['marker_stats']}")
        print(f"  Fonts: {scope_data['font_stats']}")
        print(f"  Separators: {scope_data['separator_patterns']}")
        print(f"  Ambiguous blocks: {len(scope_data['ambiguous_blocks'])}")

    print("\n=== Golden Paths ===")
    for p in gp["golden_paths"]:
        status = "PASS" if p["passed"] else "FAIL"
        print(f"  [{status}] {p['path_id']}: {p['description']}")
        print(f"         nodes={p['matched_node_count']}/{p['expected_node_count']} page_headers={p['page_headers_detected']} not_nodes={p['page_headers_are_not_nodes']}")
        for m in p["node_matches"]:
            if m["matched"]:
                print(f"           [OK] p{m['pdf_page']} {m['expected_marker']:<22} {m['heading_text']!r}")
            else:
                print(f"           [NO] {m['expected_marker']:<22} expected {m['expected_title_contains']!r} NOT FOUND")

    # Stability check
    if args.twice:
        print("\n=== Stability Check (run twice) ===")
        results2 = run_audit(pdf_path, SCOPES)
        stability = {"stable": True, "scopes": {}}
        for scope_id in results1["scopes"]:
            anchors1 = [l["raw_anchor"] for l in results1["scopes"][scope_id]["lines"]]
            anchors2 = [l["raw_anchor"] for l in results2["scopes"][scope_id]["lines"]]
            identical = anchors1 == anchors2
            stability["scopes"][scope_id] = {
                "run1_count": len(anchors1),
                "run2_count": len(anchors2),
                "identical_order": identical,
                "identical_set": set(anchors1) == set(anchors2),
            }
            if not identical:
                stability["stable"] = False
        stab_path = OUTPUT_DIR / "stability.json"
        with open(stab_path, "w", encoding="utf-8") as f:
            json.dump(stability, f, ensure_ascii=False, indent=2)
        status = "STABLE" if stability["stable"] else "UNSTABLE"
        print(f"  Result: {status}")
        for scope_id, s in stability["scopes"].items():
            print(f"    {scope_id}: identical_order={s['identical_order']} identical_set={s['identical_set']}")
        print(f"  → {stab_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
