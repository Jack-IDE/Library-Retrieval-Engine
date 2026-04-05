from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from .chunking import Chunk
from .text_utils import STOPWORDS, tokenize
from .vector_store import hashed_text_vector


@dataclass
class RetrievedChunk:
    chunk: Chunk
    lexical_score: float
    vector_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0


GUIDANCE_KEYS = ('task', 'domain', 'prefer_sources', 'avoid_sources', 'required_terms', 'max_passes')


def _is_normalized_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) and item == item.lower() for item in value)
    )


def _looks_normalized_guidance(guidance: Any) -> bool:
    if not isinstance(guidance, dict):
        return False
    if tuple(guidance.keys()) != GUIDANCE_KEYS:
        return False
    if not isinstance(guidance.get('task'), str) or guidance['task'] != guidance['task'].strip():
        return False
    if not isinstance(guidance.get('domain'), str) or guidance['domain'] != guidance['domain'].strip():
        return False
    if not _is_normalized_string_list(guidance.get('prefer_sources')):
        return False
    if not _is_normalized_string_list(guidance.get('avoid_sources')):
        return False
    if not _is_normalized_string_list(guidance.get('required_terms')):
        return False
    if not isinstance(guidance.get('max_passes'), int):
        return False
    return True


def parse_guidance(guidance: dict | None) -> dict:
    if _looks_normalized_guidance(guidance):
        return guidance
    g = guidance or {}
    return {
        'task': str(g.get('task', '')).strip(),
        'domain': str(g.get('domain', '')).strip(),
        'prefer_sources': [str(x).lower() for x in g.get('prefer_sources', [])],
        'avoid_sources': [str(x).lower() for x in g.get('avoid_sources', [])],
        'required_terms': [str(x).lower() for x in g.get('required_terms', [])],
        'max_passes': int(g.get('max_passes', 1)),
    }


def build_query_text(query: str, guidance: dict | None) -> str:
    g = parse_guidance(guidance)
    extra = ' '.join([g['task'], g['domain']] + g['required_terms'])
    return (query + ' ' + extra).strip()


def build_query_text_from_parsed(query: str, g: dict) -> str:
    extra = ' '.join([g['task'], g['domain']] + g['required_terms'])
    return (query + ' ' + extra).strip()


def _query_terms_from_parsed(query: str, g: dict) -> List[str]:
    out: List[str] = []
    for tok in tokenize(build_query_text_from_parsed(query, g)):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        out.append(tok)
    for tok in g['required_terms']:
        tok = tok.strip().lower()
        if tok and tok not in out:
            out.append(tok)
    return out


def _query_terms(query: str, guidance: dict | None) -> List[str]:
    return _query_terms_from_parsed(query, parse_guidance(guidance))


def _lexical_score_from_cache(
    chunk: Chunk,
    chunk_idx: int,
    q_tokens: Sequence[str],
    idf: Dict[str, float],
    g: dict,
    retrieval_artifacts: Dict,
    base_score: float,
) -> float:
    runtime = retrieval_artifacts.setdefault('_runtime', {})
    chunk_term_sets = runtime.get('chunk_term_sets')
    keyword_sets = runtime.get('keyword_sets')
    if chunk_term_sets is None:
        chunk_term_sets = [set(row) for row in retrieval_artifacts.get('chunk_term_lists', [])]
        runtime['chunk_term_sets'] = chunk_term_sets
    if keyword_sets is None:
        keyword_sets = [set(row) for row in retrieval_artifacts.get('keyword_lists', [])]
        runtime['keyword_sets'] = keyword_sets
    term_set = chunk_term_sets[chunk_idx] if chunk_idx < len(chunk_term_sets) else set()
    kw_set = keyword_sets[chunk_idx] if chunk_idx < len(keyword_sets) else set()
    heading_blobs = retrieval_artifacts.get('heading_blobs', [])
    heading_text = heading_blobs[chunk_idx] if chunk_idx < len(heading_blobs) else ''

    score = base_score
    score += 0.22 * sum(1 for tok in q_tokens if tok in kw_set)
    score += 0.38 * sum(1 for tok in q_tokens if tok in heading_text)
    if chunk.chunk_kind == 'code':
        code_terms = {'def', 'class', 'return', 'function', 'export', 'import'}
        code_overlap = sum(1 for tok in q_tokens if tok in code_terms or tok == chunk.symbol_name.lower())
        score += 0.15 * code_overlap
    if g['prefer_sources'] and chunk.source_type in g['prefer_sources']:
        score *= 1.20
    if g['avoid_sources'] and chunk.source_type in g['avoid_sources']:
        score *= 0.70
    req = g['required_terms']
    if req:
        matched = sum(1 for t in req if t in term_set or t in heading_text)
        if matched == 0:
            score *= 0.45
        else:
            score *= 1.0 + 0.12 * matched
    return score


