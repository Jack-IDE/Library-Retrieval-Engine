from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Sequence

from .text_utils import binary_cross_entropy, sigmoid, tokenize


@dataclass
class PairFeatures:
    q: List[float]
    c: List[float]
    g: List[float]
    x: List[float]
    q_ids: List[int]
    c_ids: List[int]
    g_ids: List[int]
    h1_pre: List[float]
    h1_act: List[float]
    h2_pre: List[float]
    h2_act: List[float]
    logit: float
    prob: float


class TinyRelevanceRanker:
    """
    Trainable reranker for (query, chunk, guidance) -> probability of relevance.

    arch='mlp'
        shared token embeddings -> [q, c, |q-c|, q*c, g] -> two hidden ReLU layers -> sigmoid

    arch='linear'
        shared token embeddings -> [q, c, |q-c|, q*c, g] -> linear sigmoid probe

    The linear path is substantially cheaper and is the default fast path for the ranker.
    """

    def __init__(self, vocab: Dict[str, int], embed_dim: int = 24, hidden1: int = 48, hidden2: int = 24, seed: int = 42, arch: str = 'mlp'):
        self.vocab = dict(vocab)
        self.reverse_vocab = {v: k for k, v in vocab.items()}
        self.vocab_size = len(vocab)
        self.embed_dim = embed_dim
        self.arch = 'linear' if str(arch).lower() == 'linear' else 'mlp'
        self.hidden1 = int(hidden1) if self.arch == 'mlp' else 0
        self.hidden2 = int(hidden2) if self.arch == 'mlp' else 0
        self.input_dim = embed_dim * 5
        self.rng = random.Random(seed)
        self.E = self._init_matrix(self.vocab_size, embed_dim, 0.12)
        if self.arch == 'linear':
            self.W0 = [self.rng.uniform(-0.12, 0.12) for _ in range(self.input_dim)]
            self.b0 = 0.0
            self.W1 = []
            self.b1 = []
            self.W2 = []
            self.b2 = []
            self.W3 = []
            self.b3 = 0.0
        else:
            self.W0 = []
            self.b0 = 0.0
            self.W1 = self._init_matrix(self.input_dim, self.hidden1, 0.12)
            self.b1 = [0.0] * self.hidden1
            self.W2 = self._init_matrix(self.hidden1, self.hidden2, 0.12)
            self.b2 = [0.0] * self.hidden2
            self.W3 = [self.rng.uniform(-0.12, 0.12) for _ in range(self.hidden2)]
            self.b3 = 0.0

    def _init_matrix(self, rows: int, cols: int, scale: float) -> List[List[float]]:
        return [[self.rng.uniform(-scale, scale) for _ in range(cols)] for _ in range(rows)]

    def zero_grads(self):
        if self.arch == 'linear':
            return {
                'E': {},
                'W0': [0.0 for _ in range(self.input_dim)],
                'b0': 0.0,
            }
        return {
            'E': {},
            'W1': [[0.0 for _ in range(self.hidden1)] for _ in range(self.input_dim)],
            'b1': [0.0 for _ in range(self.hidden1)],
            'W2': [[0.0 for _ in range(self.hidden2)] for _ in range(self.hidden1)],
            'b2': [0.0 for _ in range(self.hidden2)],
            'W3': [0.0 for _ in range(self.hidden2)],
            'b3': 0.0,
        }

    def text_to_ids(self, text: str) -> List[int]:
        return [self.vocab[t] for t in tokenize(text) if t in self.vocab]

    def _avg_embed_from_ids(self, ids: Sequence[int]) -> List[float]:
        if not ids:
            return [0.0] * self.embed_dim
        out = [0.0] * self.embed_dim
        for idx in ids:
            row = self.E[idx]
            for i in range(self.embed_dim):
                out[i] += row[i]
        inv = 1.0 / len(ids)
        for i in range(self.embed_dim):
            out[i] *= inv
        return out

    def _avg_embed(self, text: str) -> tuple[List[float], List[int]]:
        ids = self.text_to_ids(text)
        return self._avg_embed_from_ids(ids), ids

    def featurize_from_ids(self, query_ids: Sequence[int], chunk_ids: Sequence[int], guidance_ids: Sequence[int] | None = None) -> tuple[List[float], List[float], List[float], List[float], Dict[str, List[int]]]:
        q_ids = list(query_ids)
        c_ids = list(chunk_ids)
        g_ids = list(guidance_ids or [])
        q = self._avg_embed_from_ids(q_ids)
        c = self._avg_embed_from_ids(c_ids)
        g = self._avg_embed_from_ids(g_ids)
        abs_diff = [abs(a - b) for a, b in zip(q, c)]
        prod = [a * b for a, b in zip(q, c)]
        x = q + c + abs_diff + prod + g
        return q, c, g, x, {'q_ids': q_ids, 'c_ids': c_ids, 'g_ids': g_ids}

    def featurize(self, query: str, chunk: str, guidance_text: str = '') -> tuple[List[float], List[float], List[float], List[float], Dict[str, List[int]]]:
        return self.featurize_from_ids(self.text_to_ids(query), self.text_to_ids(chunk), self.text_to_ids(guidance_text))

    def _backprop_embeddings(self, result: PairFeatures, dx: Sequence[float], grads) -> None:
        e = self.embed_dim
        dq = [0.0] * e
        dc = [0.0] * e
        dg = [0.0] * e

        direct_q = dx[0:e]
        direct_c = dx[e:2 * e]
        abs_diff_dx = dx[2 * e:3 * e]
        prod_dx = dx[3 * e:4 * e]
        direct_g = dx[4 * e:5 * e]

        for i in range(e):
            dq[i] += direct_q[i]
            dc[i] += direct_c[i]
            dg[i] += direct_g[i]

            diff = result.q[i] - result.c[i]
            if diff > 0.0:
                sign = 1.0
            elif diff < 0.0:
                sign = -1.0
            else:
                sign = 0.0
            dq[i] += abs_diff_dx[i] * sign
            dc[i] -= abs_diff_dx[i] * sign

            dq[i] += prod_dx[i] * result.c[i]
            dc[i] += prod_dx[i] * result.q[i]

        token_map = {
            'q_ids': result.q_ids,
            'c_ids': result.c_ids,
            'g_ids': result.g_ids,
        }
        grad_map = {
            'q_ids': dq,
            'c_ids': dc,
            'g_ids': dg,
        }
        for key, grad_vec in grad_map.items():
            token_ids = token_map[key]
            if not token_ids:
                continue
            inv = 1.0 / len(token_ids)
            for tok_id in token_ids:
                row = grads['E'].setdefault(tok_id, [0.0] * self.embed_dim)
                for d in range(self.embed_dim):
                    row[d] += grad_vec[d] * inv

    def forward_from_ids(self, query_ids: Sequence[int], chunk_ids: Sequence[int], guidance_ids: Sequence[int] | None = None) -> PairFeatures:
        q, c, g, x, ids = self.featurize_from_ids(query_ids, chunk_ids, guidance_ids)
        if self.arch == 'linear':
            logit = self.b0
            for i in range(self.input_dim):
                logit += x[i] * self.W0[i]
            prob = sigmoid(logit)
            return PairFeatures(
                q=q,
                c=c,
                g=g,
                x=x,
                q_ids=ids['q_ids'],
                c_ids=ids['c_ids'],
                g_ids=ids['g_ids'],
                h1_pre=[],
                h1_act=[],
                h2_pre=[],
                h2_act=[],
                logit=logit,
                prob=prob,
            )

        h1_pre = [0.0] * self.hidden1
        for j in range(self.hidden1):
            acc = self.b1[j]
            for i in range(self.input_dim):
                acc += x[i] * self.W1[i][j]
            h1_pre[j] = acc
        h1_act = [v if v > 0.0 else 0.0 for v in h1_pre]

        h2_pre = [0.0] * self.hidden2
        for j in range(self.hidden2):
            acc = self.b2[j]
            for i in range(self.hidden1):
                acc += h1_act[i] * self.W2[i][j]
            h2_pre[j] = acc
        h2_act = [v if v > 0.0 else 0.0 for v in h2_pre]

        logit = self.b3
        for i in range(self.hidden2):
            logit += h2_act[i] * self.W3[i]
        prob = sigmoid(logit)
        return PairFeatures(
            q=q,
            c=c,
            g=g,
            x=x,
            q_ids=ids['q_ids'],
            c_ids=ids['c_ids'],
            g_ids=ids['g_ids'],
            h1_pre=h1_pre,
            h1_act=h1_act,
            h2_pre=h2_pre,
            h2_act=h2_act,
            logit=logit,
            prob=prob,
        )

    def forward(self, query: str, chunk: str, guidance_text: str = '') -> PairFeatures:
        return self.forward_from_ids(self.text_to_ids(query), self.text_to_ids(chunk), self.text_to_ids(guidance_text))

    def accumulate_gradients_from_ids(self, query_ids: Sequence[int], chunk_ids: Sequence[int], guidance_ids: Sequence[int] | None, target: int, grads, sample_weight: float = 1.0) -> float:
        result = self.forward_from_ids(query_ids, chunk_ids, guidance_ids)
        x = result.x
        loss = binary_cross_entropy(result.prob, target) * sample_weight
        dlogit = (result.prob - float(target)) * sample_weight

        if self.arch == 'linear':
            dx = [0.0] * self.input_dim
            for i in range(self.input_dim):
                grads['W0'][i] += x[i] * dlogit
                dx[i] = self.W0[i] * dlogit
            grads['b0'] += dlogit
            self._backprop_embeddings(result, dx, grads)
            return loss

        for i in range(self.hidden2):
            grads['W3'][i] += result.h2_act[i] * dlogit
        grads['b3'] += dlogit
        d_h2 = [self.W3[i] * dlogit for i in range(self.hidden2)]

        for i in range(self.hidden2):
            if result.h2_pre[i] <= 0.0:
                d_h2[i] = 0.0

        d_h1 = [0.0] * self.hidden1
        for i in range(self.hidden1):
            for j in range(self.hidden2):
                grads['W2'][i][j] += result.h1_act[i] * d_h2[j]
                d_h1[i] += self.W2[i][j] * d_h2[j]
        for j in range(self.hidden2):
            grads['b2'][j] += d_h2[j]

        for i in range(self.hidden1):
            if result.h1_pre[i] <= 0.0:
                d_h1[i] = 0.0

        dx = [0.0] * self.input_dim
        for i in range(self.input_dim):
            for j in range(self.hidden1):
                grads['W1'][i][j] += x[i] * d_h1[j]
                dx[i] += self.W1[i][j] * d_h1[j]
        for j in range(self.hidden1):
            grads['b1'][j] += d_h1[j]

        self._backprop_embeddings(result, dx, grads)
        return loss

    def accumulate_gradients(self, query: str, chunk: str, guidance_text: str, target: int, grads, sample_weight: float = 1.0) -> float:
        return self.accumulate_gradients_from_ids(self.text_to_ids(query), self.text_to_ids(chunk), self.text_to_ids(guidance_text), target, grads, sample_weight=sample_weight)

    def apply_gradients(self, grads, lr: float, batch_scale: float) -> None:
        scale = lr * batch_scale
        for tok_id, row_grad in grads['E'].items():
            row = self.E[tok_id]
            for d in range(self.embed_dim):
                row[d] -= scale * row_grad[d]
        if self.arch == 'linear':
            for i in range(self.input_dim):
                self.W0[i] -= scale * grads['W0'][i]
            self.b0 -= scale * grads['b0']
            return
        for i in range(self.input_dim):
            for j in range(self.hidden1):
                self.W1[i][j] -= scale * grads['W1'][i][j]
        for j in range(self.hidden1):
            self.b1[j] -= scale * grads['b1'][j]
        for i in range(self.hidden1):
            for j in range(self.hidden2):
                self.W2[i][j] -= scale * grads['W2'][i][j]
        for j in range(self.hidden2):
            self.b2[j] -= scale * grads['b2'][j]
        for i in range(self.hidden2):
            self.W3[i] -= scale * grads['W3'][i]
        self.b3 -= scale * grads['b3']

    def score(self, query: str, chunk: str, guidance_text: str = '') -> float:
        return self.forward(query, chunk, guidance_text).prob

    def score_from_ids(self, query_ids: Sequence[int], chunk_ids: Sequence[int], guidance_ids: Sequence[int] | None = None) -> float:
        return self.forward_from_ids(query_ids, chunk_ids, guidance_ids).prob


def build_vocab_from_chunks(texts: Sequence[str], min_freq: int = 1) -> Dict[str, int]:
    counts: Dict[str, int] = {'<pad>': 10**9}
    for text in texts:
        for tok in tokenize(text):
            counts[tok] = counts.get(tok, 0) + 1
    vocab: Dict[str, int] = {'<pad>': 0}
    for tok, count in sorted(counts.items()):
        if tok == '<pad>':
            continue
        if count >= min_freq:
            vocab[tok] = len(vocab)
    return vocab
