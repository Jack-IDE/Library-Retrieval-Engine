from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from brain_core.compressor_io import save_compressor
from brain_core.compressor_model import TinySentenceCompressor, build_vocab_from_chunks
from brain_core.indexing import load_index
from brain_core.weak_supervision import generate_compressor_examples


def pretokenize_examples(model: TinySentenceCompressor, examples) -> None:
    for ex in examples:
        ex.query_ids = model.text_to_ids(ex.query)
        ex.sentence_ids = model.text_to_ids(ex.sentence)
        ex.guidance_ids = model.text_to_ids(ex.guidance_text)


def evaluate(model: TinySentenceCompressor, examples):
    if not examples:
        return 0.0, 0.0
    total_loss = 0.0
    correct = 0
    for ex in examples:
        p = model.score_from_ids(ex.query_ids, ex.sentence_ids, ex.guidance_ids)
        total_loss += -(math.log(max(p, 1e-9)) if ex.label == 1 else math.log(max(1.0 - p, 1e-9)))
        pred = 1 if p >= 0.5 else 0
        correct += int(pred == ex.label)
    return total_loss / len(examples), correct / len(examples)


def save_metrics(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Train a tiny sentence compressor model.')
    parser.add_argument('--index', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--checkpoint-dir', default='')
    parser.add_argument('--embed-dim', type=int, default=20)
    parser.add_argument('--hidden1', type=int, default=40)
    parser.add_argument('--hidden2', type=int, default=20)
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--lr', type=float, default=0.05)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    chunks, _idf, metadata, _vectors = load_index(Path(args.index))
    texts = []
    for c in chunks:
        texts.extend([c.text, c.heading, c.source_path, c.symbol_name])
    vocab = build_vocab_from_chunks(texts, min_freq=1)
    examples = generate_compressor_examples(chunks, seed=args.seed)
    train = [ex for ex in examples if ex.split != 'val']
    val = [ex for ex in examples if ex.split == 'val']

    model = TinySentenceCompressor(vocab=vocab, embed_dim=args.embed_dim, hidden1=args.hidden1, hidden2=args.hidden2, seed=args.seed)
    pretokenize_examples(model, train)
    pretokenize_examples(model, val)
    rng = random.Random(args.seed)
    best_val = float('inf')
    checkpoint_dir = Path(args.checkpoint_dir) if args.checkpoint_dir else None
    best_model_path = checkpoint_dir / 'compressor_best.bin' if checkpoint_dir else None
    latest_model_path = checkpoint_dir / 'compressor_latest.bin' if checkpoint_dir else None
    metrics_path = checkpoint_dir / 'compressor_metrics.json' if checkpoint_dir else None
    history = []

    for epoch in range(1, args.epochs + 1):
        rng.shuffle(train)
        total_loss = 0.0
        seen = 0
        for i in range(0, len(train), args.batch_size):
            batch = train[i:i + args.batch_size]
            grads = model.zero_grads()
            batch_loss = 0.0
            for ex in batch:
                batch_loss += model.accumulate_gradients_from_ids(ex.query_ids, ex.sentence_ids, ex.guidance_ids, ex.label, grads)
            model.apply_gradients(grads, lr=args.lr, batch_scale=1.0 / max(1, len(batch)))
            total_loss += batch_loss
            seen += len(batch)
        train_loss = total_loss / max(1, seen)
        val_loss, val_acc = evaluate(model, val)
        history.append({'epoch': epoch, 'train_loss': train_loss, 'val_loss': val_loss, 'val_acc': val_acc})
        if checkpoint_dir:
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            save_compressor(latest_model_path, model)
            if val and val_loss < best_val:
                best_val = val_loss
                save_compressor(best_model_path, model)
            save_metrics(metrics_path, {
                'index_metadata': metadata,
                'train_examples': len(train),
                'val_examples': len(val),
                'history': history,
            })
        else:
            if val and val_loss < best_val:
                best_val = val_loss
        if epoch == 1 or epoch == args.epochs or epoch % max(1, args.epochs // 8) == 0:
            print(f'epoch {epoch:4d} | train_loss {train_loss:.4f} | val_loss {val_loss:.4f} | val_acc {val_acc:.3f}')

    if checkpoint_dir and best_model_path and best_model_path.exists():
        Path(args.model).write_bytes(best_model_path.read_bytes())
    else:
        save_compressor(args.model, model)
    print(f'Saved compressor to {args.model}')


if __name__ == '__main__':
    main()
