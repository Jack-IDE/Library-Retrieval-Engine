from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Dict, List

from .ranker_model import TinyRelevanceRanker

MAGIC = b'BRRK\x01'


def load_vocab_file(path: str | Path) -> Dict[str, int]:
    """Load a vocab.json produced by build_vocab.py."""
    path = Path(path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError(f'vocab file must be a JSON object: {path}')
    return {str(k): int(v) for k, v in raw.items()}


def vocab_fingerprint(vocab: Dict[str, int]) -> str:
    """16-char SHA-256 prefix over the token list ordered by ID.

    Stored in .brrk metadata at save time.  Call check_vocab_fingerprint()
    at load time to catch ranker/vocab mismatches before they silently
    produce bad scores.
    """
    tokens = [tok for tok, _ in sorted(vocab.items(), key=lambda kv: kv[1])]
    blob = json.dumps(tokens, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()[:16]


def check_vocab_fingerprint(model_path: Path, vocab: Dict[str, int]) -> None:
    """Raise ValueError if vocab does not match what the ranker was trained on.

    Call this after load_ranker() when you are using a fixed external vocab
    file.  Safe to skip if you are loading and immediately re-saving.
    """
    with model_path.open('rb') as f:
        magic = f.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError(f'bad ranker magic: {model_path}')
        (meta_len,) = struct.unpack('<I', f.read(4))
        metadata = json.loads(f.read(meta_len).decode('utf-8'))
    stored = metadata.get('vocab_fingerprint', '')
    if not stored:
        return  # old file saved before fingerprinting — skip silently
    expected = vocab_fingerprint(vocab)
    if stored != expected:
        raise ValueError(
            f'vocab mismatch for {model_path}:\n'
            f'  ranker trained on vocab fingerprint: {stored}\n'
            f'  provided vocab fingerprint:          {expected}\n'
            f'  Re-train the ranker against the current vocab.json.'
        )


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


def save_ranker(path: str | Path, model: TinyRelevanceRanker) -> None:
    path = Path(path)
    vocab_tokens = [tok for tok, _ in sorted(model.vocab.items(), key=lambda kv: kv[1])]
    arch = getattr(model, 'arch', 'mlp')
    if arch == 'linear':
        metadata = {
            'model_type': 'tiny_relevance_ranker',
            'arch': 'linear',
            'vocab_tokens': vocab_tokens,
            'vocab_fingerprint': vocab_fingerprint(model.vocab),
            'embed_dim': model.embed_dim,
            'hidden1': model.hidden1,
            'hidden2': model.hidden2,
            'weight_order': ['E', 'W0', 'b0'],
        }
        weights: List[float] = []
        weights.extend(_flatten_matrix(model.E))
        weights.extend(model.W0)
        weights.append(model.b0)
    else:
        metadata = {
            'model_type': 'tiny_relevance_ranker',
            'arch': 'mlp',
            'vocab_tokens': vocab_tokens,
            'vocab_fingerprint': vocab_fingerprint(model.vocab),
            'embed_dim': model.embed_dim,
            'hidden1': model.hidden1,
            'hidden2': model.hidden2,
            'weight_order': ['E', 'W1', 'b1', 'W2', 'b2', 'W3', 'b3'],
        }
        weights = []
        weights.extend(_flatten_matrix(model.E))
        weights.extend(_flatten_matrix(model.W1))
        weights.extend(model.b1)
        weights.extend(_flatten_matrix(model.W2))
        weights.extend(model.b2)
        weights.extend(model.W3)
        weights.append(model.b3)
    meta_bytes = json.dumps(metadata, separators=(',', ':')).encode('utf-8')
    with path.open('wb') as f:
        f.write(MAGIC)
        f.write(struct.pack('<I', len(meta_bytes)))
        f.write(meta_bytes)
        f.write(struct.pack(f'<{len(weights)}f', *weights))


def load_ranker(path: str | Path) -> TinyRelevanceRanker:
    path = Path(path)
    with path.open('rb') as f:
        magic = f.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError('bad ranker magic')
        (meta_len,) = struct.unpack('<I', f.read(4))
        metadata = json.loads(f.read(meta_len).decode('utf-8'))
        raw = f.read()
    if metadata.get('model_type') != 'tiny_relevance_ranker':
        raise ValueError('unsupported model type')
    vocab_tokens = list(metadata['vocab_tokens'])
    vocab = {str(tok): i for i, tok in enumerate(vocab_tokens)}
    arch = metadata.get('arch', 'mlp')
    model = TinyRelevanceRanker(
        vocab=vocab,
        embed_dim=int(metadata['embed_dim']),
        hidden1=int(metadata.get('hidden1', 48)),
        hidden2=int(metadata.get('hidden2', 24)),
        seed=0,
        arch=arch,
    )
    float_count = len(raw) // 4
    floats = list(struct.unpack(f'<{float_count}f', raw))
    offset = 0

    def take(n: int) -> List[float]:
        nonlocal offset
        chunk = floats[offset:offset+n]
        if len(chunk) != n:
            raise ValueError('truncated ranker weights')
        offset += n
        return chunk

    vs = len(vocab)
    ed = model.embed_dim
    model.E = _reshape(take(vs * ed), vs, ed)
    if arch == 'linear':
        model.W0 = take(model.input_dim)
        model.b0 = take(1)[0]
    else:
        h1 = model.hidden1
        h2 = model.hidden2
        model.W1 = _reshape(take(model.input_dim * h1), model.input_dim, h1)
        model.b1 = take(h1)
        model.W2 = _reshape(take(h1 * h2), h1, h2)
        model.b2 = take(h2)
        model.W3 = take(h2)
        model.b3 = take(1)[0]
    return model
