# Python + Food Example Library

This is a small example corpus for **Retrieval Brain**-style local retrieval, reranking, and grounded answering.
Drop the files in this folder in the "library" folder in the main project.

## What is included

- `code/` — Python source files for CLI tooling, config loading, plugins, process execution, file helpers, and output formatting
- `docs/` — user-facing guides and retrieval notes
- `specs/` — architecture and interface specifications
- `recipes/` — a focused food/recipe knowledge pack in Markdown

## Why this library exists

This library gives the project two distinct retrieval modes in one bundle:

1. **Technical retrieval** over code, docs, and specs
2. **Domain retrieval** over a structured recipe corpus

That makes it useful for smoke tests, demos, and small end-to-end evaluation runs.

## Suggested example queries

- How does config precedence work in this tool?
- What does the plugin interface require at load time?
- How should output formatting behave when `NO_COLOR` is set?
- What is the command dispatch model for the CLI?
- Explain the retrieval pipeline described in the notes.
- Find the troubleshooting advice for a missing `output.dir`.
- Give me a vegetarian chickpea dish from the recipe corpus.
- Which recipes involve long braising?
- Find a dessert that uses layered pastry and nuts.
- Show a seafood recipe suitable for tacos.

