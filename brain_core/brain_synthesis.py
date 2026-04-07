from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .ranker_model import PairFeatures, TinyRelevanceRanker
from .retrieval import RetrievedChunk, classify_query_intent, informative_query_terms, parse_guidance
from .text_utils import STOPWORDS, cosine_similarity


META_SOURCE_STEMS = {'library_input_notes', 'retrieval_notes', 'readme'}
META_QUERY_TERMS = {'library', 'libraries', 'retrieval', 'index', 'chunk', 'chunks', 'vocab', 'guidance', 'input', 'pipeline', 'corpus', 'architecture'}


@dataclass
class BrainCandidatePacket:
    chunk_id: str
    library_id: str
    source_type: str
    source_path: str
    heading: str
    candidate_rank: int
    lexical_score: float
    vector_score: float
    rerank_score: float
    final_score: float
    brain_score: float
    overlap_terms: List[str]
    overlap_count: int
    activation_head: List[int]
    activation_energy: float
    activation_similarity_to_top: float = 1.0
    activation_terms: List[str] = field(default_factory=list)
    source_match: bool = False
    meta_source: bool = False
    chunk_kind: str = ''
    line_span: str = ''
    recipe_role: str = ''
    recipe_group: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BrainDecision:
    intent: str
    composition_mode: str
    selected_chunk_ids: List[str]
    dropped_chunk_ids: List[str]
    confidence: float
    reason_flags: List[str]
    candidate_packets: List[dict]
    activation_expansion_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'intent': self.intent,
            'composition_mode': self.composition_mode,
            'selected_chunk_ids': list(self.selected_chunk_ids),
            'dropped_chunk_ids': list(self.dropped_chunk_ids),
            'confidence': float(self.confidence),
            'reason_flags': list(self.reason_flags),
            'candidate_packets': list(self.candidate_packets),
            'activation_expansion_terms': list(self.activation_expansion_terms),
        }


def _chunk_blob(item: RetrievedChunk) -> str:
    chunk = item.chunk
    return ' '.join([chunk.text, chunk.heading, chunk.symbol_name, chunk.source_path])


def _is_meta_source(item: RetrievedChunk) -> bool:
    stem = Path(str(item.chunk.source_path or '')).stem.lower()
    return stem in META_SOURCE_STEMS


def _query_is_meta(query_terms: Sequence[str]) -> bool:
    return bool(set(query_terms) & META_QUERY_TERMS)


def _activation_summary(features: Optional[PairFeatures], top_n: int = 4) -> tuple[List[int], float]:
    if features is None:
        return [], 0.0
    raw: Sequence[float]
    if features.h2_act:
        raw = features.h2_act
    elif features.h1_act:
        raw = features.h1_act
    else:
        raw = [abs(v) for v in features.x]
    scored: List[tuple[float, int]] = []
    energy = 0.0
    for idx, value in enumerate(raw):
        magnitude = abs(float(value))
        if magnitude > 0.0:
            scored.append((magnitude, idx))
            energy += magnitude
    scored.sort(key=lambda item: item[0], reverse=True)
    return [idx for _, idx in scored[:max(1, top_n)]], float(energy)


def _feature_vector(features: Optional[PairFeatures]) -> List[float]:
    if features is None:
        return []
    if features.h2_act:
        return [float(v) for v in features.h2_act]
    if features.h1_act:
        return [float(v) for v in features.h1_act]
    return [float(v) for v in features.x]


def _source_bonus(intent: str, source_type: str, meta_source: bool) -> float:
    if intent == 'recipe':
        if source_type == 'recipes':
            return 0.28 if not meta_source else 0.12
        if source_type == 'docs':
            return 0.08 if not meta_source else 0.02
        return -0.05
    if intent == 'code_project':
        if source_type == 'code':
            return 0.24 if not meta_source else 0.10
        if source_type == 'docs':
            return 0.18 if not meta_source else 0.08
        if source_type == 'specs':
            return 0.15 if not meta_source else 0.06
        return -0.06
    if meta_source:
        return -0.04
    return 0.0


def _recipe_chunk_role(item: RetrievedChunk) -> str:
    lowered = _chunk_blob(item).lower()
    has_instructions = ('instructions:' in lowered or 'steps:' in lowered or bool(re.search(r'(?:^|\n)\s*1\.\s', lowered)))
    has_ingredients = 'ingredients:' in lowered
    has_meta = any(label in lowered for label in (
        'season:', 'vibe:', 'meal type:', 'difficulty:', 'time:', 'diet:',
        'cuisine:', 'technique:', 'serves:', 'prep:', 'cook:'
    ))
    if has_instructions:
        return 'instructions'
    if has_ingredients:
        return 'ingredients'
    if has_meta:
        return 'metadata'
    return 'prose'


