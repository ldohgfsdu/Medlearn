---
name: medlearn-evaluate-training-stage
description: Evaluate MedLearn SFT datasets, curriculum stages, LoRA checkpoints, adapter metrics, and promotion readiness. Use for dataset audits, evidence-copy evaluation, stage 1, 2, or 3 training results, checkpoint comparisons, model regressions, and deciding whether a model artifact may advance to the next experiment stage.
---

# Evaluate Training Stage

## Establish The Contract

Read:

- `AGENTS.md` and its startup sources
- `context/TASK_ROUTER.yaml` — selects this skill and applicable checks
- `state/active_object.yaml` — current active object
- `state/training_dataset.yaml` — current promoting dataset version
  (`active_version`, `active_path`, `base_model`, `large_model`)
- `training/README.md`
- `training/data_cleaning_rules.yaml`
- `training/curriculum/README.md`
- the dataset `manifest.json` and `FROZEN.md` when present
- the stage-specific evaluator and tests:
  - Stage 1: `training/evaluate_stage1_evidence_copy.py`,
    `training/stage1_eval_metrics.py`
  - Stage 2: `training/evaluate_stage2_evidence_content.py`,
    `training/stage2_eval_metrics.py`
  - Stage 3: `training/evaluate_stage3_full_nodes.py`,
    `training/stage3_eval_metrics.py`
  - Adapter: `training/evaluate_sft_adapter.py`, `training/sft_eval_metrics.py`
- produced metrics and representative failures

Treat all local runs as experiments unless a separate production review gate
explicitly says otherwise.

## Stage Gates

- **Dataset**: reject invalid JSON, missing source, hallucinated entities,
  invalid targets, and evidence not present in source text. Verify frozen splits.
- **Stage 1**: evidence must be a verbatim continuous source span.
- **Stage 2**: evidence remains exact; content differs from evidence and adds no
  facts outside the source.
- **Stage 3**: full node fields are valid and grounded; keep edges outside loss
  where the curriculum specifies.
- **Promotion**: require configured thresholds and inspect failure categories.
  Aggregate scores cannot excuse grounding or medical-safety regressions. Apply
  `checklists/no-regression-rules.md` and `checklists/production-acceptance.md`
  before promoting an adapter to a production-facing artifact.

## Evaluation Rules

- Compare against the correct frozen baseline and identical evaluation set.
- Record model, adapter, dataset version, seed, evaluator version, and runtime.
- Separate schema compliance, grounding, content quality, recall, and latency.
- Inspect representative false positives and false negatives.
- Apply `checklists/evidence-copy-eval.md` and
  `checklists/no-regression-rules.md` to sampled outputs.
- Never promote an adapter because it learned the JSON envelope alone.
- Never describe a model as medically validated without qualified review.

## Medical Content Cross-Reference

Stage 1/2/3 datasets depend on evidence grounding. If sampled outputs fail
grounding gates, route the failing items through
`.agents/skills/medlearn-validate-medical-content/SKILL.md` before re-running
evaluation. Do not re-promote an adapter whose grounding failures have not been
re-validated.

## Validate

`--base-model` and `--adapter` are required by every evaluator. Map them from
`state/training_dataset.yaml`:

- `--base-model` ← `base_model` (Stage 1/2) or `large_model` (Stage 3)
- `--adapter` ← the LoRA adapter directory produced by the corresponding
  `train_stage*_*.py` run; record its path in the run report and alongside
  `state/training_dataset.yaml`'s `active_version`

Run **only** the stage being evaluated, not all four. Per-stage command
templates:

```powershell
# Stage 1 — evidence copy
.\.venv-sft\Scripts\python.exe training/evaluate_stage1_evidence_copy.py `
  --base-model <base_model path> `
  --adapter <stage1 adapter path>

# Stage 2 — evidence + content
.\.venv-sft\Scripts\python.exe training/evaluate_stage2_evidence_content.py `
  --base-model <base_model path> `
  --adapter <stage2 adapter path>

# Stage 3 — full nodes (use large_model per state/training_dataset.yaml)
.\.venv-sft\Scripts\python.exe training/evaluate_stage3_full_nodes.py `
  --base-model <large_model path> `
  --adapter <stage3 adapter path>

# Adapter-level (cross-stage) evaluation
.\.venv-sft\Scripts\python.exe training/evaluate_sft_adapter.py `
  --base-model <base_model path> `
  --adapter <adapter path>
```

Dataset audits (no model required):

```powershell
.\.venv-sft\Scripts\python.exe scripts/audit_sft_dataset.py
.\.venv-sft\Scripts\python.exe scripts/audit_sft_dataset_distribution.py
```

`.\.venv-sft\Scripts\python.exe` is the Windows path used by this project. On
other platforms, activate `.\.venv-sft` and use `python` directly. Each
evaluator also accepts `--train-dataset`, `--max-length`, `--max-new-tokens`,
`--report-json`, `--report-md`, `--failure-jsonl`; see `--help` per script.

Record model, adapter, dataset version, seed, evaluator version, and runtime
with each run.

## Failure Modes (Stop And Report)

| Condition | Action |
|-----------|--------|
| Grounding failures on sampled outputs | Stop; route through `medlearn-validate-medical-content` before re-promoting |
| Frozen split integrity broken | Stop; do not promote; restore frozen baseline |
| Adapter learned JSON envelope only | Stop; never promote |
| Dataset version in `state/training_dataset.yaml` disagrees with evaluator input | Stop; reconcile versions |
| Medical-safety regression vs baseline | Stop; never excuse via aggregate scores |

## Output

Return `pass`, `pass_with_limits`, or `fail` for the requested stage. Include
metrics, failed gates, sampled error patterns, reproducibility details, and the
next permitted action. Do not recommend broader training when the failing gate
is data quality or evaluation integrity.

`pass_with_limits` must record: which gates passed with margin, which limits
apply (e.g., scope, latency, recall threshold), the dataset version and seed,
and the conditions under which the limits remain valid. Record these in the
evaluator's `--report-json` output and reference `state/training_dataset.yaml`'s
`active_version`; do not invent a separate experiment log location.

A `pass` here is an experiment-stage gate only. Promoting the adapter to a
production-facing artifact also requires `checklists/production-acceptance.md`.
