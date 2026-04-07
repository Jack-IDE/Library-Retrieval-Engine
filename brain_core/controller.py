from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
import re
from typing import Dict, List, Optional, Sequence

from .brain_synthesis import apply_brain_decision, build_brain_decision
from .chunking import Chunk
from .compressor_model import TinySentenceCompressor
from .ranker_model import TinyRelevanceRanker
from .retrieval import RetrievedChunk, build_query_text, informative_query_terms, parse_guidance, retrieve
from .text_utils import keywords, sentence_split, tokenize

try:
    from . import phrase_engine as _pe
    _PHRASE_ENGINE_AVAILABLE = True
except Exception:
    _pe = None  # type: ignore[assignment]
    _PHRASE_ENGINE_AVAILABLE = False


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
    composition_mode: str = ''
    brain_selected_chunk_ids: List[str] = field(default_factory=list)
    brain_reason_flags: List[str] = field(default_factory=list)
    brain_expansion_terms: List[str] = field(default_factory=list)


@dataclass
class ControllerState:
    original_query: str
    guidance: dict
    guidance_text: str
    current_query: str
    max_passes: int
    seed_terms: List[str] = field(default_factory=list)
    expanded_terms: List[str] = field(default_factory=list)
    seen_chunk_ids: List[str] = field(default_factory=list)
    covered_required_terms: List[str] = field(default_factory=list)
    source_counts: Dict[str, int] = field(default_factory=dict)
    working_memory_history: List[str] = field(default_factory=list)
    pass_records: List[PassRecord] = field(default_factory=list)
    final_confidence: float = 0.0
    stop_reason: str = ''
    final_brain_decision: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QueryResult:
    answer: str
    working_memory: str
    top_results: List[RetrievedChunk]
    state: ControllerState
    brain_decision: dict = field(default_factory=dict)


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
                score = max(item.final_score, item.brain_score) + 2.0 * comp_score
            else:
                sent_terms = set(keywords(sent, limit=12))
                overlap = len(query_terms & sent_terms)
                score = max(item.final_score, item.brain_score) + 0.25 * overlap
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
    top_score = max(top_now[0].final_score, top_now[0].brain_score)
    second_score = max(top_now[1].final_score, top_now[1].brain_score) if len(top_now) > 1 else 0.0
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
    if required_terms and coverage_ratio >= 1.0 and confidence >= 0.78:
        return confidence, 'required_terms_covered'
    if not required_terms and confidence >= 0.78:
        return confidence, 'high_confidence'
    if stable_memory > 0 and confidence >= 0.72:
        return confidence, 'working_memory_stable'
    return confidence, ''


def _next_query(seed_terms: Sequence[str], state: ControllerState, uncovered_terms: Sequence[str], new_terms: Sequence[str]) -> str:
    ordered: List[str] = []
    for term in list(seed_terms) + list(state.expanded_terms) + list(uncovered_terms)[:4] + list(new_terms)[:5]:
        if term and term not in ordered:
            ordered.append(term)
    return ' '.join(ordered).strip()


def _candidate_packet_map(brain: dict) -> Dict[str, dict]:
    packets = brain.get('candidate_packets', []) if isinstance(brain, dict) else []
    out: Dict[str, dict] = {}
    for packet in packets:
        if not isinstance(packet, dict):
            continue
        chunk_id = str(packet.get('chunk_id', '')).strip()
        if chunk_id:
            out[chunk_id] = packet
    return out


def _selected_results(top_results: Sequence[RetrievedChunk], brain: dict) -> List[RetrievedChunk]:
    selected_ids = [str(x) for x in (brain.get('selected_chunk_ids', []) if isinstance(brain, dict) else []) if str(x).strip()]
    by_id = {str(item.chunk.chunk_id): item for item in top_results}
    selected = [by_id[cid] for cid in selected_ids if cid in by_id]
    if selected:
        return selected
    return list(top_results[: max(1, min(3, len(top_results)))])


