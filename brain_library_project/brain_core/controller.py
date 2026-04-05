from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Sequence

from .chunking import Chunk
from .compressor_model import TinySentenceCompressor
from .ranker_model import TinyRelevanceRanker
from .retrieval import RetrievedChunk, build_query_text, parse_guidance, retrieve
from .text_utils import keywords, sentence_split


@dataclass
class PassRecord:
    pass_index: int
    current_query: str
    retrieved_count: int
    top_chunk_ids: List[str]
    new_terms: List[str]
    covered_required_terms: List[str]
    uncovered_required_terms: List[str]
    source_counts_snapshot: Dict[str, int]
    working_memory: str
    confidence: float
    stop_reason: str = ''


@dataclass
class ControllerState:
    original_query: str
    guidance: dict
    guidance_text: str
    current_query: str
    max_passes: int
    expanded_terms: List[str] = field(default_factory=list)
    seen_chunk_ids: List[str] = field(default_factory=list)
    covered_required_terms: List[str] = field(default_factory=list)
    source_counts: Dict[str, int] = field(default_factory=dict)
    working_memory_history: List[str] = field(default_factory=list)
    pass_records: List[PassRecord] = field(default_factory=list)
    final_confidence: float = 0.0
    stop_reason: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QueryResult:
    answer: str
    working_memory: str
    top_results: List[RetrievedChunk]
    state: ControllerState


def compress_chunks(
    query: str,
    chunks: Sequence[RetrievedChunk],
    guidance_text: str = '',
    compressor: Optional[TinySentenceCompressor] = None,
    max_sentences: int = 6,
) -> str:
    scored: List[tuple[float, str]] = []
    query_terms = set(keywords(query, limit=10))
    for item in chunks:
        for sent in sentence_split(item.chunk.text):
            sent = sent.strip()
            if len(sent) < 20:
                continue
            if compressor is not None:
                comp_score = compressor.score(query, sent, guidance_text)
                score = item.final_score + 2.0 * comp_score
            else:
                sent_terms = set(keywords(sent, limit=12))
                overlap = len(query_terms & sent_terms)
                score = item.final_score + 0.25 * overlap
            scored.append((score, sent))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[str] = []
    seen = set()
    for _, sent in scored:
        if sent in seen:
            continue
        out.append(sent)
        seen.add(sent)
        if len(out) >= max_sentences:
            break
    return ' '.join(out)


def _chunk_blob(chunk: Chunk) -> str:
    return ' '.join([chunk.text, chunk.heading, chunk.symbol_name, chunk.source_path])


def _covered_required_terms(chunks: Sequence[RetrievedChunk], required_terms: Sequence[str]) -> List[str]:
    if not required_terms:
        return []
    hay = ' '.join(_chunk_blob(item.chunk).lower() for item in chunks)
    return [t for t in required_terms if t in hay]


def _compute_confidence(top_now: Sequence[RetrievedChunk], covered_terms: Sequence[str], required_terms: Sequence[str], state: ControllerState, new_terms: Sequence[str]) -> tuple[float, str]:
    if not top_now:
        return 0.0, 'no_results'
    top_score = top_now[0].final_score
    second_score = top_now[1].final_score if len(top_now) > 1 else 0.0
    margin = max(0.0, top_score - second_score)
    coverage_ratio = (len(covered_terms) / len(required_terms)) if required_terms else 1.0
    diversity = min(1.0, len(state.source_counts) / 3.0)
    stable_memory = 0.0
    if len(state.working_memory_history) >= 2:
        stable_memory = 1.0 if state.working_memory_history[-1] == state.working_memory_history[-2] else 0.0
    no_new_terms_boost = 0.0 if new_terms else 0.12
    score_signal = min(0.32, 0.08 * max(0.0, top_score))
    margin_signal = min(0.18, 0.25 * margin)
    confidence = min(0.99, 0.18 + score_signal + margin_signal + 0.30 * coverage_ratio + 0.10 * diversity + 0.08 * stable_memory + no_new_terms_boost)
    if coverage_ratio >= 1.0 and confidence >= 0.78:
        return confidence, 'required_terms_covered'
    if stable_memory > 0 and confidence >= 0.72:
        return confidence, 'working_memory_stable'
    return confidence, ''


def _next_query(original_query: str, state: ControllerState, uncovered_terms: Sequence[str], new_terms: Sequence[str]) -> str:
    tail_terms: List[str] = []
    for term in list(uncovered_terms)[:4] + list(new_terms)[:5]:
        if term not in tail_terms:
            tail_terms.append(term)
    for term in state.expanded_terms[-6:]:
        if term not in tail_terms:
            tail_terms.append(term)
    return (original_query + ' ' + ' '.join(tail_terms)).strip()


def synthesize_answer(query: str, evidence: str, top_results: Sequence[RetrievedChunk], state: ControllerState) -> str:
    lines = [
        f'Query: {query}',
        '',
        f'Controller confidence: {state.final_confidence:.3f}',
        f'Stop reason: {state.stop_reason or "max_passes_reached"}',
        f'Expanded terms: {", ".join(state.expanded_terms[:16]) or "(none)"}',
        '',
        'Working evidence summary:',
        evidence or '(no compressed evidence)',
        '',
        'Top cited chunks:',
    ]
    for item in top_results[:5]:
        c = item.chunk
        lines.append(
            f'- [{c.source_path} :: {c.chunk_id} :: lines {c.line_start}-{c.line_end}] '
            f'{c.heading} (lex={item.lexical_score:.3f}, vec={item.vector_score:.3f}, rerank={item.rerank_score:.3f}, final={item.final_score:.3f})'
        )
    lines.append('')
    lines.append('Pass trace:')
    for record in state.pass_records:
        lines.append(
            f'- pass {record.pass_index}: conf={record.confidence:.3f} '
            f'top={", ".join(record.top_chunk_ids[:3]) or "(none)"} '
            f'new_terms={", ".join(record.new_terms[:5]) or "(none)"} '
            f'uncovered={", ".join(record.uncovered_required_terms) or "(none)"}'
        )
    return '\n'.join(lines)


