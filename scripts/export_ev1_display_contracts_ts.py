"""Export display contracts to a frontend TypeScript fixture.

Reads from generated/display_contracts/ and snapshots the display
contract view model into a TypeScript constant that Expo can bundle at
build time.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_ROOT = PROJECT_ROOT / "generated" / "display_contracts" / "internal-medicine-10"
DEFAULT_OUTPUT = PROJECT_ROOT / "constants" / "ev1DisplayContracts.ts"
CHUNK_SIZE = 400_000
TEXTBOOK_TITLE = "内科学（第10版）"


def _section_id(path: Path) -> str:
    return path.name.removesuffix(".display_contract.json")


def _system_title(part_title: str) -> str:
    title = re.sub(r"^第[一二三四五六七八九十百零\d]+篇\s*", "", part_title or "")
    return title.strip() or part_title


def _page_bounds(nodes: list[dict[str, Any]]) -> tuple[int, int]:
    pages: list[int] = []
    for node in nodes:
        for item in node.get("evidence_items") or []:
            page_start = item.get("page_start")
            page_end = item.get("page_end")
            if isinstance(page_start, int):
                pages.append(page_start)
            if isinstance(page_end, int):
                pages.append(page_end)
    if not pages:
        return 0, 0
    return min(pages), max(pages)


def _compact_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "render_type": node.get("render_type"),
        "publication_state": node.get("publication_state"),
        "quality_badges": node.get("quality_badges") or [],
        "display": node.get("display") or {},
        "source_node_ids": node.get("source_node_ids") or [],
        "evidence_items": node.get("evidence_items") or [],
        **({"merge": node.get("merge")} if node.get("merge") else {}),
        **({"group": node.get("group")} if node.get("group") else {}),
    }


def build_fixture(input_root: Path, *, section_limit: int = 0, node_limit: int = 0) -> list[dict[str, Any]]:
    paths = sorted(input_root.glob("*.display_contract.json"))
    if section_limit > 0:
        paths = paths[:section_limit]

    sections: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        nodes = payload.get("nodes") or []
        if node_limit > 0:
            nodes = nodes[:node_limit]
        page_start, page_end = _page_bounds(nodes)
        part_title = payload.get("part_title") or ""
        sections.append(
            {
                "id": _section_id(path),
                "textbookId": payload.get("textbook_id"),
                "textbookTitle": TEXTBOOK_TITLE,
                "systemTitle": _system_title(part_title),
                "partTitle": part_title,
                "sectionTitle": payload.get("section_title"),
                "nodeCount": payload.get("node_count"),
                "pageStart": page_start,
                "pageEnd": page_end,
                "summary": payload.get("summary") or {},
                "nodes": [_compact_node(node) for node in nodes if isinstance(node, dict)],
            }
        )
    return sections


def write_ts_fixture(sections: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(sections, ensure_ascii=False, separators=(",", ":"))
    chunks = [body[index : index + CHUNK_SIZE] for index in range(0, len(body), CHUNK_SIZE)]
    chunk_dir = output_path.with_name(f"{output_path.stem}Chunks")
    chunk_dir.mkdir(parents=True, exist_ok=True)

    expected_names = {f"chunk{index:03d}.ts" for index in range(len(chunks))}
    for stale_path in chunk_dir.glob("chunk*.ts"):
        if stale_path.name not in expected_names:
            stale_path.unlink()

    imports: list[str] = []
    chunk_names: list[str] = []
    for index, chunk in enumerate(chunks):
        chunk_name = f"chunk{index:03d}"
        chunk_path = chunk_dir / f"{chunk_name}.ts"
        chunk_path.write_text(
            "// Auto-generated display-contract payload chunk. Do not edit.\n"
            f"export default {json.dumps(chunk, ensure_ascii=False)}\n",
            encoding="utf-8",
        )
        imports.append(
            f"import {chunk_name} from './{chunk_dir.name}/{chunk_name}'"
        )
        chunk_names.append(chunk_name)

    output_path.write_text(
        "// Auto-generated from generated/display_contracts. Do not edit medical content by hand.\n"
        "import type { Ev1DisplayContractSection } from '@/services/textbookService'\n\n"
        + "\n".join(imports)
        + "\n\n"
        + f"const EV1_DISPLAY_CONTRACT_JSON_CHUNKS = [{', '.join(chunk_names)}] as const\n\n"
        "export const EV1_DISPLAY_CONTRACT_SECTIONS = JSON.parse(\n"
        "  EV1_DISPLAY_CONTRACT_JSON_CHUNKS.join(''),\n"
        ") as Ev1DisplayContractSection[]\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--section-limit", type=int, default=0)
    parser.add_argument("--node-limit", type=int, default=0)
    args = parser.parse_args()

    sections = build_fixture(args.input_root, section_limit=args.section_limit, node_limit=args.node_limit)
    write_ts_fixture(sections, args.output)
    total_nodes = sum(len(section["nodes"]) for section in sections)
    print(f"[ev1-display-export] sections={len(sections)} nodes={total_nodes} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
