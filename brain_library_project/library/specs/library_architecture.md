# Library Architecture
The index stores chunks, metadata, IDF statistics, and vectors built from the library files.

## Retrieval And Reranking
Use lexical retrieval for the first pass and a learned ranker for the second pass. The ranker should score query, chunk, and guidance together and output a score from zero to one.

## Working Memory Compression
Compression should summarize top chunks into a smaller evidence buffer so later passes do not drag full documents through the whole loop.
