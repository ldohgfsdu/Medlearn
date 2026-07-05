# 教材管线

MedLearn 教材知识走 **EV1 证据优先管线**：先拿到可验证的原文，再决定如何展示；不是让模型自由「写教材」。

内部完整索引、ADR 与状态机在仓库 `docs/PIPELINE_INDEX.md`、`docs/CURRENT_STATE.md`（不发布到本站）。本文是开发者速览。

## 两条数据路径（不要混）

| 路径 | 用途 | 现状 |
|------|------|------|
| **本地 EV1 display bundle** | App 教材浏览 `/textbook/...` | 全书 131 章，构建时打入 `constants/ev1DisplayContracts.ts` |
| **Supabase `knowledge_nodes`** | 疾病详情等 `/disease/[id]` | 部分章节快照，与本地 bundle 不同步 |

改教材内容或验质量时，以 **本地 bundle 链路** 为准。

## EV1 生产链路（App 教材）

```text
PDF（内科学第10版）
  → Phase 1  evidence_extractor（PyMuPDF，无 LLM）
  → Phase 2  evidence_synthesis（Ollama medlearn-qwen3:8b，切条/整理）
  → Phase 3  evidence_verifier（确定性校验 + span 修补）
  → candidate cache
  → normalized cache
  → display contract
  → export_ev1_display_contracts_ts.py
  → constants/ev1DisplayContracts.ts
  → services/textbookService.ts
```

编排入口：

```powershell
cd F:\ml
python scripts\orchestrator.py build-app-knowledge-bundle
```

## 常用命令

```powershell
# 状态与候选质量
python scripts\ingest_knowledge.py --book-id internal-medicine-10 status
python scripts\ingest_knowledge.py ev1-candidate-quality-report --strict --pretty
python scripts\ingest_knowledge.py ev1-display-quality-report --strict --pretty

# App 可见质量审计（含错题 golden cases）
node scripts\audit-ev1-knowledge-quality.mjs --strict

# 管线闭环
python scripts\verify_pipeline_closure.py --json
```

缺陷队列按需重抽（默认 dry-run）：

```powershell
python scripts\ingest_knowledge.py ev1-remediate-quality-queue --limit-sections 5
python scripts\ingest_knowledge.py ev1-remediate-quality-queue --limit-sections 5 --execute
```

## 展示层（不含 LLM）

`utils/textbookStudy.ts` 负责把 display contract 变成可学习的单元与知识地图小节：

- 超大目录单元按 `StudyGroup` 拆成细单元（如 `第二节 细菌性肺炎 · 治疗`）
- 保留旧单元 ID 回退，避免错题/深链接失效
- 问题主要在**标题可读性、长段/碎段**，不是基础提取崩盘

## 质量闸门（当前口径）

| 闸门 | 含义 |
|------|------|
| `ev1-candidate-quality-report --strict` | 提取/span 缺陷为 0，`rejected=0` |
| `ev1-display-quality-report --strict` | 展示契约无 issue/warning |
| `audit-ev1-knowledge-quality --strict` | App 侧检索、evidence-only、错题定位 |

**已通过的是原文绑定与展示契约**；全书医学发布审校是另一层，未在此管线内完成。

## 遗留 V3 路径

`scripts/pipeline_v3_extract.py` + `orchestrator run-next` 仍用于逐章上传 Supabase（`knowledge_nodes`、chunks、causal chains）。与 App 当前教材 bundle **并行存在**，不要假设两边数据一致。

## 相关文档

- 仓库内：`docs/PIPELINE_INDEX.md`、`manifests/internal_medicine_ingestion.yaml`
- 本站：[项目结构](/dev/project-structure)、[验证与测试](/dev/testing)、[API](/dev/api)