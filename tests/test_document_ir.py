import unittest

from scripts.textbook_pipeline.document_ir import (
    CanonicalDocumentIR,
    DocumentNode,
    RawSpan,
    SourceScopeManifest,
    artifact_to_document_block,
    build_source_anchor,
    raw_span_to_document_block,
    validate_document_ir,
)
from scripts.textbook_pipeline.evidence_artifact import EvidenceLocator, make_artifact


def artifact():
    return make_artifact(
        textbook_id="book-a",
        book_id="book-a",
        part_title="第一篇",
        section_title="第一章",
        source_heading="定义",
        normalized_aspect=None,
        source_order=1,
        artifact_type="text_block",
        raw_text="原始 文本",
        page_start=3,
        page_end=3,
        locator=EvidenceLocator(page=3, kind="paragraph", bbox=(1, 2, 30, 40)),
    )


class DocumentIRTests(unittest.TestCase):
    def _valid_document(self):
        block = artifact_to_document_block(
            artifact(),
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
            node_id="node-1",
            page_width=600,
            page_height=800,
        )
        node = DocumentNode(
            id="node-1",
            parent_id=None,
            source_title="定义",
            source_title_raw="定义",
            marker_kind="bracket",
            origin="explicit_marker",
            source_order=1,
            sibling_order=0,
            heading_anchor_id=block.id,
            content_block_ids=(block.id,),
        )
        manifest = SourceScopeManifest(
            id="scope-manifest-1",
            textbook_version_id="book-a-v1",
            source_pdf_sha256="a" * 64,
            page_start=3,
            page_end=3,
        )
        return CanonicalDocumentIR(
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
            blocks=[block],
            nodes=[node],
            scope_manifest=manifest,
        )

    def test_adapter_preserves_raw_and_derives_text_layers(self):
        block = artifact_to_document_block(
            artifact(),
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
        )
        self.assertEqual(block.raw_text, "原始 文本")
        self.assertEqual(block.canonical_text, "原始文本")
        self.assertEqual(block.display_text, "原始文本")
        self.assertEqual(block.coordinate_space, "pdf_top_left")

    def test_identity_is_stable_and_version_owned(self):
        kwargs = dict(scope_id="chapter-1", source_pdf_sha256="a" * 64)
        first = artifact_to_document_block(
            artifact(), textbook_version_id="book-a-v1", **kwargs
        )
        repeat = artifact_to_document_block(
            artifact(), textbook_version_id="book-a-v1", **kwargs
        )
        other_version = artifact_to_document_block(
            artifact(), textbook_version_id="book-a-v2", **kwargs
        )
        self.assertEqual(first.id, repeat.id)
        self.assertNotEqual(first.id, other_version.id)

    def test_raw_span_anchor_ignores_later_classification(self):
        span = RawSpan(
            pdf_page_number=3,
            block_index=2,
            line_index=1,
            spans=({"text": "定义", "bbox": [1, 2, 30, 40], "font": "FZ"},),
        )
        first = build_source_anchor(
            span,
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
        )
        repeat = build_source_anchor(
            span,
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
        )
        self.assertEqual(first, repeat)
        self.assertEqual(len(first.span_payload_sha256), 64)

    def test_production_block_uses_preclassification_anchor(self):
        span = RawSpan(
            pdf_page_number=3,
            block_index=2,
            line_index=1,
            spans=({"text": "定义", "bbox": [1, 2, 30, 40]},),
        )
        block = raw_span_to_document_block(
            span,
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
            node_id="node-1",
            kind="text_block",
            source_order=1,
            raw_text="定义",
            page_width=600,
            page_height=800,
        )
        self.assertEqual(
            block.metadata["anchor_kind"], "pre_classification_raw_span"
        )
        self.assertEqual(len(block.metadata["span_payload_sha256"]), 64)

    def test_validation_rejects_truncated_checksum(self):
        block = artifact_to_document_block(
            artifact(),
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
        )
        document = self._valid_document()
        document.source_pdf_sha256 = "short"
        self.assertTrue(validate_document_ir(document))

    def test_valid_document_has_no_errors(self):
        self.assertEqual(validate_document_ir(self._valid_document()), [])

    def test_bbox_requires_page_dimensions_and_node_owner(self):
        block = artifact_to_document_block(
            artifact(),
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
        )
        document = CanonicalDocumentIR(
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
            blocks=[block],
        )
        errors = validate_document_ir(document)
        self.assertTrue(any("page dimensions" in error for error in errors))
        self.assertTrue(any("not owned" in error for error in errors))

    def _multi_node_document(self, *, nodes):
        """Build a document with the given nodes; one block per node."""
        blocks = []
        updated_nodes = []
        for index, node in enumerate(nodes, start=1):
            span = RawSpan(
                pdf_page_number=3,
                block_index=index,
                line_index=1,
                spans=({"text": node.id, "bbox": [1, 2, 30, 40]},),
            )
            block = raw_span_to_document_block(
                span,
                textbook_version_id="book-a-v1",
                scope_id="chapter-1",
                source_pdf_sha256="a" * 64,
                node_id=node.id,
                kind="text_block",
                source_order=index,
                raw_text=node.id,
                page_width=600,
                page_height=800,
            )
            updated_nodes.append(DocumentNode(
                id=node.id,
                parent_id=node.parent_id,
                source_title=node.source_title,
                source_title_raw=node.source_title_raw,
                marker_kind=node.marker_kind,
                origin=node.origin,
                source_order=node.source_order,
                sibling_order=node.sibling_order,
                heading_anchor_id=block.id,
                content_block_ids=(block.id,),
            ))
            blocks.append(block)
        manifest = SourceScopeManifest(
            id="scope-manifest-1",
            textbook_version_id="book-a-v1",
            source_pdf_sha256="a" * 64,
            page_start=3,
            page_end=3,
        )
        return CanonicalDocumentIR(
            textbook_version_id="book-a-v1",
            scope_id="chapter-1",
            source_pdf_sha256="a" * 64,
            blocks=blocks,
            nodes=updated_nodes,
            scope_manifest=manifest,
        )

    def _make_node(self, node_id, *, parent_id, source_order, sibling_order):
        return DocumentNode(
            id=node_id,
            parent_id=parent_id,
            source_title=node_id,
            source_title_raw=node_id,
            marker_kind="bracket",
            origin="explicit_marker",
            source_order=source_order,
            sibling_order=sibling_order,
            heading_anchor_id="placeholder",
            content_block_ids=(),
        )

    def test_validation_rejects_self_cycle(self):
        nodes = [self._make_node("node-1", parent_id="node-1", source_order=1, sibling_order=0)]
        document = self._multi_node_document(nodes=nodes)
        errors = validate_document_ir(document)
        self.assertTrue(any("cycle" in error for error in errors))

    def test_validation_rejects_two_node_cycle(self):
        nodes = [
            self._make_node("node-1", parent_id="node-2", source_order=1, sibling_order=0),
            self._make_node("node-2", parent_id="node-1", source_order=2, sibling_order=0),
        ]
        document = self._multi_node_document(nodes=nodes)
        errors = validate_document_ir(document)
        cycle_errors = [error for error in errors if "cycle" in error]
        self.assertEqual(len(cycle_errors), 2)

    def test_validation_rejects_duplicate_sibling_order_under_same_parent(self):
        nodes = [
            self._make_node("root", parent_id=None, source_order=1, sibling_order=0),
            self._make_node("child-a", parent_id="root", source_order=2, sibling_order=0),
            self._make_node("child-b", parent_id="root", source_order=3, sibling_order=0),
        ]
        document = self._multi_node_document(nodes=nodes)
        errors = validate_document_ir(document)
        dup_errors = [error for error in errors if "duplicate sibling_order" in error]
        self.assertEqual(len(dup_errors), 1)
        self.assertIn("child-b", dup_errors[0])
        self.assertIn("child-a", dup_errors[0])

    def test_validation_accepts_distinct_sibling_orders_across_parents(self):
        nodes = [
            self._make_node("root-a", parent_id=None, source_order=1, sibling_order=0),
            self._make_node("root-b", parent_id=None, source_order=2, sibling_order=1),
            self._make_node("child-a1", parent_id="root-a", source_order=3, sibling_order=0),
            self._make_node("child-b1", parent_id="root-b", source_order=4, sibling_order=0),
        ]
        document = self._multi_node_document(nodes=nodes)
        errors = validate_document_ir(document)
        self.assertFalse(any("duplicate sibling_order" in error for error in errors))
        self.assertFalse(any("cycle" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
