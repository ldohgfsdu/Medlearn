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
import unicodedata

from .evidence_artifact import EvidenceArtifact
from .evidence_span_context import (
    nearby_ordered_text,
    nearby_page_text,
    normalize_loose,
    repair_evidence_span,
)
from .evidence_synthesis import SynthesizedItem
from .paragraph_reconstruction import (
    can_stitch_artifacts,
    classify_expanded_content_risk,
    detect_title_body_mismatch,
    evidence_within_bound_artifact,
    is_extractive_paraphrase,
    is_truncated_sentence,
    repair_truncated_fields,
    sorted_artifacts,
)


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


def _normalize_loose_legacy(text: str) -> str:
    """Looser normalization: remove all whitespace and punctuation."""
    import re
    text = re.sub(r"[\s，。；：、！？…,.:;!?\-—（）()\[\]【】]", "", text)
    text = text.translate(str.maketrans("", "", "\"'`“”‘’"))
    return text.lower()


def _normalize_loose(text: str) -> str:
    """Unicode-safe loose normalization for source span matching."""
    normalized = unicodedata.normalize("NFKC", text or "")
    return "".join(
        char.lower()
        for char in normalized
        if unicodedata.category(char)[0] not in {"C", "P", "Z"}
    )


def _tokenize(text: str) -> set[str]:
    """Simple character bigram tokenization for Chinese text."""
    text = _normalize_text(text)
    if len(text) < 2:
        return {text}
    return {text[i:i+2] for i in range(len(text) - 1)}


def _preserved_provenance_notes(notes: list[str]) -> list[str]:
    return [
        note
        for note in notes
        if note.startswith("source_only_") or note.startswith("provenance_")
    ]


def _raw_span_for_loose_substring(
    haystack: str,
    needle: str,
    *,
    min_len: int = 6,
) -> str | None:
    """Return the raw continuous span whose loose-normalized text contains needle."""
    needle_loose = _normalize_loose(needle)
    if len(needle_loose) < min_len:
        return None

    normalized_chars: list[str] = []
    raw_indexes: list[int] = []
    for index, char in enumerate(haystack or ""):
        normalized = _normalize_loose(char)
        if not normalized:
            continue
        for normalized_char in normalized:
            normalized_chars.append(normalized_char)
            raw_indexes.append(index)

    normalized_haystack = "".join(normalized_chars)
    start = normalized_haystack.find(needle_loose)
    if start < 0:
        return None

    end = start + len(needle_loose)
    raw_start = raw_indexes[start]
    raw_end = raw_indexes[end - 1] + 1
    return haystack[raw_start:raw_end]


def _build_stitched_chain_for_evidence(
    artifact: EvidenceArtifact,
    all_artifacts: list[EvidenceArtifact],
    evidence_loose: str,
) -> tuple[list[EvidenceArtifact], str] | None:
    """Build the shortest structurally legal stitch chain rooted at ``artifact``.

    All chain links must pass ``can_stitch_artifacts``. Returns (chain, joined_text)
    for the shortest chain that contains ``evidence_loose`` (loose-normalized),
    else ``None``. The chain always includes ``artifact``; extension stops as soon
    as the evidence is contained, so unused stitchable blocks are never appended
    to the provenance.
    """
    if len(evidence_loose) < 8:
        return None

    ordered = sorted_artifacts(all_artifacts)
    start_index = next(
        (idx for idx, art in enumerate(ordered) if art.id == artifact.id),
        -1,
    )
    if start_index < 0:
        return None

    root = ordered[start_index]

    # Length 1: bound artifact alone
    joined_root = root.raw_text or ""
    if evidence_loose in _normalize_loose(joined_root):
        return [root], joined_root

    # Precompute maximal forward reach: furthest index reachable from start_index
    # by consecutive legal stitches (start_index, start_index+1, ..., forward_max).
    forward_max = start_index
    cursor = start_index
    while cursor + 1 < len(ordered):
        if not can_stitch_artifacts(ordered[cursor], ordered[cursor + 1]):
            break
        cursor += 1
        forward_max = cursor

    # Precompute maximal backward reach: lowest index reachable to start_index
    # by consecutive legal stitches (backward_min, ..., start_index).
    backward_min = start_index
    cursor = start_index
    while cursor - 1 >= 0:
        if not can_stitch_artifacts(ordered[cursor - 1], ordered[cursor]):
            break
        cursor -= 1
        backward_min = cursor

    max_fwd = forward_max - start_index
    max_back = start_index - backward_min
    # Safety cap to avoid unbounded chains (preserves prior 6-block ceiling).
    max_total = min(6, max_fwd + max_back + 1)

    # Iterate by total chain length (shortest first). For each length, prefer
    # forward-only extension, then progressively more backward steps. Return the
    # first chain that contains the evidence.
    for total in range(2, max_total + 1):
        for back_count in range(min(total - 1, max_back) + 1):
            fwd_count = total - 1 - back_count
            if fwd_count < 0 or fwd_count > max_fwd:
                continue
            i = start_index - back_count
            j = start_index + fwd_count
            chain = ordered[i : j + 1]
            joined = "".join(art.raw_text for art in chain if art.raw_text)
            if evidence_loose in _normalize_loose(joined):
                return chain, joined

    return None


