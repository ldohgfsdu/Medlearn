"""Step 6: Export structured data to WeChat cloud database format.

Generates two output formats:
1. WeChat 9-dimension format (knowledge_nodes.json) — for direct cloud DB import
2. Mini-program KnowledgeNode format (extractedKnowledgeNodes.json) — for seed data
"""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config

console = Console()

REQUIRED_DIMENSIONS = [
    "definition", "etiology", "pathogenesis", "pathology",
    "manifestation", "examination", "diagnosis", "treatment", "prognosis",
]

VINDICATE_DIMENSIONS = [
    "vascular", "infectious", "neoplastic", "drug", "inflammatory",
    "congenital", "autoimmune", "traumatic", "endocrine",
]

DIMENSION_LABELS = {
    "definition": "📖 定义",
    "etiology": "🔬 病因",
    "pathogenesis": "⚙️ 发病机制",
    "pathology": "🔍 病理",
    "manifestation": "🩺 临床表现",
    "examination": "📊 辅助检查",
    "diagnosis": "✅ 诊断标准",
    "treatment": "💊 治疗",
    "prognosis": "📈 预后",
}

VINDICATE_LABELS = {
    "vascular": "血管性",
    "infectious": "感染性",
    "neoplastic": "肿瘤性",
    "drug": "药物性",
    "inflammatory": "炎症性",
    "congenital": "先天性",
    "autoimmune": "自身免疫性",
    "traumatic": "创伤性",
    "endocrine": "内分泌性",
}

TYPE_MAP = {
    "disease": "disease",
    "symptom": "symptom",
    "syndrome": "disease",
    "basic": "concept",
}


def generate_id() -> str:
    return f"kn_{uuid.uuid4().hex[:8]}"


def generate_miniprogram_id(kp: dict) -> str:
    sys_name = kp.get("_system", "").replace(" ", "-")
    chap_name = kp.get("_chapter", "").replace(" ", "-")
    sec_name = kp.get("name", "").replace(" ", "-")
    return f"textbook-{sys_name}-{chap_name}-{sec_name}"[:120]


def build_content_markdown(structured: dict) -> str:
    """Build a clean markdown content string from 9 dimensions + VINDICATE."""
    parts = []
    for dim in REQUIRED_DIMENSIONS:
        val = structured.get(dim, "")
        if val and val != "教材中未详细展开":
            label = DIMENSION_LABELS.get(dim, dim)
            parts.append(f"{label}\n{val}")

    vindicate = structured.get("vindicate", {})
    if isinstance(vindicate, dict) and vindicate:
        vind_lines = ["\n🔬 鉴别诊断（VINDICATE）"]
        for vdim in VINDICATE_DIMENSIONS:
            val = vindicate.get(vdim, "")
            if val and val != "教材中未详细展开":
                label = VINDICATE_LABELS.get(vdim, vdim)
                vind_lines.append(f"- {label}：{val}")
        if len(vind_lines) > 1:
            parts.append("\n".join(vind_lines))

    return "\n\n".join(parts)


