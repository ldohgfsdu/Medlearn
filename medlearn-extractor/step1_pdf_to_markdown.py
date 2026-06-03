"""Step 1: Convert PDF to Markdown using PyMuPDF, with page index."""

import json
import sys

import fitz  # PyMuPDF
from rich.console import Console
from rich.panel import Panel

import config

console = Console()


def pdf_to_markdown(pdf_path: str, output_path: str, index_path: str) -> None:
    """Convert a PDF file to Markdown and save it, also build a page offset index."""
    console.rule("[bold blue]Step 1: PDF → Markdown")
    console.print(f"📄 PDF path: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
        total = len(doc)
        console.print(f"📖 Total pages: {total}")

        page_index = {}  # page_num -> line_offset
        line_offset = 0

        with open(output_path, "w", encoding="utf-8") as f:
            for page_num in range(1, total + 1):
                page = doc.load_page(page_num - 1)
                text = page.get_text()
                header = f"\n\n--- Page {page_num} ---\n\n"
                page_index[page_num] = line_offset + header.count("\n")
                f.write(header)
                line_offset += header.count("\n")
                f.write(text)
                line_offset += text.count("\n")
                if page_num % 50 == 0:
                    console.print(f"  Processed {page_num}/{total} pages...")
        doc.close()
    except Exception as exc:
        console.print(f"[bold red]❌ Failed to convert PDF: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Save page index
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(page_index, f, ensure_ascii=False, indent=2)

    # Read back to count
    with open(output_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    char_count = len(md_text)
    line_count = md_text.count("\n")

    console.print(Panel.fit(
        f"[green]✓[/green] Markdown saved to: {output_path}\n"
        f"[green]✓[/green] Page index saved to: {index_path}\n"
        f"[green]✓[/green] Characters: {char_count:,}\n"
        f"[green]✓[/green] Lines: {line_count:,}",
        title="Conversion Complete",
        border_style="green",
    ))


if __name__ == "__main__":
    pdf_to_markdown(
        config.PDF_PATH,
        str(config.TEXT_MD),
        str(config.OUTPUT_DIR / "page_index.json"),
    )
