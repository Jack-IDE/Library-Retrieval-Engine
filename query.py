from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain_core.compressor_io import load_compressor
from brain_core.controller import run_query_controller
from brain_core.indexing import load_index
from brain_core.ranker_io import check_vocab_fingerprint, load_ranker, load_vocab_file
from brain_core.reasoning_bridge import append_traces_jsonl, format_reasoning_trace


def main() -> None:
    parser = argparse.ArgumentParser(description='Run retrieval-guided querying over a library path.')
    parser.add_argument('--index', required=True)
    parser.add_argument('--query', required=True)
    parser.add_argument('--model', default='')
    parser.add_argument('--vocab', default='', help='Optional vocab.json to verify ranker compatibility')
    parser.add_argument('--compressor-model', default='')
    parser.add_argument('--guidance', default='{}', help='JSON guidance object')
    parser.add_argument('--library-id', default='', help='Optional hard library filter when querying a blended index')
    parser.add_argument('--top-k', type=int, default=20)
    parser.add_argument('--top-rerank', type=int, default=5)
    parser.add_argument('--trace-output', default='', help='Optional JSON file for controller trace')
    parser.add_argument('--show-reasoning', action='store_true', help='Print retrieval reasoning for detailed top results')
    parser.add_argument('--reasoning-output', default='', help='Optional JSONL file for top-result retrieval reasoning traces')
    args = parser.parse_args()

    chunks, idf, metadata, vectors = load_index(Path(args.index))
    guidance = json.loads(args.guidance)
    if args.library_id:
        guidance['library_id'] = args.library_id
    vocab = load_vocab_file(args.vocab) if args.vocab else None
    ranker = load_ranker(args.model) if args.model else None
    if ranker is not None and vocab is not None:
        check_vocab_fingerprint(Path(args.model), vocab)
    compressor = load_compressor(args.compressor_model) if args.compressor_model else None
    result = run_query_controller(
        query=args.query,
        chunks=chunks,
        idf=idf,
        guidance=guidance,
        ranker=ranker,
        compressor=compressor,
        chunk_vectors=vectors,
        vector_dim=int(metadata.get('vector_dim', 64)),
        top_k=args.top_k,
        top_rerank=args.top_rerank,
        retrieval_artifacts=metadata.get('retrieval_artifacts'),
    )
    print(result.answer)
    if result.brain_decision:
        print('\nBrain decision:')
        print(f"- intent={result.brain_decision.get('intent', '')} mode={result.brain_decision.get('composition_mode', '')} confidence={float(result.brain_decision.get('confidence', 0.0) or 0.0):.3f}")
        print(f"- selected={', '.join(result.brain_decision.get('selected_chunk_ids', [])[:5]) or '(none)'}")
        print(f"- reasons={', '.join(result.brain_decision.get('reason_flags', [])[:6]) or '(none)'}")
        print(f"- activation_expansion={', '.join(result.brain_decision.get('activation_expansion_terms', [])[:8]) or '(none)'}")
    if result.top_results:
        print('\nDetailed top results:')
        traces = []
        for item in result.top_results:
            c = item.chunk
            print(f'- {c.library_id} :: {c.source_path} :: {c.chunk_id} :: {c.heading} :: lines {c.line_start}-{c.line_end}')
            print(f'  lexical={item.lexical_score:.3f} vector={item.vector_score:.3f} rerank={item.rerank_score:.3f} final={item.final_score:.3f} brain={item.brain_score:.3f}')
            preview = c.text[:220].replace('\n', ' ')
            print(f'  {preview}')
            if item.reasoning_trace:
                from brain_core.reasoning_bridge import ReasoningTrace
                trace = ReasoningTrace(**item.reasoning_trace)
                traces.append(trace)
                if args.show_reasoning:
                    print(format_reasoning_trace(trace))
        if args.reasoning_output and traces:
            append_traces_jsonl(traces, args.reasoning_output)
            print(f'\nWrote retrieval reasoning traces to {args.reasoning_output}')
    else:
        print('\nNo top results found.')

    if args.trace_output:
        payload = {
            'query': args.query,
            'guidance': guidance,
            'answer': result.answer,
            'working_memory': result.working_memory,
            'state': result.state.to_dict(),
            'brain_decision': result.brain_decision,
            'top_results': [
                {
                    'chunk_id': item.chunk.chunk_id,
                    'library_id': item.chunk.library_id,
                    'source_path': item.chunk.source_path,
                    'heading': item.chunk.heading,
                    'line_start': item.chunk.line_start,
                    'line_end': item.chunk.line_end,
                    'preview': item.chunk.text[:240],
                    'final_score': item.final_score,
                    'brain_score': item.brain_score,
                    'lexical_score': item.lexical_score,
                    'vector_score': item.vector_score,
                    'rerank_score': item.rerank_score,
                    'reasoning_trace': item.reasoning_trace,
                    'activation_guided_terms': list(getattr(item, 'activation_guided_terms', [])[:8]),
                }
                for item in result.top_results
            ],
        }
        path = Path(args.trace_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        print(f'\nWrote controller trace to {path}')


if __name__ == '__main__':
    main()
