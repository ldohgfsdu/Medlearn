"""Deterministic paragraph reconstruction for EV1 golden-section quality fixes.

Rebuilds continuous spans only from structurally compatible adjacent text_block
artifacts: same source_heading, same document-tree parent key, same page, same
column (bbox), consecutive source_order. No fuzzy text association.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .text_layers import build_text_layers

if TYPE_CHECKING:
    from .evidence_artifact import EvidenceArtifact


CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_OR_DIGIT_RE = re.compile(r"[A-Za-z0-9／/％%～\-—]")

TRUNCATED_TAIL_RE = re.compile(
    r"(?:或|和|及|以及|包括|如|为|是|有|伴|并|但|而|且|与|在|对|从|向|把|被|将|要|可|应|需|待|的|了|着|过|发|距|射|照|物)\s*$"
)

ABNORMAL_CJK_SPACE_RE = re.compile(
    r"(?<=[\u4e00-\u9fff])[ \t\u3000]+(?=[\u4e00-\u9fff])"
)

TITLE_DEFINITION_MARKERS = ("定义", "是指", "称为", "指", "即", "意思是")
TITLE_BODY_PROPERTY_MARKERS = ("抵抗力", "敏感", "杀死", "消毒", "照射", "杀菌", "方法", "优点", "局限性")

NEW_BLOCK_PREFIX_RE = re.compile(
    r"^(?:[（(]?\s*[一二三四五六七八九十\d]+[）).、\s]|具有|分为|根据|采用|包括|①|②|③|④|⑤)"
)

PROCEDURAL_RISK_RE = re.compile(
    r"(?:距离|照射|消毒|杀菌|操作步骤|给药|剂量|用法|用量|mg|ml|μg|µg|cm|mm|km|"
    r"/m\b|/h\b|/d\b|/min\b|分钟|小时|秒|天|日|周|次/|每小时|每日|每天|单次|疗程|"
    r"滴/分|U/h|IU|浓度|配比|稀释|吸入|静脉|肌注|口服|皮下|空腹|餐前|餐后|"
    r"禁忌|不良反应|过敏|副作用|中毒|毒性|最大剂量|起始剂量|维持剂量)"
)

STITCHABLE_TEXT_BLOCK = "text_block"


@dataclass(frozen=True)
class ReconstructedSpan:
    raw_text: str
    display_text: str
    artifact_ids: tuple[str, ...]
    source_orders: tuple[int, ...]
    pages: tuple[int, ...]
    locators: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_multi_artifact(self) -> bool:
        return len(self.artifact_ids) > 1


@dataclass(frozen=True)
class RepairResult:
    raw_text: str
    display_text: str
    span: ReconstructedSpan
    note: str


def normalize_loose(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    return "".join(
        char.lower()
        for char in normalized
        if unicodedata.category(char)[0] not in {"C", "P", "Z"}
    )


def loose_contains(haystack: str, needle: str) -> bool:
    needle_loose = normalize_loose(needle)
    if not needle_loose:
        return False
    return needle_loose in normalize_loose(haystack)


def _ends_sentence(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if value[-1] in "。！？；.!?;」』\"”%％）)":
        return True
    if value[-1] == "." and not (len(value) >= 2 and value[-2].isdigit()):
        return True
    return False


def is_truncated_sentence(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if _ends_sentence(value):
        return False
    if TRUNCATED_TAIL_RE.search(value):
        return True
    if value[-1] in "，,:：、":
        return False
    return False


def is_artifact_split_candidate(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if is_truncated_sentence(value):
        return True
    if _ends_sentence(value):
        return False
    if len(value) >= 8 and CJK_RE.search(value[-1]):
        return True
    return False


def find_abnormal_chinese_spaces(text: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for match in ABNORMAL_CJK_SPACE_RE.finditer(text or ""):
        hits.append((match.start(), match.group(0)))
    return hits


CJK_LINEWRAP_SPACE_RE = re.compile(
    r"(?<=[\u4e00-\u9fff])[ \t\u3000\n]+(?=[\u4e00-\u9fff])"
)
ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200D\uFEFF]")
# Chinese punctuation: remove spaces before AND after
PUNCT_PREFIX_SPACE_RE = re.compile(r"[ \t]+([，。；：！？、])")
PUNCT_SUFFIX_SPACE_RE = re.compile(r"([，。；：！？、])[ \t]+")
# Opening brackets: （【「『  — remove spaces after these
OPEN_BRACKET_SPACE_RE = re.compile(r"([\uff08\u3010\u300c\u300e])[ \t]+")
# Closing brackets: ）】」』  — remove spaces before AND after these
CLOSE_BRACKET_PREFIX_SPACE_RE = re.compile(r"[ \t]+([\uff09\u3011\u300d\u300f])")
CLOSE_BRACKET_SUFFIX_SPACE_RE = re.compile(r"([\uff09\u3011\u300d\u300f])[ \t]+")
# Remove space between CJK char and digit (e.g., "剂量 10岁" -> "剂量10岁")
CJK_DIGIT_SPACE_RE = re.compile(r"(?<=[\u4e00-\u9fff])[ \t]+(?=\d)")


def _normalize_display_text_legacy(raw: str) -> str:
    """Normalize display text for frontend rendering.

    Mirrors ``utils/textbookStudy.ts::normalizeTextbookDisplayText``. Rules:
    - NFC normalization (NOT NFKC — NFKC decomposes full-width CJK punctuation
      like ``，``→``,`` which would modify medical text appearance; NFC preserves
      full-width punctuation while still normalizing combining characters)
    - Strip zero-width chars (U+200B-U+200D, U+FEFF)
    - Preserve paragraph boundaries (``\\n\\n``) while merging line-wrap breaks
    - Remove spaces between CJK chars (PDF line-break artifacts)
    - Remove spaces between digits and CJK chars
    - Remove spaces before and after Chinese punctuation
    - Remove spaces after opening brackets / before closing brackets
    - Preserve English word spacing and unit spacing (e.g., "10 mg", "bronchial asthma")

    Does NOT modify medical text. Does NOT reconstruct truncated sentences;
    truncation must be repaired upstream via ``reconstruct_forward_span``.
    """
    if not raw:
        return ""
    text = unicodedata.normalize("NFC", raw)
    text = ZERO_WIDTH_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Split on paragraph boundaries (2+ newlines); normalize each segment
    # independently so single line-wrap newlines can be merged while real
    # paragraph boundaries are preserved.
    segments = re.split(r"\n{2,}", text)
    normalized_segments: list[str] = []
    for segment in segments:
        s = segment
        # Collapse runs of spaces/tabs/ideographic spaces to a single space
        s = re.sub(r"[ \t\u3000]+", " ", s)
        # Remove spaces and single newlines between CJK chars (PDF line wraps)
        s = CJK_LINEWRAP_SPACE_RE.sub("", s)
        # Replace any remaining single newlines with a space (line wrap between
        # CJK and non-CJK, e.g., CJK\nEnglish)
        s = s.replace("\n", " ")
        s = re.sub(r"[ \t]+", " ", s)
        # Remove space between digit and CJK char (e.g., "10 岁" -> "10岁")
        s = re.sub(r"(?<=\d)[ \t]+(?=[\u4e00-\u9fff])", "", s)
        # Remove space between CJK char and digit (e.g., "剂量 10" -> "剂量10")
        s = CJK_DIGIT_SPACE_RE.sub("", s)
        # Remove space before Chinese punctuation
        s = PUNCT_PREFIX_SPACE_RE.sub(r"\1", s)
        # Remove space after Chinese punctuation
        s = PUNCT_SUFFIX_SPACE_RE.sub(r"\1", s)
        # Remove space after opening brackets
        s = OPEN_BRACKET_SPACE_RE.sub(r"\1", s)
        # Remove space before closing brackets
        s = CLOSE_BRACKET_PREFIX_SPACE_RE.sub(r"\1", s)
        # Remove space after closing brackets
        s = CLOSE_BRACKET_SUFFIX_SPACE_RE.sub(r"\1", s)
        normalized_segments.append(s.strip())
    return "\n\n".join(seg for seg in normalized_segments if seg)


def normalize_display_text(raw: str) -> str:
    """Compatibility entry point backed by the shared three-layer contract."""
    return build_text_layers(raw).display_text


def document_tree_parent_key(artifact: EvidenceArtifact) -> str:
    metadata = artifact.metadata or {}
    parent_id = str(metadata.get("document_tree_parent_id") or "").strip()
    if parent_id:
        return parent_id
    heading = str(artifact.source_heading or "").strip()
    aspect = str(artifact.normalized_aspect or "").strip()
    if aspect and aspect != heading:
        return f"{heading}::{aspect}"
    return heading


def _bbox_x_range(artifact: EvidenceArtifact) -> tuple[float, float] | None:
    locator = artifact.locator
    if not locator or not locator.bbox or len(locator.bbox) < 4:
        return None
    return float(locator.bbox[0]), float(locator.bbox[2])


def _bbox_top(artifact: EvidenceArtifact) -> float | None:
    locator = artifact.locator
    if not locator or not locator.bbox or len(locator.bbox) < 2:
        return None
    return float(locator.bbox[1])


def _bbox_bottom(artifact: EvidenceArtifact) -> float | None:
    locator = artifact.locator
    if not locator or not locator.bbox or len(locator.bbox) < 4:
        return None
    return float(locator.bbox[3])


def artifacts_share_column(
    left: EvidenceArtifact,
    right: EvidenceArtifact,
    *,
    min_overlap_ratio: float = 0.5,
) -> bool:
    left_range = _bbox_x_range(left)
    right_range = _bbox_x_range(right)
    if left_range is None or right_range is None:
        return False
    left_x0, left_x1 = left_range
    right_x0, right_x1 = right_range
    overlap = min(left_x1, right_x1) - max(left_x0, right_x0)
    if overlap <= 0:
        return False
    left_width = left_x1 - left_x0
    right_width = right_x1 - right_x0
    if min(left_width, right_width) <= 0:
        return False
    return overlap / min(left_width, right_width) >= min_overlap_ratio


def sorted_artifacts(artifacts: list[EvidenceArtifact]) -> list[EvidenceArtifact]:
    return sorted(
        artifacts,
        key=lambda artifact: (
            artifact.page_start,
            artifact.source_order,
            artifact.id,
        ),
    )


def artifacts_are_adjacent(
    left: EvidenceArtifact,
    right: EvidenceArtifact,
    *,
    max_order_gap: int = 1,
    max_vertical_gap: float = 40.0,
) -> bool:
    if right.source_order - left.source_order != max_order_gap:
        return False
    if left.page_start != right.page_start:
        return False
    left_bottom = _bbox_bottom(left)
    right_top = _bbox_top(right)
    if left_bottom is None or right_top is None:
        return False
    return 0 <= right_top - left_bottom <= max_vertical_gap


def junction_is_valid_continuation(left_text: str, right_text: str) -> bool:
    """True only when right continues left at a PDF split, not a new block."""
    left = (left_text or "").strip()
    right = (right_text or "").strip()
    if not left or not right:
        return False
    if _ends_sentence(left):
        return False
    if right[0] in "（(【[①②③④⑤⑥⑦⑧⑨⑩":
        return False
    if NEW_BLOCK_PREFIX_RE.match(right):
        return False

    if TRUNCATED_TAIL_RE.search(left):
        remainder = right
        if NEW_BLOCK_PREFIX_RE.match(remainder.lstrip()):
            return False
        return True

    for overlap in range(1, min(3, len(left), len(right)) + 1):
        left_suffix = left[-overlap:]
        right_prefix = right[:overlap]
        if left_suffix == right_prefix:
            continue
        remainder = right[overlap:].lstrip()
        if remainder and NEW_BLOCK_PREFIX_RE.match(remainder):
            return False
        if overlap == 1 and CJK_RE.search(left[-1]) and CJK_RE.search(right[0]) and left[-1] != right[0]:
            return True
        if LATIN_OR_DIGIT_RE.search(left[-1]) and (CJK_RE.search(right[0]) or right[0].isdigit()):
            return True
    return False


def can_stitch_artifacts(left: EvidenceArtifact, right: EvidenceArtifact) -> bool:
    if left.artifact_type != STITCHABLE_TEXT_BLOCK or right.artifact_type != STITCHABLE_TEXT_BLOCK:
        return False
    if left.source_heading != right.source_heading:
        return False
    if document_tree_parent_key(left) != document_tree_parent_key(right):
        return False
    if not artifacts_are_adjacent(left, right):
        return False
    if not artifacts_share_column(left, right):
        return False
    return junction_is_valid_continuation(left.raw_text, right.raw_text)


def can_stitch_continuation(left_text: str, right_text: str) -> bool:
    """Text-only junction check for tests; does NOT validate structural guards.

    WARNING: This function only checks text-level junction validity. It does
    NOT verify same source_heading, same Document Tree parent, same page, same
    column, continuous text_block, or reasonable bbox/source_order. Production
    code must use ``can_stitch_artifacts`` which enforces all structural
    invariants before reaching this text-level check.
    """
    return junction_is_valid_continuation(left_text, right_text)


def _artifact_locator_dict(artifact: EvidenceArtifact) -> dict[str, Any]:
    locator = artifact.locator
    if not locator:
        return {
            "artifact_id": artifact.id,
            "page": artifact.page_start,
            "source_order": artifact.source_order,
            "bbox": None,
        }
    return {
        "artifact_id": artifact.id,
        "page": locator.page,
        "source_order": artifact.source_order,
        "bbox": list(locator.bbox) if locator.bbox else None,
        "kind": locator.kind,
    }


def _join_raw_fragments(left: str, right: str) -> str:
    left = left or ""
    right = right or ""
    if not left:
        return right
    if not right:
        return left
    if left[-1].isascii() and left[-1].isalnum() and right[0].isascii() and right[0].isalnum():
        return f"{left} {right}"
    return left + right


def expand_to_sentence_boundary(raw_span: str, anchor: str) -> str:
    if not raw_span:
        return ""
    if not anchor:
        return raw_span

    loose_anchor = normalize_loose(anchor)
    loose_span = normalize_loose(raw_span)
    start_loose = loose_span.find(loose_anchor)
    if start_loose < 0:
        return raw_span

    normalized_chars: list[str] = []
    raw_indexes: list[int] = []
    for index, char in enumerate(raw_span):
        normalized = normalize_loose(char)
        if not normalized:
            continue
        for normalized_char in normalized:
            normalized_chars.append(normalized_char)
            raw_indexes.append(index)

    end_loose = start_loose + len(loose_anchor)
    raw_end = raw_indexes[min(end_loose, len(raw_indexes)) - 1] + 1

    for index in range(raw_end, len(raw_span)):
        char = raw_span[index]
        if char in "。！？；!?;」』\"”%％）)":
            return raw_span[: index + 1]
        if char == ".":
            next_char = raw_span[index + 1] if index + 1 < len(raw_span) else ""
            previous_char = raw_span[index - 1] if index > 0 else ""
            if previous_char.isdigit() and next_char.isdigit():
                continue
            return raw_span[: index + 1]
    return raw_span


def reconstruct_forward_span(
    artifacts: list[EvidenceArtifact],
    artifact_id: str,
    *,
    max_artifacts: int = 4,
) -> ReconstructedSpan | None:
    ordered = sorted_artifacts(artifacts)
    index = next((idx for idx, artifact in enumerate(ordered) if artifact.id == artifact_id), -1)
    if index < 0:
        return None

    chain = [ordered[index]]
    cursor = index
    while len(chain) < max_artifacts and cursor + 1 < len(ordered):
        left = chain[-1]
        right = ordered[cursor + 1]
        if not can_stitch_artifacts(left, right):
            break
        chain.append(right)
        cursor += 1

    if len(chain) == 1:
        return None

    raw_text = ""
    for artifact in chain:
        raw_text = _join_raw_fragments(raw_text, artifact.raw_text)

    return ReconstructedSpan(
        raw_text=raw_text,
        display_text=normalize_display_text(raw_text),
        artifact_ids=tuple(artifact.id for artifact in chain),
        source_orders=tuple(artifact.source_order for artifact in chain),
        pages=tuple(artifact.page_start for artifact in chain),
        locators=tuple(_artifact_locator_dict(artifact) for artifact in chain),
        notes=("reconstructed from adjacent text_block artifacts",),
    )


def repair_truncated_fields(
    *,
    content: str,
    evidence: str,
    artifact: EvidenceArtifact,
    all_artifacts: list[EvidenceArtifact] | None,
) -> RepairResult | None:
    if not all_artifacts:
        return None
    if not is_artifact_split_candidate(content) and not is_artifact_split_candidate(evidence):
        return None

    span = reconstruct_forward_span(all_artifacts, artifact.id)
    if not span:
        return None

    anchor = content or evidence
    if anchor and not loose_contains(span.raw_text, anchor):
        return None

    expanded_raw = expand_to_sentence_boundary(span.raw_text, anchor)
    if not expanded_raw or not loose_contains(expanded_raw, anchor):
        return None

    # Trim the chain to the shortest prefix whose joined raw_text covers
    # expanded_raw. Without this, reconstruct_forward_span's max_artifacts=4
    # ceiling appends unused stitchable blocks to provenance.
    trimmed_span = _trim_span_to_expanded_raw(span, expanded_raw, all_artifacts)

    expanded_display = normalize_display_text(expanded_raw)
    new_content = expanded_display if content and loose_contains(expanded_raw, content) else content
    return RepairResult(
        raw_text=expanded_raw,
        display_text=new_content,
        span=trimmed_span,
        note="repaired truncated span from adjacent artifacts",
    )


def _trim_span_to_expanded_raw(
    span: ReconstructedSpan,
    expanded_raw: str,
    all_artifacts: list[EvidenceArtifact],
) -> ReconstructedSpan:
    """Return a new ``ReconstructedSpan`` trimmed to the shortest chain prefix
    whose joined raw_text covers ``expanded_raw``.

    ``expanded_raw`` is always a prefix of ``span.raw_text`` (or equal to it),
    because ``expand_to_sentence_boundary`` returns ``raw_span[:index+1]``.
    Artifacts whose raw_text does not contribute to ``expanded_raw`` are
    dropped from ``artifact_ids``, ``source_orders``, ``pages``, and
    ``locators`` so that provenance reflects only the artifacts that
    actually supplied text to the repaired span.

    The returned span is always self-consistent: ``raw_text`` and
    ``display_text`` reflect ``expanded_raw`` (not the original full-chain
    text), even when the contributing prefix happens to span the entire
    chain. The original ``span`` is returned only when resolution fails or
    ``expanded_raw`` already equals ``span.raw_text``.
    """
    if not expanded_raw or expanded_raw == span.raw_text:
        return span

    artifact_map = {art.id: art for art in all_artifacts}
    chain = [artifact_map[aid] for aid in span.artifact_ids if aid in artifact_map]
    if len(chain) != len(span.artifact_ids):
        # Resolution failed; cannot safely trim. Return original span.
        return span

    # Walk the chain accumulating joined raw_text (same join logic as
    # reconstruct_forward_span). Find the shortest prefix whose accumulated
    # text covers expanded_raw as a prefix.
    accumulated = ""
    cut: int | None = None
    for index, art in enumerate(chain):
        accumulated = _join_raw_fragments(accumulated, art.raw_text or "")
        if (
            len(accumulated) >= len(expanded_raw)
            and accumulated[: len(expanded_raw)] == expanded_raw
        ):
            cut = index + 1
            break

    if cut is None:
        # No prefix covered expanded_raw; cannot safely trim. Return original.
        return span

    trimmed_chain = chain[:cut]
    return ReconstructedSpan(
        raw_text=expanded_raw,
        display_text=normalize_display_text(expanded_raw),
        artifact_ids=tuple(art.id for art in trimmed_chain),
        source_orders=tuple(art.source_order for art in trimmed_chain),
        pages=tuple(art.page_start for art in trimmed_chain),
        locators=tuple(_artifact_locator_dict(art) for art in trimmed_chain),
        notes=span.notes,
    )


def evidence_within_bound_artifact(evidence: str, artifact: EvidenceArtifact) -> bool:
    if not evidence or not artifact.raw_text:
        return False
    if evidence.strip() in artifact.raw_text:
        return True
    return loose_contains(artifact.raw_text, evidence)


def classify_expanded_content_risk(content: str, evidence: str) -> str | None:
    text = f"{content}\n{evidence}"
    if PROCEDURAL_RISK_RE.search(text):
        return "expanded procedural span requires review"
    return None


def is_extractive_paraphrase(content: str, evidence: str) -> bool:
    content = (content or "").strip()
    evidence = (evidence or "").strip()
    if not content or not evidence:
        return False
    if content not in evidence:
        return False
    index = evidence.find(content)
    if index <= 0:
        return False
    prefix = evidence[:index].strip()
    if not prefix:
        return False
    if prefix[-1] in "，,；;：:":
        return True
    if len(normalize_loose(prefix)) >= 4:
        return True
    return False


def detect_title_body_mismatch(title: str, body: str) -> str | None:
    title = (title or "").strip()
    body = (body or "").strip()
    if not title or not body:
        return None
    if title.endswith("的定义"):
        entity = title[: -len("的定义")].strip()
        if entity and entity in body:
            return None
        if any(marker in body for marker in TITLE_DEFINITION_MARKERS):
            return None
        if any(marker in body for marker in ("简称", "是一种", "指以", "指的是")):
            return None
        if any(marker in body for marker in TITLE_BODY_PROPERTY_MARKERS):
            return "title_definition_body_property_mismatch"
        return "title_definition_missing_definition_language"
    return None


def detect_heading_title_mismatch(source_heading: str, title: str, body: str) -> str | None:
    source_heading = (source_heading or "").strip()
    title = (title or "").strip()
    body = (body or "").strip()
    if not source_heading or not title:
        return None
    if source_heading == title:
        return None
    if loose_contains(body, source_heading):
        return None
    if title.endswith("的定义") and "称为" in body and "抗酸杆菌" in body:
        return "heading_title_topic_drift"
    return None


def load_artifacts_from_evidence_payload(payload: dict[str, Any]) -> list[EvidenceArtifact]:
    from .evidence_artifact import EvidenceArtifact

    artifacts = payload.get("artifacts") or []
    return [EvidenceArtifact.from_dict(item) for item in artifacts if isinstance(item, dict)]
