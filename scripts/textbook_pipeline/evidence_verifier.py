"""Evidence Verifier — Phase 2 of EV1 pipeline.

Deterministic verification of synthesized items against source artifacts.
No LLM calls. Pure string/logic checks.

Checks:
  1. evidence_substring: item.evidence must be substring of artifact.raw_text
  2. content_evidence_ratio: item.content overlap with item.evidence (warning only)
  3. page_valid: artifact.page within section page range
  4. aspect_consistent: item.aspect matches artifact.source_heading or normalized_aspect
  5. risk_downgrade: high-risk items → needs_review
  6. unsupported_terms: content terms not in evidence (warning only)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evidence_artifact import EvidenceArtifact
from .evidence_synthesis import SynthesizedItem


@dataclass
class VerificationResult:
    """Result of verifying one SynthesizedItem."""
    artifact_id: str
    item_index: int

    checks: dict[str, str] = field(default_factory=dict)  # check_name → "pass" | "fail" | "warning"
    verdict: str = "pending"  # "pass" | "needs_review" | "rejected"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "item_index": self.item_index,
            "checks": self.checks,
            "verdict": self.verdict,
            "reasons": self.reasons,
        }


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    import re
    # Remove all whitespace
    text = re.sub(r"\s+", "", text)
    # Normalize punctuation
    text = text.replace("，", ",").replace("。", ".").replace("；", ";")
    text = text.replace("（", "(").replace("）", ")")
    return text.lower()


def _normalize_loose(text: str) -> str:
    """Looser normalization: remove all whitespace and punctuation."""
    import re
    text = re.sub(r"[\s，。；：、！？…,.:;!?\-—（）()\[\]【】]", "", text)
    return text.lower()


def _tokenize(text: str) -> set[str]:
    """Simple character bigram tokenization for Chinese text."""
    text = _normalize_text(text)
    if len(text) < 2:
        return {text}
    return {text[i:i+2] for i in range(len(text) - 1)}


def check_evidence_substring(
    item: SynthesizedItem,
    artifact: EvidenceArtifact,
) -> tuple[bool, str]:
    """Check that item.evidence is a continuous substring of artifact.raw_text.

    Matching strategy (progressive relaxation):
    1. Exact substring (no normalization)
    2. Normalized whitespace/punctuation exact match
    3. Loose normalization match (all punctuation removed)
    4. Prefix match (first 20 chars)
    """
    if not item.evidence:
        return False, "evidence is empty"

    # 1. Exact substring
    if item.evidence.strip() in artifact.raw_text:
        return True, ""

    # 2. Normalized match
    norm_evidence = _normalize_text(item.evidence)
    norm_raw = _normalize_text(artifact.raw_text)
    if norm_evidence in norm_raw:
        return True, ""

    # 3. Loose normalization match (handles cross-block whitespace differences)
    loose_evidence = _normalize_loose(item.evidence)
    loose_raw = _normalize_loose(artifact.raw_text)
    if len(loose_evidence) >= 10 and loose_evidence in loose_raw:
        return True, "loose match (punctuation normalized)"

    # 4. Prefix match
    prefix = norm_evidence[:20]
    if len(prefix) >= 10 and prefix in norm_raw:
        return True, "partial match (prefix found)"

    return False, f"evidence not found in raw_text (evidence length: {len(item.evidence)})"


def check_content_evidence_ratio(
    item: SynthesizedItem,
) -> tuple[float, str]:
    """Check content-evidence overlap ratio. Returns (ratio, note).

    This is a warning-only check, not a blocker.
    """
    if not item.content or not item.evidence:
        return 0.0, "content or evidence empty"

    evidence_tokens = _tokenize(item.evidence)
    content_tokens = _tokenize(item.content)

    if not evidence_tokens:
        return 0.0, "evidence too short to tokenize"

    overlap = evidence_tokens & content_tokens
    ratio = len(overlap) / len(evidence_tokens)

    note = ""
    if ratio < 0.3:
        note = f"low overlap ({ratio:.0%}), content may exceed evidence"
    elif ratio > 0.9:
        note = f"high overlap ({ratio:.0%}), content closely follows evidence"

    return ratio, note


def check_aspect_consistent(
    item: SynthesizedItem,
    artifact: EvidenceArtifact,
) -> tuple[bool, str]:
    """Check that item.aspect matches artifact source_heading or normalized_aspect."""
    if not item.aspect:
        return False, "aspect is empty"

    # Exact match
    if item.aspect == artifact.source_heading:
        return True, ""

    if artifact.normalized_aspect and item.aspect == artifact.normalized_aspect:
        return True, ""

    # Partial match
    if item.aspect in artifact.source_heading or artifact.source_heading in item.aspect:
        return True, "partial match with source_heading"

    return False, f"aspect '{item.aspect}' doesn't match source_heading '{artifact.source_heading}'"


def check_risk_class(
    item: SynthesizedItem,
) -> tuple[str, str]:
    """Check and potentially downgrade risk_class.

    Returns (final_risk_class, note).
    """
    if item.risk_class == "candidate":
        return "needs_review", "risk_class=candidate downgraded to needs_review"
    if item.risk_class not in {"standard", "needs_review"}:
        return "needs_review", f"unknown risk_class '{item.risk_class}' downgraded"
    return item.risk_class, ""


def check_unsupported_terms(
    item: SynthesizedItem,
    artifact: EvidenceArtifact,
) -> tuple[list[str], str]:
    """Check for terms in content not present in evidence.

    This is a warning-only check, not a blocker.
    """
    if not item.content or not item.evidence:
        return [], ""

    evidence_chars = set(_normalize_text(item.evidence))
    content_chars = set(_normalize_text(item.content))

    # Find characters in content not in evidence
    missing = content_chars - evidence_chars
    # Filter out common punctuation and numbers
    significant = {c for c in missing if c.isalpha() and not c.isascii()}

    if len(significant) > 5:
        return list(significant)[:10], f"{len(significant)} CJK chars in content not in evidence"
    return [], ""


def verify_item(
    item: SynthesizedItem,
    artifact: EvidenceArtifact,
    *,
    section_page_start: int = 0,
    section_page_end: int = 9999,
) -> VerificationResult:
    """Run all verification checks on a SynthesizedItem."""
    result = VerificationResult(
        artifact_id=item.artifact_id,
        item_index=item.item_index,
    )

    # 1. Evidence substring (blocker)
    ok, note = check_evidence_substring(item, artifact)
    result.checks["evidence_substring"] = "pass" if ok else "fail"
    if not ok:
        result.reasons.append(f"evidence_substring: {note}")

    # 2. Content-evidence ratio (warning only)
    ratio, note = check_content_evidence_ratio(item)
    result.checks["content_evidence_ratio"] = "warning" if ratio < 0.3 else "pass"
    if note and ratio < 0.3:
        result.reasons.append(f"content_evidence_ratio: {note}")

    # 3. Page validity (blocker)
    page_ok = section_page_start <= item.page_start <= section_page_end
    result.checks["page_valid"] = "pass" if page_ok else "fail"
    if not page_ok:
        result.reasons.append(f"page_valid: page {item.page_start} not in range {section_page_start}-{section_page_end}")

    # 4. Aspect consistency (warning)
    aspect_ok, aspect_note = check_aspect_consistent(item, artifact)
    result.checks["aspect_consistent"] = "pass" if aspect_ok else "warning"
    if not aspect_ok:
        result.reasons.append(f"aspect_consistent: {aspect_note}")

    # 5. Risk class (may downgrade)
    final_risk, risk_note = check_risk_class(item)
    if final_risk != item.risk_class:
        result.checks["risk_downgrade"] = "fail"
        result.reasons.append(f"risk_downgrade: {risk_note}")
        item.risk_class = final_risk
    else:
        result.checks["risk_downgrade"] = "pass"

    # 6. Unsupported terms (warning only)
    terms, terms_note = check_unsupported_terms(item, artifact)
    result.checks["unsupported_terms"] = "warning" if terms else "pass"
    if terms_note:
        result.reasons.append(f"unsupported_terms: {terms_note}")

    # Determine verdict
    has_blocker = any(
        result.checks.get(c) == "fail"
        for c in ["evidence_substring", "page_valid"]
    )
    has_warning = any(
        result.checks.get(c) == "warning"
        for c in ["content_evidence_ratio", "aspect_consistent", "unsupported_terms"]
    )
    is_high_risk = item.risk_class == "needs_review"

    if has_blocker:
        result.verdict = "rejected"
    elif is_high_risk or has_warning:
        result.verdict = "needs_review"
    else:
        result.verdict = "pass"

    # Update item verification state
    item.verification_state = result.verdict
    item.verification_notes = result.reasons

    return result


def verify_items(
    items: list[SynthesizedItem],
    artifacts: list[EvidenceArtifact],
    *,
    section_page_start: int = 0,
    section_page_end: int = 9999,
) -> tuple[list[VerificationResult], dict[str, int]]:
    """Verify all items against their source artifacts.

    Returns (results, summary_counts).
    """
    artifact_map = {a.id: a for a in artifacts}
    results: list[VerificationResult] = []

    for item in items:
        artifact = artifact_map.get(item.artifact_id)
        if not artifact:
            result = VerificationResult(
                artifact_id=item.artifact_id,
                item_index=item.item_index,
                verdict="rejected",
                reasons=["source artifact not found"],
            )
            results.append(result)
            continue

        result = verify_item(
            item,
            artifact,
            section_page_start=section_page_start,
            section_page_end=section_page_end,
        )
        results.append(result)

    # Summary
    counts = {
        "total": len(results),
        "pass": sum(1 for r in results if r.verdict == "pass"),
        "needs_review": sum(1 for r in results if r.verdict == "needs_review"),
        "rejected": sum(1 for r in results if r.verdict == "rejected"),
    }

    return results, counts
