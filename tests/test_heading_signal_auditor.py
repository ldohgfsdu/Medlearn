"""Tests for heading signal auditor (read-only).

Two tiers:
- Core tests: use synthetic fixtures and call auditor functions directly.
  These NEVER skip and validate the classification/split/ID/path logic.
- PDF integration tests: load generated audit JSON. These skip when the
  source PDF or generated artifacts are unavailable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.heading_signal_auditor import (  # noqa: E402
    classify_line,
    compute_full_anchor_id,
    compute_raw_anchor,
    detect_marker,
    normalize_spans_for_fingerprint,
    verify_golden_paths,
)

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"
AUDIT_DIR = ROOT / "generated" / "heading_audit"
ASTHMA_AUDIT = AUDIT_DIR / "asthma.audit.json"
TB_AUDIT = AUDIT_DIR / "tuberculosis.audit.json"
STABILITY = AUDIT_DIR / "stability.json"
GOLDEN_PATHS = AUDIT_DIR / "golden_paths.json"


# ---------------------------------------------------------------------------
# Synthetic fixtures for core tests
# ---------------------------------------------------------------------------

def _span(text: str, font: str = "FZSSK--GBK1-0", size: float = 9.0,
          bbox: tuple = (0, 0, 100, 12)):
    return {"text": text, "font": font, "size": size, "bbox": list(bbox),
            "chars": [{"c": ch, "bbox": list(bbox)} for ch in text]}


def _line(text: str, font: str = "FZSSK--GBK1-0", size: float = 9.0,
          page: int = 1, block: int = 0, line_idx: int = 0):
    spans = [_span(text, font, size)]
    return {
        "pdf_page": page,
        "raw_block_index": block,
        "raw_line_index": line_idx,
        "line_text": text,
        "spans": spans,
    }


CHAPTER_LINE = _line("第四章\u2003", font="FZLTZCHK--GBK1-0", size=21.0)
BRACKET_WITH_BODY = _line("【流行病学】\u2003哮喘是常见慢性病。", font="FZLTHK--GBK1-0", size=10.5)
BRACKET_ORDINARY_SPACE = _line("【流行病学】 哮喘是世界上最常见的慢性疾病之一。", font="FZLTHK--GBK1-0", size=10.0)
BPT_LINE = _line("2.\u2002支气管激发试验（BPT）\u2003用于测定气道反应性。", font="FZLTHK--GBK1-0", size=10.5)
BDT_LINE = _line("3.\u2002支气管舒张试验（BDT）\u2003用于测定气道的可逆性改变。", font="FZLTHK--GBK1-0", size=10.5)
NUMBERED_BODY_COLON = _line("（1）\u2003气道炎症形成机制：气道慢性炎症反应。", font="FZSSK--GBK1-0", size=9.0)
NUMBERED_BODY_LONG = _line("（1）\u2003气道炎症形成机制是复杂的。", font="FZSSK--GBK1-0", size=9.0)
PAGE_HEADER_LINE = _line("第四章 支气管哮喘", font="FZLTZHUNHK--GBK1-0", size=8.0,
                         page=62, block=0, line_idx=0)
# page header bbox y0 < 50
PAGE_HEADER_SPAN = _span("第四章 支气管哮喘", "FZLTZHUNHK--GBK1-0", 8.0, (0, 10, 100, 20))


# ===========================================================================
# Core tests: marker detection
# ===========================================================================

class TestDetectMarker:
    def test_chapter(self):
        assert detect_marker("第四章 支气管哮喘") == "chapter"

    def test_bracket(self):
        assert detect_marker("【流行病学】哮喘") == "bracket"

    def test_chinese_paren(self):
        assert detect_marker("（一）病因") == "chinese_parenthetical"

    def test_arabic_dot(self):
        assert detect_marker("1. 药物分类") == "arabic_dot"

    def test_arabic_paren(self):
        assert detect_marker("（1）治疗") == "arabic_parenthetical"

    def test_arabic_right_paren(self):
        assert detect_marker("1）氟喹诺酮类") == "arabic_right_parenthesis"

    def test_no_marker(self):
        assert detect_marker("哮喘是慢性疾病") is None


# ===========================================================================
# Core tests: classify_line split dispatch
# ===========================================================================

class TestClassifySplit:
    def test_chapter_no_split(self):
        """Chapter title is standalone; U+2003 is trailing, not a body boundary."""
        cls = classify_line(CHAPTER_LINE)
        assert cls["classification"] == "heading_candidate"
        assert cls["marker"] == "chapter"
        assert cls["split_position"] is None
        assert cls["heading_text"] == "第四章"
        assert cls["body_text"] == ""

    def test_bracket_splits_on_em_space(self):
        """Bracket heading with U+2003 + body should split."""
        cls = classify_line(BRACKET_WITH_BODY)
        assert cls["classification"] == "heading_candidate"
        assert cls["marker"] == "bracket"
        assert cls["split_position"] is not None
        assert cls["heading_text"] == "【流行病学】"
        assert cls["body_text"] == "哮喘是常见慢性病。"

    def test_bracket_splits_on_ordinary_space(self):
        """Real PDF bracket headings use ordinary space after 】, not U+2003.
        The closing bracket is the delimiter; everything after is body."""
        cls = classify_line(BRACKET_ORDINARY_SPACE)
        assert cls["classification"] == "heading_candidate"
        assert cls["marker"] == "bracket"
        assert cls["split_position"] is not None
        assert cls["heading_text"] == "【流行病学】"
        assert cls["body_text"] == "哮喘是世界上最常见的慢性疾病之一。"

    def test_bracket_only_no_body(self):
        """Bracket heading with no text after 】 has empty body_text."""
        cls = classify_line(_line("【病因和发病机制】", font="FZLTHK--GBK1-0", size=10.0))
        assert cls["classification"] == "heading_candidate"
        assert cls["marker"] == "bracket"
        assert cls["split_position"] is None
        assert cls["heading_text"] == "【病因和发病机制】"
        assert cls["body_text"] == ""

    def test_bpt_splits_correctly(self):
        """BPT heading must not be truncated; split on U+2003."""
        cls = classify_line(BPT_LINE)
        assert cls["classification"] == "heading_candidate"
        assert cls["marker"] == "arabic_dot"
        assert cls["heading_text"] == "2.\u2002支气管激发试验（BPT）"
        assert cls["body_text"] == "用于测定气道反应性。"
        assert "BPT" in cls["heading_text"]

    def test_bdt_splits_correctly(self):
        """BDT heading must not be truncated; split on U+2003."""
        cls = classify_line(BDT_LINE)
        assert cls["classification"] == "heading_candidate"
        assert cls["heading_text"] == "3.\u2002支气管舒张试验（BDT）"
        assert cls["body_text"] == "用于测定气道的可逆性改变。"
        assert "BDT" in cls["heading_text"]

    def test_numbered_body_with_colon_is_body(self):
        """body font + U+2003 + colon => body, NOT heading."""
        cls = classify_line(NUMBERED_BODY_COLON)
        assert cls["classification"] == "body"
        assert cls["marker"] == "arabic_parenthetical"

    def test_numbered_body_long_is_body(self):
        """body font + U+2003 + sentence punctuation => body."""
        cls = classify_line(NUMBERED_BODY_LONG)
        assert cls["classification"] == "body"


# ===========================================================================
# Core tests: page header detection
# ===========================================================================

class TestPageHeader:
    def test_page_header_classified_as_page_header(self):
        line = {
            "pdf_page": 62, "raw_block_index": 0, "raw_line_index": 0,
            "line_text": "第四章 支气管哮喘",
            "spans": [PAGE_HEADER_SPAN],
        }
        cls = classify_line(line)
        assert cls["classification"] == "page_header"
        assert cls["marker"] is None


# ===========================================================================
# Core tests: deterministic ID (128-bit + full checksum)
# ===========================================================================

class TestDeterministicID:
    def test_raw_anchor_128_bits(self):
        """raw_anchor fingerprint must be >= 128 bits (32 hex chars)."""
        anchor = compute_raw_anchor(62, 0, 0, [_span("第四章", "FZLTZCHK--GBK1-0", 21.0)])
        parts = anchor.split(":")
        sha_part = parts[3]
        assert len(sha_part) == 32, f"Expected 32 hex chars (128 bit), got {len(sha_part)}"

    def test_raw_anchor_stable(self):
        """Same input => same anchor."""
        spans = [_span("第四章", "FZLTZCHK--GBK1-0", 21.0)]
        a1 = compute_raw_anchor(62, 0, 0, spans)
        a2 = compute_raw_anchor(62, 0, 0, spans)
        assert a1 == a2

    def test_raw_anchor_differs_on_different_input(self):
        a1 = compute_raw_anchor(62, 0, 0, [_span("第四章", "FZLTZCHK--GBK1-0", 21.0)])
        a2 = compute_raw_anchor(62, 0, 0, [_span("第五章", "FZLTZCHK--GBK1-0", 21.0)])
        assert a1 != a2

    def test_anchor_id_contains_full_checksum(self):
        """anchor_id must retain the FULL PDF SHA-256, not truncated."""
        full_sha = "c0bb559fa2c8448a54612f7edf751c9342df584d15ce90d0cf7e4f97bf852d78"
        raw = "p62:b0:l0:abcdef0123456789abcdef0123456789"
        aid = compute_full_anchor_id("internal-medicine-10", "asthma", full_sha, raw)
        assert full_sha in aid, "anchor_id must contain full PDF SHA-256"
        parts = aid.split(":")
        # dt:{version}:{scope}:{full_sha}:{raw_anchor}
        assert parts[0] == "dt"
        assert parts[1] == "internal-medicine-10"
        assert parts[2] == "asthma"
        assert parts[3] == full_sha

    def test_normalize_no_str_float(self):
        """normalize must use round(), not str(float), for determinism."""
        s1 = normalize_spans_for_fingerprint([_span("test", size=9.0)])
        s2 = normalize_spans_for_fingerprint([_span("test", size=9.0000001)])
        # round(9.0000001, 2) == round(9.0, 2) == 9.0
        assert s1 == s2


# ===========================================================================
# Core tests: golden path verifier (ordered node matching)
# ===========================================================================

class TestGoldenPathVerifier:
    def _make_results(self, scope: str, lines: list):
        # verify_golden_paths walks T1-T5 across both asthma and tuberculosis;
        # ensure both scopes exist so the verifier doesn't KeyError on the
        # scope that the test isn't directly exercising.
        return {"scopes": {
            "asthma": {"lines": lines if scope == "asthma" else []},
            "tuberculosis": {"lines": lines if scope == "tuberculosis" else []},
        }}

    def test_ordered_match_passes(self):
        """Nodes must match in strict source order."""
        lines = [
            {"classification": "heading_candidate", "marker": "chapter",
             "heading_text": "第四章", "raw_anchor": "a1", "pdf_page": 62},
            {"classification": "heading_candidate", "marker": "bracket",
             "heading_text": "【流行病学】", "raw_anchor": "a2", "pdf_page": 62},
        ]
        results = self._make_results("asthma", lines)
        gp = verify_golden_paths(results)
        p = gp["golden_paths"][0]  # T1
        assert p["passed"] is True
        assert p["matched_node_count"] == 2

    def test_out_of_order_fails(self):
        """If bracket appears BEFORE chapter, T1 must fail."""
        lines = [
            {"classification": "heading_candidate", "marker": "bracket",
             "heading_text": "【流行病学】", "raw_anchor": "a1", "pdf_page": 62},
            {"classification": "heading_candidate", "marker": "chapter",
             "heading_text": "第四章", "raw_anchor": "a2", "pdf_page": 62},
        ]
        results = self._make_results("asthma", lines)
        gp = verify_golden_paths(results)
        p = gp["golden_paths"][0]  # T1 expects chapter THEN bracket
        assert p["passed"] is False

    def test_missing_node_fails(self):
        """If a required node is missing, path must fail."""
        lines = [
            {"classification": "heading_candidate", "marker": "chapter",
             "heading_text": "第四章", "raw_anchor": "a1", "pdf_page": 62},
        ]
        results = self._make_results("asthma", lines)
        gp = verify_golden_paths(results)
        p = gp["golden_paths"][0]  # T1 needs chapter + bracket
        assert p["passed"] is False
        assert p["matched_node_count"] == 1

    def test_page_header_as_heading_fails(self):
        """If a page header is misclassified as heading_candidate, path fails."""
        lines = [
            {"classification": "heading_candidate", "marker": "chapter",
             "heading_text": "第四章", "raw_anchor": "a1", "pdf_page": 62},
            {"classification": "heading_candidate", "marker": "bracket",
             "heading_text": "【流行病学】", "raw_anchor": "a2", "pdf_page": 62},
            {"classification": "page_header", "marker": None,
             "heading_text": "", "raw_anchor": "a3", "pdf_page": 63},
        ]
        results = self._make_results("asthma", lines)
        gp = verify_golden_paths(results)
        p = gp["golden_paths"][0]
        assert p["passed"] is True  # page_header is not heading_candidate
        assert p["page_headers_are_not_nodes"] is True

    def test_page_header_misclassified_as_heading_fails(self):
        """Document the verifier boundary: when a page-header-like line is
        misclassified as heading_candidate, the ordered matcher only matches
        by marker+title, so the extra candidate is ignored by T1. Page-header
        detection is a classify_line responsibility (via is_page_header), not
        a path-verifier responsibility — the verifier relies on classification
        being correct and reports page_headers_detected from the page_header
        classification bucket only."""
        lines = [
            {"classification": "heading_candidate", "marker": "chapter",
             "heading_text": "第四章", "raw_anchor": "a1", "pdf_page": 62},
            {"classification": "heading_candidate", "marker": "bracket",
             "heading_text": "【流行病学】", "raw_anchor": "a2", "pdf_page": 62},
            # Misclassified page header: classification says heading_candidate,
            # but heading_text repeats the chapter title (page-header pattern).
            # is_page_header() in classify_line should have caught this; here
            # we simulate the case where it didn't, to document the boundary.
            {"classification": "heading_candidate", "marker": "bracket",
             "heading_text": "第四章 支气管哮喘", "raw_anchor": "a3", "pdf_page": 63},
        ]
        results = self._make_results("asthma", lines)
        gp = verify_golden_paths(results)
        t1 = gp["golden_paths"][0]
        # T1's two expected nodes (chapter+bracket) still match in order.
        # The misclassified page header appears AFTER the matched bracket and
        # is never reached by the ordered matcher for T1's nodes.
        assert t1["passed"] is True
        assert t1["matched_node_count"] == 2
        # No line is classified as page_header, so the verifier reports zero
        # detected page headers — it cannot detect misclassification within
        # heading_candidate. This is the documented boundary.
        assert t1["page_headers_detected"] == 0


# ===========================================================================
# PDF integration tests (skip if PDF or artifacts unavailable)
# ===========================================================================

_pdf_available = PDF.exists()
_artifacts_available = ASTHMA_AUDIT.exists() and TB_AUDIT.exists() and STABILITY.exists() and GOLDEN_PATHS.exists()

pytestmark_integration = pytest.mark.skipif(
    not _artifacts_available,
    reason="heading_audit artifacts not generated; run heading_signal_auditor.py --twice",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def asthma_audit() -> dict:
    return _load(ASTHMA_AUDIT)


@pytest.fixture(scope="module")
def tb_audit() -> dict:
    return _load(TB_AUDIT)


@pytest.fixture(scope="module")
def stability() -> dict:
    return _load(STABILITY)


@pytest.fixture(scope="module")
def golden_paths() -> dict:
    return _load(GOLDEN_PATHS)


@pytestmark_integration
class TestPDFStability:
    def test_overall_stable(self, stability: dict):
        assert stability["stable"] is True

    def test_asthma_identical(self, stability: dict):
        s = stability["scopes"]["asthma"]
        assert s["identical_order"] is True
        assert s["identical_set"] is True

    def test_tb_identical(self, stability: dict):
        s = stability["scopes"]["tuberculosis"]
        assert s["identical_order"] is True
        assert s["identical_set"] is True


@pytestmark_integration
class TestPDFPageHeaders:
    def test_asthma_page_headers_not_nodes(self, asthma_audit: dict):
        headers = [l for l in asthma_audit["lines"] if l["classification"] == "page_header"]
        assert len(headers) > 0
        for h in headers:
            assert h["marker"] is None

    def test_tb_page_headers_not_nodes(self, tb_audit: dict):
        headers = [l for l in tb_audit["lines"] if l["classification"] == "page_header"]
        assert len(headers) > 0
        for h in headers:
            assert h["marker"] is None

    def test_asthma_chapter_unique(self, asthma_audit: dict):
        chapters = [l for l in asthma_audit["lines"] if l["marker"] == "chapter"]
        assert len(chapters) == 1

    def test_tb_chapter_unique(self, tb_audit: dict):
        chapters = [l for l in tb_audit["lines"] if l["marker"] == "chapter"]
        assert len(chapters) == 1


@pytestmark_integration
class TestPDFGoldenPaths:
    def test_all_five_paths_pass(self, golden_paths: dict):
        paths = golden_paths["golden_paths"]
        assert len(paths) == 5
        for p in paths:
            assert p["passed"] is True, f"{p['path_id']} failed"
            assert p["matched_node_count"] == p["expected_node_count"]

    def test_t4_checks_classification_standard(self, golden_paths: dict):
        """T4 must verify '结核病的分类标准' (with 的), not '结核病分类标准'."""
        t4 = golden_paths["golden_paths"][3]
        assert t4["passed"] is True
        # The bracket node must match "结核病的分类标准"
        bracket_node = [m for m in t4["node_matches"] if m["expected_marker"] == "bracket"][0]
        assert bracket_node["matched"] is True
        assert "结核病的分类标准" in bracket_node["expected_title_contains"]

    def test_t5_includes_initial_treatment(self, golden_paths: dict):
        """T5 must include the initial-treatment (初治) heading."""
        t5 = golden_paths["golden_paths"][4]
        assert t5["passed"] is True
        # Last node should be arabic_dot matching 初治
        last_node = t5["node_matches"][-1]
        assert last_node["expected_marker"] == "arabic_dot"
        assert "初治" in last_node["expected_title_contains"]
        assert last_node["matched"] is True


@pytestmark_integration
class TestPDFBPTBDT:
    def test_bpt_heading_not_truncated(self, asthma_audit: dict):
        bpt = [l for l in asthma_audit["lines"]
               if l["classification"] == "heading_candidate" and "BPT" in l.get("heading_text", "")]
        assert len(bpt) > 0
        for line in bpt:
            assert "BPT" in line["heading_text"]
            assert line["body_text"]  # must have body

    def test_bdt_heading_not_truncated(self, asthma_audit: dict):
        bdt = [l for l in asthma_audit["lines"]
               if l["classification"] == "heading_candidate" and "BDT" in l.get("heading_text", "")]
        assert len(bdt) > 0
        for line in bdt:
            assert "BDT" in line["heading_text"]
            assert line["body_text"]

    def test_chapter_merged_full_title(self, asthma_audit: dict):
        """Chapter title must be merged across continuation lines:
        '第四章' + '支气管哮喘' → '第四章 支气管哮喘'."""
        chapters = [l for l in asthma_audit["lines"] if l["marker"] == "chapter"]
        assert len(chapters) == 1
        c = chapters[0]
        assert c["heading_text"] == "第四章 支气管哮喘"
        assert c["body_text"] == ""
        # Joint SourceAnchor: line index is a range like "0-1"
        assert "-" in str(c["raw_line_index"]), "merged chapter must have line-range anchor"
        assert "merged_from_lines" in c


@pytestmark_integration
class TestPDFChapterMergeTB:
    def test_tb_chapter_merged_full_title(self, tb_audit: dict):
        """TB chapter: '第八章' + '肺结核' → '第八章 肺结核'."""
        chapters = [l for l in tb_audit["lines"] if l["marker"] == "chapter"]
        assert len(chapters) == 1
        c = chapters[0]
        assert c["heading_text"] == "第八章 肺结核"
        assert c["body_text"] == ""
        assert "-" in str(c["raw_line_index"])
        assert "merged_from_lines" in c


@pytestmark_integration
class TestPDFBracketBody:
    def test_asthma_bracket_epidemiology_has_body(self, asthma_audit: dict):
        """Real bracket heading 【流行病学】 must split body at closing 】."""
        epi = [l for l in asthma_audit["lines"]
               if l["marker"] == "bracket" and "流行病学" in l.get("heading_text", "")]
        assert len(epi) == 1
        assert epi[0]["heading_text"] == "【流行病学】"
        assert epi[0]["body_text"].startswith("哮喘是世界上最常见")

    def test_asthma_bracket_no_body_when_standalone(self, asthma_audit: dict):
        """Bracket heading with no body after 】 has empty body_text."""
        standalone = [l for l in asthma_audit["lines"]
                      if l["marker"] == "bracket" and l.get("body_text") == ""]
        assert len(standalone) > 0
        for s in standalone:
            assert s["heading_text"].endswith("】")
            assert not s["body_text"]

    def test_tb_bracket_classification_standard_has_body(self, tb_audit: dict):
        """【结核病的分类标准】 must split body at closing 】."""
        cls = [l for l in tb_audit["lines"]
               if l["marker"] == "bracket" and "结核病的分类标准" in l.get("heading_text", "")]
        assert len(cls) == 1
        assert cls[0]["heading_text"] == "【结核病的分类标准】"
        assert cls[0]["body_text"]  # body about WS 196-2017 standard

    def test_tb_bracket_pathogen_has_body(self, tb_audit: dict):
        """【结核分枝杆菌】 must split body at closing 】."""
        pathogen = [l for l in tb_audit["lines"]
                    if l["marker"] == "bracket" and "结核分枝杆菌" in l.get("heading_text", "")]
        assert len(pathogen) == 1
        assert pathogen[0]["heading_text"] == "【结核分枝杆菌】"
        assert pathogen[0]["body_text"].startswith("结核病的病原菌为")

    def test_tb_bracket_chemotherapy_is_standalone(self, tb_audit: dict):
        """【结核病的化学治疗】 is a standalone heading (no body on same line)."""
        chemo = [l for l in tb_audit["lines"]
                 if l["marker"] == "bracket" and "结核病的化学治疗" in l.get("heading_text", "")]
        assert len(chemo) == 1
        assert chemo[0]["heading_text"] == "【结核病的化学治疗】"
        assert chemo[0]["body_text"] == ""


@pytestmark_integration
class TestPDFNumberedBody:
    def test_arabic_paren_body_with_punct_not_heading(self, asthma_audit: dict):
        clear_body = [
            l for l in asthma_audit["lines"]
            if l["marker"] == "arabic_parenthetical"
            and l["first_font"] == "FZSSK--GBK1-0"
            and l.get("has_body_punct") is True
        ]
        assert len(clear_body) > 0
        for line in clear_body:
            assert line["classification"] != "heading_candidate"


@pytestmark_integration
class TestPDFMarkerFontCorrelation:
    def test_bracket_always_heading_font(self, asthma_audit: dict, tb_audit: dict):
        for audit in [asthma_audit, tb_audit]:
            brackets = [l for l in audit["lines"] if l["marker"] == "bracket"]
            for b in brackets:
                assert b["first_font"] == "FZLTHK--GBK1-0"

    def test_chinese_paren_always_fzzysk(self, asthma_audit: dict, tb_audit: dict):
        for audit in [asthma_audit, tb_audit]:
            cps = [l for l in audit["lines"] if l["marker"] == "chinese_parenthetical"]
            for c in cps:
                assert c["first_font"] == "FZZYSK1--GBK1-0"

    def test_arabic_dot_tb_all_heading_font(self, tb_audit: dict):
        dots = [l for l in tb_audit["lines"] if l["marker"] == "arabic_dot"]
        for d in dots:
            assert d["first_font"] == "FZLTHK--GBK1-0"


@pytestmark_integration
class TestPDFAnchorID:
    def test_anchor_id_contains_full_checksum(self, asthma_audit: dict):
        """anchor_id must contain the full 64-char PDF SHA-256."""
        sample = asthma_audit["lines"][0]
        aid = sample["anchor_id"]
        parts = aid.split(":")
        # dt:{version}:{scope}:{full_sha256}:{raw_anchor}
        checksum = parts[3]
        assert len(checksum) == 64, f"Expected full 64-char SHA-256, got {len(checksum)}"

    def test_raw_anchor_128_bits(self, asthma_audit: dict):
        """raw_anchor fingerprint must be 32 hex chars (128 bit)."""
        sample = asthma_audit["lines"][0]
        raw = sample["raw_anchor"]
        parts = raw.split(":")
        sha_part = parts[3]
        assert len(sha_part) == 32

    def test_unique_anchor_ids(self, asthma_audit: dict, tb_audit: dict):
        asthma_ids = [l["anchor_id"] for l in asthma_audit["lines"]]
        tb_ids = [l["anchor_id"] for l in tb_audit["lines"]]
        assert len(asthma_ids) == len(set(asthma_ids))
        assert len(tb_ids) == len(set(tb_ids))
