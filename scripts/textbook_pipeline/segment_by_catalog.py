import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.textbook_pipeline.atomic_io import atomic_write_jsonl
from scripts.textbook_pipeline.catalog_utils import load_catalog
from scripts.textbook_pipeline.logger import setup_logger, get_logger

HEADING_PREFIX_RE = re.compile(
    r'^('
    r'第[一二三四五六七八九十百零0-9]+[章节篇]'
    r'|附\d*\s*'
    r'|[一二三四五六七八九十]+[、.,．]'
    r'|[（(][一二三四五六七八九十]+[）)]'
    r'|\d+[.、,．]'
    r')'
)


def normalize_strict(title: str) -> str:
    return re.sub(r'[\s　|｜]', '', title).strip()


def normalize_fuzzy(title: str) -> str:
    return re.sub(r'[\s　|｜\-—:：、，,（）()《》〈〉\u3000［］\[\]]', '', title).strip()


def strip_heading_prefix(title: str) -> str:
    value = re.sub(r'^第[一二三四五六七八九十百零0-9]+[章节篇]\s*', '', title)
    value = re.sub(r'^第[一二三四五六七八九十百零0-9]+节\s*', '', value)
    value = re.sub(r'^［?附\d*］?\s*', '', value)
    value = re.sub(r'^[一二三四五六七八九十]+[、.,．]\s*', '', value)
    value = re.sub(r'^[（(][一二三四五六七八九十]+[）)]\s*', '', value)
    value = re.sub(r'^\d+[.、,．]\s*', '', value)
    return value.strip()


