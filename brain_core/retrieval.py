from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Literal, Sequence, Tuple

from .chunking import Chunk, sanitize_library_id
from .reasoning_bridge import build_reasoning_trace, dot_product_reasoned, stable_query_id, trace_to_dict
from .text_utils import STOPWORDS, tokenize
from .vector_store import hashed_text_vector


@dataclass
class RetrievedChunk:
    chunk: Chunk
    lexical_score: float
    vector_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0
    brain_score: float = 0.0
    reasoning_trace: Dict[str, Any] | None = None
    ranker_features: Any | None = None
    activation_guided_terms: List[str] = field(default_factory=list)


GUIDANCE_KEYS = ('task', 'domain', 'prefer_sources', 'avoid_sources', 'required_terms', 'max_passes', 'library_id')

_FALLBACK_ARTIFACT_CACHE: Dict[Tuple[int, str, str, str], Dict] = {}
_RUNTIME_ARTIFACT_CACHE: Dict[str, Dict[str, Any]] = {}

QUERY_FILLER_TERMS = {
    'how', 'make', 'making', 'cook', 'cooking', 'prepare', 'preparing',
    'recipe', 'recipes', 'dish', 'dishes', 'meal', 'meals', 'method', 'methods',
    'step', 'steps', 'instruction', 'instructions', 'guide', 'show', 'tell',
    'build', 'building', 'create', 'creating', 'want', 'need', 'help',
}

RECIPE_HINT_TERMS = {
    'egg', 'eggs', 'omelet', 'omelette', 'scramble', 'scrambled', 'frittata', 'shakshuka',
    'toast', 'bread', 'pancake', 'pumpkin', 'squash', 'apple', 'oatmeal', 'mushroom',
    'mushrooms', 'potato', 'potatoes', 'breakfast', 'brunch', 'lunch', 'dinner', 'snack',
    'ingredient', 'ingredients', 'cook', 'cooking', 'recipe', 'recipes', 'dish', 'dishes',
    'meal', 'meals', 'food', 'bake', 'baked', 'autumn', 'fall', 'cozy', 'comfort',
    'comforting', 'seasonal', 'morning', 'beverage', 'beverages', 'drink', 'drinks',
    'smoothie', 'smoothies', 'lemonade', 'juice', 'tea', 'coffee', 'latte', 'iced',
}


CODE_HINT_TERMS = {
    'python', 'app', 'application', 'project', 'program', 'game', '3d', '2d', 'engine',
    'render', 'renderer', 'graphics', 'window', 'loop', 'framework', 'api', 'cli',
    'tool', 'library', 'module', 'package', 'pygame', 'opengl', 'three', 'threejs',
    'website', 'web', 'html', 'css', 'javascript', 'frontend', 'backend', 'spa', 'router',
    'route', 'refresh', '404', 'nav', 'navigation', 'modal', 'dialog', 'scroll',
}

RECIPE_WEAK_TERMS = {
    'recipe', 'recipes', 'dish', 'dishes', 'meal', 'meals', 'food', 'breakfast', 'lunch', 'dinner'
}

CODE_WEAK_TERMS = {
    'app', 'application', 'project', 'program', 'code', 'library', 'module', 'package', 'tool'
}


def _is_normalized_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item == item.lower() for item in value)


def _looks_normalized_guidance(guidance: Any) -> bool:
    if not isinstance(guidance, dict):
        return False
    if len(guidance) != len(GUIDANCE_KEYS):
        return False
    if set(guidance.keys()) != set(GUIDANCE_KEYS):
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
    if not isinstance(guidance.get('library_id'), str):
        return False
    return True


def parse_guidance(guidance: dict | None) -> dict:
    if _looks_normalized_guidance(guidance):
        return guidance
    g = guidance or {}
    raw_library_id = str(g.get('library_id', '')).strip()
    return {
        'task': str(g.get('task', '')).strip(),
        'domain': str(g.get('domain', '')).strip(),
        'prefer_sources': [str(x).lower() for x in g.get('prefer_sources', [])],
        'avoid_sources': [str(x).lower() for x in g.get('avoid_sources', [])],
        'required_terms': [str(x).lower() for x in g.get('required_terms', [])],
        'max_passes': int(g.get('max_passes', 1)),
        'library_id': sanitize_library_id(raw_library_id) if raw_library_id else '',
    }


