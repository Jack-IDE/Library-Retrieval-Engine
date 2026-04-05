from __future__ import annotations

import argparse
from pathlib import Path

from brain_core.indexing import build_full_index, save_index


def main() -> None:
    parser = argparse.ArgumentParser(description='Build a chunk index from a library path.')
    parser.add_argument('--library', required=True, help='Path to the library directory')
    parser.add_argument('--index', required=True, help='Path to the output index directory')
    parser.add_argument('--chunk-chars', type=int, default=700)
    parser.add_argument('--chunk-overlap', type=int, default=120)
    parser.add_argument('--vector-dim', type=int, default=64)
    args = parser.parse_args()

    library_root = Path(args.library)
    index_root = Path(args.index)
    chunks, idf, metadata, vectors, retrieval_artifacts = build_full_index(
        library_root,
        chunk_chars=args.chunk_chars,
        overlap=args.chunk_overlap,
        vector_dim=args.vector_dim,
    )
    save_index(index_root, chunks, idf, metadata, chunk_vectors=vectors, retrieval_artifacts=retrieval_artifacts)
    print(f'Indexed {len(chunks)} chunks from {library_root}')
    print(f'Index written to {index_root}')
    print(f'Vectors written to {index_root / "vectors.bin"}')
    print(f'Retrieval artifacts written to {index_root / "retrieval.json"}')


if __name__ == '__main__':
    main()
