"""Book registry: map textbook file names to book IDs."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path

KNOWN_BOOKS: dict[str, dict] = {
    "internal-medicine-10": {"title": "内科学", "edition": "第10版", "aliases": ["内科学（第10版）"]},
    "physiology-10":       {"title": "生理学", "edition": "第10版"},
    "biochemistry-10":     {"title": "生物化学与分子生物学", "edition": "第10版"},
    "psychology-8":        {"title": "医学心理学", "edition": "第8版"},
    "pharmacology-10":     {"title": "药理学", "edition": "第10版"},
    "health-law-6":        {"title": "卫生法", "edition": "第6版"},
    "diagnostics-10":      {"title": "诊断学", "edition": "第10版"},
    "surgery-10":          {"title": "外科学", "edition": "第10版"},
    "pediatrics-10":       {"title": "儿科学", "edition": "第10版"},
    "obstetrics-10":       {"title": "妇产科学", "edition": "第10版"},
    "immunology-8":        {"title": "医学免疫学", "edition": "第8版"},
    "preventive-medicine-8":{"title": "预防医学", "edition": "第8版"},
    "tcm-10":              {"title": "中医学", "edition": "第10版"},
    "neurology-9":         {"title": "神经病学", "edition": "第9版"},
    "medical-stats-8":     {"title": "医学统计学", "edition": "第8版"},
    "psychiatry-9":        {"title": "精神病学", "edition": "第9版"},
    "infectious-disease-10":{"title": "传染病学", "edition": "第10版"},
}

def slugify(name: str) -> str:
    n = re.sub(r'[（(].*?[)）]', '', name)
    n = re.sub(r'[^a-zA-Z0-9一-鿿]+', '-', n.strip()).strip('-').lower()
    return n

def get_book_id(file_path: str | Path) -> str:
    stem = Path(file_path).stem
    for book_id, info in KNOWN_BOOKS.items():
        for alias in info.get("aliases", []):
            if alias in stem:
                return book_id
        if slugify(info["title"]) in slugify(stem):
            return book_id
    return slugify(stem)
