"""Heading stack regression for asthma lab / pulmonary pages."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline import evidence_extractor as ex  # noqa: E402

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"


def _norm_ws(s: str) -> str:
    return " ".join((s or "").split())


@pytest.mark.skipif(not PDF.exists(), reason="textbook PDF not present")
def test_pulmonary_numbered_blocks_inherit_lung_function_heading() -> None:
    arts = ex.extract_section_evidence(
        pdf_path=PDF,
        textbook_id="internal-medicine-10",
        book_id="internal-medicine-10",
        part_title="第二篇 呼吸系统疾病",
        section_title="第四章 支气管哮喘",
        page_start=64,
        page_end=64,
    )
    markers = (
        "1. 通气功能检测",
        "2. 支气管激发试验",
        "3. 支气管舒张试验",
        "4. 呼气峰流量",
    )
    pulmonary = [
        a
        for a in arts
        if any(_norm_ws(a.raw_text or "").startswith(m) for m in markers)
    ]
    assert pulmonary, "expected numbered pulmonary blocks on p64"
    for art in pulmonary:
        assert art.source_heading == "肺功能检查", (
            f"expected 肺功能检查, got {art.source_heading!r} for {art.raw_text[:40]!r}"
        )


def test_structural_prefix_bypasses_large_font_gate() -> None:
    text = "【实验室和其他检查】"
    assert ex._block_is_heading_flag(text, max_size=10.0, body_size=10.0) is True


def test_arabic_numbered_block_never_heading() -> None:
    text = "1. 通气功能检测 哮喘发作时呈阻塞性通气功能障碍表现"
    assert ex._block_is_heading_flag(text, max_size=10.0, body_size=10.0) is False


def test_paren_mixed_split() -> None:
    text = "（一） 痰嗜酸性粒细胞计数 大多数哮喘病人诱导痰中嗜酸性粒细胞计数增高"
    heading, body = ex._split_heading_body(text)
    assert heading == "（一） 痰嗜酸性粒细胞计数"
    assert body.startswith("大多数")
    assert ex._canonical_heading_label(heading) == "痰嗜酸性粒细胞计数"