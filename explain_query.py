from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain_core.indexing import load_index
from brain_core.reasoning_bridge import append_traces_jsonl, format_reasoning_trace
from brain_core.retrieval import parse_guidance, retrieve


def main() -> None:
    parser = argparse.ArgumentParser(description='Explain raw retrieval scoring for a query.')
    parser.add_argument('--index', required=True)
    parser.add_argument('--query', required=True)
    parser.add_argument('--guidance', default='{}')
    parser.add_argument('--top-k', type=int, default=10)
    parser.add_argument('--jsonl-output', default='')
    args = parser.parse_args()

    chunks, idf, metadata, vectors = load_index(Path(args.index))
    guidance = parse_guidance(json.loads(args.guidance))
    results = retrieve(
        query=args.query,
        chunks=chunks,
        idf=idf,
        top_k=args.top_k,
        guidance=guidance,
        chunk_vectors=vectors,
        vector_dim=int(metadata.get('vector_dim', 64)),
        retrieval_artifacts=metadata.get('retrieval_artifacts'),
    )

    if not results:
        print('No retrieval results found.')
        return

    traces = []
    for rank, item in enumerate(results, start=1):
        c = item.chunk
        print(f'{rank}. {c.library_id} :: {c.source_path} :: {c.chunk_id} :: {c.heading}')
        print(f'   lexical={item.lexical_score:.3f} vector={item.vector_score:.3f} final={item.final_score:.3f}')
        if item.reasoning_trace:
            from brain_core.reasoning_bridge import ReasoningTrace
            trace = ReasoningTrace(**item.reasoning_trace)
            traces.append(trace)
            print(format_reasoning_trace(trace))
        preview = c.text[:180].replace('\n', ' ')
        print(f'   {preview}')
        print('-' * 60)

    if args.jsonl_output and traces:
        append_traces_jsonl(traces, args.jsonl_output)
        print(f'Wrote retrieval reasoning traces to {args.jsonl_output}')


if __name__ == '__main__':
    main()
