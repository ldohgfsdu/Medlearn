import json
from pathlib import Path
from typing import Any, Callable


def load_catalog(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def iter_catalog_items(
    catalog: dict[str, Any],
    visitor: Callable[[dict[str, Any], dict[str, Any], dict[str, Any], int, str | None, str | None], None],
    *,
    label: str = 'label',
    name: str = 'name',
    children_key: str = 'children',
) -> None:
    parts = catalog.get('parts', [])

    for part in parts:
        chapters = part.get('chapters', [])
        for chapter in chapters:
            _visit(chapter, {}, part, 0, None, None, visitor, label, name, children_key)


def _visit(
    node: dict[str, Any],
    extra: dict[str, Any],
    part: dict[str, Any],
    depth: int,
    parent_id: str | None,
    parent_name: str | None,
    visitor: Callable,
    label: str,
    name: str,
    children_key: str,
) -> None:
    visitor(node, extra, part, depth, parent_id, parent_name)
    node_name = node.get(name, '')
    for child in node.get(children_key, []):
        _visit(child, extra, part, depth + 1, parent_id or node_name, node_name, visitor, label, name, children_key)
