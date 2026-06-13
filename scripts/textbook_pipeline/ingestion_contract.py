"""Production contract for knowledge ingestion."""
from __future__ import annotations

ADAPTER_VERSION = "1.0.0"
PIPELINE_VERSION = "pipeline_v3+adapter"

# App-facing storage only. Do not write production data to knowledge_points.
KNOWLEDGE_POINTS_DEPRECATED = True
DEPRECATION_NOTICE = (
    "knowledge_points is deprecated. "
    "Do not write new production data into knowledge_points. "
    "All app-facing knowledge data must be written to knowledge_nodes."
)

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