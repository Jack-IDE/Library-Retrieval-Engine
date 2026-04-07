from __future__ import annotations

import argparse
from pathlib import Path

from brain_core.chunking import sanitize_library_id
from brain_core.indexing import build_full_index, build_full_index_multi, save_index


def _parse_library_specs(values: list[str]) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for value in values:
        raw = str(value).strip()
        if '=' not in raw:
            raise SystemExit(f'Invalid --library-spec {value!r}. Expected LIBRARY_ID=PATH')
        raw_library_id, raw_path = raw.split('=', 1)
        library_id = sanitize_library_id(raw_library_id)
        library_path = raw_path.strip()
        if not library_id or not library_path:
            raise SystemExit(f'Invalid --library-spec {value!r}. Expected LIBRARY_ID=PATH')
        if library_id in seen:
            raise SystemExit(f'Duplicate --library-spec library_id: {library_id}')
        seen.add(library_id)
        out.append((library_id, Path(library_path)))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description='Build a chunk index from one library path or a multi-library shared corpus.')
    parser.add_argument('--library', default='', help='Path to a single library directory')
    parser.add_argument('--library-id', default='', help='Stable namespace for a single library build; defaults to the library folder name')
    parser.add_argument('--library-spec', action='append', default=[], help='Repeat for shared indexes: LIBRARY_ID=PATH')
    parser.add_argument('--index', required=True, help='Path to the output index directory')
    parser.add_argument('--chunk-chars', type=int, default=700)
    parser.add_argument('--chunk-overlap', type=int, default=120)
    parser.add_argument('--vector-dim', type=int, default=64)
    args = parser.parse_args()

    index_root = Path(args.index)
    library_specs = _parse_library_specs(args.library_spec)

    if library_specs:
        if args.library:
            raise SystemExit('Use either --library for a single-library build or one or more --library-spec entries for a shared index, not both.')
        chunks, idf, metadata, vectors, retrieval_artifacts = build_full_index_multi(
            library_specs,
            chunk_chars=args.chunk_chars,
            overlap=args.chunk_overlap,
            vector_dim=args.vector_dim,
        )
        save_index(index_root, chunks, idf, metadata, chunk_vectors=vectors, retrieval_artifacts=retrieval_artifacts)
        print(f'Indexed {len(chunks)} chunks from {len(metadata.get("libraries", []))} libraries')
        for item in metadata.get('libraries', []):
            print(f'- {item["library_id"]}: {item["chunk_count"]} chunks from {item["library_root"]}')
        print(f'Index written to {index_root}')
        print(f'Vectors written to {index_root / "vectors.bin"}')
        print(f'Retrieval artifacts written to {index_root / "retrieval.json"}')
        return

    if not args.library:
        raise SystemExit('Provide --library PATH for a single-library build or one or more --library-spec LIBRARY_ID=PATH entries for a shared index.')

    library_root = Path(args.library)
    chunks, idf, metadata, vectors, retrieval_artifacts = build_full_index(
        library_root,
        chunk_chars=args.chunk_chars,
        overlap=args.chunk_overlap,
        vector_dim=args.vector_dim,
        library_id=args.library_id,
    )
    save_index(index_root, chunks, idf, metadata, chunk_vectors=vectors, retrieval_artifacts=retrieval_artifacts)
    print(f'Indexed {len(chunks)} chunks from {library_root}')
    print(f'Library ID: {metadata["library_id"]}')
    print(f'Index written to {index_root}')
    print(f'Vectors written to {index_root / "vectors.bin"}')
    print(f'Retrieval artifacts written to {index_root / "retrieval.json"}')


if __name__ == '__main__':
    main()
