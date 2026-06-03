import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.textbook_pipeline.atomic_io import atomic_write_json, atomic_write_jsonl
from scripts.textbook_pipeline.book_registry import infer_book, supported_files
from scripts.textbook_pipeline.lock import ParseLock
from scripts.textbook_pipeline.metadata import build_metadata, is_cache_valid, write_metadata
from scripts.textbook_pipeline.readers.factory import reader_for

PIPELINE_STEPS = {
    'reader': ['reader'],
    'segment': ['reader', 'segment'],
    'nodes': ['reader', 'segment', 'nodes'],
    'validate': ['reader', 'segment', 'nodes', 'validate'],
    'all': ['reader', 'segment', 'nodes', 'validate'],
}

DEFAULT_CATALOGS = {
    'internal-medicine': ROOT / 'scripts' / 'textbook_pipeline' / 'catalog.internal-medicine.json',
}


def output_dir_for(source: Path, out_root: Path) -> tuple[dict, Path]:
    book = infer_book(source, out_root)
    return book, out_root / book['bookId']


def catalog_for(book: dict, explicit_catalog: str | None = None) -> Path | None:
    if explicit_catalog:
        catalog = Path(explicit_catalog)
        return catalog if catalog.exists() else None
    for prefix, catalog in DEFAULT_CATALOGS.items():
        if book['bookId'].startswith(prefix):
            return catalog if catalog.exists() else None
    return None


def run_command(command: list[str], verbose: bool) -> bool:
    if verbose:
        print('[run] ' + ' '.join(command))
    try:
        subprocess.run(command, check=True, capture_output=not verbose, text=True)
        return True
    except subprocess.CalledProcessError as exc:
        if not verbose:
            print(f'[fail] {" ".join(command)}: {exc.stderr.strip() if exc.stderr else exc}')
        print(f'[fail] Step exited with code {exc.returncode}')
        return False


def run_reader(source: Path, book: dict, book_dir: Path, force: bool, wait_lock: bool, verbose: bool) -> bool:
    metadata_path = book_dir / 'metadata.json'
    cache_hit = is_cache_valid(source, metadata_path) if not force else False
    if cache_hit:
        print(f"[cache] {book['bookId']}: reader outputs are current")
        return True

    book_dir.mkdir(parents=True, exist_ok=True)
    lock = ParseLock(book_dir / '.parse.lock', book['bookId'], source, wait=wait_lock, verbose=verbose)
    try:
        with lock:
            reader = reader_for(source)
            if verbose:
                print(f'[reader] {reader.format}: {source}')
            result = reader.read(source)
            atomic_write_jsonl(book_dir / 'pages.jsonl', result.pages)
            atomic_write_json(book_dir / 'toc.json', result.toc)
            atomic_write_json(book_dir / 'reader-report.json', result.report)
            metadata = build_metadata(source, book, reader.format, result.errors)
            write_metadata(metadata_path, metadata)
            print(f"[ok] {book['bookId']}: pages={len(result.pages)}, toc={len(result.toc)}")
            return True
    except RuntimeError as exc:
        print(f'[skip] {exc}')
        return False


def ensure_reader_outputs(book_dir: Path) -> bool:
    required = [book_dir / 'pages.jsonl', book_dir / 'toc.json']
    return all(path.exists() for path in required)


def run_segment(book: dict, book_dir: Path, catalog: Path | None, verbose: bool) -> bool:
    if not catalog:
        print(f"[skip] {book['bookId']}: no catalog configured for segmentation")
        return False
    if not ensure_reader_outputs(book_dir):
        print(f"[skip] {book['bookId']}: reader outputs missing; cannot segment")
        return False
    return run_command([
        sys.executable,
        str(ROOT / 'scripts' / 'textbook_pipeline' / 'segment_by_catalog.py'),
        '--catalog', str(catalog),
        '--pages', str(book_dir / 'pages.jsonl'),
        '--toc', str(book_dir / 'toc.json'),
        '--out', str(book_dir / 'segments.jsonl'),
    ], verbose)


def run_nodes(book: dict, book_dir: Path, verbose: bool) -> bool:
    segments_path = book_dir / 'segments.jsonl'
    if not segments_path.exists():
        print(f"[skip] {book['bookId']}: segments.jsonl missing; cannot extract nodes")
        return False
    return run_command([
        sys.executable,
        str(ROOT / 'scripts' / 'textbook_pipeline' / 'extract_knowledge_enhanced.py'),
        '--segments', str(segments_path),
        '--out', str(book_dir / 'nodes.staging.json'),
    ], verbose)


