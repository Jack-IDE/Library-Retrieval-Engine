from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from brain_core.indexing import load_index
from brain_core.ranker_io import load_vocab_file, save_ranker
from brain_core.ranker_model import TinyRelevanceRanker, build_vocab_from_chunks
from brain_core.training_data import load_pairs_jsonl, merge_pair_sets, resolve_pairs_to_examples
from brain_core.weak_supervision import generate_pairs


def pretokenize_examples(model: TinyRelevanceRanker, examples) -> None:
    for ex in examples:
        ex['query_ids'] = model.text_to_ids(ex['query'])
        ex['chunk_ids'] = model.text_to_ids(ex['chunk_text'])
        ex['guidance_ids'] = model.text_to_ids(ex.get('guidance_text', ''))


def evaluate(model: TinyRelevanceRanker, examples):
    if not examples:
        return 0.0, 0.0, {}
    total_loss = 0.0
    total_weight = 0.0
    correct = 0.0
    by_source = {}
    for ex in examples:
        query_ids = ex.get('query_ids')
        chunk_ids = ex.get('chunk_ids')
        guidance_ids = ex.get('guidance_ids')
        if query_ids is not None and chunk_ids is not None:
            p = model.score_from_ids(query_ids, chunk_ids, guidance_ids)
        else:
            p = model.score(ex['query'], ex['chunk_text'], ex['guidance_text'])
        label = int(ex['label'])
        weight = float(ex.get('weight', 1.0))
        loss = weight * (-(math.log(max(p, 1e-9)) if label == 1 else math.log(max(1.0 - p, 1e-9))))
        total_loss += loss
        total_weight += weight
        pred = 1 if p >= 0.5 else 0
        correct += weight * int(pred == label)
        key = ex.get('source', 'unknown')
        row = by_source.setdefault(key, {'count': 0, 'correct_weight': 0.0, 'total_weight': 0.0})
        row['count'] += 1
        row['total_weight'] += weight
        row['correct_weight'] += weight * int(pred == label)
    source_metrics = {
        k: {
            'count': v['count'],
            'weighted_acc': (v['correct_weight'] / max(1e-9, v['total_weight'])),
        }
        for k, v in by_source.items()
    }
    return total_loss / max(1.0, total_weight), correct / max(1.0, total_weight), source_metrics


