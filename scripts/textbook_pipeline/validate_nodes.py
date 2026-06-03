import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.textbook_pipeline.atomic_io import atomic_write_json, atomic_write_text
from scripts.textbook_pipeline.catalog_utils import load_catalog

VALID_TYPES = {'concept', 'mechanism', 'disease', 'symptom', 'treatment', 'exam'}
LOW_CONFIDENCE = 0.75


def flatten_catalog(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def visit(node: dict[str, Any], part: dict[str, Any], depth: int, parent: str | None) -> None:
        segment_id = '.'.join([part['systemKey'], node['name']]) if not parent else f'{parent}.{node["name"]}'
        item = {
            'segmentId': segment_id,
            'name': node['name'],
            'label': node['label'],
            'depth': depth,
            'parentSegmentId': parent,
            'childCount': len(node.get('children', [])),
            'maxNodesPerSegment': node.get('maxNodesPerSegment'),
            'warningMaxNodes': node.get('warningMaxNodes'),
            'errorMaxNodes': node.get('errorMaxNodes'),
        }
        items.append(item)
        for child in node.get('children', []):
            visit(child, part, depth + 1, segment_id)

    for part in catalog.get('parts', []):
        for chapter in part.get('chapters', []):
            visit(chapter, part, 0, None)
    return items


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open('r', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def load_nodes(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, list):
        return payload, []
    return payload.get('nodes', []), payload.get('weakDefinitionCandidates', [])


def warning_threshold(segment: dict[str, Any]) -> int:
    if segment.get('warningMaxNodes'):
        return int(segment['warningMaxNodes'])
    if segment.get('maxNodesPerSegment'):
        return int(segment['maxNodesPerSegment'])
    return 2


def error_threshold(segment: dict[str, Any]) -> int:
    if segment.get('errorMaxNodes'):
        return int(segment['errorMaxNodes'])
    return 5


def severity_for_missing(segment: dict[str, Any]) -> str:
    label = segment.get('label', '')
    if label.startswith('附') or segment.get('depth', 0) >= 2:
        return 'warning'
    return 'error'


def validate_node_content_quality(node: dict[str, Any]) -> list[str]:
    """Validate content quality of a node."""
    issues = []
    content = node.get('content', '')
    title = node.get('title', '')
    
    if not content:
        issues.append(f'Empty content: {title}')
        return issues
    
    if len(content) < 100:
        issues.append(f'Very short content ({len(content)} chars): {title}')
    
    if len(content) > 50000:
        issues.append(f'Very long content ({len(content)} chars): {title}')
    
    if content.count('思考题') > 0 and content.index('思考题') < len(content) * 0.8:
        issues.append(f'Content contains 思考题 early: {title}')
    
    return issues


def segment_key_from_node(node: dict[str, Any]) -> str:
    span = node.get('sourceSpan') or {}
    if span.get('segmentId'):
        return str(span['segmentId'])
    heading_path = span.get('headingPath') or []
    return ' / '.join(heading_path) or node.get('chapter', '')


def add_issue(collection: list[dict[str, Any]], severity: str, code: str, message: str, **extra: Any) -> None:
    collection.append({'severity': severity, 'code': code, 'message': message, **extra})


def main() -> None:
    parser = argparse.ArgumentParser(description='Validate staged textbook knowledge nodes.')
    parser.add_argument('--catalog', required=True)
    parser.add_argument('--segments', required=True)
    parser.add_argument('--nodes', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--json-report')
    args = parser.parse_args()

    catalog = load_catalog(Path(args.catalog))
    segments = load_jsonl(Path(args.segments))
    nodes, weak_definition_candidates = load_nodes(Path(args.nodes))

    issues: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def issue(severity: str, code: str, message: str, **extra: Any) -> None:
        target = errors if severity == 'error' else warnings
        add_issue(target, severity, code, message, **extra)
        add_issue(issues, severity, code, message, **extra)

    nodes_by_chapter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    nodes_by_segment_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        title = node.get('title', '')
        if not node.get('id'):
            issue('error', 'missing-id', f'Missing id: {title}')
        if node.get('type') not in VALID_TYPES:
            issue('error', 'invalid-type', f'Invalid type for {title}: {node.get("type")}')
        if not node.get('content') or len(node.get('content', '').strip()) < 40:
            issue('error', 'content-too-short', f'Content too short: {title}', title=title)
        span = node.get('sourceSpan')
        if not span or span.get('pageStart') is None or not span.get('headingPath'):
            issue('error', 'missing-source-span', f'Missing sourceSpan: {title}', title=title)
        
        content_issues = validate_node_content_quality(node)
        for ci in content_issues:
            issue('warning', 'content-quality', ci, title=title)
        
        nodes_by_chapter[node.get('chapter', '')].append(node)
        nodes_by_segment_key[segment_key_from_node(node)].append(node)

    catalog_items = []
    for segment in segments:
        segment_nodes = nodes_by_segment_key.get(segment.get('segmentId', ''), []) or nodes_by_chapter.get(segment.get('name', ''), [])
        segment_warnings: list[str] = []
        if not segment.get('found'):
            sev = severity_for_missing(segment)
            message = f"Catalog item not found: {segment.get('label')}"
            issue(sev, 'catalog-missing', message, segmentId=segment.get('segmentId'), label=segment.get('label'), candidates=segment.get('candidates'))
            segment_warnings.append(message)
        elif float(segment.get('confidence') or 0) < LOW_CONFIDENCE:
            message = f"Low confidence segment match: {segment.get('label')} confidence={segment.get('confidence')}"
            issue('warning', 'low-segment-confidence', message, segmentId=segment.get('segmentId'))
            segment_warnings.append(message)

        count = len(segment_nodes)
        warn_max = warning_threshold(segment)
        err_max = error_threshold(segment)
        if count > err_max:
            message = f"Segment node count exceeds error threshold: {segment.get('name')} nodes={count} threshold={err_max}"
            issue('error', 'node-count-high', message, segmentId=segment.get('segmentId'))
            segment_warnings.append(message)
        elif count > warn_max:
            message = f"Segment node count exceeds warning threshold: {segment.get('name')} nodes={count} threshold={warn_max}"
            issue('warning', 'node-count-warning', message, segmentId=segment.get('segmentId'))
            segment_warnings.append(message)

        catalog_items.append({
            'segmentId': segment.get('segmentId'),
            'label': segment.get('label'),
            'name': segment.get('name'),
            'found': bool(segment.get('found')),
            'method': segment.get('method'),
            'matchType': segment.get('matchType'),
            'confidence': segment.get('confidence'),
            'pageStart': segment.get('pageStart'),
            'pageEnd': segment.get('pageEnd'),
            'nodeCount': count,
            'warnings': segment_warnings,
        })

    for segment_key, segment_nodes in nodes_by_segment_key.items():
        title_counts = Counter(node.get('title', '') for node in segment_nodes)
        for title, count in title_counts.items():
            if title and count > 3:
                issue('error', 'duplicate-title-same-segment', f'Duplicate title in same segment ({count}): {title}', segment=segment_key, title=title)
        hash_counts = Counter(node.get('contentHash') for node in segment_nodes if node.get('contentHash'))
        for content_hash, count in hash_counts.items():
            if count > 1:
                issue('warning', 'duplicate-content-same-segment', f'Duplicate content hash in same segment ({count}): {content_hash}', segment=segment_key)

    global_hash_counts = Counter(node.get('contentHash') for node in nodes if node.get('contentHash'))
    for content_hash, count in global_hash_counts.items():
        if count > 1:
            issue('warning', 'duplicate-content-cross-segment', f'Duplicate content hash across segments ({count}): {content_hash}', contentHash=content_hash)

    summary = {
        'nodes': len(nodes),
        'segments': len(segments),
        'foundSegments': sum(1 for s in segments if s.get('found')),
        'missingSegments': sum(1 for s in segments if not s.get('found')),
        'weakDefinitionCandidates': len(weak_definition_candidates),
        'errors': len(errors),
        'warnings': len(warnings),
    }
    node_stats = {
        'bySource': dict(Counter(node.get('nodeSource', 'unknown') for node in nodes)),
        'byType': dict(Counter(node.get('type', 'unknown') for node in nodes)),
    }
    json_report = {
        'summary': summary,
        'catalogItems': catalog_items,
        'segments': [{k: v for k, v in segment.items() if k != 'text'} for segment in segments],
        'nodeStats': node_stats,
        'errors': errors,
        'warnings': warnings,
    }

    report_lines = [
        '# Textbook extraction validation report',
        '',
        '## Summary',
        f"- Nodes: {summary['nodes']}",
        f"- Segments: {summary['segments']}",
        f"- Found segments: {summary['foundSegments']}",
        f"- Missing segments: {summary['missingSegments']}",
        f"- Weak definition candidates: {summary['weakDefinitionCandidates']}",
        f"- Errors: {summary['errors']}",
        f"- Warnings: {summary['warnings']}",
        '',
        '## Node stats',
        f"- By source: {node_stats['bySource']}",
        f"- By type: {node_stats['byType']}",
        '',
        '## Errors',
        *(f"- [{e['code']}] {e['message']}" for e in errors[:200]),
        '',
        '## Warnings',
        *(f"- [{w['code']}] {w['message']}" for w in warnings[:300]),
        '',
        '## Missing catalog items',
        *(f"- {item['label']} ({item['method']}/{item['matchType']})" for item in catalog_items if not item['found']),
    ]

    report_path = Path(args.report)
    json_report_path = Path(args.json_report) if args.json_report else report_path.with_suffix('.json')
    atomic_write_text(report_path, '\n'.join(report_lines), encoding='utf-8')
    atomic_write_json(json_report_path, json_report)
    print(f'Wrote {report_path} and {json_report_path}; errors={len(errors)}, warnings={len(warnings)}')
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