def _apply_chain_provenance(
    item: SynthesizedItem,
    chain: list[EvidenceArtifact],
) -> None:
    """Propagate artifact IDs and locators from a stitch chain to the item."""
    from .paragraph_reconstruction import _artifact_locator_dict

    item.source_artifact_ids = [art.id for art in chain]
    item.reconstructed_locators = [
        dict(_artifact_locator_dict(art)) for art in chain
    ]


def repair_evidence_to_content_span(
    item: SynthesizedItem,
    artifact: EvidenceArtifact,
    *,
    all_artifacts: list[EvidenceArtifact] | None = None,
) -> str:
    """Expand too-narrow evidence when item.content is a continuous source span.

    Cross-artifact expansion now requires a structurally legal stitch chain via
    ``can_stitch_artifacts``. Loose nearby_page_text / nearby_ordered_text
    concatenation is no longer trusted on its own.
    """
    if not item.content or not artifact.raw_text:
        return ""
    content_loose = _normalize_loose(item.content)
    evidence_loose = _normalize_loose(item.evidence)
    if len(content_loose) < 6 or content_loose in evidence_loose:
        return ""

    # 1. Bound artifact only
    repaired = _raw_span_for_loose_substring(artifact.raw_text, item.content)
    if repaired and content_loose in _normalize_loose(repaired):
        item.evidence = repaired
        return "evidence expanded to continuous content span (current artifact)"

    # 2. Structurally legal cross-artifact chain
    if all_artifacts:
        chain_result = _build_stitched_chain_for_evidence(
            artifact, all_artifacts, content_loose
        )
        if chain_result:
            chain, joined = chain_result
            repaired = _raw_span_for_loose_substring(joined, item.content)
            if repaired and content_loose in _normalize_loose(repaired):
                item.evidence = repaired
                _apply_chain_provenance(item, chain)
                return "evidence expanded to continuous content span (legal stitch chain)"

    return ""


