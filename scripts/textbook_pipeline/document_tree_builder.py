"""Document Tree builder — produces DocumentTree from a PDF scope.

Reuses the verified classification logic from heading_signal_auditor and
builds a heading stack to emit DocumentNode and ContentBlock records per
ADR-011 and docs/architecture/document_tree_splitter_spec.md.

Does NOT modify the production evidence_extractor. Does NOT touch the UI.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .document_tree import (
    ALLOWED_ORIGINS,
    ContentBlock,
    DocumentNode,
    DocumentTree,
    HeadingAnchor,
    MARKER_DEPTH,
    STACK_MARKERS,
    SourceAnchor,
)
from .heading_signal_auditor import (
    classify_line,
    compute_full_anchor_id,
    compute_raw_anchor,
    merge_chapter_continuations,
    scan_page,
)

TEXTBOOK_VERSION_ID = "internal-medicine-10"
CONTRACT_VERSION = "document_tree.v1"


class InvariantViolation(Exception):
    """Raised when a structural invariant (INV1-INV10) is violated."""


def _line_text_from_info(line_info: dict[str, Any]) -> str:
    return line_info.get("line_text", "").strip()


def build_scope_tree(
    pdf_path: Path,
    scope_config: dict[str, Any],
    pdf_checksum: str | None = None,
) -> DocumentTree:
    """Build a DocumentTree for a single scope.

    Args:
        pdf_path: Path to the source PDF.
        scope_config: Scope dict with scope_id, catalog_path,
            pdf_page_start_1based, pdf_page_end_1based.
        pdf_checksum: Precomputed SHA-256 of the PDF; computed if None.

    Returns:
        DocumentTree with nodes and content_blocks.
    """
    import fitz  # lazy import

    if pdf_checksum is None:
        pdf_checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    scope_id = scope_config["scope_id"]
    catalog_path = scope_config["catalog_path"]
    page_start = scope_config["pdf_page_start_1based"]
    page_end = scope_config["pdf_page_end_1based"]

    doc = fitz.open(str(pdf_path))

    # 1. Scan pages → raw line_info records
    all_lines: list[dict[str, Any]] = []
    for pn in range(page_start, page_end + 1):
        page = doc[pn - 1]
        page_lines = scan_page(page, pn)
        all_lines.extend(page_lines)
    doc.close()

    # 2. Classify + attach raw_anchor/anchor_id
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
            TEXTBOOK_VERSION_ID, scope_id, pdf_checksum, raw_anchor
        )
        classified.append({
            "raw_anchor": raw_anchor,
            "anchor_id": full_id,
            "pdf_page": line_info["pdf_page"],
            "raw_block_index": line_info["raw_block_index"],
            "raw_line_index": line_info["raw_line_index"],
            "line_text": _line_text_from_info(line_info),
            "classification": cls["classification"],
            "marker": cls["marker"],
            "font_bucket": cls.get("font_bucket"),
            "first_font": cls.get("first_font"),
            "first_size": cls.get("first_size"),
            "heading_text": cls.get("heading_text", ""),
            "body_text": cls.get("body_text", ""),
            "has_body_punct": cls.get("has_body_punct", False),
            "_spans": cls.get("_spans", line_info["spans"]),
        })

    # 3. Merge chapter continuation lines
    classified = merge_chapter_continuations(classified)

    # Strip private _spans
    for c in classified:
        c.pop("_spans", None)

    # 4. Build heading stack → DocumentNode + ContentBlock
    nodes: list[DocumentNode] = []
    content_blocks: list[ContentBlock] = []
    stack: list[DocumentNode] = []
    source_order = 0
    block_order = 0
    sibling_counters: dict[str | None, int] = {}

    for c in classified:
        classification = c["classification"]
        marker = c["marker"]

        # Page headers never produce nodes or content
        if classification == "page_header":
            continue

        # Heading candidate with a stack marker → new DocumentNode
        if (
            classification == "heading_candidate"
            and marker in STACK_MARKERS
        ):
            depth = MARKER_DEPTH[marker]
            # Pop stack to current depth
            while len(stack) > depth:
                stack.pop()
            parent = stack[-1] if stack else None
            parent_id = parent.id if parent else None

            sibling_key = parent_id
            sibling_order = sibling_counters.get(sibling_key, 0)
            sibling_counters[sibling_key] = sibling_order + 1

            heading_text = c["heading_text"]
            raw_line_index = c["raw_line_index"]
            merged_from = c.get("merged_from_lines")

            anchor = HeadingAnchor(
                pdf_page_number_1based=c["pdf_page"],
                raw_block_index=c["raw_block_index"],
                raw_line_index=raw_line_index,
                raw_anchor=c["raw_anchor"],
            )

            # source_title_raw: preserve original line text
            source_title_raw = c["line_text"]

            node = DocumentNode(
                id=c["anchor_id"],
                parent_id=parent_id,
                depth=depth,
                source_title=heading_text,
                source_title_raw=source_title_raw,
                marker_kind=marker,
                origin="explicit_marker",
                source_order=source_order,
                sibling_order=sibling_order,
                heading_anchor=anchor,
                merged_from_lines=merged_from,
            )
            nodes.append(node)
            stack.append(node)
            node.content_block_ids = []  # will fill below
            source_order += 1

            # If the heading line also has body text, emit a content block
            body_text = c.get("body_text", "")
            if body_text:
                cb_id = f"cb:{TEXTBOOK_VERSION_ID}:{scope_id}:{block_order}"
                cb = ContentBlock(
                    id=cb_id,
                    document_node_id=node.id,
                    block_type="text_block",
                    raw_text=body_text,
                    source_order=block_order,
                    source_anchor=SourceAnchor(
                        pdf_page_number_1based=c["pdf_page"],
                        raw_block_index=c["raw_block_index"],
                        raw_line_index=raw_line_index if isinstance(raw_line_index, int) else (merged_from[0] if merged_from else 0),
                    ),
                )
                content_blocks.append(cb)
                node.content_block_ids.append(cb_id)
                block_order += 1
            continue

        # Body lines → content block under current stack top
        if classification == "body" and stack:
            raw_text = c["line_text"]
            if not raw_text:
                continue
            # Skip body lines that are continuation fragments already merged
            # (merge_chapter_continuations removes them, but guard anyway)
            current_node = stack[-1]
            cb_id = f"cb:{TEXTBOOK_VERSION_ID}:{scope_id}:{block_order}"
            cb = ContentBlock(
                id=cb_id,
                document_node_id=current_node.id,
                block_type="text_block",
                raw_text=raw_text,
                source_order=block_order,
                source_anchor=SourceAnchor(
                    pdf_page_number_1based=c["pdf_page"],
                    raw_block_index=c["raw_block_index"],
                    raw_line_index=c["raw_line_index"] if isinstance(c["raw_line_index"], int) else 0,
                ),
            )
            content_blocks.append(cb)
            current_node.content_block_ids.append(cb_id)
            block_order += 1
            continue

        # Ambiguous heading_candidate with body/unknown font → pending_review
        # (does not enter the stack; recorded for human review)
        # These are intentionally skipped from the tree per spec §5.2.

    tree = DocumentTree(
        contract_version=CONTRACT_VERSION,
        textbook_version_id=TEXTBOOK_VERSION_ID,
        scope_id=scope_id,
        catalog_path=list(catalog_path),
        nodes=nodes,
        content_blocks=content_blocks,
    )

    # 5. Verify invariants
    verify_invariants(tree)

    return tree


def verify_invariants(tree: DocumentTree) -> None:
    """Verify structural invariants INV1-INV10 on the tree.

    Raises InvariantViolation on failure.
    """
    node_ids = {n.id for n in tree.nodes}
    node_order = {n.id: n.source_order for n in tree.nodes}

    # INV1: every content block belongs to an existing node
    for cb in tree.content_blocks:
        if cb.document_node_id not in node_ids:
            raise InvariantViolation(
                f"INV1: content block {cb.id} references missing node {cb.document_node_id}"
            )

    # INV2: parent_id is null or points to an earlier node; no cycles
    for n in tree.nodes:
        if n.parent_id is None:
            continue
        if n.parent_id not in node_ids:
            raise InvariantViolation(
                f"INV2: node {n.id} has dangling parent_id {n.parent_id}"
            )
        if node_order[n.parent_id] >= node_order[n.id]:
            raise InvariantViolation(
                f"INV2: node {n.id} (order {node_order[n.id]}) has parent "
                f"{n.parent_id} (order {node_order[n.parent_id]}) that appears later"
            )

    # INV3: origin, source_title_raw, heading_anchor present
    for n in tree.nodes:
        if n.origin not in ALLOWED_ORIGINS:
            raise InvariantViolation(
                f"INV3: node {n.id} has invalid origin {n.origin!r}"
            )
        if not n.source_title_raw:
            raise InvariantViolation(f"INV3: node {n.id} missing source_title_raw")
        if not n.heading_anchor.raw_anchor:
            raise InvariantViolation(f"INV3: node {n.id} missing heading_anchor")

    # INV6: source_order strictly increasing; sibling_order per parent increasing
    prev_order = -1
    for n in tree.nodes:
        if n.source_order <= prev_order:
            raise InvariantViolation(
                f"INV6: node {n.id} source_order {n.source_order} not > {prev_order}"
            )
        prev_order = n.source_order

    sibling_seen: dict[str | None, int] = {}
    for n in tree.nodes:
        key = n.parent_id
        if key not in sibling_seen:
            sibling_seen[key] = 0
        if n.sibling_order != sibling_seen[key]:
            raise InvariantViolation(
                f"INV6: node {n.id} sibling_order {n.sibling_order} != expected {sibling_seen[key]}"
            )
        sibling_seen[key] += 1

    # INV9: every node and block has a SourceAnchor
    for n in tree.nodes:
        if n.heading_anchor.pdf_page_number_1based <= 0:
            raise InvariantViolation(f"INV9: node {n.id} missing page in anchor")
    for cb in tree.content_blocks:
        if cb.source_anchor.pdf_page_number_1based <= 0:
            raise InvariantViolation(f"INV9: block {cb.id} missing page in anchor")

    # INV-content_block_ids: node.content_block_ids must reference existing blocks
    block_ids = {cb.id for cb in tree.content_blocks}
    for n in tree.nodes:
        for bid in n.content_block_ids:
            if bid not in block_ids:
                raise InvariantViolation(
                    f"node {n.id} references missing content block {bid}"
                )


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load a SourceScopeManifest JSON file."""
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def manifest_checksum(manifest: dict[str, Any]) -> str:
    """Compute the canonical manifest checksum (SHA-256 of canonical JSON)."""
    d = dict(manifest)
    d.pop("manifest_checksum", None)
    canon = json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def build_from_manifest(
    pdf_path: Path,
    manifest_path: Path,
) -> list[DocumentTree]:
    """Build DocumentTrees for all scopes in a manifest.

    Verifies manifest checksum before building.
    """
    manifest = load_manifest(manifest_path)
    stored = manifest.get("manifest_checksum", "")
    calc = manifest_checksum(manifest)
    if stored != calc:
        raise InvariantViolation(
            f"manifest checksum mismatch: stored={stored} calc={calc}"
        )

    pdf_checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    expected = manifest["source_identity"]["sha256"].lower()
    if pdf_checksum.lower() != expected:
        raise InvariantViolation(
            f"PDF checksum mismatch: file={pdf_checksum} manifest={expected}"
        )

    trees: list[DocumentTree] = []
    for scope in manifest["scopes"]:
        seg = scope["source_segments"][0]
        scope_config = {
            "scope_id": scope["scope_id"],
            "catalog_path": scope["catalog_path"],
            "pdf_page_start_1based": seg["pdf_page_start_1based"],
            "pdf_page_end_1based": seg["pdf_page_end_1based"],
        }
        tree = build_scope_tree(pdf_path, scope_config, pdf_checksum)
        trees.append(tree)
    return trees


# Default scope configs (for direct use without manifest file)
DEFAULT_SCOPES: list[dict[str, Any]] = [
    {
        "scope_id": "asthma",
        "catalog_path": ["第二篇", "第四章 支气管哮喘"],
        "pdf_page_start_1based": 62,
        "pdf_page_end_1based": 70,
    },
    {
        "scope_id": "tuberculosis",
        "catalog_path": ["第二篇", "第八章 肺结核"],
        "pdf_page_start_1based": 102,
        "pdf_page_end_1based": 116,
    },
]
