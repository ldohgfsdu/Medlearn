# Respiratory Knowledge Base Validation - 2026-06-17

## Status

`respiratory_knowledge_base_validation: accepted_for_current_scope`

This is an acceptance result for the respiratory knowledge-base production
chain only. It is not whole-book completion, product experience validation, or
full retrieval-quality evaluation.

## Scope

- Textbook: `internal-medicine-10`
- Source range: `第二篇 呼吸系统疾病`
- Sections: 17 respiratory sections
- Excluded by scope: UI changes, product validation, whole-book expansion, new
  active object creation

## Validated Chain

```text
respiratory textbook sections
-> Text-first extraction cache
-> knowledge_nodes / document_chunks
-> evidence / page range
-> remote upload
-> embedding
-> remote query hit
-> node + chunk + page range returned
```

## Evidence Artifacts

The large generated JSON artifacts are local evidence files under ignored
`generated/` output paths:

- `generated/respiratory_knowledge_nodes.json`
- `generated/respiratory_document_chunks.json`
- `generated/respiratory_upload_result.json`
- `generated/respiratory_query_acceptance.json`
- `generated/respiratory_extraction_report.md`

Because `generated/` is ignored by Git, this report records the committed
summary and points to the local evidence files.

## Acceptance Metrics

| Item | Result |
|---|---:|
| Respiratory sections | 17 |
| `knowledge_nodes` | 606 |
| `document_chunks` | 730 |
| Embedded chunks | 730 |
| Evidence coverage | 606/606 |
| Page range coverage | 606/606 |
| JSON valid rate | 17/17 |
| Empty content | 0 |
| Duplicate node IDs | 0 |
| Missing page refs | 0 |
| Fallback pages | 0 |
| Remote query smoke acceptance | 5/5 |
| Targeted unit tests | 6 passed |

## Query Smoke Acceptance

Each query returned a remote `knowledge_nodes` hit with textbook evidence, page
range, and original `document_chunks` snippet.

| Query | Hit node | Section | Page range |
|---|---|---|---:|
| 慢性支气管炎 | 职业或环境粉尘对慢性支气管炎的影响 | 第三章 慢性阻塞性肺疾病 | 54-61 |
| 肺气肿 | 慢性支气管炎的病理特征 | 第三章 慢性阻塞性肺疾病 | 54-61 |
| 支气管哮喘 | 支气管哮喘的定义 | 第四章 支气管哮喘 | 62-70 |
| 肺炎 | 肺孢子菌肺炎的病原体 | 第六章 肺部感染性疾病 | 77-98 |
| 呼吸衰竭 | 低氧性呼吸衰竭的病理生理机制 | 第十六章 呼吸衰竭与呼吸支持技术 | 179-194 |

## Limits

- `evidence_level: section_page_range`
  Page references are PDF catalog section-level page ranges, not exact
  node-level coordinates.
- `causal_chains: partial_from_parseable_links_only`
  The 15 uploaded causal chains come only from existing parseable
  `causal_links`; they do not represent a complete reasoning graph.
- `query_acceptance: query_smoke_acceptance_passed`
  The 5 query checks prove the remote path is usable for common respiratory
  topics, but they are not exhaustive retrieval-quality validation.

## Validation Commands

```powershell
.\.venv-sft\Scripts\python.exe -m unittest tests.test_extraction_routing_policy tests.test_section_upload
```

Result:

```text
Ran 6 tests
OK
```

## Next Step

Run one real respiratory wrong-question validation against the accepted
respiratory knowledge base:

```text
question_id
question_text
wrong_answer
correct_answer
tested_concept
paper_textbook_time
paper_textbook_path
kb_query
kb_hit_nodes
kb_evidence
kb_page_range
kb_time
highest_friction
bottleneck_type: search / catalog / detail / evidence
verdict: kb_helped / kb_not_helped / inconclusive
```
