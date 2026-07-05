# MedLearn PDF 知识点管线索引

## 生产入口（唯一）

| 组件 | 路径 |
|------|------|
| CLI | [`scripts/ingest_knowledge.py`](../scripts/ingest_knowledge.py) |
| 编排 | [`scripts/orchestrator.py`](../scripts/orchestrator.py) |
| V3 核心 | [`scripts/pipeline_v3_extract.py`](../scripts/pipeline_v3_extract.py) |
| 契约 | [`scripts/textbook_pipeline/ingestion_contract.py`](../scripts/textbook_pipeline/ingestion_contract.py) |
| Manifest | [`manifests/internal_medicine_ingestion.yaml`](../manifests/internal_medicine_ingestion.yaml) |

```powershell
cd F:\ml
python scripts\ingest_knowledge.py --book-id internal-medicine-10 status
python scripts\orchestrator.py run-next
python scripts\ingest_knowledge.py backfill-p0
python scripts\verify_pipeline_closure.py
```

## Current app bundle path

The mobile app currently consumes a bundled display-contract fixture at build
time. Keep this path explicit so database upload work and app-visible content do
not drift apart:

```text
generated/knowledge_nodes/internal-medicine-10/*.normalized.json
  -> scripts/ingest_knowledge.py ev1-display-contract
  -> generated/display_contracts/internal-medicine-10/*.display_contract.json
  -> scripts/export_ev1_display_contracts_ts.py
  -> constants/ev1DisplayContracts.ts
  -> [Phase 1 visual] scripts/merge_phase1_locators_bundle.py
  -> constants/phase1VisualEvidenceBundle.ts
  -> services/textbookService.ts
```

Use the orchestrated command for the local app knowledge bundle:

```powershell
python scripts\orchestrator.py build-app-knowledge-bundle
```

Run the app-visible EV1 quality audit before treating the bundle as
publication-ready:

```powershell
python scripts\orchestrator.py audit-app-knowledge-quality
```

Run the candidate extraction quality report when checking full-book EV1 source
fidelity before app bundle conversion:

```powershell
python scripts\ingest_knowledge.py ev1-candidate-quality-report --strict --pretty
python scripts\ingest_knowledge.py ev1-candidate-quality-report --strict --pretty --diagnostic-items-output generated\ev1_candidate_quality_defect_queue.json
```

The report is written to `generated/ev1_candidate_quality_report.json` and
tracks per-section coverage, rejected candidates, needs-review concentration,
deterministic verifier issue types, deterministic repair counts, and preserved
provenance counts. `needs_review` items remain source evidence for lookup, not
ordinary organized conclusions.

The same report includes `needs_review_diagnostics` so remaining non-pass items
can be separated by action instead of treated as a single quality bucket:
`high_risk_grounded_source_only` means the content is already continuously
present in source evidence and should stay evidence-only;
`intended_high_risk_source_only` should also stay evidence-only.
`standard_candidate_repairable_span` and `high_risk_repairable_span_binding`
belong in the remediation queue but can be fixed deterministically from source
context. `standard_candidate_extraction_noise` and
`high_risk_with_extraction_noise` should be re-run through the strict synthesis
prompt/hard gate before they can become organized conclusions. This diagnostic
is source-fidelity oriented; it is not a medical correctness review.

Use `--diagnostic-items-output` to write the full remediation queue with section,
page, artifact id, source evidence, current content, diagnostic class, and
recommended action.

Use the queue-driven remediation command to re-run only the affected source
artifacts. It defaults to a dry-run plan; `--execute` rewrites local EV1
synthesis and candidate caches only, with no upload:

```powershell
python scripts\ingest_knowledge.py ev1-remediate-quality-queue --limit-sections 5
python scripts\ingest_knowledge.py ev1-remediate-quality-queue --limit-sections 5 --execute
```

During EV1 synthesis, LLM output is accepted only when `evidence` is found in
the source artifact and `content` is directly contained inside that evidence
span after loose Unicode normalization. Items that require paraphrase, title
completion, table-header inference, or cross-span merging are skipped so the
source artifact can remain evidence-only instead of becoming an unsupported
organized conclusion.

The orchestrated audit exports the full-book source QA queue, then runs the
strict app-visible EV1 audit. The lower-level commands remain:

```powershell
node scripts\export-ev1-source-qa-queue.mjs --all --pretty
node scripts\audit-ev1-knowledge-quality.mjs --pretty --strict
```

The full-book queue is written to
`generated/source_qa_queue/<book_id>/_all.source_qa.json`. It records the source
evidence, page locator, QA reason, organized-conclusion visibility, and
evidence-only display state for each candidate. The exporter cross-checks the
app display contract, so `sourceEvidenceVisibleCount` means the source artifact
is actually present in the bundled display data. Rejected extraction items
remain in the queue but are not treated as app-visible evidence. When a rejected
item is not app-visible, the queue includes nearby source artifacts in
`sourceArtifactContext` so the extraction span can be repaired from textbook
text without guessing. Use `--section-id <id>` without `--all` only for targeted
single-section debugging.

The audit keeps the respiratory pulmonary infection chapter as the golden
lookup chapter for catalog and wrong-question checks, and also verifies
full-book source QA app visibility through `sourceQaBook`. The report
distinguishes synthesis coverage, normalized cache coverage, and app-visible
bundle coverage so extraction misses are not confused with organized-conclusion
publication gates. `--strict` is intended to fail only when source lookup or
display fidelity blockers remain.

`generated/knowledge_nodes_ev1/` and `generated/ev1_display_contracts/` are
legacy paths and must not be used as default production inputs.

## 写入目标

- `knowledge_nodes` — 知识点主表
- `document_chunks` — RAG 引用（`related_node_id`）
- `causal_chains` — 章节级因果链（`source=pipeline_v3`）

## 遗留 / 实验脚本（勿用于生产）

| 脚本 | 状态 | 替代 |
|------|------|------|
| `scripts/ingest_final.py` | DEPRECATED | `ingest_knowledge.py` |
| `scripts/run_optimized_pipeline.py` | EXPERIMENTAL | `ingest_knowledge.py extract` |
| `scripts/textbook_parser.py` | DEMO ONLY | `pipeline_v3_extract.py` |
| V2 `segment_by_catalog` 等 | SUPERSEDED | V3 manifest 流程 |

## 默认配置

- PDF 解析：`auto`（普通页 PyMuPDF、复杂页 Docling、扫描页 OCR）
- Embedding：`bge-m3` via Ollama（`OLLAMA_EMBED_MODEL`）
- 覆盖解析器：`MEDLEARN_PDF_PARSER=auto|pymupdf|docling` 或 CLI `--pdf-parser`