def _recipe_group_key(item: RetrievedChunk) -> str:
    heading = str(item.chunk.heading or '').strip().lower()
    source = str(item.chunk.source_path or '').strip().lower()
    if not heading:
        return ''
    return source + '::' + heading


def _is_recipe_action_query_text(query: str) -> bool:
    q = str(query or '').strip().lower()
    if not q:
        return False
    return (
        'how do i make' in q or 'how to make' in q or
        'how do i cook' in q or 'how to cook' in q or
        'how do i prepare' in q or 'how to prepare' in q or
        'recipe for' in q or q.startswith('make ') or q.startswith('cook ') or q.startswith('prepare ')
    )


def _structural_bonus(intent: str, item: RetrievedChunk) -> float:
    chunk = item.chunk
    if intent == 'code_project':
        if chunk.chunk_kind == 'code':
            return 0.12
        if chunk.source_type in {'docs', 'specs'}:
            return 0.05
    if intent == 'recipe':
        role = _recipe_chunk_role(item)
        bonus = 0.0
        if chunk.source_type == 'recipes':
            bonus += 0.08
        if role == 'instructions':
            bonus += 0.24
        elif role == 'ingredients':
            bonus += 0.10
        elif role == 'metadata':
            bonus -= 0.05
        return bonus
    return 0.0


def _input_importance_from_features(ranker: TinyRelevanceRanker, features: PairFeatures) -> List[float]:
    e = ranker.embed_dim
    if ranker.arch == 'linear':
        direct = [abs(float(v)) for v in ranker.W0]
        out = [0.0] * ranker.input_dim
        for d in range(e):
            out[e + d] = direct[e + d] + 0.35 * direct[2 * e + d] + abs(float(features.q[d])) * direct[3 * e + d]
            out[4 * e + d] = direct[4 * e + d]
        return out

    hidden2_gate = [max(0.0, float(v)) for v in features.h2_pre] if features.h2_pre else []
    hidden1_gate = [max(0.0, float(v)) for v in features.h1_pre] if features.h1_pre else []
    if not hidden2_gate or not hidden1_gate:
        return [0.0] * ranker.input_dim

    h1_to_out = [0.0] * ranker.hidden1
    for i in range(ranker.hidden1):
        acc = 0.0
        row = ranker.W2[i]
        for j in range(ranker.hidden2):
            if hidden2_gate[j] <= 0.0:
                continue
            acc += abs(float(row[j])) * abs(float(ranker.W3[j])) * hidden2_gate[j]
        h1_to_out[i] = acc

    out = [0.0] * ranker.input_dim
    for d in range(ranker.input_dim):
        acc = 0.0
        row = ranker.W1[d]
        for i in range(ranker.hidden1):
            if hidden1_gate[i] <= 0.0:
                continue
            acc += abs(float(row[i])) * h1_to_out[i] * hidden1_gate[i]
        out[d] = acc
    return out


def _token_scores_from_features(ranker: Optional[TinyRelevanceRanker], features: Optional[PairFeatures], token_ids: Sequence[int]) -> List[tuple[float, str]]:
    if ranker is None or features is None or not token_ids:
        return []
    e = ranker.embed_dim
    importance = _input_importance_from_features(ranker, features)
    if not importance:
        return []

    chunk_weights = [0.0] * e
    for d in range(e):
        chunk_weights[d] = (
            float(importance[e + d])
            + 0.35 * float(importance[2 * e + d])
            + abs(float(features.q[d])) * float(importance[3 * e + d])
            + 0.15 * float(importance[4 * e + d])
        )

    seen = set()
    scored: List[tuple[float, str]] = []
    for tok_id in token_ids:
        tok = str(ranker.reverse_vocab.get(tok_id, ''))
        if not tok or tok in seen or tok in STOPWORDS or len(tok) < 3 or tok.startswith('<'):
            continue
        seen.add(tok)
        row = ranker.E[tok_id]
        score = 0.0
        for d in range(e):
            score += abs(float(row[d])) * chunk_weights[d]
        if score > 0.0:
            scored.append((float(score), tok))
    scored.sort(key=lambda kv: kv[0], reverse=True)
    return scored


