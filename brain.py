from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from brain_core.chat_adapter import build_structured_output, build_structured_output_from_trace, generate_response, parse_brain_output
from brain_core.chunking import sanitize_library_id

ROOT = Path(__file__).resolve().parent
DEFAULT_LIBRARY = ROOT / 'library'
DEFAULT_INDEX = ROOT / 'index'
DEFAULT_MODELS = ROOT / 'models'
DEFAULT_CHECKPOINTS = ROOT / 'checkpoints'
DEFAULT_VECTOR_DIM = 64
DEFAULT_GUIDANCE = '{"max_passes":1}'
DEMO_GUIDANCE = '{"task":"find implementation details","domain":"brain interpreter","prefer_sources":["specs","code"],"required_terms":["retrieve","compress","evidence"],"max_passes":2}'
DEFAULT_RANKER_MODEL = 'ranker.brrk'
DEFAULT_COMPRESSOR_MODEL = 'compressor.bin'


_RESPONSE_CODE_HINTS = {
    'website', 'web', 'html', 'css', 'spa', 'router', 'route', 'refresh', '404', 'modal',
    'dialog', 'nav', 'scroll', 'listener', 'event', 'form', 'javascript', 'typescript', 'python',
    'node', 'react', 'component', 'api', 'server', 'frontend', 'backend'
}
_RESPONSE_FOOD_HINTS = {
    'food', 'recipe', 'cook', 'make', 'steak', 'egg', 'eggs', 'toast', 'breakfast', 'lunch', 'dinner',
    'soup', 'chicken', 'beef', 'pasta', 'salad'
}


def _merge_guidance(base_guidance: str, extra: dict) -> str:
    try:
        base = json.loads(base_guidance) if base_guidance else {}
        if not isinstance(base, dict):
            base = {}
    except Exception:
        base = {}
    merged = dict(base)
    for key, value in extra.items():
        if key in {'prefer_sources', 'avoid_sources', 'required_terms'}:
            prior = merged.get(key, [])
            if not isinstance(prior, list):
                prior = []
            merged[key] = list(dict.fromkeys([str(x) for x in prior] + [str(x) for x in value]))
        elif value not in ('', None, [], {}):
            merged[key] = value
    if 'max_passes' not in merged:
        merged['max_passes'] = 1
    return json.dumps(merged)


def _response_guidance_patch(query: str, response_mode: str) -> dict:
    q = query.lower()
    tokens = set(q.replace('/', ' ').replace('-', ' ').split())

    mode = response_mode
    if mode == 'auto':
        if tokens & _RESPONSE_CODE_HINTS:
            mode = 'code_assistant'
        elif tokens & _RESPONSE_FOOD_HINTS:
            mode = 'chatbot_food'
        else:
            mode = 'chatbot_general'

    if mode == 'code_assistant':
        return {
            'task': 'find implementation details and debugging guidance',
            'domain': 'code assistant',
            'prefer_sources': ['code', 'docs', 'specs'],
            'avoid_sources': ['recipes'],
        }
    if mode == 'chatbot_food':
        return {
            'task': 'find recipe and cooking guidance',
            'domain': 'food',
            'prefer_sources': ['recipes'],
            'avoid_sources': ['code', 'specs'],
        }
    return {}


