import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.evidence_artifact import make_artifact
from textbook_pipeline.evidence_synthesis import (
    SynthesizedItem,
    synthesize_artifacts,
    write_synthesis_cache,
)


def _artifact(order: int):
    return make_artifact(
        textbook_id="internal-medicine-10",
        book_id="internal-medicine-10",
        part_title="第一篇 绪论",
        section_title="绪论",
        source_heading="绪论",
        normalized_aspect=None,
        source_order=order,
        artifact_type="text_block",
        raw_text=f"这是第 {order} 个测试文本块，内容足够长用于合成。",
        page_start=1,
        page_end=1,
    )


class EvidenceSynthesisCheckpointTests(unittest.TestCase):
    def test_synthesize_artifacts_resumes_from_checkpoint(self):
        first = _artifact(0)
        second = _artifact(1)
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "section.synthesis.json"
            cached_item = SynthesizedItem(
                artifact_id=first.id,
                item_index=0,
                title="已缓存",
                parent_entity=None,
                aspect="绪论",
                content="已缓存内容",
                evidence="已缓存内容",
                risk_class="standard",
                source_heading="绪论",
                page_start=1,
                page_end=1,
            )
            write_synthesis_cache(
                [cached_item],
                [{"artifact_id": first.id, "artifact_type": "text_block", "page": 1, "time_s": 0}],
                checkpoint,
            )

            new_item = SynthesizedItem(
                artifact_id=second.id,
                item_index=0,
                title="新合成",
                parent_entity=None,
                aspect="绪论",
                content="新合成内容",
                evidence="新合成内容",
                risk_class="standard",
                source_heading="绪论",
                page_start=1,
                page_end=1,
            )
            with patch(
                "textbook_pipeline.evidence_synthesis.synthesize_artifact",
                return_value=([new_item], {"time_s": 1, "raw_items": 1, "valid_items": 1}),
            ) as mocked:
                items, metrics = synthesize_artifacts(
                    [first, second],
                    checkpoint_path=checkpoint,
                    resume=True,
                )

        self.assertEqual(mocked.call_count, 1)
        self.assertEqual([item.artifact_id for item in items], [first.id, second.id])
        self.assertEqual(len(metrics), 2)


if __name__ == "__main__":
    unittest.main()
