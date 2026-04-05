from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

from .chunking import Chunk, chunk_file
from .text_utils import STOPWORDS, tokenize
from .vector_store import build_chunk_vectors, load_vectors, save_vectors

SUPPORTED_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.json', '.html', '.css'}


def scan_library(library_root: Path, chunk_chars: int = 700, overlap: int = 120) -> List[Chunk]:
    chunks: List[Chunk] = []
    for path in sorted(library_root.rglob('*')):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        chunks.extend(chunk_file(path, chunk_chars=chunk_chars, overlap=overlap))
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
        term_list = sorted(counts.keys())
        chunk_term_lists.append(term_list)
        chunk_lengths.append(len(body_tokens))
        avg_len_total += len(body_tokens)

        heading_blob = ' '.join([
            chunk.heading,
            chunk.source_path,
            chunk.symbol_name,
            chunk.source_type,
        ]).lower()
        heading_blobs.append(heading_blob)
        keyword_lists.append(list(dict.fromkeys(tok.lower() for tok in chunk.keyword_list if tok.strip())))
        source_type_buckets.setdefault(chunk.source_type or 'unknown', []).append(idx)

    return {
        'postings': postings,
        'chunk_lengths': chunk_lengths,
        'chunk_term_lists': chunk_term_lists,
        'heading_blobs': heading_blobs,
        'keyword_lists': keyword_lists,
        'source_type_buckets': source_type_buckets,
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
    chunks: List[Chunk] = []
    with (index_root / 'chunks.jsonl').open('r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line)
            chunks.append(Chunk(**obj))
    with (index_root / 'idf.json').open('r', encoding='utf-8') as f:
        idf = json.load(f)
    with (index_root / 'metadata.json').open('r', encoding='utf-8') as f:
        metadata = json.load(f)
    vectors_path = index_root / 'vectors.bin'
    vectors = load_vectors(vectors_path) if vectors_path.exists() else None
    retrieval_artifacts = _load_retrieval_artifacts(index_root)
    if retrieval_artifacts is not None:
        metadata['retrieval_artifacts'] = retrieval_artifacts
    return chunks, idf, metadata, vectors


def build_full_index(library_root: Path, chunk_chars: int = 700, overlap: int = 120, vector_dim: int = 64):
    chunks = scan_library(library_root, chunk_chars=chunk_chars, overlap=overlap)
    idf = build_idf(chunks)
    vectors = build_chunk_vectors(chunks, idf=idf, dim=vector_dim)
    retrieval_artifacts = build_retrieval_artifacts(chunks)
    metadata = {
        'library_root': str(library_root.resolve()),
        'chunk_count': len(chunks),
        'chunk_chars': chunk_chars,
        'chunk_overlap': overlap,
        'vector_dim': vector_dim,
        'index_version': 3,
        'retrieval_artifact_version': 1,
    }
    return chunks, idf, metadata, vectors, retrieval_artifacts
