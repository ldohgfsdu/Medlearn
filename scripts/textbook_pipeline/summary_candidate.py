"""Review-gated editorial summary candidates.

Extractive ``SynthesizedItem`` objects remain the only automatically verifiable
organized copy.  This module gives abstractive summaries a separate contract so
they cannot masquerade as verbatim textbook evidence or become publishable
without a qualified review decision.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from .paragraph_reconstruction import (
    classify_expanded_content_risk,
    loose_contains,
)

if TYPE_CHECKING:
    from .evidence_artifact import EvidenceArtifact


SummaryRiskClass = Literal["standard", "high_risk"]
SummaryVerdict = Literal["needs_review", "rejected"]


@dataclass(frozen=True)
class SummaryEvidenceRef:
    artifact_id: str
    evidence_text: str


@dataclass
class EditorialSummaryCandidate:
    textbook_id: str
    section_id: str
    title: str
    summary_text: str
    evidence_refs: list[SummaryEvidenceRef]
    created_by: str
    evidence_version: str = "1"
    model_version: str = ""
    prompt_version: str = ""
    rule_version: str = "1"
    candidate_id: str = ""
    risk_class: SummaryRiskClass = "standard"
    review_state: SummaryVerdict = "needs_review"
    publication_state: Literal["hidden"] = "hidden"
    verification_notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.candidate_id:
            source_ids = "\0".join(ref.artifact_id for ref in self.evidence_refs)
            payload = (
                f"{self.textbook_id}\0{self.section_id}\0{self.title}"
                f"\0{self.summary_text}\0{source_ids}"
                f"\0{self.evidence_version}\0{self.model_version}"
                f"\0{self.prompt_version}\0{self.rule_version}"
            )
            self.candidate_id = (
                "summary-"
                + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
            )

    @property
    def source_artifact_ids(self) -> list[str]:
        return list(dict.fromkeys(ref.artifact_id for ref in self.evidence_refs))


@dataclass(frozen=True)
class SummaryCandidateEvaluation:
    verdict: SummaryVerdict
    source_integrity: bool
    evidence_integrity: bool
    semantic_review_required: bool
    eligible_for_organized_display: bool
    reasons: tuple[str, ...]


def evaluate_summary_candidate(
    candidate: EditorialSummaryCandidate,
    artifacts: list[EvidenceArtifact],
) -> SummaryCandidateEvaluation:
    """Validate provenance and enforce the human-review publication boundary."""
    reasons: list[str] = []
    artifact_map = {artifact.id: artifact for artifact in artifacts}

    if not candidate.summary_text.strip():
        reasons.append("summary_text is empty")
    if not candidate.evidence_refs:
        reasons.append("summary has no evidence references")

    missing_ids = [
        artifact_id
        for artifact_id in candidate.source_artifact_ids
        if artifact_id not in artifact_map
    ]
    source_integrity = bool(candidate.evidence_refs) and not missing_ids
    if missing_ids:
        reasons.append(f"missing source artifacts: {missing_ids}")

    evidence_integrity = source_integrity
    for ref in candidate.evidence_refs:
        artifact = artifact_map.get(ref.artifact_id)
        if not artifact:
            continue
        if not ref.evidence_text.strip():
            evidence_integrity = False
            reasons.append(f"{ref.artifact_id}: empty evidence span")
            continue
        if not loose_contains(artifact.raw_text, ref.evidence_text):
            evidence_integrity = False
            reasons.append(
                f"{ref.artifact_id}: evidence span not found in raw source"
            )

    risk_note = classify_expanded_content_risk(
        candidate.summary_text,
        "\n".join(ref.evidence_text for ref in candidate.evidence_refs),
    )
    if risk_note:
        candidate.risk_class = "high_risk"
        reasons.append(risk_note)

    valid = (
        bool(candidate.summary_text.strip())
        and source_integrity
        and evidence_integrity
    )
    candidate.review_state = "needs_review" if valid else "rejected"
    candidate.publication_state = "hidden"
    candidate.verification_notes = list(dict.fromkeys(reasons))

    return SummaryCandidateEvaluation(
        verdict=candidate.review_state,
        source_integrity=source_integrity,
        evidence_integrity=evidence_integrity,
        semantic_review_required=True,
        eligible_for_organized_display=False,
        reasons=tuple(candidate.verification_notes),
    )
