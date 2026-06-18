# SFT v2 Nodes Curriculum

Dataset base: `sft_v2_expanded_182` (182 Tier A samples, golden 8 eval only).

Curriculum output: `training/curriculum/sft_v2_nodes_curriculum/`

## Design

Three-stage evidence-copy curriculum for nodes-only LoRA smoke training. Do not train edges; `optional_edges` never enters loss.

### Stage 1 — `stage1_evidence_copy`

Goal: force evidence to be verbatim contiguous spans from `source_text`.

- Input: `source_text`, `parent_entity`, `candidate_aspects`
- Output: `{"nodes":[{"aspect","evidence"}],"edges":[]}`
- No content training in this stage.

### Stage 2 — `stage2_evidence_content_distill`

Goal: keep evidence exact; learn distilled `content`.

- Output: `{"nodes":[{"aspect","evidence","content"}],"edges":[]}`
- Constraints: `content != evidence`, no facts outside `source_text`.

### Stage 3 — `stage3_full_nodes_only`

Goal: production nodes-only schema.

- Output: full node fields (`title`, `type`, `parent_entity`, `aspect`, `content`, `evidence`, `tags`)
- `edges: []`; original edges stored as `optional_edges` metadata only.

## Distribution control

See `training/reports/sft_v2_expanded_182_distribution.json`.

Do not delete Tier A samples. Apply `sampling_policy.json` during training:

- chapter-balanced batches
- `max_per_parent_entity` cap
- hydrated / non-hydrated balance

## Smoke training (not started)

- Checkpoint: `training/checkpoints/qwen3-0.6b-medlearn-lora-nodes-v2-smoke/`
- Do not overwrite: `training/checkpoints/qwen3-0.6b-medlearn-lora/final`
- Post-train: `training/evaluate_sft_adapter.py`