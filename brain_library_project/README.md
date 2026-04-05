# Brain Library Project

A small, local retrieval-and-compression QA pipeline for your own text and code files.

It builds a chunked index from a library folder, trains a lightweight reranker and compressor, and answers questions with grounded evidence from the indexed corpus.

## What it does

- indexes local `.txt`, `.md`, `.py`, `.js`, `.json`, `.html`, and `.css` files
- retrieves evidence with a postings-based lexical stage, then vector scoring on pruned candidates
- reranks candidate chunks with a trained ranker
- compresses the top evidence into a compact answer
- writes an optional trace for debugging retrieval behavior

## What it does not do

- it is not a full LLM chatbot
- it does not keep long-term conversational memory
- it does not call external APIs or hosted models

## Requirements

- Python 3.10 or newer
- no third-party Python packages required for the default workflow

## Quick start

Clone the repo, then run one build command:

```bash
python3 brain.py build
```

Ask a question:

```bash
python3 brain.py ask "what does this library say about retrieval"
```

There is also a shorthand form after the first build:

```bash
python3 brain.py "what does this library say about retrieval"
```

Model filenames are configurable from the wrapper with `--ranker-model` and `--compressor-model`. The defaults are `models/ranker.brrk` and `models/compressor.bin`.

To run the full sample pipeline plus a demo query in one command:

```bash
python3 brain.py demo
```

To validate the bundled sample end to end:

```bash
python3 brain.py smoke
```

## Manual workflow

Build an index (writes `chunks.jsonl`, `idf.json`, `vectors.bin`, and `retrieval.json`):

```bash
python3 build_index.py --library ./library --index ./index --vector-dim 64
```

Generate training pairs:

```bash
python3 build_training_pairs.py --index ./index --output ./index/train_pairs.jsonl
```

Build a reusable fixed vocab (optional but recommended for portability across library swaps):

```bash
python3 build_vocab.py --sources ./library --output ./models/vocab.json
```

Train the reranker:

```bash
python3 train_ranker.py --index ./index --pairs ./index/train_pairs.jsonl --model ./models/ranker.brrk --checkpoint-dir ./checkpoints/ranker --epochs 20 --batch-size 8 --vocab ./models/vocab.json
```

Train the compressor:

```bash
python3 train_compressor.py --index ./index --model ./models/compressor.bin --checkpoint-dir ./checkpoints/compressor --epochs 12 --batch-size 8
```

Query the indexed library:

```bash
python3 query.py --index ./index --model ./models/ranker.brrk --compressor-model ./models/compressor.bin --query "how does this library describe retrieval"
```

Write a controller trace while querying:

```bash
python3 query.py --index ./index --model ./models/ranker.brrk --compressor-model ./models/compressor.bin --query "how does this library describe retrieval" --trace-output ./index/trace.json
```

## Replacing the sample library

Swap the sample files under `library/` with your own documents and source code, then rebuild the index and retrain the small models. If you want the ranker to stay portable across different library contents, keep using a frozen `vocab.json` built from a broad base corpus.

## Notes for publishing

This repo is intended as a clean prototype/reference release. Generated artifacts such as trained models, checkpoints, and temporary smoke-test outputs are ignored by git.


## Vocab safety

The ranker now stores a vocab fingerprint in its model metadata. When `models/vocab.json` is present, `brain.py ask` passes it through to `query.py`, which verifies that the ranker and vocab match before scoring. If they do not match, re-run `python3 brain.py build` or rebuild your ranker against the current vocab.
