"""Versioned canonical document intermediate representation."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .evidence_artifact import EvidenceArtifact
from .text_layers import build_text_layers


IR_SCHEMA_VERSION = "document-ir.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PageIdentity:
    pdf_page_number: int
    printed_page_label: str | None = None
    width: float | None = None
    height: float | None = None


@dataclass(frozen=True)
class SourceScopeManifest:
    id: str
    textbook_version_id: str
    source_pdf_sha256: str
    page_start: int
    page_end: int
    review_state: Literal["draft", "reviewed", "approved", "invalidated"] = "draft"
    reviewer_id: str | None = None
    reviewed_at: str | None = None


@dataclass(frozen=True)
class RawSpan:
    """Pre-classification parser span used as the sole anchor fingerprint input."""

    pdf_page_number: int
    block_index: int
    line_index: int
    spans: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class SourceAnchor:
    id: str
    raw_anchor: str
    source_pdf_sha256: str
    span_payload_sha256: str


@dataclass(frozen=True)
class DocumentNode:
    id: str
    parent_id: str | None
    source_title: str
    source_title_raw: str
    marker_kind: Literal[
        "chapter",
        "bracket",
        "chinese_parenthetical",
        "arabic_dot",
        "arabic_parenthetical",
        "arabic_right_parenthesis",
        "appendix",
        "layout",
    ]
    origin: Literal["explicit_marker", "layout_heading", "manual_confirmed"]
    source_order: int
    sibling_order: int
    heading_anchor_id: str
    content_block_ids: tuple[str, ...]


@dataclass(frozen=True)
class DocumentBlock:
    id: str
    raw_anchor: str
    node_id: str | None
    kind: Literal["text_block", "table", "figure", "caption"]
    source_order: int
    page: PageIdentity
    bbox: tuple[float, float, float, float] | None
    coordinate_space: Literal["pdf_top_left"] | None
    raw_text: str
    raw_text_sha256: str
    canonical_text: str
    display_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalDocumentIR:
    textbook_version_id: str
    scope_id: str
    source_pdf_sha256: str
    blocks: list[DocumentBlock]
    nodes: list[DocumentNode] = field(default_factory=list)
    scope_manifest: SourceScopeManifest | None = None
    schema_version: str = IR_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _span_payload(artifact: EvidenceArtifact) -> str:
    locator = artifact.locator
    payload = {
        "page": artifact.page_start,
        "source_order": artifact.source_order,
        "kind": artifact.artifact_type,
        "bbox": list(locator.bbox) if locator and locator.bbox else None,
        "raw_text": artifact.raw_text,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_source_anchor(
    raw_span: RawSpan,
    *,
    textbook_version_id: str,
    scope_id: str,
    source_pdf_sha256: str,
) -> SourceAnchor:
    """Build an ADR-011 anchor from classification-independent parser spans."""
    payload = json.dumps(
        list(raw_span.spans),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    payload_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    raw_anchor = (
        f"p{raw_span.pdf_page_number}:b{raw_span.block_index}:"
        f"l{raw_span.line_index}:{payload_sha256[:32]}"
    )
    return SourceAnchor(
        id=(
            f"dt:{textbook_version_id}:{scope_id}:"
            f"{source_pdf_sha256}:{raw_anchor}"
        ),
        raw_anchor=raw_anchor,
        source_pdf_sha256=source_pdf_sha256,
        span_payload_sha256=payload_sha256,
    )


def raw_span_to_document_block(
    raw_span: RawSpan,
    *,
    textbook_version_id: str,
    scope_id: str,
    source_pdf_sha256: str,
    node_id: str,
    kind: Literal["text_block", "table", "figure", "caption"],
    source_order: int,
    raw_text: str,
    printed_page_label: str | None = None,
    page_width: float | None = None,
    page_height: float | None = None,
) -> DocumentBlock:
    anchor = build_source_anchor(
        raw_span,
        textbook_version_id=textbook_version_id,
        scope_id=scope_id,
        source_pdf_sha256=source_pdf_sha256,
    )
    bbox_value = raw_span.spans[0].get("bbox") if raw_span.spans else None
    bbox = tuple(bbox_value) if isinstance(bbox_value, (list, tuple)) and len(bbox_value) == 4 else None
    layers = build_text_layers(raw_text)
    return DocumentBlock(
        id=anchor.id,
        raw_anchor=anchor.raw_anchor,
        node_id=node_id,
        kind=kind,
        source_order=source_order,
        page=PageIdentity(
            pdf_page_number=raw_span.pdf_page_number,
            printed_page_label=printed_page_label,
            width=page_width,
            height=page_height,
        ),
        bbox=bbox,
        coordinate_space="pdf_top_left" if bbox else None,
        raw_text=layers.raw_text,
        raw_text_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        canonical_text=layers.canonical_text,
        display_text=layers.display_text,
        metadata={
            "anchor_kind": "pre_classification_raw_span",
            "span_payload_sha256": anchor.span_payload_sha256,
        },
    )


def artifact_to_document_block(
    artifact: EvidenceArtifact,
    *,
    textbook_version_id: str,
    scope_id: str,
    source_pdf_sha256: str,
    node_id: str | None = None,
    printed_page_label: str | None = None,
    page_width: float | None = None,
    page_height: float | None = None,
) -> DocumentBlock:
    """Compatibility adapter only; production anchors must use ``RawSpan``."""
    fingerprint = hashlib.sha256(_span_payload(artifact).encode("utf-8")).hexdigest()[:32]
    raw_anchor = f"p{artifact.page_start}:b{artifact.source_order}:l0:{fingerprint}"
    block_id = (
        f"dt:{textbook_version_id}:{scope_id}:{source_pdf_sha256}:{raw_anchor}"
    )
    locator = artifact.locator
    layers = build_text_layers(artifact.raw_text)
    return DocumentBlock(
        id=block_id,
        raw_anchor=raw_anchor,
        node_id=node_id,
        kind=artifact.artifact_type,
        source_order=artifact.source_order,
        page=PageIdentity(
            pdf_page_number=artifact.page_start,
            printed_page_label=printed_page_label,
            width=page_width,
            height=page_height,
        ),
        bbox=tuple(locator.bbox) if locator and locator.bbox else None,
        coordinate_space="pdf_top_left" if locator and locator.bbox else None,
        raw_text=layers.raw_text,
        raw_text_sha256=hashlib.sha256(layers.raw_text.encode("utf-8")).hexdigest(),
        canonical_text=layers.canonical_text,
        display_text=layers.display_text,
        metadata={"legacy_evidence_artifact_id": artifact.id},
    )


def validate_document_ir(document: CanonicalDocumentIR) -> list[str]:
    errors: list[str] = []
    if document.schema_version != IR_SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if not SHA256_RE.fullmatch(document.source_pdf_sha256):
        errors.append("source_pdf_sha256 must be a full lowercase SHA-256")
    ids = [block.id for block in document.blocks]
    if len(ids) != len(set(ids)):
        errors.append("duplicate block ids")
    orders = [block.source_order for block in document.blocks]
    if orders != sorted(orders):
        errors.append("blocks must be in source_order")
    node_ids = {node.id for node in document.nodes}
    if len(node_ids) != len(document.nodes):
        errors.append("duplicate document node ids")
    nodes_by_id = {node.id: node for node in document.nodes}
    block_ids = set(ids)
    if document.scope_manifest is None:
        errors.append("scope_manifest is required")
    else:
        manifest = document.scope_manifest
        if manifest.textbook_version_id != document.textbook_version_id:
            errors.append("scope manifest textbook version mismatch")
        if manifest.source_pdf_sha256 != document.source_pdf_sha256:
            errors.append("scope manifest source checksum mismatch")
        if manifest.page_start < 1 or manifest.page_end < manifest.page_start:
            errors.append("scope manifest page range is invalid")
        if manifest.review_state in {"reviewed", "approved"} and (
            not manifest.reviewer_id or not manifest.reviewed_at
        ):
            errors.append("reviewed scope manifest requires reviewer metadata")

    sibling_orders: dict[str | None, dict[int, str]] = {}
    for node in document.nodes:
        if node.parent_id and node.parent_id not in node_ids:
            errors.append(f"{node.id}: dangling parent")
        visited: set[str] = set()
        current: str | None = node.id
        while current is not None and current in nodes_by_id:
            if current in visited:
                errors.append(f"{node.id}: parent_id cycle detected")
                break
            visited.add(current)
            current = nodes_by_id[current].parent_id
        if node.origin not in {
            "explicit_marker", "layout_heading", "manual_confirmed"
        }:
            errors.append(f"{node.id}: prohibited structural origin")
        if node.heading_anchor_id not in block_ids:
            errors.append(f"{node.id}: missing heading anchor block")
        for block_id in node.content_block_ids:
            if block_id not in block_ids:
                errors.append(f"{node.id}: dangling content block")
        parent_key = node.parent_id
        bucket = sibling_orders.setdefault(parent_key, {})
        if node.sibling_order in bucket:
            errors.append(
                f"{node.id}: duplicate sibling_order {node.sibling_order} "
                f"under parent {parent_key} (already used by "
                f"{bucket[node.sibling_order]})"
            )
        else:
            bucket[node.sibling_order] = node.id

    ownership: dict[str, int] = {block_id: 0 for block_id in block_ids}
    for node in document.nodes:
        for block_id in set((*node.content_block_ids, node.heading_anchor_id)):
            if block_id in ownership:
                ownership[block_id] += 1
    for block_id, owner_count in ownership.items():
        if owner_count != 1:
            errors.append(f"{block_id}: expected exactly one node owner, got {owner_count}")

    for block in document.blocks:
        if not block.id.startswith(
            f"dt:{document.textbook_version_id}:{document.scope_id}:"
            f"{document.source_pdf_sha256}:"
        ):
            errors.append(f"{block.id}: identity does not bind document scope")
        if block.page.pdf_page_number < 1:
            errors.append(f"{block.id}: invalid pdf page number")
        if block.bbox and block.coordinate_space is None:
            errors.append(f"{block.id}: bbox missing coordinate_space")
        if block.bbox and (block.page.width is None or block.page.height is None):
            errors.append(f"{block.id}: bbox missing page dimensions")
        expected_checksum = hashlib.sha256(block.raw_text.encode("utf-8")).hexdigest()
        if block.raw_text_sha256 != expected_checksum:
            errors.append(f"{block.id}: raw_text checksum mismatch")
        if block.node_id is None or block.node_id not in node_ids:
            errors.append(f"{block.id}: block is not owned by a document node")
        if block.node_id in node_ids:
            owner = next(node for node in document.nodes if node.id == block.node_id)
            if block.id not in owner.content_block_ids and block.id != owner.heading_anchor_id:
                errors.append(f"{block.id}: node ownership is not reciprocal")
    return errors
