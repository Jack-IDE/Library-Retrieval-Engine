from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain_core.indexing import load_index
from brain_core.retrieval import build_query_text, parse_guidance, retrieve
from brain_core.training_data import LabeledPair, save_pairs_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description='Build a manual-review JSONL of candidate query/chunk labels.')
    parser.add_argument('--index', required=True)
    parser.add_argument('--queries', required=True, help='JSONL with query_id, query, guidance, split, task, difficulty')
    parser.add_argument('--output', required=True)
    parser.add_argument('--library-id', default='', help='Optional hard library filter applied to every query candidate build')
    parser.add_argument('--top-k', type=int, default=8)
    args = parser.parse_args()

    chunks, idf, metadata, vectors = load_index(Path(args.index))
    vector_dim = int(metadata.get('vector_dim', 64))
    retrieval_artifacts = metadata.get('retrieval_artifacts')
    pairs = []
    with Path(args.queries).open('r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            obj = json.loads(line)
            query_id = str(obj.get('query_id', f'q{line_no:03d}'))
            query = str(obj['query'])
            guidance = parse_guidance(obj.get('guidance', {}))
            if args.library_id:
                guidance['library_id'] = args.library_id
            guidance_text = build_query_text('', guidance)
            split = str(obj.get('split', 'train'))
            task = str(obj.get('task', guidance.get('task', '')))
            difficulty = str(obj.get('difficulty', 'medium'))
            retrieved = retrieve(
                query,
                chunks,
                idf,
                top_k=args.top_k,
                guidance=guidance,
                chunk_vectors=vectors,
                vector_dim=vector_dim,
                retrieval_artifacts=retrieval_artifacts,
            )
            for rank, item in enumerate(retrieved, start=1):
                preview = item.chunk.text[:180].replace('\n', ' ')
                pairs.append(LabeledPair(
                    pair_id=f'{query_id}:{item.chunk.chunk_id}',
                    query_id=query_id,
                    query=query,
                    guidance_text=guidance_text,
                    chunk_id=item.chunk.chunk_id,
                    label=-1,
                    split=split,
                    weight=1.0,
                    source='manual_candidate',
                    notes=f'rank={rank} path={item.chunk.source_path} heading={item.chunk.heading} preview={preview}',
                    task=task,
                    difficulty=difficulty,
                    rationale='',
                    source_type=item.chunk.source_type,
                    library_id=item.chunk.library_id,
                    tags=list(guidance.get('required_terms', [])),
                ))
    save_pairs_jsonl(args.output, pairs)
    print(f'Wrote {len(pairs)} manual-review candidates to {args.output}')


if __name__ == '__main__':
    main()