def _clean_text(text: str) -> str:
    text = str(text or '').replace('\r', ' ')
    text = re.sub(r'`{1,3}', '', text)
    text = re.sub(r'^[#>*\-]+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _source_stub(item: RetrievedChunk) -> str:
    name = Path(str(item.chunk.source_path or '')).name or str(item.chunk.source_type or 'source')
    heading = str(item.chunk.heading or '').strip() or name
    return f'{heading} [{name}]'


def _context_frame(terms: Sequence[str], mode: str, seed: int = 0) -> str:
    cleaned = [str(term).strip() for term in terms if str(term).strip()]
    if not cleaned:
        return ''
    if _PHRASE_ENGINE_AVAILABLE:
        try:
            return _pe.context_frame(cleaned, mode, seed)
        except Exception:
            pass
    lead = ', '.join(cleaned[:4])
    return f'Relevant signal: {lead}.'


def _sentence_key(text: str) -> set[str]:
    return set(tok for tok in tokenize(_clean_text(text)) if len(tok) > 2)


def _redundant_text(text: str, kept: Sequence[str], threshold: float = 0.72) -> bool:
    current = _sentence_key(text)
    if not current:
        return True
    for prior in kept:
        prior_key = _sentence_key(prior)
        if not prior_key:
            continue
        overlap = len(current & prior_key) / max(1, len(current | prior_key))
        if overlap >= threshold:
            return True
    return False


def _extract_instruction_steps(text: str) -> List[str]:
    blob = str(text or '')
    match = re.search(r'Instructions:\s*(.*)', blob, flags=re.IGNORECASE | re.DOTALL)
    if match:
        blob = match.group(1)
    blob = blob.replace('\r', ' ').replace('\n', ' ')
    steps: List[str] = []
    numbered = re.findall(r'(?:^|\s)(\d+\.\s.*?)(?=(?:\s+\d+\.\s)|$)', blob)
    for step in numbered:
        cleaned = re.sub(r'^\d+\.\s*', '', _clean_text(step))
        lowered = cleaned.lower()
        if lowered.startswith(('ingredients:', 'season:', 'vibe:', 'meal type:', 'difficulty:', 'time:')):
            continue
        if len(cleaned) >= 12 and not _redundant_text(cleaned, steps):
            steps.append(cleaned)
    if steps:
        return steps
    for sentence in sentence_split(blob):
        cleaned = _clean_text(sentence)
        lowered = cleaned.lower()
        if len(cleaned) < 12 or lowered.startswith(('ingredients:', 'season:', 'vibe:', 'meal type:', 'difficulty:', 'time:')):
            continue
        if not _redundant_text(cleaned, steps):
            steps.append(cleaned)
        if len(steps) >= 6:
            break
    return steps


def _extract_inline_field(text: str, label: str) -> str:
    blob = str(text or '')
    pattern = rf'{re.escape(label)}:\s*(.*?)(?=(?:\s+[A-Z][A-Za-z ]{1,20}:\s)|$)'
    match = re.search(pattern, blob, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ''
    return _clean_text(match.group(1))


def _best_sentences(text: str, query: str, activation_terms: Sequence[str], max_sentences: int = 2) -> List[str]:
    query_term_set = set(keywords(query, limit=12))
    activation_term_set = {str(t).strip() for t in activation_terms if str(t).strip()}
    focus_terms = query_term_set | activation_term_set
    scored: List[tuple[float, str]] = []
    for idx, sentence in enumerate(sentence_split(text)):
        cleaned = _clean_text(sentence)
        if len(cleaned) < 28:
            continue
        sentence_terms = set(keywords(cleaned, limit=12))
        query_overlap = len(query_term_set & sentence_terms)
        activation_overlap = len(activation_term_set & sentence_terms)
        focus_overlap = len(focus_terms & sentence_terms)
        position_bonus = 0.22 / (1.0 + 0.55 * idx)
        score = position_bonus
        score += 0.26 * query_overlap
        score += 0.20 * activation_overlap
        score += 0.05 * min(4, focus_overlap)
        if idx >= 4 and focus_overlap >= 3:
            score += 0.22 + 0.04 * min(3, focus_overlap - 2)
        if ':' in cleaned:
            score += 0.04
        if idx == 0 and focus_overlap == 0:
            score -= 0.08
        scored.append((score, cleaned))
    scored.sort(key=lambda item: item[0], reverse=True)
    out: List[str] = []
    for _, sentence in scored:
        if _redundant_text(sentence, out):
            continue
        out.append(sentence)
        if len(out) >= max(1, max_sentences):
            break
    return out


def _render_use_one(query: str, selected: Sequence[RetrievedChunk], brain: dict, packet_map: Dict[str, dict], evidence: str, seed: int = 0, intro: str = '', hedge: str = '') -> str:
    primary = selected[0] if selected else None
    if primary is None:
        return evidence or '(no answer)'
    packet = packet_map.get(str(primary.chunk.chunk_id), {})
    activation_terms = packet.get('activation_terms', []) or brain.get('activation_expansion_terms', [])
    title = str(primary.chunk.heading or '').strip() or 'Best match'
    focus = _context_frame(brain.get('activation_expansion_terms', []), 'use_one', seed)
    support = _best_sentences(primary.chunk.text, query, activation_terms, max_sentences=2)
    lines: List[str] = []
    if hedge:
        lines.append(hedge)
    if intro:
        lines.append(intro)
    lines.append(f'Best match: **{title}**.')
    if focus:
        lines.append(focus)
    if str(brain.get('intent', '')) == 'recipe' and primary.chunk.source_type in {'recipes', 'docs'}:
        ingredients = _extract_inline_field(primary.chunk.text, 'Ingredients')
        steps = _extract_instruction_steps(primary.chunk.text)
        filtered_support = list(support)
        if ingredients:
            ing_key = _sentence_key(ingredients)
            steps = [step for step in steps if len(_sentence_key(step) & ing_key) / max(1, len(_sentence_key(step) | ing_key)) < 0.65]
            filtered_support = [part for part in support if len(_sentence_key(part) & ing_key) / max(1, len(_sentence_key(part) | ing_key)) < 0.65]
            lines.append('Ingredients: ' + ingredients)
        if steps:
            lines.append('Steps:\n- ' + '\n- '.join(steps[:4]))
        elif filtered_support and not ingredients:
            lines.append(' '.join(filtered_support))
        elif evidence and not ingredients:
            lines.append(evidence)
    else:
        if support:
            lines.append(' '.join(support))
        elif evidence:
            lines.append(evidence)
    if 'activation_redundant' in set(brain.get('reason_flags', [])):
        if _PHRASE_ENGINE_AVAILABLE:
            try:
                note = _pe.redundancy_note(seed)
                if note:
                    lines.append(note)
            except Exception:
                lines.append('Strongest candidates were semantically close — focused on best match.')
        else:
            lines.append('Strongest candidates were semantically close — focused on best match.')
    lines.append(f'Source focus: {_source_stub(primary)}.')
    return '\n\n'.join(line for line in lines if line)


def _render_merge_steps(query: str, selected: Sequence[RetrievedChunk], brain: dict, packet_map: Dict[str, dict], evidence: str, seed: int = 0, intro: str = '', hedge: str = '') -> str:
    focus = _context_frame(brain.get('activation_expansion_terms', []), 'merge_steps', seed)
    title = str(selected[0].chunk.heading or '').strip() if selected else 'Merged recipe path'
    merged_steps: List[str] = []
    for item in selected[:3]:
        for step in _extract_instruction_steps(item.chunk.text):
            if _redundant_text(step, merged_steps, threshold=0.68):
                continue
            merged_steps.append(step)
            if len(merged_steps) >= 6:
                break
        if len(merged_steps) >= 6:
            break
    lines: List[str] = []
    if hedge:
        lines.append(hedge)
    if intro:
        lines.append(intro)
    lines.append(f'Best merged path: **{title}**.')
    if focus:
        lines.append(focus)
    if merged_steps:
        lines.append('Steps:')
        lines.extend(f'{idx}. {step}' for idx, step in enumerate(merged_steps[:5], start=1))
    elif evidence:
        lines.append(evidence)
    if len(selected) > 1:
        if _PHRASE_ENGINE_AVAILABLE:
            try:
                note = _pe.merge_note(seed)
                if note:
                    lines.append(f'{note} drew from complementary chunks.')
            except Exception:
                lines.append('Complementary chunks merged.')
        else:
            lines.append('Complementary chunks merged.')
    lines.append('Source focus: ' + '; '.join(_source_stub(item) for item in selected[:2]) + '.')
    return '\n'.join(line for line in lines if line)


def _render_merge_context(query: str, selected: Sequence[RetrievedChunk], brain: dict, packet_map: Dict[str, dict], evidence: str, seed: int = 0, intro: str = '', hedge: str = '') -> str:
    primary = selected[0] if selected else None
    support = selected[1] if len(selected) > 1 else None
    lines: List[str] = []
    if hedge:
        lines.append(hedge)
    if intro:
        lines.append(intro)
    if primary is not None:
        lines.append(f'Best fit: **{str(primary.chunk.heading or "Primary chunk").strip()}**.')
    focus = _context_frame(brain.get('activation_expansion_terms', []), 'merge_context', seed)
    if focus:
        lines.append(focus)
    primary_summary: List[str] = []
    if primary is not None:
        primary_terms = (packet_map.get(str(primary.chunk.chunk_id), {}) or {}).get('activation_terms', [])
        primary_summary = _best_sentences(primary.chunk.text, query, primary_terms, max_sentences=2)
        if primary_summary:
            lines.append('What to do:\n- ' + '\n- '.join(primary_summary))
    if support is not None:
        support_terms = (packet_map.get(str(support.chunk.chunk_id), {}) or {}).get('activation_terms', [])
        context_parts = _best_sentences(support.chunk.text, query, support_terms, max_sentences=2)
        context_parts = [part for part in context_parts if not _redundant_text(part, primary_summary, threshold=0.66)]
        if context_parts:
            lines.append('Why / context:\n- ' + '\n- '.join(context_parts))
    if len(lines) <= 2 and evidence:
        lines.append(evidence)
    if selected:
        lines.append('Source focus: ' + '; '.join(_source_stub(item) for item in selected[:2]) + '.')
    return '\n\n'.join(line for line in lines if line)


def _render_merge_solution(query: str, selected: Sequence[RetrievedChunk], brain: dict, packet_map: Dict[str, dict], evidence: str, seed: int = 0, intro: str = '', hedge: str = '') -> str:
    primary = selected[0] if selected else None
    support = selected[1] if len(selected) > 1 else None
    lines: List[str] = []
    if hedge:
        lines.append(hedge)
    if intro:
        lines.append(intro)
    if primary is not None:
        lines.append(f'Best fit: **{str(primary.chunk.heading or "Primary chunk").strip()}**.')
    focus = _context_frame(brain.get('activation_expansion_terms', []), 'merge_solution', seed)
    if focus:
        lines.append(focus)
    if primary is not None:
        primary_terms = (packet_map.get(str(primary.chunk.chunk_id), {}) or {}).get('activation_terms', [])
        core = _best_sentences(primary.chunk.text, query, primary_terms, max_sentences=2)
        if core:
            lines.append('Core solution:\n- ' + '\n- '.join(core))
    if support is not None:
        support_terms = (packet_map.get(str(support.chunk.chunk_id), {}) or {}).get('activation_terms', [])
        add_parts = _best_sentences(support.chunk.text, query, support_terms, max_sentences=2)
        if add_parts:
            lines.append('Add from support:\n- ' + '\n- '.join(add_parts))
    if len(lines) <= 2 and evidence:
        lines.append(evidence)
    if selected:
        lines.append('Source focus: ' + '; '.join(_source_stub(item) for item in selected[:2]) + '.')
    return '\n\n'.join(line for line in lines if line)


def _render_merge(query: str, selected: Sequence[RetrievedChunk], brain: dict, packet_map: Dict[str, dict], evidence: str, seed: int = 0, intro: str = '', hedge: str = '') -> str:
    lines: List[str] = []
    if hedge:
        lines.append(hedge)
    if intro:
        lines.append(intro)
    focus = _context_frame(brain.get('activation_expansion_terms', []), 'merge', seed)
    if focus:
        lines.append(focus)
    fused: List[str] = []
    for idx, item in enumerate(selected[:3]):
        activation_terms = (packet_map.get(str(item.chunk.chunk_id), {}) or {}).get('activation_terms', [])
        for sentence in _best_sentences(item.chunk.text, query, activation_terms, max_sentences=2):
            if _redundant_text(sentence, fused, threshold=0.68):
                continue
            connector = ''
            if fused:
                if _PHRASE_ENGINE_AVAILABLE:
                    try:
                        conn_phrase = _pe.connector(brain.get('reason_flags', []), seed + idx)
                        connector = (conn_phrase + ' ') if conn_phrase else 'Also, '
                        if conn_phrase and not conn_phrase.endswith('...'):
                            fused_sentence = connector + sentence
                        else:
                            fused_sentence = connector + (sentence[0].lower() + sentence[1:] if sentence else sentence)
                    except Exception:
                        connector = 'Alongside that, ' if 'activation_complementary' in set(brain.get('reason_flags', [])) else 'Also, '
                        fused_sentence = connector + (sentence[0].lower() + sentence[1:] if sentence else sentence)
                else:
                    connector = 'Alongside that, ' if 'activation_complementary' in set(brain.get('reason_flags', [])) else 'Also, '
                    fused_sentence = connector + (sentence[0].lower() + sentence[1:] if sentence else sentence)
            else:
                fused_sentence = connector + sentence
            fused.append(fused_sentence)
            if len(fused) >= 3:
                break
        if len(fused) >= 3:
            break
    if fused:
        fused[0] = fused[0][0].upper() + fused[0][1:] if fused[0] else fused[0]
        lines.append(' '.join(fused))
    elif evidence:
        lines.append(evidence)
    if selected:
        lines.append('Source focus: ' + '; '.join(_source_stub(item) for item in selected[:2]) + '.')
    return '\n\n'.join(line for line in lines if line)


def synthesize_answer(query: str, evidence: str, top_results: Sequence[RetrievedChunk], state: ControllerState, brain_decision: dict | None = None) -> str:
    brain = brain_decision or {}
    selected = _selected_results(top_results, brain)
    packet_map = _candidate_packet_map(brain)
    mode = str(brain.get('composition_mode', 'use_one') or 'use_one')
    seed = _pe.query_seed(query, mode) if _PHRASE_ENGINE_AVAILABLE else 0
    intro = ''
    hedge = ''
    if _PHRASE_ENGINE_AVAILABLE:
        try:
            intro = _pe.mode_intro(mode, seed)
        except Exception:
            intro = ''
        try:
            hedge = _pe.hedge(float(getattr(state, 'final_confidence', 0.0) or 0.0), seed + 1)
        except Exception:
            hedge = ''

    if not selected and top_results:
        selected = list(top_results[:1])

    if mode == 'merge_steps':
        return _render_merge_steps(query, selected, brain, packet_map, evidence, seed, intro, hedge)
    if mode == 'merge_context':
        return _render_merge_context(query, selected, brain, packet_map, evidence, seed, intro, hedge)
    if mode == 'merge_solution':
        return _render_merge_solution(query, selected, brain, packet_map, evidence, seed, intro, hedge)
    if mode == 'merge':
        return _render_merge(query, selected, brain, packet_map, evidence, seed, intro, hedge)
    return _render_use_one(query, selected, brain, packet_map, evidence, seed, intro, hedge)


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
    initial_terms = informative_query_terms(query, g)[:12]
    seed_terms = list(dict.fromkeys(initial_terms + list(g.get('required_terms', []))))
    state = ControllerState(
        original_query=query,
        guidance=g,
        guidance_text=guidance_text,
        current_query=' '.join(seed_terms) if seed_terms else query,
        max_passes=max_passes,
        seed_terms=seed_terms,
        expanded_terms=[],
    )
    merged: Dict[str, RetrievedChunk] = {}

    for pass_idx in range(max_passes):
        retrieval_query = state.current_query.strip() or query
        retrieved = retrieve(
            retrieval_query,
            chunks,
            idf,
            top_k=top_k,
            guidance=g,
            chunk_vectors=chunk_vectors,
            vector_dim=vector_dim,
            retrieval_artifacts=retrieval_artifacts,
        )
        for item in retrieved:
            if ranker is not None:
                rank_text = _chunk_blob(item.chunk)
                item.ranker_features = ranker.forward(query=retrieval_query, chunk=rank_text, guidance_text=guidance_text)
                item.rerank_score = float(item.ranker_features.prob)
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
            if item.reasoning_trace is not None:
                item.reasoning_trace['final_score'] = float(item.final_score)
            prev = merged.get(item.chunk.chunk_id)
            if prev is None or item.final_score > prev.final_score:
                merged[item.chunk.chunk_id] = item

        ranked = sorted(merged.values(), key=lambda r: r.final_score, reverse=True)
        brain_decision = build_brain_decision(
            query=query,
            candidates=ranked[:max(top_rerank * 3, 8)],
            guidance=g,
            guidance_text=guidance_text,
            ranker=ranker,
            selection_limit=max(1, min(3, top_rerank)),
        )
        top_now = apply_brain_decision(ranked, brain_decision, top_rerank)
        evidence_terms = ' '.join(state.seed_terms + state.expanded_terms[:8])
        selected_now = [item for item in top_now if item.chunk.chunk_id in set(brain_decision.selected_chunk_ids)] or list(top_now)
        evidence = compress_chunks((query + ' ' + evidence_terms).strip(), selected_now, guidance_text=guidance_text, compressor=compressor)
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

        raw_new_terms = list(brain_decision.activation_expansion_terms) + keywords(evidence + ' ' + retrieval_query, limit=12)
        new_terms: List[str] = []
        blocked_terms = {'how', 'make', 'cook', 'prepare', 'recipe', 'app', 'project'}
        for term in raw_new_terms:
            if term in blocked_terms:
                continue
            if term in state.seed_terms or term in state.expanded_terms or term in new_terms:
                continue
            new_terms.append(term)
        if pass_idx + 1 < max_passes:
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
            composition_mode=brain_decision.composition_mode,
            brain_selected_chunk_ids=list(brain_decision.selected_chunk_ids),
            brain_reason_flags=list(brain_decision.reason_flags),
            brain_expansion_terms=list(brain_decision.activation_expansion_terms),
        )
        state.pass_records.append(record)
        state.final_confidence = confidence

        if stop_reason:
            state.stop_reason = stop_reason
            break
        if pass_idx + 1 < max_passes:
            state.current_query = _next_query(state.seed_terms, state, uncovered_required, new_terms)
    else:
        state.stop_reason = 'max_passes_reached'

    ranked = sorted(merged.values(), key=lambda r: r.final_score, reverse=True)
    final_candidates = ranked[:max(top_rerank * 3, 8)]
    if ranker is not None:
        for item in final_candidates:
            rank_text = _chunk_blob(item.chunk)
            item.ranker_features = ranker.forward(query=query, chunk=rank_text, guidance_text=guidance_text)
            item.rerank_score = float(item.ranker_features.prob)
    final_brain_decision = build_brain_decision(
        query=query,
        candidates=final_candidates,
        guidance=g,
        guidance_text=guidance_text,
        ranker=ranker,
        selection_limit=max(1, min(3, top_rerank)),
    )
    state.final_brain_decision = final_brain_decision.to_dict()
    top_results = apply_brain_decision(ranked, final_brain_decision, top_rerank)
    selected_final = [item for item in top_results if item.chunk.chunk_id in set(final_brain_decision.selected_chunk_ids)] or list(top_results)
    evidence_terms = ' '.join(state.seed_terms + state.expanded_terms[:8])
    evidence = compress_chunks((query + ' ' + evidence_terms).strip(), selected_final, guidance_text=guidance_text, compressor=compressor)
    answer = synthesize_answer(query, evidence, top_results, state, final_brain_decision.to_dict())
    return QueryResult(answer=answer, working_memory=evidence, top_results=top_results, state=state, brain_decision=final_brain_decision.to_dict())
