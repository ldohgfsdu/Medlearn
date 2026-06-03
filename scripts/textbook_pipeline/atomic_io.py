import json
import os
import shutil
from pathlib import Path
from typing import Any


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def check_disk_space(path: Path, expected_bytes: int = 0) -> None:
    target = path.parent if path.suffix else path
    target.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(target)
    required = max(expected_bytes * 2, 10 * 1024 * 1024)
    if usage.free < required:
        raise OSError(f'Insufficient disk space for {path}: free={usage.free}, required={required}')


def atomic_write_text(path: Path, content: str, encoding: str = 'utf-8') -> None:
    ensure_parent(path)
    check_disk_space(path, len(content.encode(encoding)))
    tmp_path = path.with_name(path.name + '.tmp')
    tmp_path.write_text(content, encoding=encoding)
    os.replace(tmp_path, path)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    content = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)
    atomic_write_text(path, content, encoding='utf-8')
