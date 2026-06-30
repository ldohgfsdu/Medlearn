"""Document Tree v1 data structures.

Defines DocumentNode, ContentBlock, and DocumentTree per ADR-011 and
docs/architecture/document_tree_v1_contract.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HeadingAnchor:
    """Source anchor for a heading node."""

    pdf_page_number_1based: int
    raw_block_index: int
    raw_line_index: int | str  # int or "first-last" range for merged lines
    raw_anchor: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pdf_page_number_1based": self.pdf_page_number_1based,
            "raw_block_index": self.raw_block_index,
            "raw_line_index": self.raw_line_index,
            "raw_anchor": self.raw_anchor,
        }


@dataclass
class SourceAnchor:
    """Source anchor for a content block."""

    pdf_page_number_1based: int
    raw_block_index: int
    raw_line_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "pdf_page_number_1based": self.pdf_page_number_1based,
            "raw_block_index": self.raw_block_index,
            "raw_line_index": self.raw_line_index,
        }


@dataclass
class DocumentNode:
    """A node in the document tree."""

    id: str
    parent_id: str | None
    depth: int
    source_title: str
    source_title_raw: str
    marker_kind: str
    origin: str
    source_order: int
    sibling_order: int
    heading_anchor: HeadingAnchor
    content_block_ids: list[str] = field(default_factory=list)
    merged_from_lines: list[int] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "source_title": self.source_title,
            "source_title_raw": self.source_title_raw,
            "marker_kind": self.marker_kind,
            "origin": self.origin,
            "source_order": self.source_order,
            "sibling_order": self.sibling_order,
            "heading_anchor": self.heading_anchor.to_dict(),
            "content_block_ids": self.content_block_ids,
        }
        if self.merged_from_lines is not None:
            d["merged_from_lines"] = self.merged_from_lines
        return d


@dataclass
class ContentBlock:
    """A content block belonging to a document node."""

    id: str
    document_node_id: str
    block_type: str
    raw_text: str
    source_order: int
    source_anchor: SourceAnchor
    evidence_artifact_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_node_id": self.document_node_id,
            "block_type": self.block_type,
            "raw_text": self.raw_text,
            "source_order": self.source_order,
            "source_anchor": self.source_anchor.to_dict(),
            "evidence_artifact_ids": self.evidence_artifact_ids,
        }


@dataclass
class DocumentTree:
    """A document tree for a single scope."""

    contract_version: str
    textbook_version_id: str
    scope_id: str
    catalog_path: list[str]
    nodes: list[DocumentNode]
    content_blocks: list[ContentBlock]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "textbook_version_id": self.textbook_version_id,
            "scope_id": self.scope_id,
            "catalog_path": self.catalog_path,
            "nodes": [n.to_dict() for n in self.nodes],
            "content_blocks": [b.to_dict() for b in self.content_blocks],
        }


# Marker kind to depth mapping (verified for asthma + tuberculosis scopes only).
# Other scopes require per-scope Transition Rule Table approved by human review.
MARKER_DEPTH: dict[str, int] = {
    "chapter": 0,
    "bracket": 1,
    "chinese_parenthetical": 2,
    "arabic_dot": 3,
}

# Markers that produce DocumentNode entries (enter the heading stack).
STACK_MARKERS = frozenset(MARKER_DEPTH.keys())

# Markers that are numbered body and never produce nodes.
BODY_ONLY_MARKERS = frozenset({
    "arabic_parenthetical",
    "arabic_right_parenthesis",
})

ALLOWED_MARKER_KINDS = frozenset({
    "chapter", "bracket", "chinese_parenthetical", "arabic_dot",
    "arabic_parenthetical", "arabic_right_parenthesis", "appendix", "layout",
})

ALLOWED_ORIGINS = frozenset({
    "explicit_marker", "layout_heading", "manual_confirmed",
})
