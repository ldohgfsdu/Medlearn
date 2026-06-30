# Adaptive PDF Parsing

The production PDF parser is `auto`. It preserves the existing Markdown
interface while selecting the safest parser for each page.

## Flow

```text
PDF
  -> bookmark catalog
     -> layout heading inference when bookmarks are absent
     -> four-page windows when no reliable headings exist
  -> page analysis
     -> PyMuPDF for ordinary text pages
     -> Docling for complex layout and table-heavy pages
     -> Docling + RapidOCR for scanned pages
  -> repeated header/footer removal
  -> text/table overlap removal
  -> structure-aware chunking
  -> page quality gate
  -> model extraction
```

## Output Artifacts

For a scoped extraction, the parser writes:

- `*.md`: cleaned source Markdown with PDF page markers
- `*.parse-report.json`: page routes, quality scores, issues, and blocking pages
- `*.source-artifacts.json`: text, table, figure, caption, page, bbox, parser,
  confidence, and asset references
- `source-assets/<book>/`: preserved original PDF image artifacts
- `<book>.parser-profile.json`: reusable header/footer profile

`source-artifacts.json` contains locating attributes. It does not claim that an
automatically generated locator is an approved permanent Source Anchor. Source
Anchor identity and relocation review remain governed by ADR-009.

## Quality Gate

Extraction stops before model inference when a page:

- has no usable text after OCR/fallback
- has a page quality score below `0.35`
- is otherwise marked as a blocking page

Warnings such as multi-column layout, Docling fallback, duplicate text, and
garbled text remain visible in the parse report.

Upload is also rejected when an extracted knowledge node cannot be matched back
to at least one page-level source locator. The quality report records
`nodes_with_source_locators`, `source_locator_coverage_ratio`, and the
`all_evidence_located` check.

## Configuration

```powershell
# Production default
$env:MEDLEARN_PDF_PARSER = "auto"

# Diagnostic overrides
$env:MEDLEARN_PDF_PARSER = "pymupdf"
$env:MEDLEARN_PDF_PARSER = "docling"
```

The CLI also accepts:

```powershell
python scripts/pipeline_v3_extract.py book.pdf --pdf-parser auto
python scripts/pipeline_v3_extract.py book.pdf --pdf-parser pymupdf
python scripts/pipeline_v3_extract.py book.pdf --pdf-parser docling
```

## Regression Commands

```powershell
.\.venv-sft\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.\.venv-sft\Scripts\python.exe scripts/verify_pipeline_closure.py --json
```