def build_query_text(query: str, guidance: dict | None) -> str:
    g = parse_guidance(guidance)
    extra = ' '.join([g['task'], g['domain']] + g['required_terms'])
    return (query + ' ' + extra).strip()


def build_query_text_from_parsed(query: str, g: dict) -> str:
    extra = ' '.join([g['task'], g['domain']] + g['required_terms'])
    return (query + ' ' + extra).strip()


TOKEN_ALIAS_VARIANTS = {
    'website': ['web', 'html', 'css', 'frontend', 'site'],
    'web': ['website', 'html', 'css', 'frontend'],
    'html': ['web', 'website', 'markup'],
    'css': ['web', 'website', 'style', 'layout'],
    'nav': ['navigation', 'menu', 'header'],
    'navbar': ['nav', 'navigation', 'header'],
    'scroll': ['sticky', 'hide', 'show'],
    'spa': ['router', 'route', 'history', 'index'],
}


def _token_variants(tok: str) -> List[str]:
    variants = [tok]
    if len(tok) > 4 and tok.endswith('ies'):
        variants.append(tok[:-3] + 'y')
    elif len(tok) > 3 and tok.endswith('es') and tok[-3] in {'s', 'x', 'z'}:
        variants.append(tok[:-2])
    elif len(tok) > 3 and tok.endswith('s') and not tok.endswith('ss'):
        variants.append(tok[:-1])
    variants.extend(TOKEN_ALIAS_VARIANTS.get(tok, []))
    out: List[str] = []
    seen = set()
    for item in variants:
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def informative_query_terms(query: str, guidance: dict | None = None) -> List[str]:
    g = parse_guidance(guidance)
    out: List[str] = []
    seen = set()
    for tok in tokenize(build_query_text_from_parsed(query, g)):
        if tok in STOPWORDS or tok in QUERY_FILLER_TERMS or len(tok) < 2:
            continue
        for variant in _token_variants(tok):
            if variant not in seen:
                out.append(variant)
                seen.add(variant)
    for tok in g['required_terms']:
        tok = tok.strip().lower()
        if not tok:
            continue
        for variant in _token_variants(tok):
            if variant not in seen:
                out.append(variant)
                seen.add(variant)
    return out

def _query_terms_from_parsed(query: str, g: dict) -> List[str]:
    return informative_query_terms(query, g)


QueryIntent = Literal['general', 'recipe', 'code_project']


def classify_query_intent(q_tokens: Sequence[str], g: dict | None = None) -> QueryIntent:
    parsed = parse_guidance(g)
    token_set = set(q_tokens)
    library_id = parsed.get('library_id', '')
    if library_id == 'food' or token_set & RECIPE_HINT_TERMS:
        return 'recipe'
    if token_set & CODE_HINT_TERMS:
        return 'code_project'
    return 'general'


def anchor_query_terms(q_tokens: Sequence[str], intent: QueryIntent) -> List[str]:
    if intent == 'recipe':
        weak = RECIPE_WEAK_TERMS
    elif intent == 'code_project':
        weak = CODE_WEAK_TERMS
    else:
        weak = set()
    anchors = [tok for tok in q_tokens if tok not in weak]
    if not anchors:
        anchors = list(q_tokens)
    return anchors[:8]


def _chunk_allowed(chunk: Chunk, g: dict) -> bool:
    library_id = g.get('library_id', '')
    if library_id and sanitize_library_id(chunk.library_id or '') != library_id:
        return False
    return True


META_SOURCE_STEMS = {'library_input_notes', 'retrieval_notes', 'readme'}
META_QUERY_TERMS = {'library', 'libraries', 'retrieval', 'index', 'chunk', 'chunks', 'vocab', 'guidance', 'input', 'pipeline', 'corpus', 'architecture'}


RECIPE_ACTION_PATTERNS = (
    'how do i make',
    'how to make',
    'how do i cook',
    'how to cook',
    'how do i prepare',
    'how to prepare',
    'recipe for',
)


def _is_recipe_action_query(query: str) -> bool:
    q = str(query or '').strip().lower()
    if not q:
        return False
    if any(pattern in q for pattern in RECIPE_ACTION_PATTERNS):
        return True
    return q.startswith('make ') or q.startswith('cook ') or q.startswith('prepare ')


def _is_food_source_path(source_path: str) -> bool:
    path = str(source_path or '').replace('\\', '/').lower()
    return '/food/' in path or path.startswith('recipes/food/') or path.startswith('docs/food/')


