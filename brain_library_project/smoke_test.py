from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return result


def main() -> None:
    root = Path(__file__).resolve().parent
    tmp = root / '.smoke_tmp'
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / 'index').mkdir(parents=True)
    (tmp / 'models').mkdir(parents=True)
    (tmp / 'checkpoints' / 'ranker').mkdir(parents=True)
    (tmp / 'checkpoints' / 'compressor').mkdir(parents=True)

    try:
        run([sys.executable, 'build_index.py', '--library', './library', '--index', str(tmp / 'index'), '--vector-dim', '64'], root)
        run([sys.executable, 'build_training_pairs.py', '--index', str(tmp / 'index'), '--output', str(tmp / 'index' / 'train_pairs.jsonl')], root)
        run([sys.executable, 'build_vocab.py', '--sources', './library', '--output', str(tmp / 'models' / 'vocab.json')], root)
        run([
            sys.executable, 'train_ranker.py', '--index', str(tmp / 'index'), '--pairs', str(tmp / 'index' / 'train_pairs.jsonl'),
            '--model', str(tmp / 'models' / 'ranker.brrk'), '--checkpoint-dir', str(tmp / 'checkpoints' / 'ranker'),
            '--epochs', '2', '--batch-size', '8', '--vocab', str(tmp / 'models' / 'vocab.json')
        ], root)
        run([
            sys.executable, 'train_compressor.py', '--index', str(tmp / 'index'), '--model', str(tmp / 'models' / 'compressor.bin'),
            '--checkpoint-dir', str(tmp / 'checkpoints' / 'compressor'), '--epochs', '2', '--batch-size', '8'
        ], root)

        trace_path = tmp / 'index' / 'smoke_trace.json'
        query_cmd = [
            sys.executable, 'query.py',
            '--index', str(tmp / 'index'),
            '--model', str(tmp / 'models' / 'ranker.brrk'),
            '--compressor-model', str(tmp / 'models' / 'compressor.bin'),
            '--vocab', str(tmp / 'models' / 'vocab.json'),
            '--query', 'how does the basic brain interpreter retrieve and compress evidence',
            '--guidance', '{"task":"find implementation details","domain":"brain interpreter","prefer_sources":["specs","code"],"required_terms":["retrieve","compress","evidence"],"max_passes":2}',
            '--trace-output', str(trace_path),
        ]
        result = run(query_cmd, root)
        if 'Detailed top results:' in result.stdout:
            detail_rows = [line for line in result.stdout.splitlines() if line.startswith('- ') and ' :: ' in line]
            if not detail_rows:
                sys.stderr.write(result.stdout)
                raise SystemExit('smoke query printed a results header but no result rows')
        if not trace_path.exists():
            raise SystemExit('smoke query did not write trace output')
        trace = json.loads(trace_path.read_text(encoding='utf-8'))
        if not trace.get('answer') or not trace.get('top_results'):
            raise SystemExit('smoke trace missing answer or top_results')
        if not trace.get('brain_decision') or not trace['brain_decision'].get('selected_chunk_ids'):
            raise SystemExit('smoke trace missing brain_decision selected_chunk_ids')

        food_root = tmp / 'food_lib'
        code_root = tmp / 'code_lib'
        (food_root / 'recipes').mkdir(parents=True)
        (code_root / 'code').mkdir(parents=True)
        (food_root / 'recipes' / 'eggs.md').write_text('# Eggs\n\nToast bread. Fry eggs in butter. Serve breakfast hot.\n', encoding='utf-8')
        (code_root / 'code' / 'parser.py').write_text('def parse_output(text):\n    return text.strip().split()\n', encoding='utf-8')
        multi_index = tmp / 'multi_index'
        multi_models = tmp / 'multi_models'
        multi_checkpoints = tmp / 'multi_checkpoints'
        run([
            sys.executable, 'brain.py', 'build-multi', '--index', str(multi_index), '--models', str(multi_models),
            '--checkpoints', str(multi_checkpoints), '--vector-dim', '32', '--ranker-epochs', '1', '--compressor-epochs', '1',
            '--skip-vocab', '--library-spec', f'food={food_root}', '--library-spec', f'code={code_root}',
        ], root)
        multi_meta = json.loads((multi_index / 'metadata.json').read_text(encoding='utf-8'))
        if not multi_meta.get('multi_library'):
            raise SystemExit('multi-library smoke build did not set multi_library metadata')
        if len(multi_meta.get('libraries', [])) != 2:
            raise SystemExit('multi-library smoke build did not preserve both library entries')
        multi_chunks = [json.loads(line) for line in (multi_index / 'chunks.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        seen_prefixes = {item['chunk_id'].split('::', 1)[0] for item in multi_chunks}
        if seen_prefixes != {'food', 'code'}:
            raise SystemExit(f'unexpected multi-library chunk prefixes: {sorted(seen_prefixes)}')
        multi_query = run([
            sys.executable, 'brain.py', 'ask', 'toast eggs breakfast', '--index', str(multi_index), '--models', str(multi_models), '--library-id', 'food'
        ], root)
        if 'food ::' not in multi_query.stdout or 'code ::' in multi_query.stdout:
            sys.stderr.write(multi_query.stdout)
            raise SystemExit('multi-library query filter did not isolate the requested library')

        print('Smoke test passed.')
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
