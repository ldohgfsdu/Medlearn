"""Production contract for knowledge ingestion."""
from __future__ import annotations

import os

ADAPTER_VERSION = "1.0.0"
PIPELINE_VERSION = "pipeline_v3+adapter"

# App-facing storage only. Do not write production data to knowledge_points.
KNOWLEDGE_POINTS_DEPRECATED = True
DEPRECATION_NOTICE = (
    "knowledge_points is deprecated. "
    "Do not write new production data into knowledge_points. "
    "All app-facing knowledge data must be written to knowledge_nodes."
)

# Production PDF parser — ingest CLI and pipeline_v3_extract share this default.
PRODUCTION_PDF_PARSER = "auto"

DEFAULT_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "bge-m3")
EMBED_DIMENSION = 1024

SECTION_STATUSES = frozenset(
    {
        "pending",
        "extracting",
        "extracted",
        "uploading",
        "uploaded",
        "verified",
        "failed",
    }
)

TERMINAL_SUCCESS = "verified"
TERMINAL_SECTION_STATUSES = frozenset({TERMINAL_SUCCESS})
RESUMABLE_STATUSES = frozenset({"pending", "failed", "extracted", "uploading", "uploaded"})


def resolve_pdf_parser_mode(*, cli_use_docling: bool = False) -> str:
    """Return production parser mode: auto (default), pymupdf, or docling."""
    if cli_use_docling:
        return "docling"
    override = os.getenv("MEDLEARN_PDF_PARSER", PRODUCTION_PDF_PARSER).strip().lower()
    if override in {"auto", "pymupdf", "docling"}:
        return override
    return PRODUCTION_PDF_PARSER


def production_pymupdf_only(*, cli_use_docling: bool = False) -> bool:
    return resolve_pdf_parser_mode(cli_use_docling=cli_use_docling) == "pymupdf"
