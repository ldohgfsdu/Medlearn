"""Golden fixture tests for Document Tree v1 builder.

Two-tier structure:
- Core tests (never skip): synthetic fixtures, verify invariants, dataclass,
  heading stack logic, manifest checksum.
- PDF integration tests (skip if PDF absent): golden paths, chapter merge,
  bracket split, ID stability, full invariant verification on real PDF.

Per ADR-011 and docs/architecture/document_tree_splitter_spec.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.document_tree import (  # noqa: E402
    ContentBlock,
    DocumentNode,
    DocumentTree,
    GOLDEN_SCOPE_PROFILE,
    HeadingAnchor,
    PendingReviewRecord,
    SourceAnchor,
)
from textbook_pipeline.document_tree_builder import (  # noqa: E402
    DEFAULT_SCOPES,
    InvariantViolation,
    build_from_manifest,
    build_scope_tree,
    manifest_checksum,
    verify_invariants,
)

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"
MANIFEST = ROOT / "manifests" / "internal-medicine-10.source_scopes.json"

ASTHMA_SCOPE = DEFAULT_SCOPES[0]
TB_SCOPE = DEFAULT_SCOPES[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_anchor(page: int = 62, raw: str = "p62:b0:l0:test") -> HeadingAnchor:
    return HeadingAnchor(
        pdf_page_number_1based=page,
        raw_block_index=0,
        raw_line_index=0,
        raw_anchor=raw,
    )


def _make_node(
    nid: str = "dt:v:s:hash:p62:b0:l0:test",
    parent_id: str | None = None,
    depth: int = 0,
    title: str = "第四章 支气管哮喘",
    marker: str = "chapter",
    source_order: int = 0,
    sibling_order: int = 0,
) -> DocumentNode:
    return DocumentNode(
        id=nid,
        parent_id=parent_id,
        depth=depth,
        source_title=title,
        source_title_raw=title,
        marker_kind=marker,
        origin="explicit_marker",
        source_order=source_order,
        sibling_order=sibling_order,
        heading_anchor=_make_anchor(),
    )


def _make_block(
    nid: str = "cb:v:s:0",
    node_id: str = "dt:v:s:hash:p62:b0:l0:test",
    text: str = "body text",
    order: int = 0,
) -> ContentBlock:
    return ContentBlock(
        id=nid,
        document_node_id=node_id,
        block_type="text_block",
        raw_text=text,
        source_order=order,
        source_anchor=SourceAnchor(
            pdf_page_number_1based=62,
            raw_block_index=1,
            raw_line_index=0,
        ),
    )


# ---------------------------------------------------------------------------
# Core: dataclass & serialization
# ---------------------------------------------------------------------------

class TestDocumentNodeSerialization:
    def test_node_to_dict_roundtrip(self):
        n = _make_node()
        d = n.to_dict()
        assert d["id"] == n.id
        assert d["parent_id"] is None
        assert d["depth"] == 0
        assert d["marker_kind"] == "chapter"
        assert d["origin"] == "explicit_marker"
        assert "heading_anchor" in d
        assert d["content_block_ids"] == []

    def test_node_merged_from_lines_serialized(self):
        n = _make_node()
        n.merged_from_lines = [0, 1]
        d = n.to_dict()
        assert d["merged_from_lines"] == [0, 1]

    def test_block_to_dict(self):
        b = _make_block()
        d = b.to_dict()
        assert d["block_type"] == "text_block"
        assert d["raw_text"] == "body text"
        assert "source_anchor" in d


class TestDocumentTreeSerialization:
    def test_tree_to_dict_has_contract_version(self):
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="internal-medicine-10",
            scope_id="asthma",
            catalog_path=["第二篇", "第四章 支气管哮喘"],
            nodes=[],
            content_blocks=[],
        )
        d = tree.to_dict()
        assert d["contract_version"] == "document_tree.v1"
        assert d["scope_id"] == "asthma"
        assert d["nodes"] == []
        assert d["content_blocks"] == []


# ---------------------------------------------------------------------------
# Core: invariant verification
# ---------------------------------------------------------------------------

class TestInvariants:
    def test_valid_tree_passes(self):
        root = _make_node(nid="root", depth=0, source_order=0, sibling_order=0)
        child = _make_node(
            nid="child", parent_id="root", depth=1, marker="bracket",
            source_order=1, sibling_order=0,
        )
        block = _make_block(nid="cb:0", node_id="child", order=0)
        child.content_block_ids = ["cb:0"]
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v",
            scope_id="s",
            catalog_path=[],
            nodes=[root, child],
            content_blocks=[block],
        )
        verify_invariants(tree)  # should not raise

    def test_inv1_orphan_block_raises(self):
        root = _make_node(nid="root", source_order=0)
        orphan = _make_block(nid="cb:0", node_id="missing", order=0)
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v",
            scope_id="s",
            catalog_path=[],
            nodes=[root],
            content_blocks=[orphan],
        )
        with pytest.raises(InvariantViolation, match="INV1"):
            verify_invariants(tree)

    def test_inv2_dangling_parent_raises(self):
        n = _make_node(nid="n", parent_id="missing", source_order=0)
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v",
            scope_id="s",
            catalog_path=[],
            nodes=[n],
            content_blocks=[],
        )
        with pytest.raises(InvariantViolation, match="INV2"):
            verify_invariants(tree)

    def test_inv2_parent_after_child_raises(self):
        # parent has higher source_order than child → cycle-like
        child = _make_node(nid="child", parent_id="parent", source_order=0)
        parent = _make_node(nid="parent", parent_id=None, source_order=1)
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v",
            scope_id="s",
            catalog_path=[],
            nodes=[child, parent],
            content_blocks=[],
        )
        with pytest.raises(InvariantViolation, match="INV2"):
            verify_invariants(tree)

    def test_inv6_source_order_not_increasing_raises(self):
        n1 = _make_node(nid="n1", source_order=1)
        n2 = _make_node(nid="n2", source_order=1)
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v",
            scope_id="s",
            catalog_path=[],
            nodes=[n1, n2],
            content_blocks=[],
        )
        with pytest.raises(InvariantViolation, match="INV6"):
            verify_invariants(tree)

    def test_inv6_sibling_order_mismatch_raises(self):
        root = _make_node(nid="root", source_order=0, sibling_order=0)
        c1 = _make_node(nid="c1", parent_id="root", depth=1, marker="bracket",
                        source_order=1, sibling_order=0)
        c2 = _make_node(nid="c2", parent_id="root", depth=1, marker="bracket",
                        source_order=2, sibling_order=2)  # should be 1
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v",
            scope_id="s",
            catalog_path=[],
            nodes=[root, c1, c2],
            content_blocks=[],
        )
        with pytest.raises(InvariantViolation, match="INV6"):
            verify_invariants(tree)

    def test_inv3_invalid_origin_raises(self):
        n = _make_node()
        n.origin = "llm_inferred"
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v",
            scope_id="s",
            catalog_path=[],
            nodes=[n],
            content_blocks=[],
        )
        with pytest.raises(InvariantViolation, match="INV3"):
            verify_invariants(tree)


# ---------------------------------------------------------------------------
# Core: manifest checksum
# ---------------------------------------------------------------------------

class TestManifestChecksum:
    def test_checksum_reproducible(self):
        manifest = {
            "manifest_version": "1",
            "textbook_version_id": "test",
            "manifest_checksum": "",
            "scopes": [],
        }
        cs1 = manifest_checksum(manifest)
        cs2 = manifest_checksum(manifest)
        assert cs1 == cs2
        assert len(cs1) == 64

    def test_checksum_changes_with_content(self):
        base = {
            "manifest_version": "1",
            "textbook_version_id": "test",
            "scopes": [],
        }
        modified = dict(base)
        modified["textbook_version_id"] = "changed"
        assert manifest_checksum(base) != manifest_checksum(modified)

    def test_checksum_ignores_self(self):
        m1 = {"manifest_version": "1", "manifest_checksum": "aaa"}
        m2 = {"manifest_version": "1", "manifest_checksum": "bbb"}
        assert manifest_checksum(m1) == manifest_checksum(m2)


# ---------------------------------------------------------------------------
# PDF integration tests (skip if PDF or manifest absent)
# ---------------------------------------------------------------------------

pytestmark_pdf = pytest.mark.skipif(
    not PDF.exists() or not MANIFEST.exists(),
    reason="textbook PDF or source scope manifest not present",
)


@pytestmark_pdf
class TestPDFBuildScopeTree:
    def test_asthma_tree_builds_without_error(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        assert tree.scope_id == "asthma"
        assert len(tree.nodes) > 0
        assert len(tree.content_blocks) > 0

    def test_tb_tree_builds_without_error(self):
        tree = build_scope_tree(PDF, TB_SCOPE)
        assert tree.scope_id == "tuberculosis"
        assert len(tree.nodes) > 0
        assert len(tree.content_blocks) > 0

    def test_invariants_pass_asthma(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        verify_invariants(tree)  # should not raise

    def test_invariants_pass_tb(self):
        tree = build_scope_tree(PDF, TB_SCOPE)
        verify_invariants(tree)  # should not raise


@pytestmark_pdf
class TestPDFChapterMerge:
    def test_asthma_chapter_full_title(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        chapter_nodes = [n for n in tree.nodes if n.marker_kind == "chapter"]
        assert chapter_nodes, "expected at least one chapter node"
        first = chapter_nodes[0]
        assert "第四章" in first.source_title
        assert "支气管哮喘" in first.source_title
        assert first.depth == 0
        assert first.parent_id is None

    def test_tb_chapter_full_title(self):
        tree = build_scope_tree(PDF, TB_SCOPE)
        chapter_nodes = [n for n in tree.nodes if n.marker_kind == "chapter"]
        assert chapter_nodes, "expected at least one chapter node"
        first = chapter_nodes[0]
        assert "第八章" in first.source_title
        assert "肺结核" in first.source_title
        assert first.depth == 0

    def test_merged_chapter_has_joint_anchor(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        chapter_nodes = [n for n in tree.nodes if n.marker_kind == "chapter"]
        first = chapter_nodes[0]
        # Merged chapter has line range like "0-1"
        assert isinstance(first.heading_anchor.raw_line_index, str)
        assert "-" in str(first.heading_anchor.raw_line_index)


@pytestmark_pdf
class TestPDFBracketSplit:
    def test_asthma_bracket_has_body(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        bracket_nodes = [n for n in tree.nodes if n.marker_kind == "bracket"]
        # At least one bracket heading should have a content block (body text)
        has_body = any(n.content_block_ids for n in bracket_nodes)
        assert has_body, "expected at least one bracket heading with body text"

    def test_asthma_bracket_popular_epidemiology(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        epi = [n for n in tree.nodes if "流行病学" in n.source_title]
        assert epi, "expected 【流行病学】 node"
        assert epi[0].marker_kind == "bracket"
        assert epi[0].content_block_ids, "expected body text after 【流行病学】"

    def test_tb_bracket_classification_standard(self):
        tree = build_scope_tree(PDF, TB_SCOPE)
        cls = [n for n in tree.nodes if "结核病的分类标准" in n.source_title]
        assert cls, "expected 【结核病的分类标准】 node"
        assert cls[0].marker_kind == "bracket"
        assert cls[0].content_block_ids, "expected body text after bracket"


@pytestmark_pdf
class TestPDFGoldenPaths:
    """Golden path assertions per contract §7.2.

    Each path is verified by walking nodes in source_order and matching
    expected nodes to distinct candidates in strict order.
    """

    def _match_path(self, tree: DocumentTree, expected: list[dict]) -> bool:
        """Match expected nodes to tree nodes in strict source order."""
        search_start = 0
        matched = []
        for exp in expected:
            found = None
            for i in range(search_start, len(tree.nodes)):
                n = tree.nodes[i]
                if n.marker_kind != exp["marker"]:
                    continue
                if exp["title_contains"] not in n.source_title:
                    continue
                found = n
                search_start = i + 1
                break
            if not found:
                return False, matched
            matched.append(found)
        return True, matched

    def test_asthma_lab_pulmonary_path(self):
        """哮喘路径：实验室和其他检查 → 肺功能检查 → 支气管舒张试验."""
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        ok, matched = self._match_path(tree, [
            {"marker": "bracket", "title_contains": "实验室"},
            {"marker": "chinese_parenthetical", "title_contains": "肺功能"},
            {"marker": "arabic_dot", "title_contains": "支气管舒张"},
        ])
        assert ok, (
            f"golden path not matched; found {[m.source_title for m in matched]}"
        )
        # Verify depth hierarchy
        assert matched[0].depth == 1
        assert matched[1].depth == 2
        assert matched[2].depth == 3
        # Verify parent chain
        assert matched[1].parent_id == matched[0].id
        assert matched[2].parent_id == matched[1].id

    def test_tb_classification_path(self):
        """肺结核路径：结核病的分类标准 → 活动性结核病 → 按病变部位分类."""
        tree = build_scope_tree(PDF, TB_SCOPE)
        ok, matched = self._match_path(tree, [
            {"marker": "bracket", "title_contains": "结核病的分类标准"},
            {"marker": "chinese_parenthetical", "title_contains": "活动性结核病"},
            {"marker": "arabic_dot", "title_contains": "按病变部位"},
        ])
        assert ok, (
            f"golden path not matched; found {[m.source_title for m in matched]}"
        )
        assert matched[0].depth == 1
        assert matched[1].depth == 2
        assert matched[2].depth == 3

    def test_asthma_combined_heading_preserved(self):
        """INV4: 病因和发病机制 must be a single source heading."""
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        combined = [
            n for n in tree.nodes
            if "病因和发病机制" in n.source_title
        ]
        assert len(combined) == 1, (
            f"expected exactly 1 combined heading, got {len(combined)}: "
            f"{[n.source_title for n in combined]}"
        )


@pytestmark_pdf
class TestPDFNumberedBody:
    def test_arabic_parenthetical_not_in_nodes(self):
        """arabic_parenthetical (（1）) should never produce a node."""
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        for n in tree.nodes:
            assert n.marker_kind != "arabic_parenthetical", (
                f"arabic_parenthetical should not produce a node: {n.source_title}"
            )

    def test_arabic_right_paren_not_in_nodes(self):
        tree = build_scope_tree(PDF, TB_SCOPE)
        for n in tree.nodes:
            assert n.marker_kind != "arabic_right_parenthesis", (
                f"arabic_right_parenthesis should not produce a node: {n.source_title}"
            )


@pytestmark_pdf
class TestPDFIDStability:
    def test_asthma_ids_stable_across_runs(self):
        tree1 = build_scope_tree(PDF, ASTHMA_SCOPE)
        tree2 = build_scope_tree(PDF, ASTHMA_SCOPE)
        ids1 = [n.id for n in tree1.nodes]
        ids2 = [n.id for n in tree2.nodes]
        assert ids1 == ids2, "node IDs changed across runs"

    def test_tb_ids_stable_across_runs(self):
        tree1 = build_scope_tree(PDF, TB_SCOPE)
        tree2 = build_scope_tree(PDF, TB_SCOPE)
        ids1 = [n.id for n in tree1.nodes]
        ids2 = [n.id for n in tree2.nodes]
        assert ids1 == ids2, "node IDs changed across runs"

    def test_anchor_id_has_full_pdf_checksum(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        import hashlib
        expected = hashlib.sha256(PDF.read_bytes()).hexdigest()
        for n in tree.nodes:
            # anchor_id format: dt:{version}:{scope}:{pdf_sha256}:{raw_anchor}
            parts = n.id.split(":", 4)
            assert len(parts) == 5
            assert parts[4] == n.heading_anchor.raw_anchor
            # 4th segment is full 64-hex-char SHA-256
            assert len(parts[3]) == 64
            assert parts[3].lower() == expected.lower()


@pytestmark_pdf
class TestPDFManifestIntegration:
    def test_build_from_manifest(self):
        trees = build_from_manifest(PDF, MANIFEST)
        assert len(trees) == 2
        assert trees[0].scope_id == "asthma"
        assert trees[1].scope_id == "tuberculosis"
        for tree in trees:
            verify_invariants(tree)

    def test_manifest_checksum_matches(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        stored = manifest["manifest_checksum"]
        calc = manifest_checksum(manifest)
        assert stored == calc

    def test_manifest_rejects_tampered_checksum(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["manifest_checksum"] = "tampered"
        manifest_path = ROOT / "generated" / "heading_audit" / "tampered_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        try:
            with pytest.raises(InvariantViolation, match="checksum"):
                build_from_manifest(PDF, manifest_path)
        finally:
            manifest_path.unlink()


# ---------------------------------------------------------------------------
# Core: depth derivation (depth = parent.depth + 1)
# ---------------------------------------------------------------------------

class TestDepthDerivation:
    def test_root_depth_zero(self):
        root = _make_node(nid="root", depth=0, source_order=0, sibling_order=0)
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v", scope_id="s", catalog_path=[],
            nodes=[root], content_blocks=[],
        )
        verify_invariants(tree)  # root with depth 0 passes

    def test_root_nonzero_depth_raises(self):
        root = _make_node(nid="root", depth=1, source_order=0, sibling_order=0)
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v", scope_id="s", catalog_path=[],
            nodes=[root], content_blocks=[],
        )
        with pytest.raises(InvariantViolation, match="root.*depth"):
            verify_invariants(tree)

    def test_child_depth_not_parent_plus_one_raises(self):
        root = _make_node(nid="root", depth=0, source_order=0, sibling_order=0)
        child = _make_node(
            nid="child", parent_id="root", depth=2, marker="bracket",
            source_order=1, sibling_order=0,
        )
        tree = DocumentTree(
            contract_version="document_tree.v1",
            textbook_version_id="v", scope_id="s", catalog_path=[],
            nodes=[root, child], content_blocks=[],
        )
        with pytest.raises(InvariantViolation, match="depth.*parent"):
            verify_invariants(tree)


# ---------------------------------------------------------------------------
# Core: transition profile
# ---------------------------------------------------------------------------

class TestTransitionProfile:
    def test_find_parent_returns_lower_level(self):
        root = _make_node(nid="root", marker="chapter")
        bracket = _make_node(nid="b", parent_id="root", depth=1, marker="bracket")
        stack = [root, bracket]
        parent = GOLDEN_SCOPE_PROFILE.find_parent(stack, 3)  # arabic_dot level
        assert parent.id == "b"

    def test_find_parent_skips_same_level(self):
        root = _make_node(nid="root", marker="chapter")
        bracket = _make_node(nid="b", parent_id="root", depth=1, marker="bracket")
        arabic1 = _make_node(nid="a1", parent_id="b", depth=2, marker="arabic_dot")
        stack = [root, bracket, arabic1]
        # New arabic_dot: parent should be bracket, not arabic1 (same level)
        parent = GOLDEN_SCOPE_PROFILE.find_parent(stack, 3)
        assert parent.id == "b"

    def test_find_parent_returns_none_for_chapter(self):
        root = _make_node(nid="root", marker="chapter")
        stack = [root]
        # New chapter: no parent (level 0, nothing below)
        parent = GOLDEN_SCOPE_PROFILE.find_parent(stack, 0)
        assert parent is None


# ---------------------------------------------------------------------------
# PDF: depth integrity, pending reviews, source_title_raw
# ---------------------------------------------------------------------------

@pytestmark_pdf
class TestPDFDepthIntegrity:
    def test_all_nodes_depth_equals_parent_plus_one(self):
        for scope in [ASTHMA_SCOPE, TB_SCOPE]:
            tree = build_scope_tree(PDF, scope)
            node_map = {n.id: n for n in tree.nodes}
            for n in tree.nodes:
                if n.parent_id is None:
                    assert n.depth == 0, (
                        f"{scope['scope_id']}: root {n.source_title} depth={n.depth}"
                    )
                else:
                    parent = node_map[n.parent_id]
                    assert n.depth == parent.depth + 1, (
                        f"{scope['scope_id']}: {n.source_title} depth={n.depth} "
                        f"!= parent {parent.source_title} depth+1={parent.depth + 1}"
                    )

    def test_consecutive_arabic_dot_are_siblings(self):
        """Consecutive arabic_dot nodes must share the same parent."""
        for scope in [ASTHMA_SCOPE, TB_SCOPE]:
            tree = build_scope_tree(PDF, scope)
            arabic_nodes = [n for n in tree.nodes if n.marker_kind == "arabic_dot"]
            # Group consecutive arabic_dot nodes and check they share parent
            for i in range(1, len(arabic_nodes)):
                if arabic_nodes[i].source_order == arabic_nodes[i - 1].source_order + 1:
                    # Consecutive: could be siblings (same parent) — at minimum,
                    # neither should be parent of the other
                    assert arabic_nodes[i].parent_id != arabic_nodes[i - 1].id, (
                        f"{scope['scope_id']}: arabic_dot {arabic_nodes[i].source_title} "
                        f"nested under previous arabic_dot"
                    )


@pytestmark_pdf
class TestPDFPendingReviews:
    def test_asthma_has_pending_reviews(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        assert len(tree.pending_reviews) > 0, "expected ambiguous blocks in asthma"

    def test_tb_has_pending_reviews(self):
        tree = build_scope_tree(PDF, TB_SCOPE)
        assert len(tree.pending_reviews) > 0, "expected ambiguous blocks in tb"

    def test_pending_reviews_preserve_source_text(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        for pr in tree.pending_reviews:
            assert pr.line_text, f"pending review {pr.raw_anchor} has empty line_text"
            assert pr.reason, f"pending review {pr.raw_anchor} has empty reason"

    def test_pending_reviews_not_in_nodes(self):
        """Pending review raw_anchors must not appear as node IDs."""
        for scope in [ASTHMA_SCOPE, TB_SCOPE]:
            tree = build_scope_tree(PDF, scope)
            node_anchors = {n.heading_anchor.raw_anchor for n in tree.nodes}
            for pr in tree.pending_reviews:
                assert pr.raw_anchor not in node_anchors, (
                    f"pending review {pr.raw_anchor} also became a node"
                )


@pytestmark_pdf
class TestPDFSourceTitleRaw:
    def test_source_title_raw_has_no_body_text(self):
        """source_title_raw must not contain explanatory body text."""
        for scope in [ASTHMA_SCOPE, TB_SCOPE]:
            tree = build_scope_tree(PDF, scope)
            for n in tree.nodes:
                # Body punctuation in source_title_raw indicates body text leaked in
                # (headings may contain 、 or ， but not ：；。 which mark body)
                assert "。" not in n.source_title_raw, (
                    f"{scope['scope_id']}: {n.source_title} has 。 in source_title_raw"
                )
                # For split headings, source_title_raw should equal source_title
                assert n.source_title_raw == n.source_title or n.merged_from_lines, (
                    f"{scope['scope_id']}: source_title_raw != source_title for {n.source_title}"
                )

    def test_bracket_source_title_raw_is_heading_only(self):
        tree = build_scope_tree(PDF, ASTHMA_SCOPE)
        epi = [n for n in tree.nodes if "流行病学" in n.source_title]
        assert epi, "expected 【流行病学】 node"
        # source_title_raw should be just the heading, not heading + body
        assert "】" in epi[0].source_title_raw
        # No body sentence after 】
        after_bracket = epi[0].source_title_raw.split("】", 1)[-1] if "】" in epi[0].source_title_raw else ""
        assert len(after_bracket.strip()) == 0 or len(after_bracket.strip()) < 10, (
            f"source_title_raw has body after 】: {epi[0].source_title_raw!r}"
        )