def _composition_mode(intent: str, packets: Sequence[BrainCandidatePacket], similarity_map: Dict[tuple[str, str], float]) -> tuple[str, List[str]]:
    if not packets:
        return 'no_answer', ['no_candidates']
    reasons: List[str] = []
    if len(packets) == 1:
        reasons.append('single_selected_chunk')
        return 'use_one', reasons

    top = packets[0]
    second = packets[1]
    sim = similarity_map.get((top.chunk_id, second.chunk_id), similarity_map.get((second.chunk_id, top.chunk_id), 1.0))
    close_scores = second.brain_score >= top.brain_score * 0.82
    complementary = sim <= 0.84
    redundant = sim >= 0.93
    cross_source = top.source_type != second.source_type

    if intent == 'recipe':
        if close_scores and complementary:
            reasons.extend(['activation_complementary', 'multi_recipe_support'])
            return 'merge_steps', reasons
        if redundant:
            reasons.append('activation_redundant')
        reasons.append('dominant_recipe_chunk')
        return 'use_one', reasons

    if intent == 'code_project':
        if close_scores and complementary and cross_source:
            reasons.extend(['activation_complementary', 'cross_source_context'])
            return 'merge_context', reasons
        if close_scores and complementary:
            reasons.extend(['activation_complementary', 'multi_code_support'])
            return 'merge_solution', reasons
        if redundant:
            reasons.append('activation_redundant')
        reasons.append('dominant_code_chunk')
        return 'use_one', reasons

    if close_scores and complementary:
        reasons.extend(['activation_complementary', 'cross_source_support' if cross_source else 'multi_support'])
        return 'merge', reasons
    if redundant:
        reasons.append('activation_redundant')
    reasons.append('dominant_chunk')
    return 'use_one', reasons


