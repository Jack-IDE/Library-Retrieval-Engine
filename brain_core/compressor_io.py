from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import List

from .compressor_model import TinySentenceCompressor

MAGIC = b'BLCP\x01'


def _flatten_matrix(matrix: List[List[float]]) -> List[float]:
    out: List[float] = []
    for row in matrix:
        out.extend(float(v) for v in row)
    return out


def _reshape(flat: List[float], rows: int, cols: int) -> List[List[float]]:
    out: List[List[float]] = []
    idx = 0
    for _ in range(rows):
        out.append(list(flat[idx:idx+cols]))
        idx += cols
    return out


def save_compressor(path: str | Path, model: TinySentenceCompressor) -> None:
    path = Path(path)
    vocab_tokens = [tok for tok, _ in sorted(model.vocab.items(), key=lambda kv: kv[1])]
    metadata = {
        'model_type': 'tiny_sentence_compressor',
        'vocab_tokens': vocab_tokens,
        'embed_dim': model.embed_dim,
        'hidden1': model.hidden1,
        'hidden2': model.hidden2,
        'weight_order': ['E', 'W1', 'b1', 'W2', 'b2', 'W3', 'b3'],
    }
    meta_bytes = json.dumps(metadata, separators=(',', ':')).encode('utf-8')
    weights: List[float] = []
    weights.extend(_flatten_matrix(model.E))
    weights.extend(_flatten_matrix(model.W1))
    weights.extend(model.b1)
    weights.extend(_flatten_matrix(model.W2))
    weights.extend(model.b2)
    weights.extend(model.W3)
    weights.append(model.b3)
    with path.open('wb') as f:
        f.write(MAGIC)
        f.write(struct.pack('<I', len(meta_bytes)))
        f.write(meta_bytes)
        f.write(struct.pack(f'<{len(weights)}f', *weights))


def load_compressor(path: str | Path) -> TinySentenceCompressor:
    path = Path(path)
    with path.open('rb') as f:
        magic = f.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError('bad compressor magic')
        (meta_len,) = struct.unpack('<I', f.read(4))
        metadata = json.loads(f.read(meta_len).decode('utf-8'))
        raw = f.read()
    if metadata.get('model_type') != 'tiny_sentence_compressor':
        raise ValueError('unsupported compressor type')
    vocab_tokens = list(metadata['vocab_tokens'])
    vocab = {str(tok): i for i, tok in enumerate(vocab_tokens)}
    model = TinySentenceCompressor(vocab=vocab, embed_dim=int(metadata['embed_dim']), hidden1=int(metadata['hidden1']), hidden2=int(metadata['hidden2']), seed=0)
    float_count = len(raw) // 4
    floats = list(struct.unpack(f'<{float_count}f', raw))
    offset = 0
    def take(n: int) -> List[float]:
        nonlocal offset
        chunk = floats[offset:offset+n]
        if len(chunk) != n:
            raise ValueError('truncated compressor weights')
        offset += n
        return chunk
    vs = len(vocab)
    ed = model.embed_dim
    h1 = model.hidden1
    h2 = model.hidden2
    model.E = _reshape(take(vs * ed), vs, ed)
    model.W1 = _reshape(take(model.input_dim * h1), model.input_dim, h1)
    model.b1 = take(h1)
    model.W2 = _reshape(take(h1 * h2), h1, h2)
    model.b2 = take(h2)
    model.W3 = take(h2)
    model.b3 = take(1)[0]
    return model
