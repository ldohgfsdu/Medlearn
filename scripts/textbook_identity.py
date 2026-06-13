"""Shared textbook identity metadata for extraction pipelines."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextbookIdentity:
    canonical_id: str
    display_name: str
    subject_name: str
    edition: str
    source_filename: str
    aliases: tuple[str, ...]


INTERNAL_MEDICINE_10 = TextbookIdentity(
    canonical_id="internal-medicine-10",
    display_name="内科学（第10版）",
    subject_name="内科学",
    edition="第10版",
    source_filename="内科学（第10版）.pdf",
    aliases=("内科学（第10版）", "internal-medicine-10"),
)

CANONICAL_TEXTBOOK_ID = INTERNAL_MEDICINE_10.canonical_id

_REGISTRY: dict[str, TextbookIdentity] = {
    INTERNAL_MEDICINE_10.canonical_id: INTERNAL_MEDICINE_10,
}


def get_textbook_identity(textbook_id: str) -> TextbookIdentity:
    identity = _REGISTRY.get(textbook_id)
    if identity is None:
        raise KeyError(f"Unknown textbook_id: {textbook_id}")
    return identity
