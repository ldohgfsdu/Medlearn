import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .atomic_io import atomic_write_json

PIPELINE_VERSION = '0.2.0'
PARSER_VERSION = '0.2.0'


def sample_hash(path: Path, sample_size: int = 4096) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        h.update(f.read(sample_size))
    return h.hexdigest()[:16]


def source_signature(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        'sourceMtime': stat.st_mtime,
        'sourceSize': stat.st_size,
        'sourceSampleHash': sample_hash(path),
    }


def build_metadata(source_path: Path, book: dict[str, Any], fmt: str, errors: list[str] | None = None) -> dict[str, Any]:
    return {
        'generatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'sourcePath': str(source_path),
        'sourceFilename': source_path.name,
        'format': fmt,
        'parserVersion': PARSER_VERSION,
        'pipelineVersion': PIPELINE_VERSION,
        **source_signature(source_path),
        **book,
        'errors': errors or [],
    }


def read_metadata(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def is_cache_valid(source_path: Path, metadata_path: Path) -> bool:
    metadata = read_metadata(metadata_path)
    if not metadata:
        return False
    sig = source_signature(source_path)
    return (
        metadata.get('sourceMtime') == sig['sourceMtime'] and
        metadata.get('sourceSize') == sig['sourceSize'] and
        metadata.get('sourceSampleHash') == sig['sourceSampleHash'] and
        metadata.get('pipelineVersion') == PIPELINE_VERSION
    )


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    atomic_write_json(path, metadata)