def run_query_controller(
    query: str,
    chunks: Sequence[Chunk],
    idf: Dict[str, float],
    guidance: dict | None = None,
    ranker: Optional[TinyRelevanceRanker] = None,
    compressor: Optional[TinySentenceCompressor] = None,
    chunk_vectors: Sequence[Sequence[float]] | None = None,
    vector_dim: int = 64,
    top_k: int = 20,
    top_rerank: int = 5,
    retrieval_artifacts: Dict | None = None,
) -> QueryResult:
    g = parse_guidance(guidance)
    max_passes = max(1, int(g.get('max_passes', 1)))
    guidance_text = build_query_text('', g)
    initial_terms = keywords(build_query_text(query, g), limit=12)
    state = ControllerState(
        original_query=query,
        guidance=g,
        guidance_text=guidance_text,
        current_query=query,
        max_passes=max_passes,
        expanded_terms=list(dict.fromkeys(initial_terms + list(g.get('required_terms', [])))),
    )
    merged: Dict[str, RetrievedChunk] = {}

    for pass_idx in range(max_passes):
        retrieval_query = state.current_query + ' ' + ' '.join(state.expanded_terms[-8:])
        retrieved = retrieve(
            retrieval_query,
            chunks,
            idf,
            top_k=top_k,
            guidance=guidance,
            chunk_vectors=chunk_vectors,
            vector_dim=vector_dim,
            retrieval_artifacts=retrieval_artifacts,
        )
        for item in retrieved:
            if ranker is not None:
                rank_text = _chunk_blob(item.chunk)
                item.rerank_score = ranker.score(query=retrieval_query, chunk=rank_text, guidance_text=guidance_text)
                base_score = 0.45 * item.lexical_score + 1.20 * max(0.0, item.vector_score) + 2.20 * item.rerank_score
            else:
                item.rerank_score = 0.0
                base_score = item.lexical_score + 1.0 * max(0.0, item.vector_score)

            novelty_mult = 0.84 if item.chunk.chunk_id in state.seen_chunk_ids else 1.0
            preferred_mult = 1.0
            if g['prefer_sources'] and item.chunk.source_type in g['prefer_sources']:
                if state.source_counts.get(item.chunk.source_type, 0) == 0:
                    preferred_mult += 0.08
            uncovered_terms = [t for t in g['required_terms'] if t not in state.covered_required_terms]
            coverage_mult = 1.0 + 0.05 * sum(1 for t in uncovered_terms if t in _chunk_blob(item.chunk).lower())
            item.final_score = base_score * novelty_mult * preferred_mult * coverage_mult
            prev = merged.get(item.chunk.chunk_id)
            if prev is None or item.final_score > prev.final_score:
                merged[item.chunk.chunk_id] = item

        ranked = sorted(merged.values(), key=lambda r: r.final_score, reverse=True)
        top_now = ranked[:top_rerank]
        evidence = compress_chunks(query + ' ' + ' '.join(state.expanded_terms[:8]), top_now, guidance_text=guidance_text, compressor=compressor)
        state.working_memory_history.append(evidence)

        pass_seen = []
        for item in top_now:
            cid = item.chunk.chunk_id
            pass_seen.append(cid)
            if cid not in state.seen_chunk_ids:
                state.seen_chunk_ids.append(cid)
                st = item.chunk.source_type or 'unknown'
                state.source_counts[st] = state.source_counts.get(st, 0) + 1

        covered_now = _covered_required_terms(top_now, g['required_terms'])
        for term in covered_now:
            if term not in state.covered_required_terms:
                state.covered_required_terms.append(term)

        new_terms = [t for t in keywords(evidence + ' ' + retrieval_query, limit=12) if t not in state.expanded_terms]
        for term in new_terms[:6]:
            state.expanded_terms.append(term)

        uncovered_required = [t for t in g['required_terms'] if t not in state.covered_required_terms]
        confidence, stop_reason = _compute_confidence(top_now, state.covered_required_terms, g['required_terms'], state, new_terms)
        record = PassRecord(
            pass_index=pass_idx + 1,
            current_query=retrieval_query,
            retrieved_count=len(retrieved),
            top_chunk_ids=pass_seen,
            new_terms=new_terms[:8],
            covered_required_terms=list(state.covered_required_terms),
            uncovered_required_terms=uncovered_required,
            source_counts_snapshot=dict(state.source_counts),
            working_memory=evidence,
            confidence=confidence,
            stop_reason=stop_reason,
        )
        state.pass_records.append(record)
        state.final_confidence = confidence

        if stop_reason:
            state.stop_reason = stop_reason
            break
        if pass_idx + 1 < max_passes:
            state.current_query = _next_query(query, state, uncovered_required, new_terms)
    else:
        state.stop_reason = 'max_passes_reached'

    ranked = sorted(merged.values(), key=lambda r: r.final_score, reverse=True)
    top_results = ranked[:top_rerank]
    evidence = compress_chunks(query + ' ' + ' '.join(state.expanded_terms[:8]), top_results, guidance_text=guidance_text, compressor=compressor)
    answer = synthesize_answer(query, evidence, top_results, state)
    return QueryResult(answer=answer, working_memory=evidence, top_results=top_results, state=state)