def run_validate(book: dict, book_dir: Path, catalog: Path | None, verbose: bool) -> bool:
    if not catalog:
        print(f"[skip] {book['bookId']}: no catalog configured for validation")
        return False
    nodes_path = book_dir / 'nodes.staging.json'
    segments_path = book_dir / 'segments.jsonl'
    if not nodes_path.exists() or not segments_path.exists():
        print(f"[skip] {book['bookId']}: nodes or segments missing; cannot validate")
        return False
    return run_command([
        sys.executable,
        str(ROOT / 'scripts' / 'textbook_pipeline' / 'validate_nodes.py'),
        '--catalog', str(catalog),
        '--segments', str(segments_path),
        '--nodes', str(nodes_path),
        '--report', str(book_dir / 'validation-report.md'),
    ], verbose)


def parse_one(source: Path, out_root: Path, force: bool, wait_lock: bool, dry_run: bool, verbose: bool, pipeline: str, catalog_arg: str | None = None) -> None:
    book, book_dir = output_dir_for(source, out_root)
    metadata_path = book_dir / 'metadata.json'
    cache_hit = is_cache_valid(source, metadata_path) if not force else False
    steps = PIPELINE_STEPS[pipeline]
    catalog = catalog_for(book, catalog_arg)
    print(f"[book] {source.name} -> {book['bookId']} ({'cache-hit' if cache_hit else 'parse'})")
    if dry_run:
        print(f'  out: {book_dir}')
        print(f"  pipeline: {' -> '.join(steps)}")
        print(f"  catalog: {catalog if catalog else '(none; reader only)'}")
        return

    reader_ok = True
    if 'reader' in steps:
        reader_ok = run_reader(source, book, book_dir, force, wait_lock, verbose)
    if not reader_ok:
        return
    if 'segment' in steps and not run_segment(book, book_dir, catalog, verbose):
        return
    if 'nodes' in steps and not run_nodes(book, book_dir, verbose):
        return
    if 'validate' in steps:
        run_validate(book, book_dir, catalog, verbose)


def select_interactive(files: list[Path]) -> list[Path]:
    for index, file in enumerate(files, start=1):
        print(f'[{index}] {file.name}')
    raw = input('Select textbooks (number, comma list, all, q): ').strip()
    if raw.lower() == 'q':
        return []
    if raw.lower() == 'all':
        return files
    selected: list[Path] = []
    for part in raw.split(','):
        try:
            idx = int(part.strip())
            if 1 <= idx <= len(files):
                selected.append(files[idx - 1])
        except ValueError:
            pass
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description='Universal textbook parser')
    sub = parser.add_subparsers(dest='command', required=True)

    def add_common(p):
        p.add_argument('--out', default='generated/textbook')
        p.add_argument('--force', action='store_true')
        p.add_argument('--wait-lock', action='store_true')
        p.add_argument('--dry-run', action='store_true')
        p.add_argument('--verbose', action='store_true')
        p.add_argument('--pipeline', choices=['reader', 'segment', 'nodes', 'validate', 'all'], default='reader')
        p.add_argument('--catalog', help='Catalog JSON to use for segment/nodes/validate phases')

    p_interactive = sub.add_parser('interactive')
    p_interactive.add_argument('--input', default='textbook')
    add_common(p_interactive)

    p_auto = sub.add_parser('auto')
    p_auto.add_argument('--input', default='textbook')
    add_common(p_auto)

    p_parse = sub.add_parser('parse')
    p_parse.add_argument('--file', required=True)
    add_common(p_parse)

    args = parser.parse_args()
    out_root = Path(args.out)

    if args.command == 'parse':
        files = supported_files(Path(args.file))
    else:
        files = supported_files(Path(args.input))
        if args.command == 'interactive':
            files = select_interactive(files)

    if not files:
        print('[info] no supported textbooks selected')
        return

    for source in files:
        parse_one(source, out_root, args.force, args.wait_lock, args.dry_run, args.verbose, args.pipeline, args.catalog)


if __name__ == '__main__':
    main()
