"""Step 5: Validate structured knowledge points and generate review sample."""

import json
import random
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config

console = Console()

REQUIRED_DIMENSIONS = [
    "definition",
    "etiology",
    "pathogenesis",
    "pathology",
    "manifestation",
    "examination",
    "diagnosis",
    "treatment",
    "prognosis",
]

VINDICATE_DIMENSIONS = [
    "vascular",
    "infectious",
    "neoplastic",
    "drug",
    "inflammatory",
    "congenital",
    "autoimmune",
    "traumatic",
    "endocrine",
]


def validate_kp(kp: dict) -> list:
    """Validate a single knowledge point and return list of issues."""
    issues = []
    structured = kp.get("structured")
    if not structured or not isinstance(structured, dict):
        issues.append("Missing structured data")
        return issues

    # Check 9 dimensions — "教材中未详细展开" means textbook doesn't cover it, not an error
    for dim in REQUIRED_DIMENSIONS:
        val = structured.get(dim)
        if not val:
            issues.append(f"Dimension '{dim}' missing or empty")

    # Check vindicate
    vindicate = structured.get("vindicate", {})
    if not isinstance(vindicate, dict):
        issues.append("VINDICATE missing or not a dict")
    else:
        for vdim in VINDICATE_DIMENSIONS:
            if vdim not in vindicate or not vindicate[vdim]:
                issues.append(f"VINDICATE dimension '{vdim}' missing")

    # Check keywords
    keywords = structured.get("keywords", [])
    if len(keywords) < config.MIN_KEYWORDS:
        issues.append(f"Keywords count {len(keywords)} < {config.MIN_KEYWORDS}")

    # Check key_points
    key_points = structured.get("key_points", [])
    if len(key_points) < config.MIN_KEY_POINTS:
        issues.append(f"Key points count {len(key_points)} < {config.MIN_KEY_POINTS}")

    return issues


def validate(structured_path: str, review_sample_path: str) -> None:
    """Validate all knowledge points and generate review sample."""
    console.rule("[bold blue]Step 5: Validate Structured Data")

    with open(structured_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    kps = data.get("knowledge_points", [])
    total = len(kps)
    valid_count = 0
    issue_count = 0
    all_issues = []

    for kp in kps:
        if kp.get("structurize_status") != "success":
            continue
        issues = validate_kp(kp)
        if issues:
            issue_count += 1
            for issue in issues:
                all_issues.append({
                    "name": kp["name"],
                    "issue": issue,
                })
        else:
            valid_count += 1

    # Generate review sample (10% random)
    successful_kps = [kp for kp in kps if kp.get("structurize_status") == "success"]
    sample_size = max(1, int(len(successful_kps) * config.REVIEW_SAMPLE_RATE))
    review_sample = random.sample(successful_kps, min(sample_size, len(successful_kps)))

    with open(review_sample_path, "w", encoding="utf-8") as f:
        json.dump({"review_sample": review_sample}, f, ensure_ascii=False, indent=2)

    # Print report
    table = Table(title="Validation Report")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Total knowledge points", str(total))
    table.add_row("Successfully structured", str(len(successful_kps)))
    table.add_row("Fully valid", str(valid_count))
    table.add_row("With issues", str(issue_count))
    table.add_row("Review sample size", str(len(review_sample)))

    console.print(table)
    console.print(Panel.fit(
        f"[green]✓[/green] Review sample saved to: {review_sample_path}",
        title="Validation Complete",
        border_style="green",
    ))

    if all_issues:
        console.print(f"[yellow]⚠ Top 10 issues:[/yellow]")
        for item in all_issues[:10]:
            console.print(f"  - {item['name']}: {item['issue']}")


if __name__ == "__main__":
    validate(str(config.STRUCTURED_JSON), str(config.REVIEW_SAMPLE_JSON))
