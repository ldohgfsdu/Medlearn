# Textbook extraction pipeline

This pipeline stages textbook extraction before any production data is emitted.

## Safety rule

Do **not** write to `src/db/extractedKnowledge.ts` until:

1. Reader outputs have source page/chunk information.
2. Catalog segmentation finds expected headings with acceptable confidence.
3. Knowledge nodes include source spans and pass validation.
4. `validation-report.md` and `validation-report.json` have been reviewed.

## Unified CLI

```bash
# Dry-run every supported PDF/TXT under textbook/.
python scripts/textbook_parser.py auto --input textbook --out generated/textbook --dry-run --pipeline all

# Parse one textbook through every staging phase.
python scripts/textbook_parser.py parse --file "textbook/内科学（第10版）.pdf" --out generated/textbook --pipeline all --verbose

# Re-run one phase and its prerequisites.
python scripts/textbook_parser.py parse --file "textbook/内科学（第10版）.pdf" --out generated/textbook --pipeline nodes --force --verbose
python scripts/textbook_parser.py parse --file "textbook/内科学（第10版）.pdf" --out generated/textbook --pipeline validate --verbose

# Interactive selection.
python scripts/textbook_parser.py interactive --input textbook --out generated/textbook --pipeline reader
```

Common options:

- `--force`: ignore cache and regenerate reader outputs.
- `--wait-lock`: wait if another process is parsing the same book; default is skip.
- `--dry-run`: show selected files, bookId, output directory, cache status, catalog, and pipeline without writing.
- `--verbose`: print detailed commands and reader status.
- `--pipeline reader|segment|nodes|validate|all`: choose the staging depth.
- `--catalog <path>`: override the default catalog used for segment/nodes/validate.

## Output layout

Each textbook is written to an independent ASCII `bookId` directory:

```text
generated/textbook/
  internal-medicine-10/
    pages.jsonl
    toc.json
    segments.jsonl
    nodes.staging.json
    validation-report.md
    validation-report.json
    reader-report.json
    metadata.json
```

## Direct script commands

```bash
python scripts/textbook_pipeline/extract_pdf_text.py --pdf "textbook/内科学（第10版）.pdf" --out generated/textbook
python scripts/textbook_pipeline/segment_by_catalog.py --catalog scripts/textbook_pipeline/catalog.internal-medicine.json --pages generated/textbook/internal-medicine-10/pages.jsonl --toc generated/textbook/internal-medicine-10/toc.json --out generated/textbook/internal-medicine-10/segments.jsonl
python scripts/textbook_pipeline/extract_knowledge_nodes.py --segments generated/textbook/internal-medicine-10/segments.jsonl --out generated/textbook/internal-medicine-10/nodes.staging.json
python scripts/textbook_pipeline/validate_nodes.py --catalog scripts/textbook_pipeline/catalog.internal-medicine.json --segments generated/textbook/internal-medicine-10/segments.jsonl --nodes generated/textbook/internal-medicine-10/nodes.staging.json --report generated/textbook/internal-medicine-10/validation-report.md
```

## Current scope

The default catalog currently covers the respiratory-system part of internal medicine. Other textbooks can still be parsed through the reader phase; add a catalog JSON or pass `--catalog` before running segment/nodes/validate.

The catalog schema may later add `extends` for cross-textbook reuse. Keep new catalog files compatible with that direction by storing textbook-specific overrides separately from reusable chapter templates.