def save_metrics(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Train a tiny relevance ranker from labeled query/chunk pairs.')
    parser.add_argument('--index', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--pairs', default='', help='Optional JSONL labeled pairs file')
    parser.add_argument('--manual-pairs', default='', help='Optional manual JSONL labels to merge and prioritize')
    parser.add_argument('--checkpoint-dir', default='')
    parser.add_argument('--arch', default='linear', choices=['linear', 'mlp'])
    parser.add_argument('--embed-dim', type=int, default=24)
    parser.add_argument('--hidden1', type=int, default=48)
    parser.add_argument('--hidden2', type=int, default=24)
    parser.add_argument('--epochs', type=int, default=40)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--lr', type=float, default=0.05)
    parser.add_argument('--val-fraction', type=float, default=0.15)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--manual-weight-boost', type=float, default=2.5)
    parser.add_argument('--hard-negatives-per-positive', type=int, default=1)
    parser.add_argument('--vocab', default='', metavar='PATH',
                        help='Fixed vocab.json from build_vocab.py.  '
                             'If omitted, vocab is built from the current index '
                             '(old behaviour — not portable across libraries).')
    args = parser.parse_args()

    chunks, _idf, metadata, _vectors = load_index(Path(args.index))
    chunk_by_id = {c.chunk_id: c for c in chunks}

    if args.vocab:
        vocab_path = Path(args.vocab)
        if not vocab_path.exists():
            raise FileNotFoundError(f'--vocab file not found: {vocab_path}')
        vocab = load_vocab_file(vocab_path)
        print(f'Vocab:    fixed  ({len(vocab):,} tokens)  ← {vocab_path}')
    else:
        texts = [c.text + ' ' + c.heading + ' ' + c.source_path + ' ' + c.symbol_name for c in chunks]
        vocab = build_vocab_from_chunks(texts, min_freq=1)
        print(f'Vocab:    built from index  ({len(vocab):,} tokens)  — not portable across libraries')

    if args.pairs:
        base_pairs = load_pairs_jsonl(args.pairs)
    else:
        base_pairs = generate_pairs(
            chunks,
            negatives_per_positive=2,
            seed=args.seed,
            val_fraction=args.val_fraction,
            idf=_idf,
            retrieval_artifacts=metadata.get('retrieval_artifacts'),
            chunk_vectors=_vectors,
            vector_dim=int(metadata.get('vector_dim', 64)),
            hard_negatives_per_positive=args.hard_negatives_per_positive,
        )
    if args.manual_pairs:
        manual_pairs = load_pairs_jsonl(args.manual_pairs)
        pairs = merge_pair_sets(manual_pairs, base_pairs)
    else:
        pairs = base_pairs

    examples = resolve_pairs_to_examples(pairs, chunk_by_id)
    for ex in examples:
        if str(ex.get('source', '')).startswith('manual'):
            ex['weight'] = float(ex.get('weight', 1.0)) * args.manual_weight_boost

    train = [ex for ex in examples if ex.get('split', 'train') != 'val']
    val = [ex for ex in examples if ex.get('split', 'train') == 'val']
    if not val:
        rng = random.Random(args.seed)
        rng.shuffle(train)
        val_count = max(1, int(len(train) * args.val_fraction)) if train else 0
        val = train[:val_count]
        train = train[val_count:] if val_count else train

    model = TinyRelevanceRanker(vocab=vocab, embed_dim=args.embed_dim, hidden1=args.hidden1, hidden2=args.hidden2, seed=args.seed, arch=args.arch)
    pretokenize_examples(model, train)
    pretokenize_examples(model, val)
    rng = random.Random(args.seed)
    best_val = float('inf')
    history = []
    checkpoint_dir = Path(args.checkpoint_dir) if args.checkpoint_dir else None
    best_model_path = checkpoint_dir / 'ranker_best.bin' if checkpoint_dir else None
    latest_model_path = checkpoint_dir / 'ranker_latest.bin' if checkpoint_dir else None
    metrics_path = checkpoint_dir / 'ranker_metrics.json' if checkpoint_dir else None

    for epoch in range(1, args.epochs + 1):
        rng.shuffle(train)
        total_loss = 0.0
        seen_weight = 0.0
        for i in range(0, len(train), args.batch_size):
            batch = train[i:i + args.batch_size]
            grads = model.zero_grads()
            batch_loss = 0.0
            batch_weight = 0.0
            for ex in batch:
                weight = float(ex.get('weight', 1.0))
                loss = model.accumulate_gradients_from_ids(ex['query_ids'], ex['chunk_ids'], ex.get('guidance_ids', []), ex['label'], grads, sample_weight=weight)
                batch_loss += loss
                batch_weight += weight
            model.apply_gradients(grads, lr=args.lr, batch_scale=1.0 / max(1.0, batch_weight))
            total_loss += batch_loss
            seen_weight += batch_weight
        train_loss = total_loss / max(1.0, seen_weight)
        val_loss, val_acc, val_source_metrics = evaluate(model, val)
        row = {'epoch': epoch, 'train_loss': train_loss, 'val_loss': val_loss, 'val_acc': val_acc, 'val_source_metrics': val_source_metrics}
        history.append(row)
        if checkpoint_dir:
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            save_ranker(latest_model_path, model)
            if val and val_loss < best_val:
                best_val = val_loss
                save_ranker(best_model_path, model)
            save_metrics(metrics_path, {
                'index_metadata': metadata,
                'ranker_arch': args.arch,
                'vocab_source': args.vocab if args.vocab else 'built_from_index',
                'vocab_size': len(vocab),
                'train_examples': len(train),
                'val_examples': len(val),
                'history': history,
            })
        else:
            if val and val_loss < best_val:
                best_val = val_loss
        if epoch == 1 or epoch == args.epochs or epoch % max(1, args.epochs // 8) == 0:
            print(f'epoch {epoch:4d} | arch {args.arch:6s} | train_loss {train_loss:.4f} | val_loss {val_loss:.4f} | val_acc {val_acc:.3f}')

    if checkpoint_dir and best_model_path and best_model_path.exists():
        Path(args.model).write_bytes(best_model_path.read_bytes())
    else:
        save_ranker(args.model, model)
    print(f'Saved ranker to {args.model}')


if __name__ == '__main__':
    main()
