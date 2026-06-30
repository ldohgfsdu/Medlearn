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
class PendingReviewRecord:
    """An ambiguous source line pending human review.

    Body-font heading candidates and other ambiguous blocks are persisted
    here instead of being silently promoted to DocumentNode or discarded.
    The source text is preserved so no content is lost.
    """

    raw_anchor: str
    pdf_page: int
    raw_block_index: int
    raw_line_index: int | str
    line_text: str
    marker: str | None
    font_bucket: str | None
    first_font: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_anchor": self.raw_anchor,
            "pdf_page": self.pdf_page,
            "raw_block_index": self.raw_block_index,
            "raw_line_index": self.raw_line_index,
            "line_text": self.line_text,
            "marker": self.marker,
            "font_bucket": self.font_bucket,
            "first_font": self.first_font,
            "reason": self.reason,
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
    pending_reviews: list[PendingReviewRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "textbook_version_id": self.textbook_version_id,
            "scope_id": self.scope_id,
            "catalog_path": self.catalog_path,
            "nodes": [n.to_dict() for n in self.nodes],
            "content_blocks": [b.to_dict() for b in self.content_blocks],
            "pending_reviews": [p.to_dict() for p in self.pending_reviews],
        }


# ---------------------------------------------------------------------------
# Per-scope transition profile
# ---------------------------------------------------------------------------

@dataclass
class ScopeTransitionProfile:
    """Defines marker hierarchy levels for a specific scope.

    The level is used to find the parent node (the nearest stack node
    with a strictly lower level). Depth is always derived as
    parent.depth + 1, never hardcoded from the level.

    This profile is verified only for the asthma and tuberculosis golden
    scopes. Other scopes require a human-approved transition table.
    """

    marker_levels: dict[str, int]

    def level_of(self, marker: str | None) -> int | None:
        if marker is None:
            return None
        return self.marker_levels.get(marker)

    def find_parent(self, stack: list["DocumentNode"], new_level: int) -> "DocumentNode | None":
        """Find the nearest stack node with level strictly below new_level."""
        for node in reversed(stack):
            node_level = self.marker_levels.get(node.marker_kind)
            if node_level is not None and node_level < new_level:
                return node
        return None


# Verified transition profile for asthma + tuberculosis golden scopes.
GOLDEN_SCOPE_PROFILE = ScopeTransitionProfile(
    marker_levels={
        "chapter": 0,
        "bracket": 1,
        "chinese_parenthetical": 2,
        "arabic_dot": 3,
        "appendix": 1,
    }
)

# Markers that can produce DocumentNode entries when paired with heading font.
STACK_MARKERS = frozenset(GOLDEN_SCOPE_PROFILE.marker_levels.keys())

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