def build_brain_decision(
    query: str,
    candidates: Sequence[RetrievedChunk],
    guidance: dict | None = None,
    guidance_text: str = '',
    ranker: Optional[TinyRelevanceRanker] = None,
    selection_limit: int = 3,
) -> BrainDecision:
    g = parse_guidance(guidance)
    query_terms = informative_query_terms(query, g)[:16]
    intent = classify_query_intent(query_terms, g)
    meta_query = _query_is_meta(query_terms)

    packets: List[BrainCandidatePacket] = []
    features_by_id: Dict[str, PairFeatures | None] = {}

    for rank, item in enumerate(candidates, start=1):
        blob = _chunk_blob(item)
        lowered = blob.lower()
        features = item.ranker_features if item.ranker_features is not None else (ranker.forward(query, blob, guidance_text) if ranker is not None else None)
        if item.ranker_features is None and features is not None:
            item.ranker_features = features
        features_by_id[str(item.chunk.chunk_id)] = features
        activation_head, activation_energy = _activation_summary(features)
        overlap_terms = [term for term in query_terms if term in lowered]
        meta_source = _is_meta_source(item)
        source_bonus = _source_bonus(intent, item.chunk.source_type or '', meta_source)
        structural_bonus = _structural_bonus(intent, item)
        overlap_bonus = 0.12 * len(overlap_terms)
        model_prob = float(features.prob) if features is not None else float(item.rerank_score)
        activation_terms = [tok for _, tok in _token_scores_from_features(ranker, features, getattr(features, 'c_ids', []))[:6]]
        item.activation_guided_terms = list(activation_terms)
        brain_score = (
            0.35 * float(item.final_score)
            + 2.40 * model_prob
            + overlap_bonus
            + 0.03 * min(8.0, activation_energy)
            + source_bonus
            + structural_bonus
        )
        if meta_source and not meta_query:
            brain_score *= 0.62
        packet = BrainCandidatePacket(
            chunk_id=str(item.chunk.chunk_id),
            library_id=str(item.chunk.library_id),
            source_type=str(item.chunk.source_type),
            source_path=str(item.chunk.source_path),
            heading=str(item.chunk.heading),
            candidate_rank=rank,
            lexical_score=float(item.lexical_score),
            vector_score=float(item.vector_score),
            rerank_score=float(item.rerank_score),
            final_score=float(item.final_score),
            brain_score=float(brain_score),
            overlap_terms=overlap_terms[:8],
            overlap_count=len(overlap_terms),
            activation_head=activation_head,
            activation_energy=float(activation_energy),
            activation_terms=activation_terms[:6],
            source_match=source_bonus > 0.0,
            meta_source=meta_source,
            chunk_kind=str(item.chunk.chunk_kind),
            line_span=f'{item.chunk.line_start}-{item.chunk.line_end}',
            recipe_role=_recipe_chunk_role(item) if intent == 'recipe' else '',
            recipe_group=_recipe_group_key(item) if intent == 'recipe' else '',
        )
        item.brain_score = float(brain_score)
        packets.append(packet)

    packets.sort(key=lambda packet: packet.brain_score, reverse=True)

    if intent == 'recipe' and packets and _is_recipe_action_query_text(query):
        if packets[0].recipe_role != 'instructions':
            top_score = packets[0].brain_score
            for idx, packet in enumerate(packets[1:], start=1):
                if packet.recipe_role == 'instructions' and packet.brain_score >= top_score * 0.85:
                    promoted = packets.pop(idx)
                    packets.insert(0, promoted)
                    break

    similarity_map: Dict[tuple[str, str], float] = {}
    for i in range(len(packets)):
        fa = _feature_vector(features_by_id.get(packets[i].chunk_id))
        for j in range(i + 1, len(packets)):
            fb = _feature_vector(features_by_id.get(packets[j].chunk_id))
            sim = cosine_similarity(fa, fb) if fa and fb and len(fa) == len(fb) else 0.0
            similarity_map[(packets[i].chunk_id, packets[j].chunk_id)] = float(sim)

    if packets:
        top_id = packets[0].chunk_id
        packets[0].activation_similarity_to_top = 1.0
        for packet in packets[1:]:
            packet.activation_similarity_to_top = similarity_map.get((top_id, packet.chunk_id), similarity_map.get((packet.chunk_id, top_id), 0.0))

    selected: List[BrainCandidatePacket] = []
    if packets:
        selected.append(packets[0])
        top_score = packets[0].brain_score
        for packet in packets[1:]:
            if len(selected) >= max(1, selection_limit):
                break
            within_range = packet.brain_score >= top_score * 0.78 or packet.brain_score >= top_score - 0.75
            complementary = True
            if selected:
                similarities = [
                    similarity_map.get((packet.chunk_id, prior.chunk_id), similarity_map.get((prior.chunk_id, packet.chunk_id), 0.0))
                    for prior in selected
                ]
                complementary = bool(similarities) and max(similarities) <= 0.90
            if intent == 'code_project':
                allowed = packet.source_type in {'code', 'docs', 'specs'}
            elif intent == 'recipe':
                allowed = packet.source_type in {'recipes', 'docs'}
                if allowed and selected:
                    same_recipe = [prior for prior in selected if packet.recipe_group and prior.recipe_group and prior.recipe_group == packet.recipe_group]
                    if same_recipe:
                        prior_roles = {prior.recipe_role for prior in same_recipe}
                        if packet.recipe_role in prior_roles:
                            allowed = False
                        elif packet.recipe_role != 'instructions' and 'instructions' not in prior_roles:
                            allowed = False
                if allowed and _is_recipe_action_query_text(query):
                    if packet.recipe_role == 'metadata' and not any(pr.recipe_role == 'instructions' for pr in selected):
                        allowed = False
            else:
                allowed = True
            if within_range and complementary and allowed:
                selected.append(packet)

    composition_mode, mode_reasons = _composition_mode(intent, selected, similarity_map)
    selected_ids = [packet.chunk_id for packet in selected]
    dropped_ids = [packet.chunk_id for packet in packets if packet.chunk_id not in set(selected_ids)]

    activation_expansion_terms: List[str] = []
    seen_terms = set(query_terms)
    for packet in selected[:2]:
        for term in packet.activation_terms:
            if term not in seen_terms:
                activation_expansion_terms.append(term)
                seen_terms.add(term)
            if len(activation_expansion_terms) >= 8:
                break
        if len(activation_expansion_terms) >= 8:
            break

    gap = 0.0
    if len(packets) >= 2:
        gap = max(0.0, packets[0].brain_score - packets[1].brain_score)
    confidence = 0.18
    if packets:
        confidence += min(0.42, 0.10 * max(0.0, packets[0].brain_score))
    confidence += min(0.16, 0.22 * gap)
    confidence += min(0.14, 0.05 * len(selected_ids))
    if all(packet.source_match for packet in selected):
        confidence += 0.06
    if composition_mode != 'use_one' and activation_expansion_terms:
        confidence += 0.03
    confidence = min(0.99, confidence)

    reason_flags = list(dict.fromkeys(mode_reasons + [
        'activation_threaded_rerank',
        'activation_guided_expansion' if activation_expansion_terms else 'keyword_expansion_fallback',
        'overlap_focus' if any(packet.overlap_count for packet in selected) else 'low_overlap',
        'source_bias_applied' if any(packet.source_match for packet in packets) else 'source_bias_neutral',
    ]))

    return BrainDecision(
        intent=intent,
        composition_mode=composition_mode,
        selected_chunk_ids=selected_ids,
        dropped_chunk_ids=dropped_ids,
        confidence=float(confidence),
        reason_flags=reason_flags,
        candidate_packets=[packet.to_dict() for packet in packets[:8]],
        activation_expansion_terms=activation_expansion_terms,
    )


def apply_brain_decision(candidates: Sequence[RetrievedChunk], decision: BrainDecision, limit: int) -> List[RetrievedChunk]:
    by_id = {item.chunk.chunk_id: item for item in candidates}
    ordered: List[RetrievedChunk] = []
    for chunk_id in decision.selected_chunk_ids:
        item = by_id.get(chunk_id)
        if item is not None and item not in ordered:
            ordered.append(item)
    remainder = [item for item in candidates if item not in ordered]
    remainder.sort(key=lambda item: getattr(item, 'brain_score', item.final_score), reverse=True)
    ordered.extend(remainder)
    return ordered[:max(1, limit)]
