# Basic Brain Interpreter
The system scans a small library of text and code files, keeps knowledge outside the weights, and answers questions by retrieving evidence from the library.

## Retrieval And Compression
The first pass should retrieve broad candidates. Later passes should rerank, compress evidence, and carry forward useful terms instead of restarting from scratch.

## Answer Behavior
Answers should cite the top chunks, summarize the strongest evidence, and avoid claiming knowledge that is not present in the library.
