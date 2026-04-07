from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .chunking import Chunk
from .retrieval import retrieve
from .text_utils import keywords, sentence_split
from .training_data import LabeledPair


@dataclass
class CompressorExample:
    query: str
    guidance_text: str
    sentence: str
    label: int
    split: str = 'train'
    query_ids: List[int] = field(default_factory=list)
    sentence_ids: List[int] = field(default_factory=list)
    guidance_ids: List[int] = field(default_factory=list)


def _query_from_chunk(chunk: Chunk) -> List[str]:
    queries: List[str] = []
    base_terms = ' '.join(chunk.keyword_list[:6])
    queries.append(f'find details {base_terms}')
    if chunk.heading and chunk.heading != 'root':
        queries.append(f'{chunk.heading} implementation details')
    if chunk.symbol_name:
        queries.append(f'{chunk.symbol_name} implementation summary')
        queries.append(f'how does {chunk.symbol_name} work')
    stem = chunk.source_path.split('/')[-1].rsplit('.', 1)[0]
    queries.append(f'{stem} summary')
    text = chunk.text.lower()
    if any(tok in text for tok in ['retrieve', 'retrieval', 'evidence']):
        queries.append('how does the brain interpreter retrieve evidence')
    if any(tok in text for tok in ['controller', 'passes', 'state']):
        queries.append('how does the controller carry state across passes')
    if chunk.chunk_kind == 'code':
        queries.append(f'code path for {stem}')
    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))


def _build_negative_pools(chunks: Sequence[Chunk]):
    all_ids = list(range(len(chunks)))
    by_library: Dict[str, List[int]] = {}
    source_lookup: Dict[int, str] = {}
    library_lookup: Dict[int, str] = {}
    for idx, chunk in enumerate(chunks):
        source_type = chunk.source_type or 'unknown'
        library_id = chunk.library_id or 'library'
        by_library.setdefault(library_id, []).append(idx)
        source_lookup[idx] = source_type
        library_lookup[idx] = library_id
    return all_ids, by_library, source_lookup, library_lookup


def _sample_random_negative_indices(
    chunk_idx: int,
    chunk_source: str,
    chunk_library: str,
    all_ids: Sequence[int],
    by_library: Dict[str, List[int]],
    source_lookup: Dict[int, str],
    library_lookup: Dict[int, str],
    negatives_per_positive: int,
    rng: random.Random,
    blocked: set[int] | None = None,
) -> List[int]:
    blocked = blocked or set()
    same_library = [idx for idx in by_library.get(chunk_library, []) if idx != chunk_idx and idx not in blocked]
    same_library_diff_source = [idx for idx in same_library if source_lookup.get(idx, 'unknown') != chunk_source]
    primary_pool = same_library_diff_source or same_library
    if len(primary_pool) < negatives_per_positive:
        fallback = [
            idx for idx in all_ids
            if idx != chunk_idx and idx not in blocked and library_lookup.get(idx, '') != chunk_library
        ]
        primary_pool = list(dict.fromkeys(primary_pool + fallback))
    if not primary_pool:
        return []
    take = min(negatives_per_positive, len(primary_pool))
    if take >= len(primary_pool):
        return list(primary_pool)
    return rng.sample(primary_pool, take)


def _mine_hard_negative_indices(
    query: str,
    positive_idx: int,
    chunks: Sequence[Chunk],
    chunk_id_to_idx: Dict[str, int],
    idf: Dict[str, float] | None,
    retrieval_artifacts: Dict | None,
    chunk_vectors: Sequence[Sequence[float]] | None,
    vector_dim: int,
    hard_negatives_per_positive: int,
) -> List[int]:
    if not idf or hard_negatives_per_positive <= 0:
        return []
    positive_chunk = chunks[positive_idx]
    retrieved = retrieve(
        query,
        chunks,
        idf,
        top_k=max(20, hard_negatives_per_positive * 6),
        guidance={'library_id': positive_chunk.library_id},
        chunk_vectors=chunk_vectors,
        vector_dim=vector_dim,
        retrieval_artifacts=retrieval_artifacts,
    )
    out: List[int] = []
    seen = set()
    positive_chunk_id = positive_chunk.chunk_id
    for item in retrieved:
        if item.chunk.chunk_id == positive_chunk_id:
            continue
        idx = chunk_id_to_idx.get(item.chunk.chunk_id)
        if idx is None or idx == positive_idx or idx in seen:
            continue
        seen.add(idx)
        out.append(idx)
        if len(out) >= hard_negatives_per_positive:
            break
    return out


