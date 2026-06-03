"""Step 3: Split knowledge points from full text using textbook page numbers.

Builds a mapping from textbook page numbers to PDF page numbers,
because the TOC uses textbook pages while the markdown uses PDF pages.
"""

import json
import re

from rich.console import Console
from rich.panel import Panel

import config

console = Console()


def build_textbook_page_map(md_text: str) -> dict[int, int]:
    """Build a mapping: textbook_page_number -> pdf_page_number.

    PDF text contains both "--- Page N ---" (PDF page) and the textbook
    page number immediately after (as a standalone number on its own line).
    """
    mapping = {}
    for match in re.finditer(r"--- Page (\d+) ---", md_text):
        pdf_page = int(match.group(1))
        chunk_start = match.end()
        chunk = md_text[chunk_start:chunk_start + 60]
        m = re.search(r"^\s*(\d{1,4})\s*\n", chunk, re.MULTILINE)
        if m:
            textbook_page = int(m.group(1))
            if 1 <= textbook_page <= 2000:
                mapping[textbook_page] = pdf_page
    return mapping


def extract_text_by_textbook_pages(
    md_text: str,
    page_map: dict[int, int],
    textbook_start: int,
    textbook_end: int,
) -> str:
    """Extract text between textbook_start and textbook_end pages,
    using the mapping to find actual PDF pages."""
    page_markers = {}
    for match in re.finditer(r"--- Page (\d+) ---", md_text):
        page_markers[int(match.group(1))] = match.start()

    pdf_start = None
    pdf_end = None

    for tb_page in range(textbook_start, textbook_end + 20):
        if tb_page in page_map:
            pdf_start = page_map[tb_page]
            break

    if pdf_start is None:
        for tb_page in range(textbook_start, max(1, textbook_start - 10), -1):
            if tb_page in page_map:
                pdf_start = page_map[tb_page]
                break

    if pdf_start is None:
        return ""

    for tb_page in range(textbook_end, textbook_end + 30):
        if tb_page in page_map:
            pdf_page = page_map[tb_page]
            if pdf_page + 1 in page_markers:
                pdf_end = page_markers[pdf_page + 1]
            elif pdf_page in page_markers:
                pdf_end = page_markers.get(pdf_page + 1, len(md_text))
            break

    if pdf_end is None:
        for pdf_num in sorted(page_markers.keys()):
            if pdf_num > page_map.get(textbook_start, 0):
                pdf_end = page_markers[pdf_num]
                break
        if pdf_end is None:
            pdf_end = len(md_text)

    if pdf_start not in page_markers:
        return ""

    start_pos = page_markers[pdf_start]
    return md_text[start_pos:pdf_end].strip()


def split_knowledge(md_path: str, toc_path: str, output_path: str) -> None:
    """Read full text and TOC, extract each knowledge point's text by textbook page range."""
    console.rule("[bold blue]Step 3: Split Knowledge Points (Local Page-based)")

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    with open(toc_path, "r", encoding="utf-8") as f:
        toc = json.load(f)

    page_map = build_textbook_page_map(md_text)
    console.print(f"📖 Built textbook→PDF page mapping: {len(page_map)} pages")
    if page_map:
        sample = sorted(page_map.items())[:5]
        console.print(f"   Sample: {[(tb, f'PDF{pdf}') for tb, pdf in sample]}")

    all_kps = []
    for sys in toc.get("systems", []):
        for chap in sys.get("chapters", []):
            for sec in chap.get("sections", []):
                sec["_system"] = sys["name"]
                sec["_chapter"] = chap["name"]
                all_kps.append(sec)

    all_kps.sort(key=lambda x: x.get("start_page") or 0)

    console.print(f"🔍 Total knowledge points to split: {len(all_kps)}")

    for i, kp in enumerate(all_kps):
        start_page = kp.get("start_page")
        if start_page is None or start_page <= 0:
            kp["extracted_text"] = ""
            kp["status"] = "error: no start_page"
            continue

        if i + 1 < len(all_kps):
            next_page = all_kps[i + 1].get("start_page")
            end_page = next_page if next_page else start_page + 20
        else:
            end_page = start_page + 50

        text = extract_text_by_textbook_pages(md_text, page_map, start_page, end_page)
        if text:
            kp["extracted_text"] = text
            kp["pdf_start"] = page_map.get(start_page)
            kp["status"] = "success"
        else:
            kp["extracted_text"] = ""
            kp["status"] = f"error: no pdf page for textbook pages {start_page}-{end_page}"

    all_kps.sort(key=lambda x: (x.get("start_page") or 9999, x.get("_system", ""), x.get("_chapter", ""), x.get("name", "")))

    success = sum(1 for r in all_kps if r["status"] == "success")
    failed = len(all_kps) - success

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"knowledge_points": all_kps}, f, ensure_ascii=False, indent=2)

    console.print(Panel.fit(
        f"[green]✓[/green] Blocks saved to: {output_path}\n"
        f"[green]✓[/green] Success: {success}\n"
        f"[red]✗[/red] Failed: {failed}",
        title="Split Complete",
        border_style="green" if failed == 0 else "yellow",
    ))


if __name__ == "__main__":
    split_knowledge(str(config.TEXT_MD), str(config.TOC_JSON), str(config.BLOCKS_JSON))
