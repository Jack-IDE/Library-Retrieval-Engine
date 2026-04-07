# Brain Library Project

A local question-answer tool for your own files.

It reads your library folders, builds a searchable index, and answers questions using evidence from those files.

The answer path now uses an **active synthesis step**:

- retrieval proposes the top candidates
- the brain reranks those candidates and chooses selected chunk IDs
- the controller compresses evidence from those selected chunks
- `query.py --trace-output ...` writes the brain decision into the trace JSON

## What files it can read

- `.txt`
- `.md`
- `.py`
- `.js`
- `.json`
- `.html`
- `.css`

## Requirements

- Python 3.10+
- no third-party packages needed for the normal workflow


## Bundled example library

This bundle now ships with **one built-in merged library** inside `brain_library_project/library/`.

That single library includes:

- the original brain-interpreter reference material
- `library/recipes/food/ and library/docs/food/` — the Python food example corpus
- `library/code/web/ / library/docs/web/ / library/specs/web/` — the HTML website example corpus

So you can build one library and query both food and web material without separate `food` and `web` library IDs.

Build the merged bundled library:

```
python3 brain.py build-library
python3 brain.py ask "how do I make steak" --library-id example
python3 brain.py respond "how do I build a sticky nav that hides on scroll" --library-id example --response-mode code_assistant
python3 brain.py respond "why does my SPA 404 on refresh" --library-id example --response-mode code_assistant
```

Or use the tiny wrapper script:

```
python3 build_all_library.py
```

## Easiest way to use it

### If you have one library folder

Example folder:

```
library/
```

### Step 1 — build it

```
python3 brain.py build --library ./library --library-id mylib
```

### Step 2 — ask it something

```
python3 brain.py ask "your question here" --library-id mylib
```

Or get a cleaner chat-style reply plus optional structured JSON:

```
python3 brain.py respond "your question here" --library-id mylib
python3 brain.py respond "your question here" --library-id mylib --print-json --structured-output out.json --response-output out.txt
```

Example:

```
python3 brain.py ask "how do I make eggs for breakfast" --library-id mylib
```

---

### If you have multiple library folders

Example folders:

```
libraries/
  food/
  code/
```

### Step 1 — build them together

```
python3 brain.py build-multi --library-spec food=./libraries/food --library-spec code=./libraries/code
```

`brain.py` now resolves relative library paths from the shell directory you ran it from, and falls back to paths relative to the project root if needed.

### Step 2 — ask across everything

```
python3 brain.py ask "your question here"
```

Or shape the answer for chatbot / code-assistant use:

```
python3 brain.py respond "your question here"
python3 brain.py respond "how does parsing work" --response-mode code_assistant
```

Example:

```
python3 brain.py ask "how is retrieval implemented"
```

### Step 3 — ask only one library

```
python3 brain.py ask "your question here" --library-id food
```

Example:

```
python3 brain.py ask "how do I make eggs" --library-id food
```

## That is the whole basic workflow

### One library

```
python3 brain.py build --library ./library --library-id mylib
python3 brain.py ask "your question here" --library-id mylib
```

For the bundled merged library, the easiest command is:

```
python3 brain.py build-library
```

### Multiple libraries

```
python3 brain.py build-multi --library-spec food=./libraries/food --library-spec code=./libraries/code
python3 brain.py ask "your question here"
python3 brain.py ask "your question here" --library-id food
```

## What `library-id` means

`library-id` is just the short name for a library.

Examples:

```
food
code
docs
recipes
```

Pick a simple name and keep using it for that library.

## Recommended folder layouts

### One library

```
project/
  brain.py
  library/
```

### Multiple libraries

```
project/
  brain.py
  libraries/
    food/
    code/
    docs/
```

## Real examples

### One library

```
python3 brain.py build --library ./library --library-id recipes
python3 brain.py ask "how do I make toast" --library-id recipes
```

### Two libraries

```
python3 brain.py build-multi --library-spec recipes=./libraries/recipes --library-spec code=./libraries/code
python3 brain.py ask "how do I make toast" --library-id recipes
python3 brain.py ask "how does parsing work" --library-id code
```

## Ignore this for now

You do not need to think about these unless you want custom control later:

- index paths
- model paths
- checkpoints
- chunk settings
- low-level scripts

## Optional shortcuts

After the first build, this also works **if you used the default index and model locations**:

```
python3 brain.py "your question here"
```

To run the bundled demo:

```
python3 brain.py demo
```

To run the smoke test:

```
python3 brain.py smoke
```

## Cleaner response mode

`respond` runs the normal retrieval path, parses the plain-text output, and then emits a cleaner final reply.

Examples:

```
python3 brain.py respond "how do I make eggs" --library-id example
python3 brain.py respond "how do I build a sticky nav" --library-id example --response-mode code_assistant
python3 brain.py respond "how do I make eggs" --library-id example --print-json --structured-output structured.json --response-output response.txt
```

