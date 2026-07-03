"""Deterministic raw, canonical, and display text layers."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200D\uFEFF]")
CJK_LINE_WRAP_RE = re.compile(
    r"(?<=[\u4e00-\u9fff])[ \t\u3000\n]+(?=[\u4e00-\u9fff])"
)
CJK_DIGIT_SPACE_RE = re.compile(r"(?<=[\u4e00-\u9fff])[ \t]+(?=\d)")
DIGIT_CJK_SPACE_RE = re.compile(r"(?<=\d)[ \t]+(?=[\u4e00-\u9fff])")
PUNCT_PREFIX_SPACE_RE = re.compile(r"[ \t]+([，。；：！？、])")
PUNCT_SUFFIX_SPACE_RE = re.compile(r"([，。；：！？、])[ \t]+")
OPEN_BRACKET_SPACE_RE = re.compile(r"([（【「『])[ \t]+")
CLOSE_BRACKET_PREFIX_SPACE_RE = re.compile(r"[ \t]+([）】」』])")
CLOSE_BRACKET_SUFFIX_SPACE_RE = re.compile(r"([）】」』])[ \t]+")


@dataclass(frozen=True)
class TextLayers:
    raw_text: str
    canonical_text: str
    display_text: str


def canonicalize_source_text(raw_text: str) -> str:
    """Repair encoding and physical line wraps while preserving paragraphs."""
    if not raw_text:
        return ""
    text = unicodedata.normalize("NFC", raw_text)
    text = ZERO_WIDTH_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    segments: list[str] = []
    for segment in re.split(r"\n{2,}", text):
        value = re.sub(r"[ \t\u3000]+", " ", segment)
        value = CJK_LINE_WRAP_RE.sub("", value)
        value = value.replace("\n", " ")
        value = re.sub(r"[ \t]+", " ", value).strip()
        if value:
            segments.append(value)
    return "\n\n".join(segments)


def format_display_text(canonical_text: str) -> str:
    """Apply typography-only spacing cleanup to canonical source text."""
    if not canonical_text:
        return ""
    segments: list[str] = []
    for segment in canonical_text.split("\n\n"):
        value = CJK_LINE_WRAP_RE.sub("", segment)
        value = DIGIT_CJK_SPACE_RE.sub("", value)
        value = CJK_DIGIT_SPACE_RE.sub("", value)
        value = PUNCT_PREFIX_SPACE_RE.sub(r"\1", value)
        value = PUNCT_SUFFIX_SPACE_RE.sub(r"\1", value)
        value = OPEN_BRACKET_SPACE_RE.sub(r"\1", value)
        value = CLOSE_BRACKET_PREFIX_SPACE_RE.sub(r"\1", value)
        value = CLOSE_BRACKET_SUFFIX_SPACE_RE.sub(r"\1", value).strip()
        if value:
            segments.append(value)
    return "\n\n".join(segments)


def build_text_layers(raw_text: str) -> TextLayers:
    canonical_text = canonicalize_source_text(raw_text)
    return TextLayers(
        raw_text=raw_text,
        canonical_text=canonical_text,
        display_text=format_display_text(canonical_text),
    )