def flatten_catalog(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def visit(
        node: dict[str, Any],
        path: list[str],
        part: dict[str, Any],
        depth: int,
        parent_id: str | None,
    ) -> None:
        heading_path = [part['title'], *path, node['label']]
        segment_id = '.'.join([
            part['systemKey'],
            *[p.split(' ', 1)[-1] for p in path],
            node['name'],
        ])
        item: dict[str, Any] = {
            'segmentId': segment_id,
            'parentSegmentId': parent_id,
            'systemKey': part['systemKey'],
            'subject': part['subject'],
            'name': node['name'],
            'label': node['label'],
            'aliases': node.get('aliases', []),
            'headingPath': heading_path,
            'depth': depth,
            'hasChildren': bool(node.get('children')),
            'childCount': len(node.get('children', [])),
            'maxNodesPerSegment': node.get('maxNodesPerSegment'),
            'warningMaxNodes': node.get('warningMaxNodes'),
            'errorMaxNodes': node.get('errorMaxNodes'),
        }
        items.append(item)
        for child in node.get('children', []):
            visit(child, [*path, node['label']], part, depth + 1, segment_id)

    for part in catalog.get('parts', []):
        for chapter in part.get('chapters', []):
            visit(chapter, [], part, 0, None)
    return items


def load_pages(path: Path) -> list[dict[str, Any]]:
    logger = get_logger()
    try:
        with path.open('r', encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f'Failed to load pages from {path}: {e}')
        return []


def load_toc(path: Path | None) -> list[dict[str, Any]]:
    logger = get_logger()
    if not path or not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning(f'Failed to load TOC from {path}: {exc}')
        return []


def candidates_for(item: dict[str, Any]) -> list[str]:
    candidates = [item['label'], item['name'], *item.get('aliases', [])]
    candidates.extend(strip_heading_prefix(c) for c in list(candidates))
    return [c for c in candidates if c]


def find_by_toc(
    item: dict[str, Any],
    toc: list[dict[str, Any]],
    last_matched_index: int = 0,
) -> tuple[dict[str, Any] | None, str, float, list[dict[str, Any]], int]:
    strict_keys = {normalize_strict(c) for c in candidates_for(item) if c}
    fuzzy_keys = {normalize_fuzzy(c) for c in candidates_for(item) if c}
    fuzzy_candidates: list[dict[str, Any]] = []

    for idx, entry in enumerate(toc):
        title = entry.get('title', '')
        strict_title = normalize_strict(title)
        if strict_title in strict_keys or normalize_strict(strip_heading_prefix(title)) in strict_keys:
            return entry, 'strict', 0.98, [], idx

    for idx in range(last_matched_index, len(toc)):
        entry = toc[idx]
        title = entry.get('title', '')
        fuzzy_title = normalize_fuzzy(title)
        stripped_fuzzy = normalize_fuzzy(strip_heading_prefix(title))
        if (
            fuzzy_title in fuzzy_keys
            or stripped_fuzzy in fuzzy_keys
            or any(k and (k in fuzzy_title or fuzzy_title in k) for k in fuzzy_keys)
        ):
            return entry, 'fuzzy', 0.85, [], idx

    for entry in toc:
        title = entry.get('title', '')
        fuzzy_title = normalize_fuzzy(title)
        stripped_fuzzy = normalize_fuzzy(strip_heading_prefix(title))
        if (
            fuzzy_title in fuzzy_keys
            or stripped_fuzzy in fuzzy_keys
            or any(k and (k in fuzzy_title or fuzzy_title in k) for k in fuzzy_keys)
        ):
            fuzzy_candidates.append({
                'title': title,
                'page': entry.get('pageNumber'),
                'level': entry.get('level'),
                'reason': 'fuzzy toc candidate',
            })

    return None, 'fuzzy-candidate', 0.0, fuzzy_candidates[:5], last_matched_index


def looks_like_heading(line: str, item: dict[str, Any]) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return False
    normalized = normalize_strict(stripped)
    keys = [normalize_strict(c) for c in candidates_for(item) if c]
    if normalized in keys:
        return True
    if HEADING_PREFIX_RE.match(stripped) and any(
        k and (normalized.endswith(k) or normalized == k) for k in keys
    ):
        return True
    stripped_no_brackets = re.sub(r'［\s*附\s*(\d*)\s*］', r'附\1', stripped)
    normalized_no_brackets = normalize_strict(stripped_no_brackets)
    if normalized_no_brackets != normalized and normalized_no_brackets in keys:
        return True
    if HEADING_PREFIX_RE.match(stripped_no_brackets) and any(
        k and (normalized_no_brackets.endswith(k) or normalized_no_brackets == k) for k in keys
    ):
        return True
    return False


def pages_in_scope(
    pages: list[dict[str, Any]],
    start_hint: int | None = None,
    end_hint: int | None = None,
) -> list[dict[str, Any]]:
    if start_hint is None or end_hint is None:
        return pages
    return [p for p in pages if start_hint <= int(p['pageNumber']) <= end_hint]


def find_by_body(
    item: dict[str, Any],
    pages: list[dict[str, Any]],
    start_hint: int | None = None,
    end_hint: int | None = None,
) -> tuple[int | None, str, float]:
    for page in pages_in_scope(pages, start_hint, end_hint):
        for line in page['text'].splitlines():
            if looks_like_heading(line, item):
                return int(page['pageNumber']), 'body-regex', 0.78
    return None, 'not-found', 0.0


def page_text_range(pages: list[dict[str, Any]], start_page: int, end_page: int) -> str:
    chunks = [p['text'] for p in pages if start_page <= int(p['pageNumber']) <= end_page]
    return '\n'.join(chunks).strip()


def parent_scope(
    item: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> tuple[int | None, int | None]:
    parent_id = item.get('parentSegmentId')
    if not parent_id:
        return None, None
    parent = by_id.get(parent_id)
    if not parent:
        return None, None
    return parent.get('pageStart'), parent.get('pageEnd')


def calculate_ranges(
    located: list[dict[str, Any]],
    max_page: int,
    toc: list[dict[str, Any]] | None = None,
) -> None:
    logger = get_logger()
    for index, item in enumerate(located):
        start = item.get('pageStart')
        if start is None:
            item['pageEnd'] = None
            item['rangeSource'] = 'missing'
            continue
        end = max_page
        range_source = 'max-page'
        for other in located[index + 1:]:
            other_start = other.get('pageStart')
            if other_start is None or other_start <= start:
                continue
            if other['depth'] <= item['depth']:
                end = other_start - 1
                range_source = 'next-sibling-or-ancestor'
                break
        if item.get('tocLevel') is not None and item.get('tocPage') is not None and toc:
            next_toc_pages = [
                int(entry['pageNumber'])
                for entry in toc
                if int(entry.get('pageNumber') or 0) > start
                and int(entry.get('level') or 99) <= int(item['tocLevel'])
            ]
            if next_toc_pages:
                end = min(end, min(next_toc_pages) - 1)
                range_source = 'next-toc-sibling-or-ancestor'
        if end < start:
            logger.warning(
                f'Range anomaly: segment={item.get("segmentId")}, '
                f'start={start}, end={end}, rangeSource={range_source}'
            )
            item['pageEnd'] = start
            item['rangeSource'] = f'range-anomaly({range_source})'
        else:
            item['pageEnd'] = end
            item['rangeSource'] = range_source


def main() -> None:
    parser = argparse.ArgumentParser(description='Segment extracted pages by catalog headings.')
    parser.add_argument('--catalog', required=True, help='Path to catalog JSON')
    parser.add_argument('--pages', required=True, help='Path to pages.jsonl')
    parser.add_argument('--toc', help='Path to toc.json (optional)')
    parser.add_argument('--out', required=True, help='Output path for segments.jsonl')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    log_level = 10 if args.verbose else 20
    setup_logger(level=log_level)
    logger = get_logger()

    catalog_path = Path(args.catalog)
    pages_path = Path(args.pages)
    out_path = Path(args.out)

    if not catalog_path.exists():
        logger.error(f'Catalog file not found: {catalog_path}')
        sys.exit(1)
    if not pages_path.exists():
        logger.error(f'Pages file not found: {pages_path}')
        sys.exit(1)

    try:
        catalog = load_catalog(catalog_path)
        pages = load_pages(pages_path)
        toc = load_toc(Path(args.toc)) if args.toc else []
        items = flatten_catalog(catalog)
        max_page = max((int(p['pageNumber']) for p in pages), default=0)

        logger.info(f'Loaded catalog: {len(items)} items, {len(pages)} pages, {len(toc)} TOC entries')

        located: list[dict[str, Any]] = []
        last_toc_index = 0
        use_toc = len(toc) >= 5

        for item in items:
            if use_toc:
                entry, match_type, confidence, candidates, new_index = find_by_toc(
                    item, toc, last_toc_index
                )
                if entry is not None:
                    last_toc_index = new_index + 1
            else:
                entry, match_type, confidence, candidates, new_index = None, 'not-found', 0.0, [], 0
            method = 'toc' if entry is not None else 'not-found'
            page = int(entry['pageNumber']) if entry is not None else None
            located.append({
                **item,
                'pageStart': page,
                'method': method,
                'matchType': match_type,
                'confidence': confidence,
                'candidates': candidates,
                'tocLevel': entry.get('level') if entry else None,
                'tocTitle': entry.get('title') if entry else None,
                'tocPage': entry.get('pageNumber') if entry else None,
            })

        calculate_ranges(located, max_page, toc)
        by_id = {item['segmentId']: item for item in located}

        for item in located:
            if item.get('pageStart') is not None:
                continue
            start_hint, end_hint = parent_scope(item, by_id)
            page, body_match, body_confidence = find_by_body(item, pages, start_hint, end_hint)
            if page is not None:
                item.update({
                    'pageStart': page,
                    'method': 'body-heading',
                    'matchType': body_match,
                    'confidence': body_confidence,
                    'pageEnd': end_hint or page,
                    'rangeSource': 'parent-boundary' if end_hint else 'body-heading-single-page',
                })

        calculate_ranges(located, max_page, toc)

        rows: list[dict[str, Any]] = []
        for item in located:
            start = item['pageStart']
            end = item.get('pageEnd')
            if start is None or end is None:
                rows.append({**item, 'pageEnd': None, 'text': '', 'textHash': None, 'found': False})
                continue
            text = page_text_range(pages, start, end)
            rows.append({
                **item,
                'pageEnd': end,
                'text': text,
                'textHash': hashlib.sha256(text.encode('utf-8')).hexdigest()[:16],
                'found': True,
            })

        atomic_write_jsonl(out_path, rows)
        missing = sum(1 for row in rows if not row['found'])
        logger.info(f'Wrote {out_path}: segments={len(rows)}, missing={missing}')

    except Exception as e:
        logger.error(f'Unexpected error: {e}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
