from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Optional, Sequence

DECISION_BM25 = 'bm25'
DECISION_VECTOR = 'vector'
DECISION_HYBRID = 'hybrid'


@dataclass(frozen=True)
class ReasoningTrace:
    query_id: str
    doc_id: str
    bm25_raw: float
    vector_raw: float
    bm25_weighted: float
    vector_weighted: float
    final_score: float
    decision_path: str
    dominant_feature: Optional[int]
    dominant_contribution: float
    top_feature_indices: list[int]
    top_feature_contributions: list[float]
    timestamp_ms: int


def stable_query_id(query: str, guidance: dict | None = None) -> str:
    payload = {'query': query, 'guidance': guidance or {}}
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.blake2b(raw, digest_size=8).hexdigest()


def dot_product_reasoned(
    query_vec: Sequence[float],
    doc_vec: Sequence[float],
    top_n: int = 3,
) -> tuple[float, Optional[int], float, list[int], list[float]]:
    if len(query_vec) != len(doc_vec):
        raise ValueError(
            f'vector length mismatch: len(query_vec)={len(query_vec)} != len(doc_vec)={len(doc_vec)}'
        )
    total = 0.0
    best_index: Optional[int] = None
    best_contribution = float('-inf')
    scored_dims: list[tuple[float, int]] = []
    for i, (qv, dv) in enumerate(zip(query_vec, doc_vec)):
        contribution = float(qv) * float(dv)
        total += contribution
        scored_dims.append((contribution, i))
        if contribution > best_contribution:
            best_contribution = contribution
            best_index = i
    if best_index is None:
        return 0.0, None, 0.0, [], []
    scored_dims.sort(key=lambda item: item[0], reverse=True)
    top = [(i, c) for c, i in scored_dims[:max(1, top_n)] if c != 0.0]
    return total, best_index, float(best_contribution), [i for i, _ in top], [float(c) for _, c in top]


def choose_decision_path(
    bm25_weighted: float,
    vector_weighted: float,
    dominance_ratio: float = 1.5,
) -> str:
    if bm25_weighted > vector_weighted * dominance_ratio:
        return DECISION_BM25
    if vector_weighted > bm25_weighted * dominance_ratio:
        return DECISION_VECTOR
    return DECISION_HYBRID


def build_reasoning_trace(
    *,
    query_id: str,
    doc_id: str,
    bm25_raw: float,
    vector_raw: float,
    dominant_feature: Optional[int],
    dominant_contribution: float,
    top_feature_indices: Sequence[int] | None = None,
    top_feature_contributions: Sequence[float] | None = None,
    bm25_weight: float = 1.0,
    vector_weight: float = 3.0,
    dominance_ratio: float = 1.5,
    timestamp_ms: Optional[int] = None,
) -> ReasoningTrace:
    bm25_weighted = float(bm25_raw) * float(bm25_weight)
    vector_weighted = max(0.0, float(vector_raw)) * float(vector_weight)
    final_score = bm25_weighted + vector_weighted
    decision_path = choose_decision_path(
        bm25_weighted,
        vector_weighted,
        dominance_ratio=dominance_ratio,
    )
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    return ReasoningTrace(
        query_id=str(query_id),
        doc_id=str(doc_id),
        bm25_raw=float(bm25_raw),
        vector_raw=float(vector_raw),
        bm25_weighted=float(bm25_weighted),
        vector_weighted=float(vector_weighted),
        final_score=float(final_score),
        decision_path=decision_path,
        dominant_feature=dominant_feature,
        dominant_contribution=float(dominant_contribution),
        top_feature_indices=list(top_feature_indices or []),
        top_feature_contributions=[float(v) for v in (top_feature_contributions or [])],
        timestamp_ms=int(timestamp_ms),
    )


def trace_to_dict(trace: ReasoningTrace) -> dict[str, Any]:
    return asdict(trace)


def trace_to_json_line(trace: ReasoningTrace) -> str:
    return json.dumps(trace_to_dict(trace), sort_keys=True, separators=(',', ':'))


def append_traces_jsonl(traces: Iterable[ReasoningTrace], path: str) -> None:
    with open(path, 'a', encoding='utf-8') as f:
        for trace in traces:
            f.write(trace_to_json_line(trace))
            f.write('\n')


def format_reasoning_trace(trace: ReasoningTrace) -> str:
    lines = [
        f'    reasoning.query_id={trace.query_id}',
        f'    reasoning.decision={trace.decision_path}',
        f'    reasoning.bm25_raw={trace.bm25_raw:.3f}',
        f'    reasoning.vector_raw={trace.vector_raw:.3f}',
        f'    reasoning.bm25_weighted={trace.bm25_weighted:.3f}',
        f'    reasoning.vector_weighted={trace.vector_weighted:.3f}',
        f'    reasoning.final_score={trace.final_score:.3f}',
        f'    reasoning.dominant_feature={trace.dominant_feature}',
        f'    reasoning.dominant_contribution={trace.dominant_contribution:.3f}',
    ]
    if trace.top_feature_indices:
        pairs = ', '.join(
            f'{idx}:{contrib:.3f}'
            for idx, contrib in zip(trace.top_feature_indices, trace.top_feature_contributions)
        )
        lines.append(f'    reasoning.top_features={pairs}')
    return '\n'.join(lines)
