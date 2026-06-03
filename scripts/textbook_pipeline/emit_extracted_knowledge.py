import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.textbook_pipeline.atomic_io import atomic_write_text

SOURCE_ORDER = {'segment-main': 0, 'definition-sentence': 1, 'explicit-heading': 2}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open('r', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def validation_counts(validation: dict[str, Any]) -> tuple[int, int]:
    summary = validation.get('summary') or {}
    return int(summary.get('errors') or len(validation.get('errors') or [])), int(summary.get('warnings') or len(validation.get('warnings') or []))


def node_sort_key(node: dict[str, Any], segment_order: dict[str, int]) -> tuple[int, int, int]:
    span = node.get('sourceSpan') or {}
    segment_id = span.get('segmentId') or ''
    return (
        segment_order.get(segment_id, 999999),
        SOURCE_ORDER.get(node.get('nodeSource'), 99),
        int(span.get('lineStart') if span.get('lineStart') is not None else 999999),
    )


def ts_string(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def normalize_node(node: dict[str, Any], metadata: dict[str, Any], generated_at: int) -> dict[str, Any]:
    tags = list(dict.fromkeys([*(node.get('tags') or []), metadata.get('bookId'), metadata.get('title'), metadata.get('edition')]))
    tags = [tag for tag in tags if tag]
    return {
        'id': node.get('id'),
        'type': node.get('type'),
        'title': node.get('title'),
        'subject': node.get('subject'),
        'chapter': node.get('chapter'),
        'content': node.get('content'),
        'keyPoints': node.get('keyPoints') or [],
        'causalLinks': node.get('causalLinks') or [],
        'relatedNodes': node.get('relatedNodes') or [],
        'difficulty': node.get('difficulty') or 2,
        'tags': tags,
        'source': 'seed',
        'bookId': metadata.get('bookId'),
        'textbook': metadata.get('title') or metadata.get('sourceFilename'),
        'edition': metadata.get('edition'),
        'nodeSource': node.get('nodeSource'),
        'inferred': bool(node.get('inferred')),
        'sourceSpan': node.get('sourceSpan'),
        'generatedAt': generated_at,
        'createdAt': generated_at,
        'updatedAt': generated_at,
    }


def build_textbook_index(metadata: dict[str, Any], segments: list[dict[str, Any]]) -> str:
    chapters = [
        {
            'segmentId': s.get('segmentId'),
            'parentSegmentId': s.get('parentSegmentId'),
            'label': s.get('label'),
            'name': s.get('name'),
            'subject': s.get('subject'),
            'depth': s.get('depth'),
            'pageStart': s.get('pageStart'),
            'pageEnd': s.get('pageEnd'),
            'found': bool(s.get('found')),
        }
        for s in segments
    ]
    payload = [{
        'bookId': metadata.get('bookId'),
        'title': metadata.get('title') or metadata.get('sourceFilename'),
        'edition': metadata.get('edition'),
        'sourceFilename': metadata.get('sourceFilename'),
        'chapters': chapters,
    }]
    return "export interface ExtractedTextbookChapter {\n  segmentId?: string;\n  parentSegmentId?: string | null;\n  label?: string;\n  name: string;\n  subject?: string;\n  depth?: number;\n  pageStart?: number | null;\n  pageEnd?: number | null;\n  found?: boolean;\n}\n\nexport interface ExtractedTextbookInfo {\n  bookId: string;\n  title: string;\n  edition?: string | null;\n  sourceFilename?: string;\n  chapters: ExtractedTextbookChapter[];\n}\n\nexport const extractedTextbooks: ExtractedTextbookInfo[] = " + ts_string(payload) + ";\n"


def main() -> None:
    parser = argparse.ArgumentParser(description='Emit validated textbook staging nodes into app TypeScript data.')
    parser.add_argument('--nodes', required=True)
    parser.add_argument('--segments', required=True)
    parser.add_argument('--metadata', required=True)
    parser.add_argument('--validation', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--index-out')
    parser.add_argument('--allow-warnings', action='store_true')
    args = parser.parse_args()

    nodes_payload = load_json(Path(args.nodes))
    nodes = nodes_payload.get('nodes', nodes_payload if isinstance(nodes_payload, list) else [])
    segments = load_jsonl(Path(args.segments))
    metadata = load_json(Path(args.metadata))
    validation = load_json(Path(args.validation))
    errors, warnings = validation_counts(validation)
    if errors:
        raise SystemExit(f'Validation has {errors} errors; refusing to emit app data')
    if warnings and not args.allow_warnings:
        raise SystemExit(f'Validation has {warnings} warnings; pass --allow-warnings to emit anyway')

    generated_at = int(time.time() * 1000)
    segment_order = {s.get('segmentId'): idx for idx, s in enumerate(segments)}
    app_nodes = [normalize_node(node, metadata, generated_at) for node in sorted(nodes, key=lambda n: node_sort_key(n, segment_order))]

    header = f"""import type {{ KnowledgeNode }} from '../types/knowledge';

// 自动从教材 staging 生成，请勿手改节点内容。
// 教材: {metadata.get('title') or metadata.get('sourceFilename')} {metadata.get('edition') or ''}
// bookId: {metadata.get('bookId')}
// 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(generated_at / 1000))}
// 总知识点数: {len(app_nodes)}
// validation: errors={errors}, warnings={warnings}

export const extractedKnowledgeNodes: KnowledgeNode[] = """
    content = header + ts_string(app_nodes) + ";\n"
    atomic_write_text(Path(args.out), content, encoding='utf-8')
    print(f'Wrote {args.out}; nodes={len(app_nodes)}; validation errors={errors}, warnings={warnings}')

    index_out = Path(args.index_out) if args.index_out else Path(args.out).with_name('extractedTextbookIndex.ts')
    atomic_write_text(index_out, build_textbook_index(metadata, segments), encoding='utf-8')
    print(f'Wrote {index_out}; chapters={len(segments)}')


if __name__ == '__main__':
    main()
