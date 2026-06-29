---
name: medlearn-evaluate-training-stage
description: Evaluate MedLearn SFT datasets, curriculum stages, LoRA checkpoints, adapter metrics, and promotion readiness. Use for dataset audits, evidence-copy evaluation, stage 1, 2, or 3 training results, checkpoint comparisons, model regressions, and deciding whether a model artifact may advance to the next experiment stage.
---

# Evaluate Training Stage

## Establish The Contract

Read:

- `training/README.md`
- `training/data_cleaning_rules.yaml`
- `training/curriculum/README.md`
- the dataset `manifest.json` and `FROZEN.md` when present
- the stage-specific evaluator and tests
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
  Aggregate scores cannot excuse grounding or medical-safety regressions.

## Evaluation Rules

- Compare against the correct frozen baseline and identical evaluation set.
- Record model, adapter, dataset version, seed, evaluator version, and runtime.
- Separate schema compliance, grounding, content quality, recall, and latency.
- Inspect representative false positives and false negatives.
- Apply `checklists/evidence-copy-eval.md` to sampled outputs.
- Never promote an adapter because it learned the JSON envelope alone.
- Never describe a model as medically validated without qualified review.

## Output

Return `pass`, `pass_with_limits`, or `fail` for the requested stage. Include
metrics, failed gates, sampled error patterns, reproducibility details, and the
next permitted action. Do not recommend broader training when the failing gate
is data quality or evaluation integrity.

A `pass` here is an experiment-stage gate only. Promoting the adapter to a
production-facing artifact also requires `checklists/production-acceptance.md`.