def generate_pairs(
    chunks: Sequence[Chunk],
    negatives_per_positive: int = 2,
    seed: int = 42,
    val_fraction: float = 0.15,
    idf: Dict[str, float] | None = None,
    retrieval_artifacts: Dict | None = None,
    chunk_vectors: Sequence[Sequence[float]] | None = None,
    vector_dim: int = 64,
    hard_negatives_per_positive: int = 1,
) -> List[LabeledPair]:
    rng = random.Random(seed)
    pairs: List[LabeledPair] = []
    chunk_list = list(chunks)
    pos_counter = 0
    all_ids, by_library, chunk_source_lookup, chunk_library_lookup = _build_negative_pools(chunk_list)
    chunk_id_to_idx = {item.chunk_id: idx for idx, item in enumerate(chunk_list)}

    for idx, chunk in enumerate(chunk_list):
        chunk_source = chunk.source_type or 'unknown'
        chunk_library = chunk.library_id or 'library'
        guidance = f'library {chunk_library} domain {chunk_source} task find implementation details kind {chunk.chunk_kind}'
        positives = _query_from_chunk(chunk)
        for q in positives:
            split = 'val' if rng.random() < val_fraction else 'train'
            pairs.append(LabeledPair(
                pair_id=f'pos-{pos_counter}',
                query=q,
                guidance_text=guidance,
                chunk_id=chunk.chunk_id,
                label=1,
                split=split,
                weight=1.0,
                source='weak_supervision',
                notes=f'positive from {chunk.source_path}',
                source_type=chunk_source,
                library_id=chunk_library,
            ))

            used_negatives: set[int] = set()
            hard_take = min(max(0, hard_negatives_per_positive), max(0, negatives_per_positive))
            hard_indices = _mine_hard_negative_indices(
                q,
                idx,
                chunk_list,
                chunk_id_to_idx,
                idf,
                retrieval_artifacts,
                chunk_vectors,
                vector_dim,
                hard_take,
            )
            for neg_idx, neg in enumerate(hard_indices):
                used_negatives.add(neg)
                neg_chunk = chunk_list[neg]
                pairs.append(LabeledPair(
                    pair_id=f'hard-neg-{pos_counter}-{neg_idx}',
                    query=q,
                    guidance_text=guidance,
                    chunk_id=neg_chunk.chunk_id,
                    label=0,
                    split=split,
                    weight=1.15,
                    source='weak_supervision_hard_negative',
                    notes=f'hard negative from retrieval near-miss {neg_chunk.source_path}',
                    source_type=neg_chunk.source_type or 'unknown',
                    library_id=neg_chunk.library_id or 'library',
                    hard_negative_for=chunk.chunk_id,
                    tags=['hard_negative', 'retrieval_mined'],
                ))

            remaining = max(0, negatives_per_positive - len(hard_indices))
            random_indices = _sample_random_negative_indices(
                idx,
                chunk_source,
                chunk_library,
                all_ids,
                by_library,
                chunk_source_lookup,
                chunk_library_lookup,
                remaining,
                rng,
                blocked=used_negatives,
            )
            for neg_idx, neg in enumerate(random_indices):
                neg_chunk = chunk_list[neg]
                pairs.append(LabeledPair(
                    pair_id=f'neg-{pos_counter}-{neg_idx}',
                    query=q,
                    guidance_text=guidance,
                    chunk_id=neg_chunk.chunk_id,
                    label=0,
                    split=split,
                    weight=1.0,
                    source='weak_supervision',
                    notes=f'random negative from {neg_chunk.source_path}',
                    source_type=neg_chunk.source_type or 'unknown',
                    library_id=neg_chunk.library_id or 'library',
                ))
            pos_counter += 1
    rng.shuffle(pairs)
    return pairs


def generate_compressor_examples(chunks: Sequence[Chunk], seed: int = 42, val_fraction: float = 0.15) -> List[CompressorExample]:
    rng = random.Random(seed)
    out: List[CompressorExample] = []
    for chunk in chunks:
        sents = sentence_split(chunk.text)
        if not sents:
            continue
        q_list = _query_from_chunk(chunk)
        local_keywords = set(chunk.keyword_list[:8])
        scored = []
        for sent in sents:
            sent_keys = set(keywords(sent, limit=10))
            overlap = len(sent_keys & local_keywords)
            scored.append((overlap, sent))
        scored.sort(key=lambda x: x[0], reverse=True)
        positives = [s for overlap, s in scored[: min(2, len(scored))] if s.strip()]
        negatives = [s for overlap, s in scored[-min(2, len(scored)):] if s.strip()]
        for q in q_list[:3]:
            split = 'val' if rng.random() < val_fraction else 'train'
            guidance = f'library {chunk.library_id or "library"} domain {chunk.source_type} task compress evidence'
            for sent in positives:
                out.append(CompressorExample(query=q, guidance_text=guidance, sentence=sent, label=1, split=split))
            for sent in negatives:
                if sent not in positives:
                    out.append(CompressorExample(query=q, guidance_text=guidance, sentence=sent, label=0, split=split))
    rng.shuffle(out)
    return out