## Advanced options

### Custom chunk sizing

```
python3 brain.py build --library ./library --library-id mylib --chunk-chars 900 --chunk-overlap 160
```

### Custom output locations

```
python3 brain.py build --library ./library --library-id mylib --index ./runs/mylib/index --models ./runs/mylib/models --checkpoints ./runs/mylib/checkpoints
```

### Build only the index

Single library:

```
python3 build_index.py --library ./library --library-id mylib --index ./index
```

Multiple libraries:

```
python3 build_index.py --index ./index --library-spec food=./libraries/food --library-spec code=./libraries/code
```

### Manual workflow

Only use this if you want to run each stage yourself.

```
python3 build_index.py --library ./library --index ./index --vector-dim 64
python3 build_training_pairs.py --index ./index --output ./index/train_pairs.jsonl
python3 build_vocab.py --sources ./library --output ./models/vocab.json
python3 train_ranker.py --index ./index --pairs ./index/train_pairs.jsonl --model ./models/ranker.brrk --checkpoint-dir ./checkpoints/ranker --epochs 20 --batch-size 8 --vocab ./models/vocab.json
python3 train_compressor.py --index ./index --model ./models/compressor.bin --checkpoint-dir ./checkpoints/compressor --epochs 12 --batch-size 8
python3 query.py --index ./index --model ./models/ranker.brrk --compressor-model ./models/compressor.bin --query "how does this library describe retrieval"
```

## Notes

- chunk IDs are globally unique: `library_id::relative/path.ext::chunk_number`
- `--library-id` is a hard filter during query time
- `--library-spec` format is `LIBRARY_ID=PATH`
- if you swap in new files, rebuild before asking questions again
- if your vocab and ranker stop matching, rebuild using the same kind of build you used before:
  - single library: `python3 brain.py build --library ./library --library-id mylib`
  - multiple libraries: `python3 brain.py build-multi --library-spec food=./libraries/food --library-spec code=./libraries/code`


## Retrieval reasoning

This build includes an offline reasoning layer for raw retrieval scoring.

Show controller output plus per-result retrieval reasoning:

```text
python3 query.py --index ./index --query "fast json parser" --show-reasoning
```

Inspect raw retrieval scoring without the controller/reranker summary layer:

```text
python3 explain_query.py --index ./index --query "fast json parser"
```

Write top retrieval traces as JSONL:

```text
python3 explain_query.py --index ./index --query "fast json parser" --jsonl-output ./reasoning_traces.jsonl
```


## Explain mode

Use `brain.py explain` when you want a retrieval-focused view instead of the normal answer-first query flow. It prints the top raw retrieval matches, their lexical/vector/final scores, and the reasoning trace fields that explain why those chunks ranked highly.

Examples:

```
python3 brain.py explain "fast json parser"
python3 brain.py explain "fast json parser" --top-k 5
python3 brain.py ask "fast json parser" --show-reasoning
python3 brain.py explain "fast json parser" --reasoning-output reasoning_traces.jsonl
```


## Bundled library layout

The built-in `library/` folder is organized by actual domain now:

- `library/code/brain/ / library/docs/brain/ / library/specs/brain/` — project-specific retrieval/interpreter material
- `library/code/python/ / library/docs/python/ / library/specs/python/` — Python CLI/tooling example material
- `library/recipes/food/ and library/docs/food/` — food-only recipe corpus
- `library/code/web/ / library/docs/web/ / library/specs/web/` — HTML/CSS/JS example material
- `library/phrases/` — natural language phrase library used by the synthesis renderer

## Phrase engine

The synthesis renderer uses a phrase library to produce natural, varied output instead of fixed boilerplate strings.

The phrase database lives at:

```
library/phrases/english_phrases_db.json
```

This file is bundled and requires no setup — the engine finds it automatically at that path.

**What it affects:**

- Connectors between merged chunks (`merge`, `merge_context`, `merge_solution`, `merge_steps` modes) — e.g. "Building on what was said...", "Not only that but also...", "With that being said..."
- Context framing for activation expansion terms — e.g. "On a related note... butter, fond, crust."
- Redundancy notes when candidates were semantically close — e.g. "I have my reservations.", "Let's not jump to conclusions."
- Merge explanation notes — e.g. "Long story short...", "To make a long story short..."

**Phrase selection is stable:** the same query always picks the same phrase, so output is deterministic. Different queries pick different phrases from the same pool.

**Fallback:** if the phrase file is missing or fails to load, all renderers fall back to short neutral strings. The system runs correctly either way.

To point the engine at a different phrase file at runtime:

```python
from brain_core import phrase_engine
phrase_engine.configure('/path/to/your/english_phrases_db.json')
```


Phrase engine notes:
- `mode_intro()` is now used in the mode-shaped renderers.
- `hedge()` is now used for low-confidence answers.
