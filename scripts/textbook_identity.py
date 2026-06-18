"""Shared textbook identity metadata for extraction pipelines."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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


@dataclass(frozen=True)
class IngestionContext:
    book_id: str
    identity: TextbookIdentity
    pdf_path: Path
    manifest_path: Path
    catalog_path: Path
    v3_output_dir: Path
    generated_root: Path

    @property
    def pdf_stem(self) -> str:
        return self.pdf_path.stem


def resolve_ingestion_context(book_id: str, project_root: Path) -> IngestionContext:
    identity = get_textbook_identity(book_id)
    if book_id == INTERNAL_MEDICINE_10.canonical_id:
        return IngestionContext(
            book_id=book_id,
            identity=identity,
            pdf_path=project_root / "textbook" / identity.source_filename,
            manifest_path=project_root / "manifests" / "internal_medicine_ingestion.yaml",
            catalog_path=project_root / "scripts" / "catalog.internal-medicine.json",
            v3_output_dir=project_root / "generated" / "pipeline_v3",
            generated_root=project_root / "generated" / "knowledge_nodes",
        )
    raise KeyError(f"No ingestion manifest configured for textbook_id: {book_id}")
