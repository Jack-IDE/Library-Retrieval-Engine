from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field, fields
from pathlib import Path
from typing import Dict, List, Sequence


@dataclass
class LabeledPair:
    pair_id: str
    query: str
    guidance_text: str
    chunk_id: str
    label: int = -1
    split: str = 'train'
    weight: float = 1.0
    source: str = 'manual'
    notes: str = ''
    query_id: str = ''
    task: str = ''
    difficulty: str = 'medium'
    rationale: str = ''
    source_type: str = ''
    hard_negative_for: str = ''
    tags: List[str] = field(default_factory=list)


def save_pairs_jsonl(path: str | Path, pairs: Sequence[LabeledPair]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for pair in pairs:
            f.write(json.dumps(asdict(pair), ensure_ascii=False) + '\n')


def load_pairs_jsonl(path: str | Path) -> List[LabeledPair]:
    path = Path(path)
    out: List[LabeledPair] = []
    valid_fields = {f.name for f in fields(LabeledPair)}
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            if 'tags' not in obj or obj['tags'] is None:
                obj['tags'] = []
            filtered = {k: v for k, v in obj.items() if k in valid_fields}
            out.append(LabeledPair(**filtered))
    return out


def merge_pair_sets(primary_pairs: Sequence[LabeledPair], secondary_pairs: Sequence[LabeledPair]) -> List[LabeledPair]:
    """
    Merge pair sets using (query, chunk_id) as the semantic key.
    Pairs from primary_pairs override pairs from secondary_pairs.
    This is useful when manual labels should override weak supervision.
    """
    merged: Dict[tuple[str, str], LabeledPair] = {}
    for pair in secondary_pairs:
        merged[(pair.query.strip().lower(), pair.chunk_id)] = pair
    for pair in primary_pairs:
        merged[(pair.query.strip().lower(), pair.chunk_id)] = pair
    return list(merged.values())


def resolve_pairs_to_examples(pairs: Sequence[LabeledPair], chunk_by_id: Dict[str, object]):
    examples = []
    for pair in pairs:
        if int(pair.label) not in (0, 1):
            continue
        chunk = chunk_by_id.get(pair.chunk_id)
        if chunk is None:
            continue
        source_type = pair.source_type or getattr(chunk, 'source_type', '')
        examples.append({
            'pair_id': pair.pair_id,
            'query_id': pair.query_id,
            'query': pair.query,
            'guidance_text': pair.guidance_text,
            'chunk_id': pair.chunk_id,
            'chunk_text': chunk.text,
            'label': int(pair.label),
            'split': pair.split,
            'weight': float(pair.weight),
            'source': pair.source,
            'notes': pair.notes,
            'task': pair.task,
            'difficulty': pair.difficulty,
            'rationale': pair.rationale,
            'source_type': source_type,
            'hard_negative_for': pair.hard_negative_for,
            'tags': list(pair.tags),
        })
    return examples
