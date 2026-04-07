#!/usr/bin/env python3
"""
build_vocab.py — Build and save a fixed vocabulary for brain_library.

Run this once over a broad base corpus.  The resulting vocab.json is
shipped alongside brain.gguf and stays frozen across library swaps.

Usage:
    # Scan one or more directories / files:
    python build_vocab.py --sources library/ docs/ --output vocab.json

    # Set a minimum token frequency (default 2):
    python build_vocab.py --sources library/ --min-freq 2 --output vocab.json

    # Cap vocab size (keeps highest-frequency tokens):
    python build_vocab.py --sources library/ --max-tokens 8000 --output vocab.json

    # Merge an existing vocab.json with new sources (additive, never shrinks):
    python build_vocab.py --sources new_library/ --merge vocab.json --output vocab.json

    # Show stats only, don't write:
    python build_vocab.py --sources library/ --dry-run

Supported file extensions (all decoded as UTF-8, errors ignored):
    .txt  .md  .rst  .py  .js  .ts  .c  .cpp  .h  .java  .json
    .yaml .yml .toml .ini .cfg .sh  .html .css  .xml  .csv
    .go   .rs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Import tokenizer and stopwords from the runtime package so vocab-building
# stays aligned with query-time tokenization.
# ─────────────────────────────────────────────────────────────────────────────

from brain_core.text_utils import STOPWORDS, tokenize

# Extensions we'll read.  Anything else is silently skipped.
TEXT_EXTENSIONS = {
    '.txt', '.md', '.rst',
    '.py', '.js', '.ts', '.c', '.cpp', '.h', '.java', '.go', '.rs',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
    '.sh', '.html', '.css', '.xml', '.csv',
}


# ─────────────────────────────────────────────────────────────────────────────
# File collection
# ─────────────────────────────────────────────────────────────────────────────

def collect_files(sources: List[Path]) -> List[Path]:
    """Expand directories recursively; keep plain files that match extensions."""
    out: List[Path] = []
    for src in sources:
        if src.is_file():
            if src.suffix.lower() in TEXT_EXTENSIONS:
                out.append(src)
            else:
                print(f'  Skipping (unsupported extension): {src}')
        elif src.is_dir():
            for p in sorted(src.rglob('*')):
                if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS:
                    out.append(p)
        else:
            print(f'  Warning: source not found: {src}')
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Counting
# ─────────────────────────────────────────────────────────────────────────────

def count_tokens(files: List[Path]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for path in files:
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError as exc:
            print(f'  Warning: could not read {path}: {exc}')
            continue
        for tok in tokenize(text):
            if tok in STOPWORDS:
                continue
            if len(tok) < 2:
                continue
            counts[tok] = counts.get(tok, 0) + 1
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Vocab assembly
# ─────────────────────────────────────────────────────────────────────────────

def build_vocab(
    counts: Dict[str, int],
    min_freq: int,
    max_tokens: Optional[int],
    existing: Optional[Dict[str, int]] = None,
) -> Dict[str, int]:
    """
    Turn a raw frequency dict into a vocab mapping token -> int ID.

    existing:  if provided, merge — existing tokens keep their IDs,
               new tokens are appended.  Never removes tokens.
    """
    # Filter by frequency
    qualified = {tok: freq for tok, freq in counts.items() if freq >= min_freq}

    # Sort by frequency descending, then alphabetical for stability
    ranked = sorted(qualified.items(), key=lambda kv: (-kv[1], kv[0]))

    if max_tokens is not None:
        # Reserve slot 0 for <pad>, so effective cap is max_tokens - 1 new tokens
        ranked = ranked[:max(0, max_tokens - 1)]

    if existing:
        vocab = dict(existing)
        next_id = max(vocab.values()) + 1
        for tok, _ in ranked:
            if tok not in vocab:
                vocab[tok] = next_id
                next_id += 1
    else:
        vocab: Dict[str, int] = {'<pad>': 0}
        for tok, _ in ranked:
            vocab[tok] = len(vocab)

    return vocab


# ─────────────────────────────────────────────────────────────────────────────
# Load / save
# ─────────────────────────────────────────────────────────────────────────────

def load_vocab(path: Path) -> Dict[str, int]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError(f'vocab file must be a JSON object: {path}')
    return {str(k): int(v) for k, v in raw.items()}


def save_vocab(path: Path, vocab: Dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sort by ID for human-readable output
    ordered = dict(sorted(vocab.items(), key=lambda kv: kv[1]))
    path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False), encoding='utf-8')


# ─────────────────────────────────────────────────────────────────────────────
# Stats display
# ─────────────────────────────────────────────────────────────────────────────

def print_stats(counts: Dict[str, int], vocab: Dict[str, int], min_freq: int) -> None:
    total_unique = len(counts)
    after_filter = sum(1 for f in counts.values() if f >= min_freq)
    in_vocab = len(vocab) - 1  # exclude <pad>

    # Frequency bands
    bands = [(1, 1), (2, 4), (5, 19), (20, 99), (100, 999), (1000, 10**9)]
    print(f'\n  Unique raw tokens:       {total_unique:>8,}')
    print(f'  After min_freq={min_freq:<3}:        {after_filter:>8,}')
    print(f'  Final vocab (excl pad):  {in_vocab:>8,}')
    print()
    print('  Frequency distribution of raw tokens:')
    for lo, hi in bands:
        count = sum(1 for f in counts.values() if lo <= f <= hi)
        label = f'{lo}' if lo == hi else (f'{lo}–{hi}' if hi < 10**9 else f'{lo}+')
        bar = '█' * min(40, count // max(1, total_unique // 40))
        print(f'    [{label:>8}]  {count:>7,}  {bar}')

    # Top 20 tokens
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:20]
    print()
    print('  Top 20 tokens:')
    for tok, freq in top:
        in_v = '✓' if tok in vocab else '✗'
        print(f'    {in_v}  {freq:>7,}  {tok}')


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Build a fixed vocab.json for brain_library.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--sources', nargs='+', required=True, metavar='PATH',
                        help='Directories or files to scan')
    parser.add_argument('--output', default='vocab.json', metavar='PATH',
                        help='Where to write the vocab (default: vocab.json)')
    parser.add_argument('--min-freq', type=int, default=2, metavar='N',
                        help='Minimum token frequency to include (default: 2)')
    parser.add_argument('--max-tokens', type=int, default=None, metavar='N',
                        help='Cap total vocab size (keeps highest-frequency tokens)')
    parser.add_argument('--merge', default='', metavar='PATH',
                        help='Existing vocab.json to merge into (additive only)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print stats but do not write output')
    args = parser.parse_args()

    sources = [Path(s) for s in args.sources]
    out_path = Path(args.output)

    # Collect + count
    print(f'\nScanning sources...')
    files = collect_files(sources)
    if not files:
        print('  No supported files found.  Check --sources paths.')
        sys.exit(1)
    print(f'  Files found: {len(files)}')

    print('Counting tokens...')
    counts = count_tokens(files)
    print(f'  Done.  Unique tokens before filtering: {len(counts):,}')

    # Load existing vocab if merging
    existing: Optional[Dict[str, int]] = None
    if args.merge:
        merge_path = Path(args.merge)
        if merge_path.exists():
            existing = load_vocab(merge_path)
            print(f'  Merging with existing vocab ({len(existing):,} tokens): {merge_path}')
        else:
            print(f'  Warning: --merge path not found, starting fresh: {merge_path}')

    # Build
    vocab = build_vocab(counts, args.min_freq, args.max_tokens, existing)

    # Stats
    print_stats(counts, vocab, args.min_freq)

    if args.dry_run:
        print('\n  --dry-run set, nothing written.')
        return

    save_vocab(out_path, vocab)
    size_kb = out_path.stat().st_size / 1024
    print(f'\nSaved: {out_path}  ({size_kb:.1f} KB,  {len(vocab):,} tokens incl. <pad>)')
    print('Done.')


if __name__ == '__main__':
    main()