def lexical_score_from_parsed(query: str, chunk: Chunk, idf: Dict[str, float], g: dict) -> float:
    q_tokens = [t for t in tokenize(build_query_text_from_parsed(query, g)) if t not in STOPWORDS]
    if not q_tokens:
        return 0.0
    c_tokens = tokenize(' '.join([chunk.text, chunk.heading, chunk.source_path, chunk.symbol_name]))
    c_set = set(c_tokens)
    score = 0.0
    for tok in q_tokens:
        if tok in c_set:
            score += idf.get(tok, 1.0)
    score += 0.22 * sum(1 for tok in q_tokens if tok in chunk.keyword_list)
    heading_text = ' '.join([chunk.heading, chunk.source_path, chunk.symbol_name]).lower()
    score += 0.38 * sum(1 for tok in q_tokens if tok in heading_text)
    if chunk.chunk_kind == 'code':
        code_terms = {'def', 'class', 'return', 'function', 'export', 'import'}
        code_overlap = sum(1 for tok in q_tokens if tok in code_terms or tok == chunk.symbol_name.lower())
        score += 0.15 * code_overlap
    if g['prefer_sources'] and chunk.source_type in g['prefer_sources']:
        score *= 1.20
    if g['avoid_sources'] and chunk.source_type in g['avoid_sources']:
        score *= 0.70
    req = g['required_terms']
    if req:
        matched = sum(1 for t in req if t in c_set)
        if matched == 0:
            score *= 0.45
        else:
            score *= 1.0 + 0.12 * matched
    return score


def lexical_score(query: str, chunk: Chunk, idf: Dict[str, float], guidance: dict | None = None) -> float:
    return lexical_score_from_parsed(query, chunk, idf, parse_guidance(guidance))


def _retrieve_with_artifacts(
    query: str,
    chunks: Sequence[Chunk],
    idf: Dict[str, float],
    top_k: int,
    guidance: dict | None,
    chunk_vectors: Sequence[Sequence[float]] | None,
    vector_dim: int,
    retrieval_artifacts: Dict,
) -> List[RetrievedChunk]:
    g = parse_guidance(guidance)
    q_tokens = _query_terms_from_parsed(query, g)
    if not q_tokens:
        return []

    postings = retrieval_artifacts.get('postings', {})
    chunk_lengths = retrieval_artifacts.get('chunk_lengths', [])
    avg_chunk_length = float(retrieval_artifacts.get('avg_chunk_length', 1.0) or 1.0)

    k1 = 1.2
    bm25_b = 0.75
    lexical_candidates: Dict[int, float] = {}
    for tok in q_tokens:
        tok_postings = postings.get(tok)
        if not tok_postings:
            continue
        tok_idf = idf.get(tok, 1.0)
        for chunk_idx, tf in tok_postings:
            length = chunk_lengths[chunk_idx] if chunk_idx < len(chunk_lengths) else 0
            denom = tf + k1 * (1.0 - bm25_b + bm25_b * (length / max(1e-9, avg_chunk_length)))
            score = tok_idf * ((tf * (k1 + 1.0)) / max(1e-9, denom))
            lexical_candidates[chunk_idx] = lexical_candidates.get(chunk_idx, 0.0) + score

    if not lexical_candidates:
        return []

    lexical_limit = min(max(top_k * 12, 120), max(len(lexical_candidates), top_k))
    ranked_candidates = sorted(lexical_candidates.items(), key=lambda kv: kv[1], reverse=True)[:lexical_limit]

    query_text = build_query_text_from_parsed(query, g)
    qv = hashed_text_vector(query_text, idf, dim=vector_dim) if chunk_vectors is not None else None
    vector_limit = min(len(ranked_candidates), max(top_k * 4, 48))
    scored: List[RetrievedChunk] = []
    for rank, (idx, bm25_score) in enumerate(ranked_candidates):
        chunk = chunks[idx]
        lex = _lexical_score_from_cache(chunk, idx, q_tokens, idf, g, retrieval_artifacts, bm25_score)
        vec = 0.0
        if qv is not None and rank < vector_limit and idx < len(chunk_vectors):
            row = chunk_vectors[idx]
            vec = sum(q_weight * row_weight for q_weight, row_weight in zip(qv, row))
            vec = max(-1.0, min(1.0, vec))
        combined = lex + max(0.0, vec) * 3.0
        scored.append(RetrievedChunk(chunk=chunk, lexical_score=lex, vector_score=vec, final_score=combined))

    scored.sort(key=lambda r: r.final_score, reverse=True)
    return [r for r in scored[:top_k] if r.final_score > 0.0]


def retrieve(
    query: str,
    chunks: Sequence[Chunk],
    idf: Dict[str, float],
    top_k: int = 20,
    guidance: dict | None = None,
    chunk_vectors: Sequence[Sequence[float]] | None = None,
    vector_dim: int = 64,
    retrieval_artifacts: Dict | None = None,
) -> List[RetrievedChunk]:
    if retrieval_artifacts:
        return _retrieve_with_artifacts(query, chunks, idf, top_k, guidance, chunk_vectors, vector_dim, retrieval_artifacts)

    g = parse_guidance(guidance)
    query_text = build_query_text_from_parsed(query, g)
    qv = hashed_text_vector(query_text, idf, dim=vector_dim) if chunk_vectors is not None else None
    scored: List[RetrievedChunk] = []
    for idx, chunk in enumerate(chunks):
        lex = lexical_score_from_parsed(query, chunk, idf, g)
        vec = 0.0
        if qv is not None and idx < len(chunk_vectors):
            row = chunk_vectors[idx]
            vec = sum(q_weight * row_weight for q_weight, row_weight in zip(qv, row))
            vec = max(-1.0, min(1.0, vec))
        combined = lex + max(0.0, vec) * 3.0
        item = RetrievedChunk(chunk=chunk, lexical_score=lex, vector_score=vec, final_score=combined)
        scored.append(item)
    scored.sort(key=lambda r: r.final_score, reverse=True)
    return [r for r in scored[:top_k] if r.final_score > 0.0]