def build_knowledge_node(kp: dict, index: int) -> dict:
    """Convert to WeChat 9-dimension cloud database format."""
    structured = kp.get("structured", {})
    return {
        "_id": generate_id(),
        "order": index,
        "definition": structured.get("definition", ""),
        "etiology": structured.get("etiology", ""),
        "pathogenesis": structured.get("pathogenesis", ""),
        "pathology": structured.get("pathology", ""),
        "manifestation": structured.get("manifestation", ""),
        "examination": structured.get("examination", ""),
        "diagnosis": structured.get("diagnosis", ""),
        "treatment": structured.get("treatment", ""),
        "prognosis": structured.get("prognosis", ""),
        "vindicate": structured.get("vindicate", {v: "" for v in VINDICATE_DIMENSIONS}),
        "key_points": structured.get("key_points", []),
        "common_misconceptions": structured.get("common_misconceptions", []),
        "system": kp.get("_system", ""),
        "chapter": kp.get("_chapter", ""),
        "section": kp.get("name", ""),
        "startPage": kp.get("start_page"),
        "aliases": structured.get("aliases", []),
        "keywords": structured.get("keywords", []),
        "icon": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


def build_miniprogram_node(kp: dict, ts: int, index: int) -> dict:
    """Convert to mini-program KnowledgeNode format."""
    structured = kp.get("structured", {})
    sys_name = kp.get("_system", "")
    chap_name = kp.get("_chapter", "")
    sec_name = kp.get("name", "")
    kp_type = kp.get("type", "basic")
    node_type = TYPE_MAP.get(kp_type, "concept")

    content = build_content_markdown(structured)
    if not content:
        content = structured.get("definition", "")

    keywords = structured.get("keywords", [])
    aliases = structured.get("aliases", [])
    tags = list(dict.fromkeys([
        sys_name, chap_name, sec_name,
        "internal-medicine-10", "内科学", "第10版",
        *keywords[:5],
    ]))

    return {
        "id": generate_miniprogram_id(kp),
        "order": index,
        "type": node_type,
        "title": sec_name,
        "subject": f"内科学 - {sys_name}",
        "chapter": chap_name,
        "knowledgePath": [sys_name, chap_name],
        "content": content,
        "keyPoints": structured.get("key_points", []),
        "causalLinks": [],
        "relatedNodes": [],
        "difficulty": 2,
        "tags": tags,
        "source": "seed",
        "bookId": "internal-medicine-10",
        "textbook": "内科学",
        "edition": "第10版",
        "nodeSource": "segment-main",
        "inferred": False,
        "sourceSpan": {
            "pageStart": kp.get("start_page"),
            "pageEnd": None,
            "headingPath": [sys_name, chap_name, sec_name],
        },
        "generatedAt": ts,
        "createdAt": ts,
        "updatedAt": ts,
    }


def export(structured_path: str, nodes_path: str, report_path: str) -> None:
    """Export to multiple formats."""
    console.rule("[bold blue]Step 6: Export to WeChat & Mini-Program Format")

    with open(structured_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    kps = data.get("knowledge_points", [])
    nodes = []
    mp_nodes = []
    system_stats = {}
    field_coverage = {dim: 0 for dim in REQUIRED_DIMENSIONS}
    total_structured = 0
    now_ts = int(time.time() * 1000)

    for i, kp in enumerate(kps):
        if kp.get("structurize_status") != "success":
            continue
        total_structured += 1

        node = build_knowledge_node(kp, i)
        nodes.append(node)

        mp_node = build_miniprogram_node(kp, now_ts, i)
        mp_nodes.append(mp_node)

        sys_name = node["system"] or "Unknown"
        system_stats[sys_name] = system_stats.get(sys_name, 0) + 1

        for dim in REQUIRED_DIMENSIONS:
            val = node.get(dim, "")
            if val and val != "教材中未详细展开":
                field_coverage[dim] += 1

    # Write WeChat format
    with open(nodes_path, "w", encoding="utf-8") as f:
        json.dump({"knowledge_nodes": nodes}, f, ensure_ascii=False, indent=2)

    # Write mini-program format
    mp_path = str(Path(nodes_path).parent / "extractedKnowledgeNodes.json")
    with open(mp_path, "w", encoding="utf-8") as f:
        json.dump(mp_nodes, f, ensure_ascii=False, indent=2)

    # Generate report
    report_lines = [
        "# MedLearn Knowledge Extraction Report",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Overview",
        "",
        f"- Total knowledge points: {len(kps)}",
        f"- Successfully structured: {total_structured}",
        f"- WeChat nodes: {len(nodes)}",
        f"- Mini-program nodes: {len(mp_nodes)}",
        "",
        "## System Distribution",
        "",
        "| System | Count |",
        "|--------|-------|",
    ]
    for sys_name, count in sorted(system_stats.items(), key=lambda x: -x[1]):
        report_lines.append(f"| {sys_name} | {count} |")

    report_lines.extend([
        "",
        "## Field Completeness",
        "",
        "| Dimension | Filled | Rate |",
        "|-----------|--------|------|",
    ])
    for dim in REQUIRED_DIMENSIONS:
        filled = field_coverage[dim]
        rate = (filled / total_structured * 100) if total_structured else 0
        report_lines.append(f"| {dim} | {filled} | {rate:.1f}% |")

    overall_rate = (
        sum(field_coverage.values()) / (total_structured * len(REQUIRED_DIMENSIONS)) * 100
        if total_structured else 0
    )
    report_lines.extend([
        "",
        f"**Overall completeness: {overall_rate:.1f}%**",
        "",
        "## Output Files",
        "",
        f"- `{nodes_path}` — WeChat 9-dimension cloud database format",
        f"- `{mp_path}` — Mini-program KnowledgeNode JSON format",
    ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    # Console summary
    table = Table(title="Export Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("WeChat nodes exported", str(len(nodes)))
    table.add_row("Mini-program nodes exported", str(len(mp_nodes)))
    table.add_row("Systems", str(len(system_stats)))
    table.add_row("Overall completeness", f"{overall_rate:.1f}%")

    console.print(table)
    console.print(Panel.fit(
        f"[green]✓[/green] WeChat format: {nodes_path}\n"
        f"[green]✓[/green] Mini-program format: {mp_path}\n"
        f"[green]✓[/green] Report: {report_path}",
        title="Export Complete",
        border_style="green",
    ))


if __name__ == "__main__":
    export(str(config.STRUCTURED_JSON), str(config.KNOWLEDGE_NODES_JSON), str(config.REPORT_MD))
