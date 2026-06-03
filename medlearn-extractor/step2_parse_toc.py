"""Step 2: Parse table of contents from Markdown text using regex (no LLM needed).

This module extracts the table of contents structure directly from the Markdown
text using regex patterns, eliminating the need for LLM-based TOC parsing.
"""

import json
import re
import sys

from rich.console import Console
from rich.panel import Panel

import config

console = Console()


# ── Chinese number mapping ─────────────────────────────────────────
CN_NUMBERS = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}


def cn_to_int(cn: str) -> int:
    """Convert Chinese number string to integer (supports 1-99)."""
    if not cn:
        return 0
    total = 0
    curr = 0
    for ch in cn:
        val = CN_NUMBERS.get(ch, 0)
        if val == 10:
            if curr == 0:
                curr = 1
            total += curr * 10
            curr = 0
        else:
            curr = val
    return total + curr


# ── Regex patterns ─────────────────────────────────────────────────
# System header: 第一篇　绪论 or 第一篇 绪论
SYSTEM_RE = re.compile(
    r'第(?P<num>[一二三四五六七八九十]+)篇\s+(?P<name>[^\n]+)'
)

# Chapter header: 第一章　总论 or 第一章 总论
CHAPTER_RE = re.compile(
    r'第(?P<num>[一二三四五六七八九十]+)章\s+(?P<name>[^\n]+)'
)

# Section header: 第一节　概述 or 第一节 概述
SECTION_RE = re.compile(
    r'第(?P<num>[一二三四五六七八九十]+)节\s+(?P<name>[^\n]+)'
)

# Sub-section: 一、　肺炎链球菌肺炎 or 一、 肺炎链球菌肺炎
SUBSECTION_RE = re.compile(
    r'[一二三四五六七八九十]+、\s+(?P<name>[^\n]+)'
)

# Appendix: ［附］　流行性感冒 or [附] 流行性感冒 or ［附1］
APPENDIX_RE = re.compile(
    r'[\[［]附\d*[\]］]\s+(?P<name>[^\n]+)'
)

# Page number at end of line: .. 2 or .... 10
# The page number may be preceded by dots and thin spaces
PAGE_RE = re.compile(r'\.(?:\s*\.)*\s*(?P<page>\d+)\s*$')


def clean_name(name: str) -> str:
    """Remove trailing dots and page numbers from name."""
    # Find the first dot character
    idx = name.find('.')
    if idx != -1:
        # Remove the dot and everything after it
        return name[:idx].strip()
    return name.strip()


def extract_page(line: str) -> int | None:
    """Extract page number from end of TOC line."""
    m = PAGE_RE.search(line)
    return int(m.group('page')) if m else None


def classify_type(name: str) -> str:
    """Classify knowledge point type based on name."""
    name_lower = name.lower()
    if any(w in name_lower for w in ['概述', '总论', '概论', '分类', '诊断', '治疗', '预防']):
        return 'basic'
    if any(w in name_lower for w in ['综合征', '症候群']):
        return 'syndrome'
    if any(w in name_lower for w in ['症状', '体征', '表现']):
        return 'symptom'
    return 'disease'


def parse_toc_local(md_path: str, output_path: str) -> None:
    """Parse TOC from Markdown using regex (no LLM)."""
    console.rule("[bold blue]Step 2: Parse Table of Contents (Local Regex)")

    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Find the actual TOC section (the one with system headers)
    toc_start = None
    for m in SYSTEM_RE.finditer(text):
        # Check if preceded by "目录" within 500 chars
        start = max(0, m.start() - 500)
        if '目录' in text[start:m.start()]:
            toc_start = text.rfind('目录', start, m.start())
            break

    if toc_start is None:
        console.print("[bold red]❌ Could not find TOC section")
        sys.exit(1)

    # Find where TOC ends (before first substantial content page)
    first_system_content = text.find('第一篇', toc_start + 100)
    if first_system_content == -1:
        first_system_content = len(text)

    toc_text = text[toc_start:first_system_content]
    console.print(f"📖 TOC section: {len(toc_text):,} chars")

    # Parse systems
    systems = []
    current_system = None
    current_chapter = None

    lines = toc_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Check for system header
        m = SYSTEM_RE.match(line)
        if m:
            if current_system:
                systems.append(current_system)
            current_system = {
                "name": clean_name(m.group('name')),
                "chapters": []
            }
            current_chapter = None
            i += 1
            continue

        # Check for chapter header
        m = CHAPTER_RE.match(line)
        if m and current_system is not None:
            current_chapter = {
                "name": clean_name(m.group('name')),
                "sections": []
            }
            current_system["chapters"].append(current_chapter)
            i += 1
            continue

        # Check for section header
        m = SECTION_RE.match(line)
        if m and current_chapter is not None:
            name = clean_name(m.group('name'))
            page = extract_page(line)
            current_chapter["sections"].append({
                "name": name,
                "type": classify_type(name),
                "start_page": page,
            })
            i += 1
            continue

        # Check for appendix
        m = APPENDIX_RE.match(line)
        if m and current_chapter is not None:
            name = clean_name(m.group('name'))
            page = extract_page(line)
            current_chapter["sections"].append({
                "name": name,
                "type": classify_type(name),
                "start_page": page,
            })
            i += 1
            continue

        # Check for sub-section (only if no section header on this line)
        m = SUBSECTION_RE.match(line)
        if m and current_chapter is not None:
            name = clean_name(m.group('name'))
            page = extract_page(line)
            current_chapter["sections"].append({
                "name": name,
                "type": classify_type(name),
                "start_page": page,
            })
            i += 1
            continue

        i += 1

    # Don't forget the last system
    if current_system:
        systems.append(current_system)

    # Post-process: handle chapters with no subsections (single-disease chapters)
    for system in systems:
        new_chapters = []
        for chapter in system["chapters"]:
            # If chapter has no sections, it might be a single-disease chapter
            if not chapter["sections"]:
                # Check if chapter name looks like a disease (not "总论" etc.)
                if classify_type(chapter["name"]) == "disease":
                    # Find the original line to extract page number
                    chapter_page = None
                    for line in lines:
                        if chapter["name"] in line and '章' in line:
                            chapter_page = extract_page(line)
                            break
                    chapter["sections"].append({
                        "name": chapter["name"],
                        "type": "disease",
                        "start_page": chapter_page,
                    })
            if chapter["sections"] or chapter["name"] in ["总论", "概述"]:
                new_chapters.append(chapter)
        system["chapters"] = new_chapters

    # Build final TOC
    final_toc = {"systems": systems}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_toc, f, ensure_ascii=False, indent=2)

    total_kp = sum(
        len(sec)
        for sys in systems
        for chap in sys.get("chapters", [])
        for sec in chap.get("sections", [])
    )

    console.print(Panel.fit(
        f"[green]✓[/green] TOC saved to: {output_path}\n"
        f"[green]✓[/green] Systems: {len(systems)}\n"
        f"[green]✓[/green] Total knowledge points: {total_kp}",
        title="TOC Parsed (Local)",
        border_style="green",
    ))


if __name__ == "__main__":
    parse_toc_local(str(config.TEXT_MD), str(config.TOC_JSON))
