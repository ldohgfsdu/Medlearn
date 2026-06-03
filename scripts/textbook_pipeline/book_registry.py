import hashlib
import re
from pathlib import Path
from typing import Any

KNOWN_TITLES = {
    '内科学': 'internal-medicine',
    '生理学': 'physiology',
    '生物化学与分子生物学': 'biochemistry-molecular-biology',
    '医学心理学': 'medical-psychology',
    '药理学': 'pharmacology',
    '卫生法': 'health-law',
    '诊断学': 'diagnostics',
    '外科学': 'surgery',
    '儿科学': 'pediatrics',
    '妇产科学': 'obstetrics-gynecology',
    '医学免疫学': 'medical-immunology',
    '预防医学': 'preventive-medicine',
    '中医学': 'traditional-chinese-medicine',
    '神经病学': 'neurology',
    '医学统计学': 'medical-statistics',
    '精神病学': 'psychiatry',
    '传染病学': 'infectious-diseases',
}

CHINESE_NUMBERS = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}

EDITION_PATTERNS = [
    re.compile(r'(.+?)（第([0-9一二两三四五六七八九十]+)版）'),
    re.compile(r'(.+?)\(第([0-9一二两三四五六七八九十]+)版\)'),
    re.compile(r'(.+?)\s*第([0-9一二两三四五六七八九十]+)版'),
    re.compile(r'(.+?)[\s_]*([0-9一二两三四五六七八九十]+)版'),
]

VOLUME_PATTERNS = [
    (re.compile(r'[（(]上册[）)]|上册'), 'vol1'),
    (re.compile(r'[（(]下册[）)]|下册'), 'vol2'),
    (re.compile(r'第?1册|第一册'), 'vol1'),
    (re.compile(r'第?2册|第二册'), 'vol2'),
]


def chinese_number_to_int(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    if value == '十':
        return 10
    if value.startswith('十') and len(value) == 2:
        return 10 + CHINESE_NUMBERS.get(value[1], 0)
    if value.endswith('十') and len(value) == 2:
        return CHINESE_NUMBERS.get(value[0], 0) * 10
    if '十' in value and len(value) == 3:
        return CHINESE_NUMBERS.get(value[0], 0) * 10 + CHINESE_NUMBERS.get(value[2], 0)
    return CHINESE_NUMBERS.get(value)


def normalize_title(raw: str) -> str:
    value = re.sub(r'^[0-9]+\.\s*', '', raw)
    value = re.sub(r'[（(].*?[）)]', '', value)
    value = re.sub(r'[_\-\s]+', '', value)
    return value.strip()


def fallback_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:10]


def infer_book(path: Path, out_root: Path | None = None) -> dict[str, Any]:
    stem = path.stem
    title_raw = stem
    edition_number: int | None = None
    for pattern in EDITION_PATTERNS:
        match = pattern.search(stem)
        if match:
            title_raw = match.group(1)
            edition_number = chinese_number_to_int(match.group(2))
            break

    volume = None
    for pattern, volume_id in VOLUME_PATTERNS:
        if pattern.search(stem):
            volume = volume_id
            break

    title = normalize_title(title_raw)
    slug = None
    for known, known_slug in sorted(KNOWN_TITLES.items(), key=lambda x: len(x[0]), reverse=True):
        if known in title:
            title = known
            slug = known_slug
            break
    if not slug:
        slug = f'book-{fallback_hash(stem)}'

    parts = [slug]
    if edition_number:
        parts.append(str(edition_number))
    if volume:
        parts.append(volume)
    base_book_id = '-'.join(parts)
    book_id = base_book_id

    if out_root:
        suffix = 2
        while (out_root / book_id).exists():
            metadata_path = out_root / book_id / 'metadata.json'
            if metadata_path.exists() and str(path) in metadata_path.read_text(encoding='utf-8', errors='ignore'):
                break
            book_id = f'{base_book_id}-v{suffix}'
            suffix += 1

    return {
        'bookId': book_id,
        'title': title or stem,
        'edition': f'第{edition_number}版' if edition_number else None,
        'editionNumber': edition_number,
        'volume': volume,
        'sourceFilename': path.name,
    }


def supported_files(input_path: Path) -> list[Path]:
    exts = {'.pdf', '.txt'}
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in exts else []
    return sorted([p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() in exts])
