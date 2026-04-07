from __future__ import annotations

import math
import re
from typing import Dict, List, Sequence

TOKEN_RE = re.compile(r"[a-z0-9_']+")
STOPWORDS = {
    'the','a','an','and','or','to','of','in','on','for','with','is','are','was','were','be','by','it',
    'this','that','as','at','from','into','if','then','than','can','will','would','should','could','we',
    'you','they','he','she','them','our','your','their','but','not','do','does','did','so','such','via'
}


def normalize_text(text: str) -> str:
    return text.replace('\r\n', '\n').replace('\r', '\n')


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


def keywords(text: str, limit: int = 12) -> List[str]:
    counts: Dict[str, int] = {}
    for tok in tokenize(text):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:limit]]


def sentence_split(text: str) -> List[str]:
    text = normalize_text(text)
    raw = re.split(r'(?<=[.!?])\s+|\n{2,}', text)
    return [s.strip() for s in raw if s.strip()]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError('vector length mismatch')
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def binary_cross_entropy(prob: float, target: int) -> float:
    p = min(max(prob, 1e-9), 1.0 - 1e-9)
    if target == 1:
        return -math.log(p)
    return -math.log(1.0 - p)


def stable_shuffle(items: Sequence, seed: int) -> List:
    import random
    data = list(items)
    rng = random.Random(seed)
    rng.shuffle(data)
    return data
