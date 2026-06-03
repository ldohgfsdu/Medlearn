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


def extract_chapter_info(title: str) -> tuple[str, str]:
    match = re.match(r'(第[一二三四五六七八九十百零0-9]+章)\s*(.+)', title)
    if match:
        return match.group(1), match.group(2).strip()
    return '', clean_title(title)


def extract_section_info(title: str) -> tuple[str, str]:
    match = re.match(r'(第[一二三四五六七八九十百零0-9]+节)\s*(.+)', title)
    if match:
        return match.group(1), match.group(2).strip()
    return '', clean_title(title)


def generate_catalog_from_toc(toc: list[dict[str, Any]], book_name: str) -> dict[str, Any]:
    chapters: list[dict[str, Any]] = []
    current_chapter: dict[str, Any] | None = None

    for entry in toc:
        level = entry.get('level', 1)
        title = entry.get('title', '').replace('\u0000', '').strip()
        page = entry.get('pageNumber', 0)

        if not title or title in ['封面页', '书名页', '版权页', '编委名单', '目录', '前言', '序言']:
            continue

        if level == 1 and '章' in title:
            chapter_num, chapter_name = extract_chapter_info(title)
            current_chapter = {
                'name': chapter_name,
                'label': title,
                'pageNum': page,
                'children': [],
            }
            chapters.append(current_chapter)

        elif level == 2 and current_chapter is not None:
            section_num, section_name = extract_section_info(title)
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

            catalog_path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            chapters = catalog['parts'][0]['chapters'] if catalog['parts'] else []
            print(f'[ok] {catalog_name}: {len(chapters)} chapters')

        except Exception as e:
            print(f'[error] {catalog_name}: {e}')


if __name__ == '__main__':
    main()
