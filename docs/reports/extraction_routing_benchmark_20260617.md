# Extraction Routing Benchmark - 2026-06-17

## Purpose

This report records the evidence used to fix the extraction routing policy for
the current ingestion cleanup work. It does not create a new active object and
does not change the project-level priority. The evidence supports the current
`respiratory_mvp_real_question_validation` work by reducing extraction-route
uncertainty.

## Evidence Source

- Source file: `generated/vision_compare/summary_20260617_125826.json`
- Pages: 77-86
- PDF render: 100 DPI
- Text model settings: `think=false`, `temperature=0`, `num_predict=4096`
- Vision model settings: `think=false`, `temperature=0`, `num_predict=2048`

## Benchmark Result

| Metric | Result |
|---|---:|
| Text success rate | 8/10 |
| Vision success rate | 6/10 |
| Fallback triggered | 2 |
| Fallback improved | 2/2 |
| Selected route: text | 8 |
| Selected route: vision | 2 |

## Page-Level Routing Decisions

| Page | Page type | Text nodes | Text JSON | Vision nodes | Vision JSON | Selected route | Notes |
|---:|---|---:|---|---:|---|---|---|
| 77 | text | 15 | valid | 0 | invalid | text | Vision failure reason: `non_json_response`; raw response began as JSON but was truncated before a complete object. |
| 78 | unknown | 14 | valid | 11 | valid | text | Text succeeded; Vision comparison does not override. |
| 79 | unknown | 0 | invalid | 9 | valid | vision | Fallback improved. |
| 80 | unknown | 8 | valid | 0 | invalid | text | Vision JSON failure ignored because Text succeeded. |
| 81 | table | 28 | valid | 9 | valid | text | `page_type=table` is not enough to default to Vision; Text produced more nodes and still requires structure review for table fidelity. |
| 82 | unknown | 0 | invalid | 11 | valid | vision | Fallback improved. |
| 83 | unknown | 9 | valid | 0 | invalid | text | Vision JSON failure ignored because Text succeeded. |
| 84 | unknown | 10 | valid | 0 | invalid | text | Vision JSON failure ignored because Text succeeded. |
| 85 | mixed | 8 | valid | 12 | valid | text | Vision nodes were higher, but this only marks `needs_quality_review`; it does not automatically override Text. |
| 86 | unknown | 25 | valid | 9 | valid | text | Text succeeded; Vision comparison does not override. |

## Failure Attribution

Page 77 Vision failure is classified as:

```text
failure_reason=non_json_response
```

Reason: the Vision raw response was non-empty and began as JSON, but it ended
inside an unfinished string. It did not contain "unclear", "cannot recognize",
or equivalent failure language. The rendered image was 800x1103 at 100 DPI and
showed complete upright body text, so this run does not support
`image_preprocess_failed`.

## Fixed Routing Policy

Default extraction route is Text.

1. Run Text first for every page.
2. If Text JSON is valid and `nodes > 0`, set `selected_route=text`.
3. In production routing, do not call Vision after Text succeeds.
4. If Text JSON is invalid, fallback to Vision with
   `fallback_reason=text_json_invalid`.
5. If Text JSON is valid but `nodes=0`, fallback to Vision with
   `fallback_reason=text_nodes_zero`.
6. If Vision nodes are higher but Text succeeded, set
   `quality_notes=needs_quality_review`; do not automatically replace Text.
7. If Vision JSON is invalid but Text succeeded, ignore the Vision failure for
   routing.
8. Do not route to Vision solely because `page_type=table`; table pages still
   require source-structure quality review under ADR-009.

## Required Result Fields

Future extraction comparison results must include:

- `selected_route`
- `fallback_reason`
- `text_nodes`
- `text_json_valid`
- `vision_nodes`
- `vision_json_valid`
- `quality_notes`

## Interpretation

This benchmark supports Text-first routing. It does not support continuing
Vision-only parameter tuning as the next priority. Vision remains useful as a
fallback when Text fails or as a comparison signal that can create
`needs_quality_review`, especially for mixed or structure-heavy pages.

This report is evidence for extraction-chain cleanup only. It does not add a new
active object.
