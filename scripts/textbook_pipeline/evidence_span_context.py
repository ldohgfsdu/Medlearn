"""Nearby artifact span reconstruction for EV1 verification.

When PDF text blocks split a sentence across artifacts, synthesized evidence may
be continuous in same-page nearby text but not in the bound artifact alone.
"""
from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .evidence_artifact import EvidenceArtifact


def normalize_loose_legacy(text: str) -> str:
    text = re.sub(r"[\s，。；：、！？…,.:;!?\-—（）()\[\]【】]", "", text or "")
    return text.translate(str.maketrans("", "", "\"'`“”‘’")).lower()


def normalize_loose(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    return "".join(
        char.lower()
        for char in normalized
        if unicodedata.category(char)[0] not in {"C", "P", "Z"}
    )


def sorted_page_artifacts(artifacts: list[EvidenceArtifact]) -> list[EvidenceArtifact]:
    return sorted(
        artifacts,
        key=lambda artifact: (
            artifact.page_start,
            artifact.source_order,
            artifact.id,
        ),
    )


def nearby_page_text(
    artifacts: list[EvidenceArtifact],
    artifact_id: str,
    *,
    radius: int = 3,
) -> str:
    ordered = sorted_page_artifacts(artifacts)
    target_index = next(
        (index for index, artifact in enumerate(ordered) if artifact.id == artifact_id),
        -1,
    )
    if target_index == -1:
        return ""

    target_page = ordered[target_index].page_start
    neighbors = [
        artifact
        for artifact in ordered[max(0, target_index - radius) : target_index + radius + 1]
        if artifact.page_start == target_page
    ]
    return "".join(artifact.raw_text for artifact in neighbors if artifact.raw_text)


def nearby_ordered_text(
    artifacts: list[EvidenceArtifact],
    artifact_id: str,
    *,
    radius: int = 3,
) -> str:
    """Return adjacent artifact text in reading order, allowing page breaks."""
    ordered = sorted_page_artifacts(artifacts)
    target_index = next(
        (index for index, artifact in enumerate(ordered) if artifact.id == artifact_id),
        -1,
    )
    if target_index == -1:
        return ""

    neighbors = ordered[max(0, target_index - radius) : target_index + radius + 1]
    return "".join(artifact.raw_text for artifact in neighbors if artifact.raw_text)


def find_shortest_raw_span(haystack: str, anchor_loose: str, *, min_len: int = 8) -> str | None:
    if len(anchor_loose) < min_len:
        return None

    best: str | None = None
    best_len = len(haystack) + 1
    for start in range(len(haystack)):
        for end in range(start + min_len, len(haystack) + 1):
            candidate = haystack[start:end]
            if anchor_loose not in normalize_loose(candidate):
                continue
            span_len = end - start
            if span_len < best_len:
                best = candidate
                best_len = span_len
    return best


LIST_MARKER_CHARS = "①②③④⑤⑥⑦⑧⑨⑩"


def expand_backward_for_split_prefix(haystack: str, start: int, *, max_lookback: int = 24) -> int:
    expanded = start
    for offset in range(1, max_lookback + 1):
        pos = start - offset
        if pos < 0:
            break
        char = haystack[pos]
        if char == "。":
            break
        expanded = pos
        if char in LIST_MARKER_CHARS:
            break
    return expanded


def find_longest_raw_span_containing(
    haystack: str,
    anchor_loose: str,
    *,
    min_len: int = 8,
    max_len: int = 320,
) -> str | None:
    if len(anchor_loose) < min_len:
        return None

    best: str | None = None
    best_len = 0
    for start in range(len(haystack)):
        upper = min(len(haystack) + 1, start + max_len + 1)
        for end in range(start + min_len, upper):
            candidate = haystack[start:end]
            if anchor_loose not in normalize_loose(candidate):
                continue
            span_len = end - start
            if span_len > best_len:
                best = candidate
                best_len = span_len
    return best


def repair_evidence_span(
    evidence: str,
    target_raw: str,
    nearby_text: str,
) -> tuple[str, str] | None:
    """Find a verbatim nearby span to replace synthesized evidence."""
    if not evidence or not nearby_text:
        return None

    loose_evidence = normalize_loose(evidence)
    loose_nearby = normalize_loose(nearby_text)
    loose_target = normalize_loose(target_raw)

    if len(loose_evidence) >= 10 and loose_evidence in loose_nearby:
        span = find_shortest_raw_span(nearby_text, loose_evidence)
        if span:
            return span, "repaired to nearby continuous span"

    if (
        len(loose_target) >= 8
        and loose_target in loose_evidence
        and loose_evidence not in loose_nearby
        and loose_target in loose_nearby
    ):
        span = find_longest_raw_span_containing(nearby_text, loose_target)
        if span:
            return span, "repaired cross-artifact compressed span"

    if len(loose_target) >= 8 and loose_target in loose_nearby:
        span = find_shortest_raw_span(nearby_text, loose_target)
        if span:
            start = nearby_text.find(span)
            if start > 0:
                expanded_start = expand_backward_for_split_prefix(nearby_text, start)
                span = nearby_text[expanded_start : start + len(span)]
            return span, "repaired via bound artifact span in nearby text"

    for length in range(len(loose_evidence), 9, -1):
        suffix = loose_evidence[-length:]
        if suffix not in loose_nearby:
            continue
        span = find_shortest_raw_span(nearby_text, suffix)
        if span:
            return span, f"repaired via evidence suffix overlap ({length} chars)"

    return None
