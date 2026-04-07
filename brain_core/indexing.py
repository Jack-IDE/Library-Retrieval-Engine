from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from .chunking import CODE_EXTENSIONS, Chunk, chunk_file, derive_library_id, sanitize_library_id
from .text_utils import STOPWORDS, tokenize
from .vector_store import build_chunk_vectors, load_vectors, save_vectors


SUPPORTED_EXTENSIONS = {'.txt', '.md', '.json', '.html', '.css'} | CODE_EXTENSIONS

META_LIBRARY_FILENAMES = {'library_input_notes.txt', 'retrieval_notes.txt'}


def _should_skip_index_path(path: Path, library_root: Path) -> bool:
    rel = path.resolve().relative_to(library_root.resolve()).as_posix().lower()
    name = path.name.lower()
    if name in META_LIBRARY_FILENAMES:
        return True
    if rel == 'readme.md':
        return True
    return False


def _validate_library_root(library_root: Path) -> Path:
    library_root = Path(library_root)
    if not library_root.is_dir():
        raise SystemExit(f'Library path not found: {library_root}')
    return library_root


def scan_library(library_root: Path, chunk_chars: int = 700, overlap: int = 120, library_id: str = '') -> List[Chunk]:
    normalized_library_id = sanitize_library_id(library_id or derive_library_id(library_root))
    chunks: List[Chunk] = []
    for path in sorted(library_root.rglob('*')):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if _should_skip_index_path(path, library_root):
            continue
        chunks.extend(
            chunk_file(
                path,
                chunk_chars=chunk_chars,
                overlap=overlap,
                library_root=library_root,
                library_id=normalized_library_id,
            )
        )
    return chunks


def build_idf(chunks: List[Chunk]) -> Dict[str, float]:
    doc_freq: Dict[str, int] = {}
    for chunk in chunks:
        seen = set(tokenize(' '.join([
            chunk.text,
            chunk.heading,
            chunk.source_path,
            chunk.symbol_name,
            ' '.join(chunk.keyword_list),
        ])))
        for tok in seen:
            doc_freq[tok] = doc_freq.get(tok, 0) + 1
    total_docs = max(1, len(chunks))
    return {tok: math.log((1 + total_docs) / (1 + df)) + 1.0 for tok, df in doc_freq.items()}


def build_retrieval_artifacts(chunks: List[Chunk]) -> Dict:
    postings: Dict[str, List[List[int]]] = {}
    chunk_lengths: List[int] = []
    chunk_term_lists: List[List[str]] = []
    heading_blobs: List[str] = []
    keyword_lists: List[List[str]] = []
    source_type_buckets: Dict[str, List[int]] = {}
    library_id_buckets: Dict[str, List[int]] = {}
    avg_len_total = 0

    for idx, chunk in enumerate(chunks):
        body_tokens = [
            tok for tok in tokenize(' '.join([
                chunk.text,
                chunk.heading,
                chunk.source_path,
                chunk.symbol_name,
            ]))
            if tok not in STOPWORDS and len(tok) >= 2
        ]
        counts: Dict[str, int] = {}
        for tok in body_tokens:
            counts[tok] = counts.get(tok, 0) + 1
        for tok, tf in counts.items():
            postings.setdefault(tok, []).append([idx, tf])
        chunk_term_lists.append(sorted(counts.keys()))
        chunk_lengths.append(len(body_tokens))
        avg_len_total += len(body_tokens)

        heading_blob = ' '.join([
            chunk.heading,
            chunk.source_path,
            chunk.symbol_name,
            chunk.source_type,
            chunk.library_id,
        ]).lower()
        heading_blobs.append(heading_blob)
        keyword_lists.append(list(dict.fromkeys(tok.lower() for tok in chunk.keyword_list if tok.strip())))
        source_type_buckets.setdefault(chunk.source_type or 'unknown', []).append(idx)
        library_id_buckets.setdefault(chunk.library_id or 'library', []).append(idx)

    return {
        'postings': postings,
        'chunk_lengths': chunk_lengths,
        'chunk_term_lists': chunk_term_lists,
        'heading_blobs': heading_blobs,
        'keyword_lists': keyword_lists,
        'source_type_buckets': source_type_buckets,
        'library_id_buckets': library_id_buckets,
        'avg_chunk_length': (avg_len_total / max(1, len(chunks))),
    }


