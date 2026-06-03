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
    title = re.sub(r'^[一二三四五六七八九十]+[、.]', '', title)
    title = re.sub(r'^第[一二三四五六七八九十百零0-9]+[章节篇]', '', title)
    return title.strip()


def extract_chapter_name(title: str) -> str:
    match = re.match(r'第[一二三四五六七八九十百零0-9]+章\s*(.+)', title)
    if match:
        return match.group(1).strip()
    return clean_title(title)


def generate_catalog_from_toc(toc: list[dict[str, Any]], book_name: str) -> dict[str, Any]:
    parts: list[dict[str, Any]] = []
    current_part: dict[str, Any] | None = None
    current_chapter: dict[str, Any] | None = None

    for entry in toc:
        level = entry.get('level', 1)
        title = entry.get('title', '').replace('\u0000', '').strip()

        if not title or title in ['封面页', '书名页', '版权页', '编委名单', '目录', '前言', '序言']:
            continue

        if level == 1:
            if '篇' in title:
                part_name = clean_title(title)
                system_key = part_name.replace('篇', '')
                current_part = {
                    'systemKey': system_key,
                    'subject': f'{book_name} - {system_key}',
                    'title': title,
                    'chapters': [],
                }
                parts.append(current_part)
                current_chapter = None
            elif '章' in title:
                if current_part is None:
                    current_part = {
                        'systemKey': '总论',
                        'subject': f'{book_name} - 总论',
                        'title': '总论',
                        'chapters': [],
                    }
                    parts.append(current_part)
                chapter_name = extract_chapter_name(title)
                current_chapter = {
                    'name': chapter_name,
                    'label': title,
                    'children': [],
                }
                current_part['chapters'].append(current_chapter)

        elif level == 2:
            if current_chapter is not None:
                section_name = clean_title(title)
                section = {
                    'name': section_name,
                    'label': title,
                }
                current_chapter.setdefault('children', []).append(section)

    for part in parts:
        for chapter in part['chapters']:
            if not chapter.get('children'):
                del chapter['children']

    return {
        'book': book_name,
        'parts': parts,
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

        if catalog_path.exists():
            print(f'[skip] {catalog_name} already exists')
            continue

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
            print(f'[ok] Generated {catalog_name}: {len(catalog["parts"])} parts')

        except Exception as e:
            print(f'[error] Failed to generate {catalog_name}: {e}')


if __name__ == '__main__':
    main()
