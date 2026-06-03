"""One-click runner for the MedLearn knowledge extraction pipeline."""

import argparse
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
import step1_pdf_to_markdown
import step2_parse_toc
import step3_split_knowledge
import step4_rule_based
import step5_validate
import step6_export

console = Console()

# Re-define steps cleanly
STEP_DEFS = {
    "step1": {
        "name": "PDF → Markdown",
        "func": step1_pdf_to_markdown.pdf_to_markdown,
        "args": lambda: (config.PDF_PATH, str(config.TEXT_MD), str(config.OUTPUT_DIR / "page_index.json")),
    },
    "step2": {
        "name": "Parse TOC",
        "func": step2_parse_toc.parse_toc_local,
        "args": lambda: (str(config.TEXT_MD), str(config.TOC_JSON)),
    },
    "step3": {
        "name": "Split Knowledge",
        "func": step3_split_knowledge.split_knowledge,
        "args": lambda: (str(config.TEXT_MD), str(config.TOC_JSON), str(config.BLOCKS_JSON)),
    },
    "step4": {
        "name": "Structurize (Rule-based)",
        "func": step4_rule_based.structurize_knowledge,
        "args": lambda: (str(config.BLOCKS_JSON), str(config.STRUCTURED_JSON)),
    },
    "step5": {
        "name": "Validate",
        "func": step5_validate.validate,
        "args": lambda: (str(config.STRUCTURED_JSON), str(config.REVIEW_SAMPLE_JSON)),
    },
    "step6": {
        "name": "Export",
        "func": step6_export.export,
        "args": lambda: (str(config.STRUCTURED_JSON), str(config.KNOWLEDGE_NODES_JSON), str(config.REPORT_MD)),
    },
}


def main():
    parser = argparse.ArgumentParser(description="MedLearn Knowledge Extractor")
    parser.add_argument("--pdf", default=None, help="Path to the PDF file")
    parser.add_argument("--from", dest="from_step", default="step1", help="Start from step (step1-step6)")
    args = parser.parse_args()

    if args.pdf:
        config.PDF_PATH = args.pdf

    start_step = args.from_step.lower().strip()
    if start_step not in STEP_DEFS:
        console.print(f"[bold red]❌ Invalid step: {start_step}")
        return

    console.rule("[bold green]MedLearn Knowledge Extractor Pipeline")
    console.print(f"📁 Output directory: {config.OUTPUT_DIR}")
    console.print(f"📄 PDF path: {config.PDF_PATH}")
    console.print(f"🤖 LLM provider: {config.LLM_PROVIDER}")
    console.print(f"🔧 Start from: {start_step}")
    console.print("")

    start_time = time.time()
    step_times = []

    for step_key in ["step1", "step2", "step3", "step4", "step5", "step6"]:
        if step_key < start_step:
            continue

        step_def = STEP_DEFS[step_key]
        step_start = time.time()

        try:
            step_def["func"](*step_def["args"]())
        except Exception as exc:
            console.print(f"[bold red]❌ Step {step_key} failed: {exc}")
            raise

        step_elapsed = time.time() - step_start
        step_times.append((step_def["name"], step_elapsed))

    total_elapsed = time.time() - start_time

    # Summary table
    table = Table(title="Pipeline Summary")
    table.add_column("Step", style="cyan")
    table.add_column("Time", style="magenta")
    for name, elapsed in step_times:
        table.add_row(name, f"{elapsed:.1f}s")
    table.add_row("[bold]Total[/bold]", f"[bold]{total_elapsed:.1f}s[/bold]")

    console.print("")
    console.print(table)

    console.print(Panel.fit(
        f"[green]✓[/green] All steps completed!\n"
        f"[green]✓[/green] Output: {config.OUTPUT_DIR}\n"
        f"[green]✓[/green] Total time: {total_elapsed:.1f}s",
        title="Pipeline Complete",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