def _is_meta_source_path(source_path: str) -> bool:
    path = str(source_path or '').replace('\\', '/').lower()
    stem = Path(path).stem
    return stem in META_SOURCE_STEMS


def _meta_source_penalty(score: float, chunk: Chunk, q_tokens: Sequence[str], intent: QueryIntent) -> float:
    if not _is_meta_source_path(chunk.source_path):
        return score
    token_set = set(q_tokens)
    if token_set & META_QUERY_TERMS:
        return score
    if intent == 'code_project':
        return score * 0.18
    if intent == 'recipe':
        return score * 0.22
    return score * 0.35


def _apply_heading_focus_bias(score: float, q_tokens: Sequence[str], heading_set: set[str], g: dict) -> float:
    if g.get('required_terms'):
        return score
    if len(q_tokens) > 3:
        return score
    heading_matches = sum(1 for tok in q_tokens if tok in heading_set)
    if heading_matches:
        return score * (1.0 + 0.18 * heading_matches)
    return score * 0.82


def _runtime_cache_key(retrieval_artifacts: Dict) -> str:
    digest = hashlib.sha1()
    chunk_lengths = retrieval_artifacts.get('chunk_lengths', [])
    heading_blobs = retrieval_artifacts.get('heading_blobs', [])
    keyword_lists = retrieval_artifacts.get('keyword_lists', [])
    digest.update(str(len(chunk_lengths)).encode('utf-8'))
    digest.update(b'|')
    digest.update(str(sum(int(x) for x in chunk_lengths)).encode('utf-8'))
    digest.update(b'|')
    if heading_blobs:
        digest.update(str(heading_blobs[0]).encode('utf-8', errors='replace'))
        digest.update(b'|')
        digest.update(str(heading_blobs[-1]).encode('utf-8', errors='replace'))
    digest.update(b'|')
    digest.update(str(len(keyword_lists)).encode('utf-8'))
    return digest.hexdigest()


def _runtime_artifact_cache(retrieval_artifacts: Dict) -> Dict[str, Any]:
    cache_key = _runtime_cache_key(retrieval_artifacts)
    runtime = _RUNTIME_ARTIFACT_CACHE.get(cache_key)
    if runtime is None:
        runtime = {
            'chunk_term_sets': [set(row) for row in retrieval_artifacts.get('chunk_term_lists', [])],
            'keyword_sets': [set(row) for row in retrieval_artifacts.get('keyword_lists', [])],
            'heading_sets': [set(tokenize(blob)) for blob in retrieval_artifacts.get('heading_blobs', [])],
        }
        _RUNTIME_ARTIFACT_CACHE[cache_key] = runtime
    return runtime