def check_evidence_substring(
    item: SynthesizedItem,
    artifact: EvidenceArtifact,
    *,
    all_artifacts: list[EvidenceArtifact] | None = None,
) -> tuple[bool, str]:
    """Check that item.evidence is a continuous substring of artifact.raw_text.

    Matching strategy (progressive relaxation):
    1. Exact substring (no normalization)
    2. Normalized whitespace/punctuation exact match
    3. Loose normalization match (all punctuation removed) — single artifact only
    4. Structurally legal cross-artifact stitch chain via can_stitch_artifacts;
       multi-artifact matches propagate provenance and force needs_review.
    Prefix-only matches no longer return pass; they are downgraded to a
    cross-artifact warning that requires review.
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

    # 3. Loose normalization match — single bound artifact only
    loose_evidence = _normalize_loose(item.evidence)
    loose_raw = _normalize_loose(artifact.raw_text)
    if len(loose_evidence) >= 10 and loose_evidence in loose_raw:
        return True, "loose match (punctuation normalized)"

    # 4. Structurally legal cross-artifact stitch chain
    if all_artifacts:
        chain_result = _build_stitched_chain_for_evidence(
            artifact, all_artifacts, loose_evidence
        )
        if chain_result:
            chain, joined = chain_result
            # Locate a verbatim span within the joined chain text
            repaired = repair_evidence_span(item.evidence, artifact.raw_text, joined)
            if repaired:
                span, _note = repaired
                item.evidence = span
            elif loose_evidence in _normalize_loose(joined):
                # Fall back to the full joined chain text
                item.evidence = joined
            _apply_chain_provenance(item, chain)
            if len(chain) > 1:
                return True, "nearby artifact span (legal stitch chain, multi-artifact)"
            return True, "nearby artifact span (cross-block continuous)"

    # 5. Prefix-only match — no longer a pass; flag as needs_review
    prefix = norm_evidence[:20]
    if len(prefix) >= 10 and prefix in norm_raw:
        return False, "prefix-only match; full evidence not in bound artifact"

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
    all_artifacts: list[EvidenceArtifact] | None = None,
    section_page_start: int = 0,
    section_page_end: int = 9999,
) -> VerificationResult:
    """Run all verification checks on a SynthesizedItem."""
    result = VerificationResult(
        artifact_id=item.artifact_id,
        item_index=item.item_index,
    )

    # 1. Evidence substring (blocker)
    ok, note = check_evidence_substring(
        item,
        artifact,
        all_artifacts=all_artifacts,
    )
    result.checks["evidence_substring"] = "pass" if ok else "fail"
    if not ok:
        result.reasons.append(f"evidence_substring: {note}")
    elif note:
        result.reasons.append(f"evidence_substring: {note}")
        # Multi-artifact stitch chain forces needs_review — provenance must be reviewed
        if "multi-artifact" in note or len(item.source_artifact_ids) > 1:
            result.checks["evidence_substring"] = "warning"
            result.reasons.append(
                "evidence_substring: multi-artifact span pending provenance review"
            )

    repair_note = repair_evidence_to_content_span(
        item,
        artifact,
        all_artifacts=all_artifacts,
    )
    result.checks["evidence_content_span"] = "pass"
    if repair_note:
        result.reasons.append(f"evidence_content_span: {repair_note}")
        expanded_risk = classify_expanded_content_risk(item.content, item.evidence)
        if expanded_risk:
            result.checks["expanded_content_risk"] = "warning"
            result.reasons.append(f"expanded_content_risk: {expanded_risk}")
            item.risk_class = "needs_review"

    original_content = item.content
    original_evidence = item.evidence
    if is_extractive_paraphrase(original_content, original_evidence):
        result.checks["extractive_paraphrase"] = "warning"
        result.reasons.append(
            "extractive_paraphrase: content drops leading evidence context"
        )

    title_mismatch = detect_title_body_mismatch(item.title, original_content)
    if title_mismatch:
        result.checks["title_body_mismatch"] = "warning"
        result.reasons.append(f"title_body_mismatch: {title_mismatch}")

    truncated_repair = None
    if (
        result.checks.get("extractive_paraphrase") != "warning"
        and result.checks.get("title_body_mismatch") != "warning"
    ):
        truncated_repair = repair_truncated_fields(
            content=item.content,
            evidence=item.evidence,
            artifact=artifact,
            all_artifacts=all_artifacts,
        )
    if truncated_repair:
        item.evidence = truncated_repair.raw_text
        item.content = truncated_repair.display_text
        item.source_artifact_ids = list(truncated_repair.span.artifact_ids)
        item.reconstructed_locators = [dict(locator) for locator in truncated_repair.span.locators]
        result.checks["paragraph_reconstruction"] = "warning"
        result.reasons.append(f"paragraph_reconstruction: {truncated_repair.note}")
        result.reasons.append(
            "paragraph_reconstruction: multi-artifact span pending provenance review"
            if truncated_repair.span.is_multi_artifact
            else "paragraph_reconstruction: expanded span exceeds bound artifact"
        )
        if not evidence_within_bound_artifact(item.evidence, artifact):
            result.reasons.append(
                "paragraph_reconstruction: evidence exceeds bound artifact raw_text"
            )
        expanded_risk = classify_expanded_content_risk(item.content, item.evidence)
        if expanded_risk:
            result.checks["expanded_content_risk"] = "warning"
            result.reasons.append(f"expanded_content_risk: {expanded_risk}")
            item.risk_class = "needs_review"
    elif is_truncated_sentence(item.content) or is_truncated_sentence(item.evidence):
        result.checks["unresolved_truncation"] = "fail"
        result.reasons.append("paragraph_reconstruction: unresolved truncated sentence")
        unresolved_risk = classify_expanded_content_risk(item.content, item.evidence)
        if unresolved_risk:
            result.checks["expanded_content_risk"] = "warning"
            result.reasons.append(f"expanded_content_risk: {unresolved_risk}")
            item.risk_class = "needs_review"
        else:
            result.reasons.append("publication_state: evidence_only_required")

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
    has_review_warning = any(
        result.checks.get(c) == "warning"
        for c in [
            "evidence_substring",
            "aspect_consistent",
            "unsupported_terms",
            "paragraph_reconstruction",
            "extractive_paraphrase",
            "title_body_mismatch",
            "expanded_content_risk",
        ]
    )
    is_high_risk = item.risk_class == "needs_review"
    unresolved_truncation = result.checks.get("unresolved_truncation") == "fail"
    requires_evidence_only = unresolved_truncation and result.checks.get("expanded_content_risk") != "warning"

    if has_blocker:
        result.verdict = "rejected"
    elif truncated_repair is not None:
        result.verdict = "needs_review"
    elif is_high_risk or has_review_warning:
        result.verdict = "needs_review"
    elif requires_evidence_only:
        result.verdict = "evidence_only"
    else:
        result.verdict = "pass"

    # Update item verification state while preserving provenance notes that were
    # attached before deterministic verification, such as source-only fallbacks.
    # Diagnostic verifier notes are recomputed every run so stale failures do not
    # remain after deterministic evidence repair.
    provenance_notes = _preserved_provenance_notes(item.verification_notes)
    item.verification_state = result.verdict
    item.verification_notes = list(dict.fromkeys([*provenance_notes, *result.reasons]))

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
            all_artifacts=artifacts,
            section_page_start=section_page_start,
            section_page_end=section_page_end,
        )
        results.append(result)

    # Summary
    counts = {
        "total": len(results),
        "pass": sum(1 for r in results if r.verdict == "pass"),
        "needs_review": sum(1 for r in results if r.verdict == "needs_review"),
        "evidence_only": sum(1 for r in results if r.verdict == "evidence_only"),
        "rejected": sum(1 for r in results if r.verdict == "rejected"),
    }

    return results, counts