def save_index(
    index_root: Path,
    chunks: List[Chunk],
    idf: Dict[str, float],
    metadata: Dict,
    chunk_vectors: List[List[float]] | None = None,
    retrieval_artifacts: Dict | None = None,
) -> None:
    index_root.mkdir(parents=True, exist_ok=True)
    with (index_root / 'chunks.jsonl').open('w', encoding='utf-8') as f:
        for chunk in chunks:
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + '\n')
    with (index_root / 'idf.json').open('w', encoding='utf-8') as f:
        json.dump(idf, f, ensure_ascii=False, separators=(',', ':'))
    with (index_root / 'metadata.json').open('w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    if chunk_vectors is not None:
        save_vectors(index_root / 'vectors.bin', chunk_vectors, dim=metadata['vector_dim'])
    if retrieval_artifacts is not None:
        with (index_root / 'retrieval.json').open('w', encoding='utf-8') as f:
            json.dump(retrieval_artifacts, f, ensure_ascii=False, separators=(',', ':'))


def _load_retrieval_artifacts(index_root: Path) -> Dict | None:
    path = index_root / 'retrieval.json'
    if not path.exists():
        return None
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def load_index(index_root: Path) -> Tuple[List[Chunk], Dict[str, float], Dict, List[List[float]] | None]:
    metadata_path = index_root / 'metadata.json'
    if metadata_path.exists():
        with metadata_path.open('r', encoding='utf-8') as f:
            metadata = json.load(f)
    else:
        metadata = {}
    default_library_id = sanitize_library_id(metadata.get('library_id') or derive_library_id(Path(metadata.get('library_root', index_root.name))))

    chunks: List[Chunk] = []
    with (index_root / 'chunks.jsonl').open('r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line)
            if 'library_id' not in obj or not obj.get('library_id'):
                obj['library_id'] = default_library_id
            chunks.append(Chunk(**obj))
    with (index_root / 'idf.json').open('r', encoding='utf-8') as f:
        idf = json.load(f)
    metadata.setdefault('library_id', default_library_id)
    vectors_path = index_root / 'vectors.bin'
    vectors = load_vectors(vectors_path) if vectors_path.exists() else None
    retrieval_artifacts = _load_retrieval_artifacts(index_root)
    if retrieval_artifacts is not None:
        metadata['retrieval_artifacts'] = retrieval_artifacts
    return chunks, idf, metadata, vectors


def _normalize_library_entries(library_entries: Sequence[tuple[str, Path]]) -> List[tuple[str, Path]]:
    normalized: List[tuple[str, Path]] = []
    seen_ids: set[str] = set()
    for raw_library_id, raw_root in library_entries:
        library_root = _validate_library_root(Path(raw_root))
        library_id = sanitize_library_id(raw_library_id or derive_library_id(library_root))
        if library_id in seen_ids:
            raise ValueError(f'duplicate library_id in multi-library build: {library_id}')
        seen_ids.add(library_id)
        normalized.append((library_id, library_root))
    return normalized


def build_full_index(
    library_root: Path,
    chunk_chars: int = 700,
    overlap: int = 120,
    vector_dim: int = 64,
    library_id: str = '',
):
    library_root = _validate_library_root(library_root)
    normalized_library_id = sanitize_library_id(library_id or derive_library_id(library_root))
    chunks = scan_library(library_root, chunk_chars=chunk_chars, overlap=overlap, library_id=normalized_library_id)
    idf = build_idf(chunks)
    vectors = build_chunk_vectors(chunks, idf=idf, dim=vector_dim)
    retrieval_artifacts = build_retrieval_artifacts(chunks)
    metadata = {
        'library_root': str(library_root.resolve()),
        'library_id': normalized_library_id,
        'chunk_count': len(chunks),
        'chunk_chars': chunk_chars,
        'chunk_overlap': overlap,
        'vector_dim': vector_dim,
        'multi_library': False,
        'libraries': [{
            'library_id': normalized_library_id,
            'library_root': str(library_root.resolve()),
            'chunk_count': len(chunks),
        }],
        'index_version': 5,
        'retrieval_artifact_version': 2,
    }
    return chunks, idf, metadata, vectors, retrieval_artifacts


def build_full_index_multi(
    library_entries: Sequence[tuple[str, Path]],
    chunk_chars: int = 700,
    overlap: int = 120,
    vector_dim: int = 64,
):
    normalized_entries = _normalize_library_entries(library_entries)
    all_chunks: List[Chunk] = []
    libraries_meta: List[Dict[str, object]] = []
    for library_id, library_root in normalized_entries:
        chunks = scan_library(library_root, chunk_chars=chunk_chars, overlap=overlap, library_id=library_id)
        all_chunks.extend(chunks)
        libraries_meta.append({
            'library_id': library_id,
            'library_root': str(library_root.resolve()),
            'chunk_count': len(chunks),
        })

    idf = build_idf(all_chunks)
    vectors = build_chunk_vectors(all_chunks, idf=idf, dim=vector_dim)
    retrieval_artifacts = build_retrieval_artifacts(all_chunks)
    metadata = {
        'library_root': '',
        'library_id': 'multi',
        'library_ids': [item['library_id'] for item in libraries_meta],
        'chunk_count': len(all_chunks),
        'chunk_chars': chunk_chars,
        'chunk_overlap': overlap,
        'vector_dim': vector_dim,
        'multi_library': True,
        'libraries': libraries_meta,
        'index_version': 5,
        'retrieval_artifact_version': 2,
    }
    return all_chunks, idf, metadata, vectors, retrieval_artifacts