def _lexical_score_from_cache(
    query: str,
    chunk: Chunk,
    chunk_idx: int,
    q_tokens: Sequence[str],
    anchor_terms: Sequence[str],
    intent: QueryIntent,
    idf: Dict[str, float],
    g: dict,
    retrieval_artifacts: Dict,
    base_score: float,
) -> float:
    runtime = _runtime_artifact_cache(retrieval_artifacts)
    chunk_term_sets = runtime.get('chunk_term_sets', [])
    keyword_sets = runtime.get('keyword_sets', [])
    heading_sets = runtime.get('heading_sets', [])
    term_set = chunk_term_sets[chunk_idx] if chunk_idx < len(chunk_term_sets) else set()
    kw_set = keyword_sets[chunk_idx] if chunk_idx < len(keyword_sets) else set()
    heading_set = heading_sets[chunk_idx] if chunk_idx < len(heading_sets) else set()

    score = base_score
    score += 0.22 * sum(1 for tok in q_tokens if tok in kw_set)
    score += 0.38 * sum(1 for tok in q_tokens if tok in heading_set)

    anchor_heading = sum(1 for tok in anchor_terms if tok in heading_set)
    anchor_keywords = sum(1 for tok in anchor_terms if tok in kw_set)
    anchor_body = sum(1 for tok in anchor_terms if tok in term_set)
    matched_anchor_count = sum(1 for tok in anchor_terms if tok in heading_set or tok in kw_set or tok in term_set)
    if anchor_heading:
        score += 1.45 * anchor_heading
    if anchor_keywords:
        score += 0.75 * anchor_keywords
    if anchor_body:
        score += 0.22 * anchor_body
    if anchor_terms and matched_anchor_count == 0:
        score *= 0.62 if intent != 'general' else 0.78
    if intent == 'code_project' and len(anchor_terms) >= 2:
        important_code_terms = {'3d', '2d', 'game', 'graphics', 'render', 'engine', 'window', 'loop'}
        need_matches = 2 if any(tok in important_code_terms for tok in anchor_terms) else 1
        if matched_anchor_count < need_matches:
            score *= 0.55

    if chunk.chunk_kind == 'code':
        code_terms = {'def', 'class', 'return', 'function', 'export', 'import'}
        code_overlap = sum(1 for tok in q_tokens if tok in code_terms or tok == chunk.symbol_name.lower())
        score += 0.15 * code_overlap
    score = _apply_heading_focus_bias(score, anchor_terms or q_tokens, heading_set, g)

    if intent == 'recipe':
        recipe_action = _is_recipe_action_query(query)
        food_source = _is_food_source_path(chunk.source_path)
        if chunk.source_type == 'recipes':
            score *= 1.34 if recipe_action else 1.16
        elif chunk.source_type in {'docs', 'specs', 'code'}:
            if recipe_action:
                score *= 0.82 if food_source else 0.34
            else:
                score *= 0.86 if food_source else 0.72
    elif intent == 'code_project':
        if chunk.source_type in {'docs', 'specs'}:
            score *= 1.16
        elif chunk.source_type == 'code':
            score *= 1.06

    score = _meta_source_penalty(score, chunk, q_tokens, intent)
    if g['prefer_sources'] and chunk.source_type in g['prefer_sources']:
        score *= 1.20
    if g['avoid_sources'] and chunk.source_type in g['avoid_sources']:
        score *= 0.70
    req = g['required_terms']
    if req:
        matched = sum(1 for term in req if term in term_set or term in heading_set)
        if matched == 0:
            score *= 0.45
        else:
            score *= 1.0 + 0.12 * matched
    return score


def lexical_score_from_parsed(query: str, chunk: Chunk, idf: Dict[str, float], g: dict) -> float:
    if not _chunk_allowed(chunk, g):
        return 0.0
    q_tokens = _query_terms_from_parsed(query, g)
    if not q_tokens:
        return 0.0
    intent = classify_query_intent(q_tokens, g)
    anchor_terms = anchor_query_terms(q_tokens, intent)
    c_tokens = tokenize(' '.join([chunk.text, chunk.heading, chunk.source_path, chunk.symbol_name]))
    c_set = set(c_tokens)
    heading_text = ' '.join([
        chunk.heading,
        chunk.source_path,
        chunk.symbol_name,
        chunk.source_type,
        chunk.library_id,
    ]).lower()
    heading_set = set(tokenize(heading_text))
    score = 0.0
    for tok in q_tokens:
        if tok in c_set:
            score += idf.get(tok, 1.0)
    score += 0.22 * sum(1 for tok in q_tokens if tok in chunk.keyword_list)
    score += 0.38 * sum(1 for tok in q_tokens if tok in heading_set)
    anchor_heading = sum(1 for tok in anchor_terms if tok in heading_set)
    anchor_keywords = sum(1 for tok in anchor_terms if tok in chunk.keyword_list)
    anchor_body = sum(1 for tok in anchor_terms if tok in c_set)
    matched_anchor_count = sum(1 for tok in anchor_terms if tok in heading_set or tok in chunk.keyword_list or tok in c_set)
    score += 1.45 * anchor_heading + 0.75 * anchor_keywords + 0.22 * anchor_body
    if anchor_terms and matched_anchor_count == 0:
        score *= 0.62 if intent != 'general' else 0.78
    if intent == 'code_project' and len(anchor_terms) >= 2:
        important_code_terms = {'3d', '2d', 'game', 'graphics', 'render', 'engine', 'window', 'loop'}
        need_matches = 2 if any(tok in important_code_terms for tok in anchor_terms) else 1
        if matched_anchor_count < need_matches:
            score *= 0.55
    if chunk.chunk_kind == 'code':
        code_terms = {'def', 'class', 'return', 'function', 'export', 'import'}
        code_overlap = sum(1 for tok in q_tokens if tok in code_terms or tok == chunk.symbol_name.lower())
        score += 0.15 * code_overlap
    score = _apply_heading_focus_bias(score, anchor_terms or q_tokens, heading_set, g)
    if intent == 'recipe':
        recipe_action = _is_recipe_action_query(query)
        food_source = _is_food_source_path(chunk.source_path)
        if chunk.source_type == 'recipes':
            score *= 1.34 if recipe_action else 1.16
        elif chunk.source_type in {'docs', 'specs', 'code'}:
            if recipe_action:
                score *= 0.82 if food_source else 0.34
            else:
                score *= 0.86 if food_source else 0.72
    elif intent == 'code_project':
        if chunk.source_type in {'docs', 'specs'}:
            score *= 1.16
        elif chunk.source_type == 'code':
            score *= 1.06
    if g['prefer_sources'] and chunk.source_type in g['prefer_sources']:
        score *= 1.20
    if g['avoid_sources'] and chunk.source_type in g['avoid_sources']:
        score *= 0.70
    req = g['required_terms']
    if req:
        matched = sum(1 for term in req if term in c_set or term in heading_set)
        if matched == 0:
            score *= 0.45
        else:
            score *= 1.0 + 0.12 * matched
    return score


