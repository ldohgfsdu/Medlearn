"""Evidence Artifact Contract — Phase 0 of EV1 pipeline.

Minimal deterministic object produced from PDF/manifest without LLM.
Each artifact represents one structural unit (paragraph, table, figure)
within a textbook section.

Design rules:
  - source_heading preserves the original textbook heading (display/evidence fidelity)
  - normalized_aspect is optional, for internal search/assessment only
  - No medical conclusions are generated here
  - IDs are deterministic (same input → same ID)
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from .text_layers import build_text_layers


ARTIFACT_TYPES = frozenset({"text_block", "table", "figure", "caption"})
VERIFICATION_STATES = frozenset({"source_verified", "source_uncertain"})


@dataclass(frozen=True)
class EvidenceLocator:
    """Where this artifact lives in the physical PDF."""
    page: int
    kind: str  # "paragraph" | "table" | "figure" | "caption"
    bbox: tuple[float, ...] | None = None  # (x0, y0, x1, y1) if available


@dataclass
class EvidenceArtifact:
    """One structural unit extracted deterministically from a PDF section.

    This is the minimum object the EV1 pipeline produces before any LLM call.
    """
    # Identity
    id: str                           # stable SHA256(textbook_id + section_key + source_order)
    textbook_id: str                  # e.g. "internal-medicine-10"
    book_id: str                      # same as textbook_id for compatibility

    # Location
    part_title: str                   # e.g. "第四篇 消化系统疾病"
    section_title: str                # e.g. "第四章 胃炎"
    page_start: int
    page_end: int

    # Content classification
    source_heading: str               # original textbook heading (display/evidence fidelity)
    normalized_aspect: str | None     # optional, for internal search only
    source_order: int                 # sequential within section

    # Artifact payload
    artifact_type: str                # "text_block" | "table" | "figure" | "caption"
    raw_text: str                     # verbatim from PDF, no LLM rewriting

    # Provenance
    locator: EvidenceLocator | None = None
    checksum: str = ""                # SHA256(raw_text)
    verification_state: str = "source_verified"

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def canonical_text(self) -> str:
        """Normalized source text without mutating the evidence payload."""
        return build_text_layers(self.raw_text).canonical_text

    @property
    def display_text(self) -> str:
        """Presentation text derived deterministically from ``raw_text``."""
        return build_text_layers(self.raw_text).display_text

    def __post_init__(self) -> None:
        if not self.checksum and self.raw_text:
            # Can't modify frozen dataclass after init, so this is set by factory
            pass

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.locator:
            d["locator"] = asdict(self.locator)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceArtifact:
        payload = dict(data)
        loc_data = payload.pop("locator", None)
        locator = EvidenceLocator(**loc_data) if loc_data else None
        return cls(locator=locator, **payload)


def stable_artifact_id(
    textbook_id: str,
    part_title: str,
    section_title: str,
    source_order: int,
) -> str:
    """Generate deterministic artifact ID from section + order."""
    key = f"{textbook_id}\0{part_title}\0{section_title}\0{source_order}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return f"ev1-{digest}"


def content_checksum(text: str) -> str:
    """SHA256 of raw text for dedup."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def make_artifact(
    *,
    textbook_id: str,
    book_id: str,
    part_title: str,
    section_title: str,
    source_heading: str,
    normalized_aspect: str | None,
    source_order: int,
    artifact_type: str,
    raw_text: str,
    page_start: int,
    page_end: int,
    locator: EvidenceLocator | None = None,
    verification_state: str = "source_verified",
    metadata: dict[str, Any] | None = None,
) -> EvidenceArtifact:
    """Factory with auto-generated ID and checksum."""
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(f"Invalid artifact_type: {artifact_type}")
    if verification_state not in VERIFICATION_STATES:
        raise ValueError(f"Invalid verification_state: {verification_state}")

    return EvidenceArtifact(
        id=stable_artifact_id(textbook_id, part_title, section_title, source_order),
        textbook_id=textbook_id,
        book_id=book_id,
        part_title=part_title,
        section_title=section_title,
        page_start=page_start,
        page_end=page_end,
        source_heading=source_heading,
        normalized_aspect=normalized_aspect,
        source_order=source_order,
        artifact_type=artifact_type,
        raw_text=raw_text,
        locator=locator,
        checksum=content_checksum(raw_text),
        verification_state=verification_state,
        metadata=metadata or {},
    )