def run_step(*args: str) -> None:
    cmd = [sys.executable, *args]
    print('>>', ' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def run_step_capture(*args: str) -> str:
    cmd = [sys.executable, *args]
    print('>>', ' '.join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    return proc.stdout


def _resolve_user_path(raw_path: str) -> Path:
    raw = str(raw_path).strip()
    if not raw:
        raise SystemExit('Expected a non-empty path.')
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()

    cwd_candidate = (Path.cwd() / path).resolve()
    root_candidate = (ROOT / path).resolve()

    if cwd_candidate.exists():
        return cwd_candidate
    if root_candidate.exists():
        return root_candidate
    return cwd_candidate


def _parse_library_specs(values: list[str]) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for value in values:
        raw = str(value).strip()
        if '=' not in raw:
            raise SystemExit(f'Invalid --library-spec {value!r}. Expected LIBRARY_ID=PATH')
        raw_library_id, raw_path = raw.split('=', 1)
        library_id = sanitize_library_id(raw_library_id)
        library_path = raw_path.strip()
        if not library_id or not library_path:
            raise SystemExit(f'Invalid --library-spec {value!r}. Expected LIBRARY_ID=PATH')
        if library_id in seen:
            raise SystemExit(f'Duplicate --library-spec library_id: {library_id}')
        seen.add(library_id)
        out.append((library_id, _resolve_user_path(library_path)))
    return out


def build_pipeline(
    libraries: list[tuple[str, Path]],
    index: Path,
    models: Path,
    checkpoints: Path,
    vector_dim: int,
    chunk_chars: int,
    chunk_overlap: int,
    ranker_epochs: int,
    compressor_epochs: int,
    skip_vocab: bool,
    ranker_arch: str,
    ranker_model_name: str,
    compressor_model_name: str,
) -> None:
    index.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    (checkpoints / 'ranker').mkdir(parents=True, exist_ok=True)
    (checkpoints / 'compressor').mkdir(parents=True, exist_ok=True)

    if not libraries:
        raise SystemExit('No libraries provided for build.')

    if len(libraries) == 1:
        library_id, library = libraries[0]
        build_index_cmd = [
            'build_index.py', '--library', str(library), '--index', str(index), '--vector-dim', str(vector_dim),
            '--chunk-chars', str(chunk_chars), '--chunk-overlap', str(chunk_overlap), '--library-id', library_id,
        ]
    else:
        build_index_cmd = [
            'build_index.py', '--index', str(index), '--vector-dim', str(vector_dim),
            '--chunk-chars', str(chunk_chars), '--chunk-overlap', str(chunk_overlap),
        ]
        for library_id, library in libraries:
            build_index_cmd.extend(['--library-spec', f'{library_id}={library}'])
    run_step(*build_index_cmd)

    run_step('build_training_pairs.py', '--index', str(index), '--output', str(index / 'train_pairs.jsonl'))
    if not skip_vocab:
        vocab_cmd = ['build_vocab.py', '--sources', *[str(path) for _, path in libraries], '--output', str(models / 'vocab.json')]
        run_step(*vocab_cmd)

    ranker_cmd = [
        'train_ranker.py', '--index', str(index), '--pairs', str(index / 'train_pairs.jsonl'),
        '--model', str(models / ranker_model_name), '--checkpoint-dir', str(checkpoints / 'ranker'),
        '--arch', ranker_arch, '--epochs', str(ranker_epochs), '--batch-size', '8',
    ]
    if not skip_vocab:
        ranker_cmd.extend(['--vocab', str(models / 'vocab.json')])
    run_step(*ranker_cmd)

    run_step(
        'train_compressor.py', '--index', str(index), '--model', str(models / compressor_model_name),
        '--checkpoint-dir', str(checkpoints / 'compressor'), '--epochs', str(compressor_epochs), '--batch-size', '8'
    )


def ask_query(
    index: Path,
    models: Path,
    query: str,
    guidance: str,
    trace_output: str = '',
    ranker_model_name: str = DEFAULT_RANKER_MODEL,
    compressor_model_name: str = DEFAULT_COMPRESSOR_MODEL,
    library_id: str = '',
    show_reasoning: bool = False,
    reasoning_output: str = '',
) -> None:
    cmd = [
        'query.py', '--index', str(index), '--model', str(models / ranker_model_name),
        '--compressor-model', str(models / compressor_model_name), '--query', query, '--guidance', guidance,
    ]
    if library_id:
        cmd.extend(['--library-id', library_id])
    vocab_path = models / 'vocab.json'
    if vocab_path.exists():
        cmd.extend(['--vocab', str(vocab_path)])
    if trace_output:
        cmd.extend(['--trace-output', trace_output])
    if show_reasoning:
        cmd.append('--show-reasoning')
    if reasoning_output:
        cmd.extend(['--reasoning-output', reasoning_output])
    run_step(*cmd)



def respond_query(
    index: Path,
    models: Path,
    query: str,
    guidance: str,
    trace_output: str = '',
    ranker_model_name: str = DEFAULT_RANKER_MODEL,
    compressor_model_name: str = DEFAULT_COMPRESSOR_MODEL,
    library_id: str = '',
    show_reasoning: bool = False,
    reasoning_output: str = '',
    response_mode: str = 'auto',
    structured_output: str = '',
    response_output: str = '',
    raw_output: str = '',
    print_json: bool = False,
) -> None:
    effective_guidance = _merge_guidance(guidance, _response_guidance_patch(query, response_mode))

    cmd = [
        'query.py', '--index', str(index), '--model', str(models / ranker_model_name),
        '--compressor-model', str(models / compressor_model_name), '--query', query, '--guidance', effective_guidance,
    ]
    if library_id:
        cmd.extend(['--library-id', library_id])
    vocab_path = models / 'vocab.json'
    if vocab_path.exists():
        cmd.extend(['--vocab', str(vocab_path)])
    temp_trace_path: Path | None = None
    trace_path = Path(trace_output) if trace_output else None
    if trace_path is None:
        fd, tmp_name = tempfile.mkstemp(prefix='brain_respond_trace_', suffix='.json')
        Path(tmp_name).unlink(missing_ok=True)
        temp_trace_path = Path(tmp_name)
        trace_path = temp_trace_path
    cmd.extend(['--trace-output', str(trace_path)])
    if show_reasoning:
        cmd.append('--show-reasoning')
    if reasoning_output:
        cmd.extend(['--reasoning-output', reasoning_output])

    raw_text = run_step_capture(*cmd)

    if raw_output:
        raw_path = Path(raw_output)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw_text, encoding='utf-8')

    structured = None
    if trace_path is not None and trace_path.exists():
        try:
            trace_payload = json.loads(trace_path.read_text(encoding='utf-8'))
            structured = build_structured_output_from_trace(trace_payload, mode=response_mode)
        except Exception:
            structured = None
    if structured is None:
        parsed = parse_brain_output(raw_text)
        structured = build_structured_output(parsed, mode=response_mode)
    response = generate_response(structured)

    if temp_trace_path is not None:
        temp_trace_path.unlink(missing_ok=True)

    if structured_output:
        structured_path = Path(structured_output)
        structured_path.parent.mkdir(parents=True, exist_ok=True)
        structured_path.write_text(json.dumps(structured, indent=2), encoding='utf-8')
        print(f'Wrote structured output to {structured_path}')

    if response_output:
        response_path = Path(response_output)
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response_path.write_text(response + '\n', encoding='utf-8')
        print(f'Wrote generated response to {response_path}')

    if print_json:
        print(json.dumps(structured, indent=2))
        print()

    print(response)

def explain_query(
    index: Path,
    query: str,
    guidance: str,
    library_id: str = '',
    top_k: int = 10,
    reasoning_output: str = '',
) -> None:
    cmd = [
        'explain_query.py', '--index', str(index), '--query', query, '--guidance', guidance, '--top-k', str(top_k),
    ]
    if library_id:
        payload = guidance
        try:
            g = json.loads(guidance) if guidance else {}
            g['library_id'] = library_id
            payload = json.dumps(g)
        except Exception:
            payload = guidance
        cmd = [
            'explain_query.py', '--index', str(index), '--query', query, '--guidance', payload, '--top-k', str(top_k),
        ]
    if reasoning_output:
        cmd.extend(['--jsonl-output', reasoning_output])
    run_step(*cmd)
def ensure_built(
    index: Path,
    models: Path,
    ranker_model_name: str = DEFAULT_RANKER_MODEL,
    compressor_model_name: str = DEFAULT_COMPRESSOR_MODEL,
) -> None:
    missing = []
    if not (index / 'chunks.jsonl').exists():
        missing.append(str(index / 'chunks.jsonl'))
    if not (models / ranker_model_name).exists():
        missing.append(str(models / ranker_model_name))
    if not (models / compressor_model_name).exists():
        missing.append(str(models / compressor_model_name))
    if missing:
        raise SystemExit(
            'Project is not built yet. Missing: ' + ', '.join(missing) + '\n'
            'Run: python3 brain.py build'
        )


def main() -> None:
    parser = argparse.ArgumentParser(description='Simple wrapper for the Brain Library pipeline.')
    parser.add_argument('command', nargs='?', default='help', help='build, build-library, build-multi, ask, respond, explain, demo, smoke, or a direct question')
    parser.add_argument('rest', nargs='*', help='Question text when using ask or direct-question mode')
    parser.add_argument('--library', default=str(DEFAULT_LIBRARY))
    parser.add_argument('--library-id', default='', help='Stable namespace for this library, and optional hard filter at query time')
    parser.add_argument('--library-spec', action='append', default=[], help='Repeat for shared builds: LIBRARY_ID=PATH')
    parser.add_argument('--index', default=str(DEFAULT_INDEX))
    parser.add_argument('--models', default=str(DEFAULT_MODELS))
    parser.add_argument('--checkpoints', default=str(DEFAULT_CHECKPOINTS))
    parser.add_argument('--ranker-model', default=DEFAULT_RANKER_MODEL)
    parser.add_argument('--compressor-model', default=DEFAULT_COMPRESSOR_MODEL)
    parser.add_argument('--vector-dim', type=int, default=DEFAULT_VECTOR_DIM)
    parser.add_argument('--chunk-chars', type=int, default=700)
    parser.add_argument('--chunk-overlap', type=int, default=120)
    parser.add_argument('--ranker-epochs', type=int, default=16)
    parser.add_argument('--arch', default='linear', choices=['linear', 'mlp'])
    parser.add_argument('--compressor-epochs', type=int, default=12)
    parser.add_argument('--skip-vocab', action='store_true')
    parser.add_argument('--guidance', default=DEFAULT_GUIDANCE)
    parser.add_argument('--trace-output', default='')
    parser.add_argument('--show-reasoning', action='store_true', help='For ask/explain: print retrieval reasoning under top results')
    parser.add_argument('--reasoning-output', default='', help='For ask/explain: optional JSONL file for retrieval reasoning traces')
    parser.add_argument('--top-k', type=int, default=10, help='For explain: how many retrieval results to print')
    parser.add_argument('--response-mode', default='auto', choices=['auto', 'chatbot_food', 'chatbot_general', 'code_assistant'], help='For respond: force the response shaping mode')
    parser.add_argument('--structured-output', default='', help='For respond: optional JSON file for parsed structured output')
    parser.add_argument('--response-output', default='', help='For respond: optional text file for generated response')
    parser.add_argument('--raw-output', default='', help='For respond: optional text file for the raw captured query.py output')
    parser.add_argument('--print-json', action='store_true', help='For respond: print the structured JSON before the generated response')
    args = parser.parse_args()

    library = _resolve_user_path(args.library)
    index = _resolve_user_path(args.index)
    models = _resolve_user_path(args.models)
    checkpoints = _resolve_user_path(args.checkpoints)
    ranker_model_name = args.ranker_model
    compressor_model_name = args.compressor_model
    command = args.command
    library_specs = _parse_library_specs(args.library_spec)

    if command == 'build-library':
        if args.library_spec:
            raise SystemExit('build-library uses the bundled merged ./library folder. Do not pass --library-spec.')
        if args.library == str(DEFAULT_LIBRARY):
            library = DEFAULT_LIBRARY.resolve()
        args.library_id = sanitize_library_id(args.library_id or 'example')

    if command in {'build', 'build-library', 'build-multi'}:
        if library_specs and args.library != str(DEFAULT_LIBRARY):
            raise SystemExit('Use either --library for a single-library build or --library-spec for a shared multi-library build, not both.')
        libraries = library_specs or [(sanitize_library_id(args.library_id or library.name), library)]
        build_pipeline(
            libraries,
            index,
            models,
            checkpoints,
            args.vector_dim,
            args.chunk_chars,
            args.chunk_overlap,
            args.ranker_epochs,
            args.compressor_epochs,
            args.skip_vocab,
            args.arch,
            ranker_model_name,
            compressor_model_name,
        )
        print('\nBuild complete. Ask something with: python3 brain.py ask "your question"')
        return

    if command == 'ask':
        if not args.rest:
            raise SystemExit('Usage: python3 brain.py ask "your question"')
        ensure_built(index, models, ranker_model_name, compressor_model_name)
        query_text = ' '.join(args.rest)
        ask_query(
            index,
            models,
            query_text,
            args.guidance,
            args.trace_output,
            ranker_model_name,
            compressor_model_name,
            args.library_id,
            args.show_reasoning,
            args.reasoning_output,
        )
        return

    if command == 'respond':
        if not args.rest:
            raise SystemExit('Usage: python3 brain.py respond "your question"')
        ensure_built(index, models, ranker_model_name, compressor_model_name)
        query_text = ' '.join(args.rest)
        respond_query(
            index,
            models,
            query_text,
            args.guidance,
            args.trace_output,
            ranker_model_name,
            compressor_model_name,
            args.library_id,
            args.show_reasoning,
            args.reasoning_output,
            args.response_mode,
            args.structured_output,
            args.response_output,
            args.raw_output,
            args.print_json,
        )
        return

    if command == 'explain':
        if not args.rest:
            raise SystemExit('Usage: python3 brain.py explain "your question"')
        ensure_built(index, models, ranker_model_name, compressor_model_name)
        explain_query(index, ' '.join(args.rest), args.guidance, args.library_id, args.top_k, args.reasoning_output)
        return

    if command == 'demo':
        if library_specs:
            raise SystemExit('demo uses the bundled single demo library. Use build or build-multi for shared indexes.')
        libraries = [(sanitize_library_id(args.library_id or library.name), library)]
        build_pipeline(
            libraries,
            index,
            models,
            checkpoints,
            args.vector_dim,
            args.chunk_chars,
            args.chunk_overlap,
            args.ranker_epochs,
            args.compressor_epochs,
            args.skip_vocab,
            args.arch,
            ranker_model_name,
            compressor_model_name,
        )
        demo_guidance = DEMO_GUIDANCE if args.guidance == DEFAULT_GUIDANCE else args.guidance
        ask_query(index, models, 'how does the basic brain interpreter retrieve and compress evidence', demo_guidance, args.trace_output, ranker_model_name, compressor_model_name, args.library_id)
        return

    if command == 'smoke':
        run_step('smoke_test.py')
        return

    if command == 'help':
        print('Usage:')
        print('  python3 brain.py build [--library PATH] [--library-id your_library] [--chunk-chars N] [--chunk-overlap N]')
        print('  python3 brain.py build-library [--library-id example]   # easiest way to build the bundled merged library')
        print('  python3 brain.py build-multi --library-spec food=./food --library-spec code=./code [--chunk-chars N] [--chunk-overlap N]')
        print('  python3 brain.py ask "your question" [--library-id your_library] [--show-reasoning] [--reasoning-output traces.jsonl]')
        print('  python3 brain.py respond "your question" [--response-mode auto|chatbot_food|chatbot_general|code_assistant] [--structured-output out.json] [--response-output out.txt] [--print-json]')
        print('  python3 brain.py explain "your question" [--library-id your_library] [--top-k N] [--reasoning-output traces.jsonl]')
        print('  python3 brain.py demo')
        print('  python3 brain.py smoke')
        print('  python3 brain.py "your question"   # shorthand for ask')
        return

    question = ' '.join([command, *args.rest]).strip()
    if not question:
        raise SystemExit('Usage: python3 brain.py help')
    ensure_built(index, models, ranker_model_name, compressor_model_name)
    ask_query(index, models, question, args.guidance, args.trace_output, ranker_model_name, compressor_model_name, args.library_id)


if __name__ == '__main__':
    main()