def lexical_score(query: str, chunk: Chunk, idf: Dict[str, float], guidance: dict | None = None) -> float:
    return lexical_score_from_parsed(query, chunk, idf, parse_guidance(guidance))


def _allowed_candidate_indices(chunks: Sequence[Chunk], g: dict, retrieval_artifacts: Dict | None = None) -> set[int] | None:
    library_id = g.get('library_id', '')
    if not library_id:
        return None
    if retrieval_artifacts is not None:
        buckets = retrieval_artifacts.get('library_id_buckets', {})
        if library_id in buckets:
            return set(int(x) for x in buckets[library_id])
    return {idx for idx, chunk in enumerate(chunks) if _chunk_allowed(chunk, g)}


def _build_fallback_retrieval_artifacts(chunks: Sequence[Chunk]) -> Dict:
    postings: Dict[str, List[List[int]]] = {}
    chunk_lengths: List[int] = []
    chunk_term_lists: List[List[str]] = []
    heading_blobs: List[str] = []
    keyword_lists: List[List[str]] = []
    avg_len_total = 0

    for idx, chunk in enumerate(chunks):
        body_tokens = [
            tok for tok in tokenize(' '.join([
                chunk.text,
                chunk.heading,
                chunk.source_path,
                chunk.symbol_name,
            ]))
            if tok not in STOPWORDS and len(tok) >= 2
        ]
        counts: Dict[str, int] = {}
        for tok in body_tokens:
            counts[tok] = counts.get(tok, 0) + 1
        for tok, tf in counts.items():
            postings.setdefault(tok, []).append([idx, tf])
        chunk_term_lists.append(sorted(counts.keys()))
        chunk_lengths.append(len(body_tokens))
        avg_len_total += len(body_tokens)
        heading_blobs.append(' '.join([
            chunk.heading,
            chunk.source_path,
            chunk.symbol_name,
            chunk.source_type,
            chunk.library_id,
        ]).lower())
        keyword_lists.append(list(dict.fromkeys(tok.lower() for tok in chunk.keyword_list if tok.strip())))

    return {
        'postings': postings,
        'chunk_lengths': chunk_lengths,
        'chunk_term_lists': chunk_term_lists,
        'heading_blobs': heading_blobs,
        'keyword_lists': keyword_lists,
        'avg_chunk_length': (avg_len_total / max(1, len(chunks))),
    }


def _fallback_cache_key(chunks: Sequence[Chunk]) -> Tuple[int, str, str, str]:
    chunk_count = len(chunks)
    first_chunk_id = chunks[0].chunk_id if chunk_count else ''
    last_chunk_id = chunks[-1].chunk_id if chunk_count else ''
    digest = hashlib.sha1()
    for chunk in chunks:
        digest.update(chunk.chunk_id.encode('utf-8', errors='replace'))
        digest.update(b'\x1f')
    return (chunk_count, digest.hexdigest(), first_chunk_id, last_chunk_id)


def _get_fallback_retrieval_artifacts(chunks: Sequence[Chunk]) -> Dict:
    cache_key = _fallback_cache_key(chunks)
    cached = _FALLBACK_ARTIFACT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    artifacts = _build_fallback_retrieval_artifacts(chunks)
    _FALLBACK_ARTIFACT_CACHE[cache_key] = artifacts
    return artifacts


