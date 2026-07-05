---
name: medlearn-review-ingestion
description: Review or change MedLearn's textbook ingestion pipeline, catalog mapping, normalization, evidence binding, embeddings, uploads, and pipeline state. Use for PDF extraction, manifests, knowledge_nodes, document_chunks, causal_chains, source evidence, page references, backfills, and ingestion release-readiness work.
---

# Review MedLearn Ingestion

## Establish The Production Path

Read:

- `AGENTS.md` and its startup sources
- `context/TASK_ROUTER.yaml` — selects this skill, the route's `adr_tags`,
  and the applicable checks
- `state/active_object.yaml` — current active object; ingestion work must stay
  inside its scope or state the conflict before expanding
- `docs/PIPELINE_INDEX.md`
- `manifests/internal_medicine_ingestion.yaml`
- `state/knowledge_ingestion.yaml`
- accepted ADRs selected through `docs/ADR_INDEX.yaml` using the ingestion
  route's `adr_tags` (`textbook_version`, `textbook_pipeline`,
  `evidence_artifact`, `knowledge_detail`)
- the changed scripts and their tests

### Production entry points

The authoritative list of production CLI scripts, orchestrator commands, and
their roles lives in `docs/PIPELINE_INDEX.md`. **Do not copy that list into
this skill** — it drifts. When you need to know which script is the production
CLI, which is the orchestrator, which is deprecated, or which manifest is
current, read `PIPELINE_INDEX.md` directly and treat it as authoritative.

Rules:

- Treat `scripts/ingest_knowledge.py` and `scripts/orchestrator.py` together
  as the production CLI surface unless `PIPELINE_INDEX.md` says otherwise.
- Do not revive scripts that `PIPELINE_INDEX.md` marks deprecated or
  experimental (e.g., `ingest_evidence_first.py` unless explicitly
  re-activated).
- If `PIPELINE_INDEX.md` and a script disagree, fix `PIPELINE_INDEX.md` or the
  script — do not silently work around the drift.

### Manifests

Manifests and their current production status are tracked in
`PIPELINE_INDEX.md` and `state/knowledge_ingestion.yaml`. Two manifest files
currently exist (`manifests/internal_medicine_ingestion.yaml`,
`manifests/respiratory_manifest.yaml`); do not assume which is production
without consulting those two sources.

## Review

1. Confirm textbook version, catalog node, source range, and source order.
2. Confirm extraction preserves source headings and combined or missing aspects.
3. Confirm every organized item binds to local evidence and a valid page.
4. Confirm structured evidence is not flattened into misleading plain text.
5. Confirm IDs and references remain stable and uploads are idempotent.
6. Confirm nodes, chunks, and causal chains stay referentially consistent.
7. Confirm unsafe or unreviewed content cannot become ordinary-user-visible.
8. Apply `checklists/evidence-copy-eval.md`, `checklists/app-integration-gate.md`,
   and `checklists/no-regression-rules.md`.

## Backfill Guardrails

Backfills (page references, evidence joins, embeddings, ID regeneration)
re-write existing artifacts and are the highest-risk ingestion operations.
Apply the project memory rules:

- Mark historical verification evidence as invalid when page identifiers
  change; do not silently re-link old evidence to new pages.
- Evidence joins must resolve 100% of references with explicit `artifact_id`;
  partial joins are blocked, never downgraded to fuzzy text matching.
- Preserve stable raw anchors (PDF page, block, line indices) and SHA-256
  payload hashing with at least 128-bit identifiers; do not regenerate IDs
  from derived structural paths.
- Re-run `scripts/verify_pipeline_closure.py` after every backfill before
  declaring the pipeline closed.

## Embeddings

Embeddings backfills use `scripts/backfill_chunk_embeddings_ollama.py` against
chunk tables produced by the V3 pipeline. Treat embedding generation as a
candidate step: source fidelity and evidence joins must already be closed
before an embedding backfill runs. Embeddings are not publication approval.

## Cross-Reference

### Phase 1 visual evidence

Ingestion controls fields that `.agents/skills/medlearn-phase1-visual-evidence/SKILL.md`
depends on. Coordinate before merging any change to these on already-published
sections:

- `originArtifactIds` — parser lineage path; absence forces the asthma
  `knowledge_node_evidence_json` bridge.
- `artifact_id` — current asthma bridge identifier on evidence items.
- `pageLabel` vs `pdfPageIndex` — must stay distinct; never assume
  `pdfPageIndex = int(pageLabel) - 1`.
- `bbox` / `bboxNorm` — top-left origin, no Y-flip; normalized to `[0, 1]`.

### Medical content validation

Ingestion changes evidence bindings, page references, `artifact_id` joins, or
`needs_review` gating on a published section require re-validation of affected
medical content through `.agents/skills/medlearn-validate-medical-content/SKILL.md`.
Do not declare a section app-visible or publication-ready after such changes
until medical content validation has been re-run.

## Validate

Run the narrowest relevant tests first, then the data and release gates.

### Code-side

```powershell
.\.venv-sft\Scripts\python.exe scripts\verify_p0_smoke.py
.\.venv-sft\Scripts\python.exe scripts\verify_pipeline_closure.py
.\.venv-sft\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

`.\.venv-sft\Scripts\python.exe` is the Windows path used by this project. On
other platforms, activate `.\.venv-sft` and use `python` directly.

### Data and release-side

Required before treating the bundle as app-visible or publication-ready:

```powershell
.\.venv-sft\Scripts\python.exe scripts\validate_project_state.py
.\.venv-sft\Scripts\python.exe scripts\orchestrator.py audit-app-knowledge-quality
.\.venv-sft\Scripts\python.exe scripts\ingest_knowledge.py ev1-candidate-quality-report --strict --pretty
.\.venv-sft\Scripts\python.exe scripts\orchestrator.py build-app-knowledge-bundle
```

Do not run broad LLM re-extraction or remote upload merely to review code.
Require explicit scope and environment confirmation before costly or mutating
pipeline operations.

## Failure Modes (Stop And Report)

| Condition | Action |
|-----------|--------|
| Evidence join resolution < 100% | Stop; do not fall back to fuzzy text matching |
| Backfill would re-link old evidence to changed page identifiers | Stop; mark historical evidence invalid first |
| `originArtifactIds` / `artifact_id` changes on a published section | Stop; coordinate with Phase 1 visual evidence skill |
| `pageLabel` and `pdfPageIndex` disagree for pilot pages | Stop; fix the page map |
| Unsafe or unreviewed content would become ordinary-user-visible | Stop; apply `evidence_only` or hide the conclusion |
| Untracked ingestion assets in a clean checkout | Stop; track assets before claiming release-ready |
| Active object scope is violated by the requested change | Stop; report the conflict before expanding scope |

## Output

State which textbook version and sections were assessed, which gates passed,
which operations were not run, and whether the result is code-ready,
data-ready, app-visible, or medically reviewed. These are distinct states.
