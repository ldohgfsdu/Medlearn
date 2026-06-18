---
name: medlearn-review-ingestion
description: Review or change MedLearn's textbook ingestion pipeline, catalog mapping, normalization, evidence binding, embeddings, uploads, and pipeline state. Use for PDF extraction, manifests, knowledge_nodes, document_chunks, causal_chains, source evidence, page references, backfills, and ingestion release-readiness work.
---

# Review MedLearn Ingestion

## Establish The Production Path

Read:

- `docs/PIPELINE_INDEX.md`
- `manifests/internal_medicine_ingestion.yaml`
- `state/knowledge_ingestion.yaml`
- accepted ADRs selected through `docs/ADR_INDEX.yaml`
- the changed scripts and their tests

Treat `scripts/ingest_knowledge.py` as the production CLI unless current code and
the maintained pipeline index explicitly replace it. Do not revive scripts
listed as deprecated or experimental.

## Review

1. Confirm textbook version, catalog node, source range, and source order.
2. Confirm extraction preserves source headings and combined or missing aspects.
3. Confirm every organized item binds to local evidence and a valid page.
4. Confirm structured evidence is not flattened into misleading plain text.
5. Confirm IDs and references remain stable and uploads are idempotent.
6. Confirm nodes, chunks, and causal chains stay referentially consistent.
7. Confirm unsafe or unreviewed content cannot become ordinary-user-visible.
8. Apply `checklists/evidence-copy-eval.md` and
   `checklists/app-integration-gate.md`.

## Validate

Prefer targeted tests first, then:

```powershell
.\.venv-sft\Scripts\python.exe scripts\verify_p0_smoke.py
.\.venv-sft\Scripts\python.exe scripts\verify_pipeline_closure.py
.\.venv-sft\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Do not run broad LLM re-extraction or remote upload merely to review code.
Require explicit scope and environment confirmation before costly or mutating
pipeline operations.

## Report

State which textbook version and sections were assessed, which gates passed,
which operations were not run, and whether the result is code-ready,
data-ready, app-visible, or medically reviewed. These are distinct states.