def _score_retrieved_candidates(
    query: str,
    chunks: Sequence[Chunk],
    idf: Dict[str, float],
    top_k: int,
    g: dict,
    q_tokens: Sequence[str],
    anchor_terms: Sequence[str],
    intent: QueryIntent,
    allowed_indices: set[int] | None,
    chunk_vectors: Sequence[Sequence[float]] | None,
    vector_dim: int,
    retrieval_artifacts: Dict,
) -> List[RetrievedChunk]:
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
            if allowed_indices is not None and chunk_idx not in allowed_indices:
                continue
            length = chunk_lengths[chunk_idx] if chunk_idx < len(chunk_lengths) else 0
            denom = tf + k1 * (1.0 - bm25_b + bm25_b * (length / max(1e-9, avg_chunk_length)))
            score = tok_idf * ((tf * (k1 + 1.0)) / max(1e-9, denom))
            lexical_candidates[chunk_idx] = lexical_candidates.get(chunk_idx, 0.0) + score

    if not lexical_candidates:
        return []

    lexical_limit = min(max(top_k * 12, 120), max(len(lexical_candidates), top_k))
    ranked_candidates = sorted(lexical_candidates.items(), key=lambda kv: kv[1], reverse=True)[:lexical_limit]

    query_text = ' '.join(anchor_terms + [tok for tok in q_tokens if tok not in anchor_terms])
    qv = hashed_text_vector(query_text, idf, dim=vector_dim) if chunk_vectors is not None else None
    query_id = stable_query_id(query, g)
    vector_limit = min(len(ranked_candidates), max(top_k * 4, 48))
    scored: List[RetrievedChunk] = []
    for rank, (idx, bm25_score) in enumerate(ranked_candidates):
        chunk = chunks[idx]
        lex = _lexical_score_from_cache(query, chunk, idx, q_tokens, anchor_terms, intent, idf, g, retrieval_artifacts, bm25_score)
        vec = 0.0
        dominant_feature = None
        dominant_contribution = 0.0
        top_feature_indices: List[int] = []
        top_feature_contributions: List[float] = []
        if qv is not None and rank < vector_limit and idx < len(chunk_vectors):
            row = chunk_vectors[idx]
            raw_vec, dominant_feature, dominant_contribution, top_feature_indices, top_feature_contributions = dot_product_reasoned(qv, row)
            vec = max(-1.0, min(1.0, raw_vec))
        trace = build_reasoning_trace(
            query_id=query_id,
            doc_id=chunk.chunk_id,
            bm25_raw=lex,
            vector_raw=vec,
            dominant_feature=dominant_feature,
            dominant_contribution=dominant_contribution,
            top_feature_indices=top_feature_indices,
            top_feature_contributions=top_feature_contributions,
            bm25_weight=1.0,
            vector_weight=3.0,
        )
        scored.append(RetrievedChunk(
            chunk=chunk,
            lexical_score=lex,
            vector_score=vec,
            final_score=trace.final_score,
            reasoning_trace=trace_to_dict(trace),
        ))

    scored.sort(key=lambda r: r.final_score, reverse=True)
    return [item for item in scored[:top_k] if item.final_score > 0.0]


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
    intent = classify_query_intent(q_tokens, g)
    anchor_terms = anchor_query_terms(q_tokens, intent)

    allowed_indices = _allowed_candidate_indices(chunks, g, retrieval_artifacts=retrieval_artifacts)
    if allowed_indices == set():
        return []

    return _score_retrieved_candidates(
        query,
        chunks,
        idf,
        top_k,
        g,
        q_tokens,
        anchor_terms,
        intent,
        allowed_indices,
        chunk_vectors,
        vector_dim,
        retrieval_artifacts,
    )


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
    q_tokens = _query_terms_from_parsed(query, g)
    if not q_tokens:
        return []
    intent = classify_query_intent(q_tokens, g)
    anchor_terms = anchor_query_terms(q_tokens, intent)

    allowed_indices = _allowed_candidate_indices(chunks, g)
    if allowed_indices == set():
        return []

    fallback_artifacts = _get_fallback_retrieval_artifacts(chunks)
    return _score_retrieved_candidates(
        query,
        chunks,
        idf,
        top_k,
        g,
        q_tokens,
        anchor_terms,
        intent,
        allowed_indices,
        chunk_vectors,
        vector_dim,
        fallback_artifacts,
    )
