from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path
from typing import Dict, List, Sequence

from .text_utils import STOPWORDS, tokenize

VEC_MAGIC = b'BLV1'


def _hash_index(token: str, dim: int) -> tuple[int, float]:
    h = hashlib.blake2b(token.encode('utf-8'), digest_size=8).digest()
    value = int.from_bytes(h, 'little', signed=False)
    index = value % dim
    sign = -1.0 if ((value >> 8) & 1) else 1.0
    return index, sign


def hashed_text_vector(text: str, idf: Dict[str, float], dim: int = 64) -> List[float]:
    vec = [0.0] * dim
    counts: Dict[str, int] = {}
    for tok in tokenize(text):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    if not counts:
        return vec
    for tok, count in counts.items():
        idx, sign = _hash_index(tok, dim)
        weight = (1.0 + math.log(count)) * idf.get(tok, 1.0)
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        inv = 1.0 / norm
        vec = [v * inv for v in vec]
    return vec


def build_chunk_vectors(chunks, idf: Dict[str, float], dim: int = 64) -> List[List[float]]:
    vectors: List[List[float]] = []
    for chunk in chunks:
        text = ' '.join([
            chunk.heading,
            chunk.symbol_name,
            chunk.source_type,
            chunk.source_path,
            chunk.text,
            ' '.join(chunk.keyword_list),
        ])
        vectors.append(hashed_text_vector(text, idf, dim=dim))
    return vectors


def save_vectors(path: str | Path, vectors: Sequence[Sequence[float]], dim: int) -> None:
    path = Path(path)
    rows = len(vectors)
    with path.open('wb') as f:
        f.write(VEC_MAGIC)
        f.write(struct.pack('<II', rows, dim))
        for row in vectors:
            if len(row) != dim:
                raise ValueError('vector dim mismatch')
            f.write(struct.pack(f'<{dim}f', *row))


def load_vectors(path: str | Path) -> List[List[float]]:
    path = Path(path)
    with path.open('rb') as f:
        magic = f.read(4)
        if magic != VEC_MAGIC:
            raise ValueError('bad vector magic')
        rows, dim = struct.unpack('<II', f.read(8))
        out: List[List[float]] = []
        for _ in range(rows):
            raw = f.read(dim * 4)
            if len(raw) != dim * 4:
                raise ValueError('truncated vector file')
            out.append(list(struct.unpack(f'<{dim}f', raw)))
    return out

