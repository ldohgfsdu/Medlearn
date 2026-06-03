import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.textbook_pipeline.atomic_io import atomic_write_json, atomic_write_jsonl
from scripts.textbook_pipeline.book_registry import infer_book
from scripts.textbook_pipeline.metadata import build_metadata, write_metadata
from scripts.textbook_pipeline.readers.pdf_reader import PdfReader


def main() -> None:
    parser = argparse.ArgumentParser(description='Extract page text and PDF TOC from a textbook PDF.')
    parser.add_argument('--pdf', required=True, help='Path to the textbook PDF')
    parser.add_argument('--out', required=True, help='Output root directory')
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    out_root = Path(args.out)
    book = infer_book(pdf_path, out_root)
    book_dir = out_root / book['bookId']
    reader = PdfReader()
    result = reader.read(pdf_path)

    atomic_write_jsonl(book_dir / 'pages.jsonl', result.pages)
    atomic_write_json(book_dir / 'toc.json', result.toc)
    atomic_write_json(book_dir / 'reader-report.json', result.report)
    write_metadata(book_dir / 'metadata.json', build_metadata(pdf_path, book, reader.format, result.errors))

    print(f"Wrote {book_dir / 'pages.jsonl'}")
    print(f"Wrote {book_dir / 'toc.json'}")
    print(f"Wrote {book_dir / 'reader-report.json'}")
    print(f"Wrote {book_dir / 'metadata.json'}")


if __name__ == '__main__':
    main()
