from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)


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
        run([sys.executable, 'train_ranker.py', '--index', str(tmp / 'index'), '--pairs', str(tmp / 'index' / 'train_pairs.jsonl'), '--model', str(tmp / 'models' / 'ranker.brrk'), '--checkpoint-dir', str(tmp / 'checkpoints' / 'ranker'), '--epochs', '2', '--batch-size', '8', '--vocab', str(tmp / 'models' / 'vocab.json')], root)
        run([sys.executable, 'train_compressor.py', '--index', str(tmp / 'index'), '--model', str(tmp / 'models' / 'compressor.bin'), '--checkpoint-dir', str(tmp / 'checkpoints' / 'compressor'), '--epochs', '2', '--batch-size', '8'], root)

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
        result = subprocess.run(query_cmd, cwd=root, text=True, capture_output=True)
        if result.returncode != 0:
            sys.stderr.write(result.stdout)
            sys.stderr.write(result.stderr)
            raise SystemExit(result.returncode)
        if 'Detailed top results:' in result.stdout and ' :: ' not in result.stdout:
            sys.stderr.write(result.stdout)
            raise SystemExit('smoke query printed a results header but no result rows')
        if not trace_path.exists():
            raise SystemExit('smoke query did not write trace output')
        trace = json.loads(trace_path.read_text(encoding='utf-8'))
        if not trace.get('answer') or not trace.get('top_results'):
            raise SystemExit('smoke trace missing answer or top_results')
        print('Smoke test passed.')
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
