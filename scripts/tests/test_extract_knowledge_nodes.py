import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.textbook_pipeline.extract_knowledge_nodes import (
    clean_text,
    slug,
    hash_text,
    infer_node_type,
    extract_key_points,
)


def test_clean_text():
    assert clean_text("  hello  \n  world  ") == "hello\nworld"
    assert clean_text("\n\n\n") == ""
    assert clean_text("single line") == "single line"


def test_slug():
    assert slug("hello world") == "hello-world"
    assert slug("疾病诊断") == "疾病诊断"
    assert slug("test/path") == "test-path"
    assert slug("") == "node"
    assert slug("a" * 100)[:80] == "a" * 80


def test_hash_text():
    result = hash_text("test")
    assert len(result) == 16
    assert hash_text("test") == hash_text("test")
    assert hash_text("test") != hash_text("different")


def test_infer_node_type():
    assert infer_node_type("肺炎", "") == "disease"
    assert infer_node_type("病理机制", "") == "mechanism"
    assert infer_node_type("临床表现", "") == "symptom"
    assert infer_node_type("治疗方案", "") == "treatment"
    assert infer_node_type("基础概念", "") == "concept"
    assert infer_node_type("", "这是一种疾病") == "disease"


def test_extract_key_points():
    text = """这是介绍
• 要点一
• 要点二
1. 第一点
2. 第二点
普通文本"""
    points = extract_key_points(text)
    assert len(points) == 4
    assert "要点一" in points
    assert "1. 第一点" in points


def test_extract_key_points_empty():
    assert extract_key_points("") == []
    assert extract_key_points("普通文本\n没有要点") == []


def test_extract_key_points_limit():
    text = "\n".join([f"• 要点{i}" for i in range(20)])
    points = extract_key_points(text)
    assert len(points) == 10
