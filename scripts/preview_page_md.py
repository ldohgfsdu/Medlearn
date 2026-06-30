#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from textbook_pipeline.adaptive_pdf_parser import AdaptivePdfParser

pdf = Path(r"F:\ml\textbook\内科学（第10版）.pdf")
parser = AdaptivePdfParser(pdf, mode="pymupdf")
pages = [int(x) for x in sys.argv[1:]] or [81, 112, 282, 233]
for p in pages:
    md, rep = parser.parse_range(p, p)
    info = rep["pages"][0]
    print("=" * 60)
    print(
        f"Page {p}: tables={info['table_count']} quality={info['quality_score']} "
        f"chars={len(md)} issues={info['issues']}"
    )
    print(md[:800])
    print("...")