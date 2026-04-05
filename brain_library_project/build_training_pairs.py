from __future__ import annotations

import argparse
from pathlib import Path

from brain_core.indexing import load_index
from brain_core.training_data import save_pairs_jsonl
from brain_core.weak_supervision import generate_pairs


def main() -> None:
    parser = argparse.ArgumentParser(description='Build labeled JSONL training pairs for the reranker.')
    parser.add_argument('--index', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--negatives-per-positive', type=int, default=2)
    parser.add_argument('--hard-negatives-per-positive', type=int, default=1)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--val-fraction', type=float, default=0.15)
    args = parser.parse_args()

    chunks, idf, metadata, vectors = load_index(Path(args.index))
    pairs = generate_pairs(
        chunks,
        negatives_per_positive=args.negatives_per_positive,
        seed=args.seed,
        val_fraction=args.val_fraction,
        idf=idf,
        retrieval_artifacts=metadata.get('retrieval_artifacts'),
        chunk_vectors=vectors,
        vector_dim=int(metadata.get('vector_dim', 64)),
        hard_negatives_per_positive=args.hard_negatives_per_positive,
    )
    save_pairs_jsonl(args.output, pairs)
    print(f'Wrote {len(pairs)} labeled pairs to {args.output}')


if __name__ == '__main__':
    main()
