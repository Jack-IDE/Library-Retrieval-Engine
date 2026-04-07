# Library Layout

This library is organized by **content type first**.

## Folders

- `code/`
  - `code/brain/` — core brain/interpreter code examples
  - `code/python/` — Python example code and utilities
  - `code/web/` — HTML/CSS/JS example code

- `docs/`
  - `docs/brain/` — retrieval and library notes for the brain/interpreter material
  - `docs/python/` — Python guides, walkthroughs, and troubleshooting
  - `docs/web/` — web guides, topic writeups, patterns, and troubleshooting
  - `docs/food/` — food-query notes

- `specs/`
  - `specs/brain/` — brain/interpreter reference material
  - `specs/python/` — Python interface/reference material
  - `specs/web/` — web structure and architecture reference material

- `recipes/`
  - `recipes/food/` — actual food recipe content

## Placement rule

- actual code file -> `code/`
- explanatory writeup / guide / troubleshooting note -> `docs/`
- structured reference / spec / schema-like material -> `specs/`
- actual recipe corpus -> `recipes/`

That is the whole rule.


## Internal library-maintenance notes

Files named `library_input_notes.txt`, `retrieval_notes.txt`, and the top-level `README.md` are for humans maintaining the corpus. They are not intended to dominate normal end-user retrieval.
