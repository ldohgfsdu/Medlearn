"""Cache metadata: pipeline version and source-file validation."""
from __future__ import annotations
import os
from pathlib import Path

PIPELINE_VERSION = "2.0.0"

def is_cache_valid(generated_meta: dict, source_path: str | Path) -> bool:
    """Validate cached metadata against current source file and pipeline version."""
    if not generated_meta:
        return False
    src = Path(source_path)
    if not src.exists():
        return False
    return (
        generated_meta.get("sourceMtime") == os.path.getmtime(src)
        and generated_meta.get("sourceSize") == os.path.getsize(src)
        and generated_meta.get("pipelineVersion") == PIPELINE_VERSION
    )
