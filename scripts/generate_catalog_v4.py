import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.textbook_pipeline.book_registry import KNOWN_TITLES


def clean_title(title: str) -> str:
    title = title.replace('\u0000', '').strip()
    return title.strip()


def detect_structure(toc: list[dict[str, Any]]) -> str:
    has_part = False
    has_chapter = False
    has_section = False

    for entry in toc:
        title = entry.get('title', '').replace('\u0000', '').strip()
        level = entry.get('level', 1)

        if level == 1 and '篇' in title:
            has_part = True
        if level == 2 and '章' in title:
            has_chapter = True
        if level == 3 and '节' in title:
            has_section = True

    if has_part and has_chapter:
        return 'part-chapter-section'
    elif has_chapter:
        return 'chapter-section'
    else:
        return 'flat'


def extract_name(title: str, pattern: str) -> str:
    match = re.match(pattern, title)
    if match:
        return match.group(1).strip()
    return clean_title(title)


def generate_catalog_from_toc(toc: list[dict[str, Any]], book_name: str) -> dict[str, Any]:
    structure = detect_structure(toc)

    if structure == 'part-chapter-section':
        return generate_part_chapter_catalog(toc, book_name)
    elif structure == 'chapter-section':
        return generate_chapter_catalog(toc, book_name)
    else:
        return generate_flat_catalog(toc, book_name)


def generate_part_chapter_catalog(toc: list[dict[str, Any]], book_name: str) -> dict[str, Any]:
    parts: list[dict[str, Any]] = []
    current_part: dict[str, Any] | None = None
    current_chapter: dict[str, Any] | None = None

    for entry in toc:
        level = entry.get('level', 1)
        title = entry.get('title', '').replace('\u0000', '').strip()
        page = entry.get('pageNumber', 0)

        if not title or title in ['封面页', '书名页', '版权页', '编委名单', '目录', '前言', '序言']:
            continue

        if level == 1 and '篇' in title:
            part_name = extract_name(title, r'第[一二三四五六七八九十百零0-9]+篇\s*(.+)')
            current_part = {
                'systemKey': part_name,
                'subject': f'{book_name} - {part_name}',
                'title': title,
                'chapters': [],
            }
            parts.append(current_part)
            current_chapter = None

        elif level == 2 and '章' in title and current_part is not None:
            chapter_name = extract_name(title, r'第[一二三四五六七八九十百零0-9]+章\s*(.+)')
            current_chapter = {
                'name': chapter_name,
                'label': title,
                'pageNum': page,
                'children': [],
            }
            current_part['chapters'].append(current_chapter)

        elif level == 3 and '节' in title and current_chapter is not None:
            section_name = extract_name(title, r'第[一二三四五六七八九十百零0-9]+节\s*[|｜]?\s*(.+)')
            current_chapter['children'].append({
                'name': section_name,
                'label': title,
                'pageNum': page,
            })

    for part in parts:
        for chapter in part['chapters']:
            if not chapter.get('children'):
                del chapter['children']

    return {
        'book': f'{book_name}（第10版）',
        'parts': parts,
    }


def generate_chapter_catalog(toc: list[dict[str, Any]], book_name: str) -> dict[str, Any]:
    chapters: list[dict[str, Any]] = []
    current_chapter: dict[str, Any] | None = None

    for entry in toc:
        level = entry.get('level', 1)
        title = entry.get('title', '').replace('\u0000', '').strip()
        page = entry.get('pageNumber', 0)

        if not title or title in ['封面页', '书名页', '版权页', '编委名单', '目录', '前言', '序言']:
            continue

        if level == 1 and '章' in title:
            chapter_name = extract_name(title, r'第[一二三四五六七八九十百零0-9]+章\s*(.+)')
            current_chapter = {
                'name': chapter_name,
                'label': title,
                'pageNum': page,
                'children': [],
            }
            chapters.append(current_chapter)

        elif level == 2 and '节' in title and current_chapter is not None:
            section_name = extract_name(title, r'第[一二三四五六七八九十百零0-9]+节\s*(.+)')
            current_chapter['children'].append({
                'name': section_name,
                'label': title,
                'pageNum': page,
            })

    for chapter in chapters:
        if not chapter.get('children'):
            del chapter['children']

    part = {
        'systemKey': book_name,
        'subject': book_name,
        'title': f'{book_name}（第10版）',
        'chapters': chapters,
    }

    return {
        'book': f'{book_name}（第10版）',
        'parts': [part],
    }


def generate_flat_catalog(toc: list[dict[str, Any]], book_name: str) -> dict[str, Any]:
    chapters: list[dict[str, Any]] = []

    for entry in toc:
        level = entry.get('level', 1)
        title = entry.get('title', '').replace('\u0000', '').strip()
        page = entry.get('pageNumber', 0)

        if not title or title in ['封面页', '书名页', '版权页', '编委名单', '目录', '前言', '序言']:
            continue

        if level == 1:
            chapters.append({
                'name': clean_title(title),
                'label': title,
                'pageNum': page,
            })

    part = {
        'systemKey': book_name,
        'subject': book_name,
        'title': f'{book_name}（第10版）',
        'chapters': chapters,
    }

    return {
        'book': f'{book_name}（第10版）',
        'parts': [part],
    }


def main():
    generated_dir = ROOT / 'generated' / 'textbook'
    output_dir = ROOT / 'scripts' / 'textbook_pipeline'

    for book_dir in generated_dir.iterdir():
        if not book_dir.is_dir():
            continue

        toc_path = book_dir / 'toc.json'
        if not toc_path.exists():
            continue

        catalog_name = f'catalog.{book_dir.name}.json'
        catalog_path = output_dir / catalog_name

        try:
            toc = json.loads(toc_path.read_text(encoding='utf-8'))
            book_name = book_dir.name.rsplit('-', 1)[0].replace('-', ' ')

            for known, slug in KNOWN_TITLES.items():
                if slug in book_dir.name:
                    book_name = known
                    break

            metadata_path = book_dir / 'metadata.json'
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
                if 'title' in metadata:
                    book_name = metadata['title']

            catalog = generate_catalog_from_toc(toc, book_name)
            structure = detect_structure(toc)

            catalog_path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )

            parts = catalog['parts']
            total_chapters = sum(len(p.get('chapters', [])) for p in parts)
            total_sections = sum(
                len(ch.get('children', []))
                for p in parts
                for ch in p.get('chapters', [])
            )
            print(f'[ok] {catalog_name}: {structure}, {len(parts)} parts, {total_chapters} chapters, {total_sections} sections')

        except Exception as e:
            print(f'[error] {catalog_name}: {e}')


if __name__ == '__main__':
    main()
