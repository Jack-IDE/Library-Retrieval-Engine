from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

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


def run_step(*args: str) -> None:
    cmd = [sys.executable, *args]
    print('>>', ' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def build_pipeline(
    library: Path,
    index: Path,
    models: Path,
    checkpoints: Path,
    vector_dim: int,
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

    run_step('build_index.py', '--library', str(library), '--index', str(index), '--vector-dim', str(vector_dim))
    run_step('build_training_pairs.py', '--index', str(index), '--output', str(index / 'train_pairs.jsonl'))
    if not skip_vocab:
        run_step('build_vocab.py', '--sources', str(library), '--output', str(models / 'vocab.json'))

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


def ask_query(index: Path, models: Path, query: str, guidance: str, trace_output: str = '', ranker_model_name: str = DEFAULT_RANKER_MODEL, compressor_model_name: str = DEFAULT_COMPRESSOR_MODEL) -> None:
    cmd = [
        'query.py', '--index', str(index), '--model', str(models / ranker_model_name),
        '--compressor-model', str(models / compressor_model_name), '--query', query, '--guidance', guidance,
    ]
    vocab_path = models / 'vocab.json'
    if vocab_path.exists():
        cmd.extend(['--vocab', str(vocab_path)])
    if trace_output:
        cmd.extend(['--trace-output', trace_output])
    run_step(*cmd)


def ensure_built(index: Path, models: Path, ranker_model_name: str = DEFAULT_RANKER_MODEL, compressor_model_name: str = DEFAULT_COMPRESSOR_MODEL) -> None:
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
    parser.add_argument('command', nargs='?', default='help', help='build, ask, demo, smoke, or a direct question')
    parser.add_argument('rest', nargs='*', help='Question text when using ask or direct-question mode')
    parser.add_argument('--library', default=str(DEFAULT_LIBRARY))
    parser.add_argument('--index', default=str(DEFAULT_INDEX))
    parser.add_argument('--models', default=str(DEFAULT_MODELS))
    parser.add_argument('--checkpoints', default=str(DEFAULT_CHECKPOINTS))
    parser.add_argument('--ranker-model', default=DEFAULT_RANKER_MODEL)
    parser.add_argument('--compressor-model', default=DEFAULT_COMPRESSOR_MODEL)
    parser.add_argument('--vector-dim', type=int, default=DEFAULT_VECTOR_DIM)
    parser.add_argument('--ranker-epochs', type=int, default=16)
    parser.add_argument('--arch', default='linear', choices=['linear', 'mlp'])
    parser.add_argument('--compressor-epochs', type=int, default=12)
    parser.add_argument('--skip-vocab', action='store_true')
    parser.add_argument('--guidance', default=DEFAULT_GUIDANCE)
    parser.add_argument('--trace-output', default='')
    args = parser.parse_args()

    library = Path(args.library)
    index = Path(args.index)
    models = Path(args.models)
    checkpoints = Path(args.checkpoints)
    ranker_model_name = args.ranker_model
    compressor_model_name = args.compressor_model
    command = args.command

    if command == 'build':
        build_pipeline(library, index, models, checkpoints, args.vector_dim, args.ranker_epochs, args.compressor_epochs, args.skip_vocab, args.arch, ranker_model_name, compressor_model_name)
        print('\nBuild complete. Ask something with: python3 brain.py ask "your question"')
        return

    if command == 'ask':
        if not args.rest:
            raise SystemExit('Usage: python3 brain.py ask "your question"')
        ensure_built(index, models, ranker_model_name, compressor_model_name)
        ask_query(index, models, ' '.join(args.rest), args.guidance, args.trace_output, ranker_model_name, compressor_model_name)
        return

    if command == 'demo':
        build_pipeline(library, index, models, checkpoints, args.vector_dim, args.ranker_epochs, args.compressor_epochs, args.skip_vocab, args.arch, ranker_model_name, compressor_model_name)
        demo_guidance = DEMO_GUIDANCE if args.guidance == DEFAULT_GUIDANCE else args.guidance
        ask_query(index, models, 'how does the basic brain interpreter retrieve and compress evidence', demo_guidance, args.trace_output, ranker_model_name, compressor_model_name)
        return

    if command == 'smoke':
        run_step('smoke_test.py')
        return

    if command == 'help':
        print('Usage:')
        print('  python3 brain.py build')
        print('  python3 brain.py ask "your question"')
        print('  python3 brain.py demo')
        print('  python3 brain.py smoke')
        print('  python3 brain.py "your question"   # shorthand for ask')
        return

    question = ' '.join([command, *args.rest]).strip()
    if not question:
        raise SystemExit('Usage: python3 brain.py help')
    ensure_built(index, models, ranker_model_name, compressor_model_name)
    ask_query(index, models, question, args.guidance, args.trace_output, ranker_model_name, compressor_model_name)


if __name__ == '__main__':
    main()
