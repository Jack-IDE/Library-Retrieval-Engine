from __future__ import annotations

from .ranker_model import TinyRelevanceRanker, build_vocab_from_chunks


class TinySentenceCompressor(TinyRelevanceRanker):
    """Separate sentence-scoring model used during evidence compression."""
    pass


__all__ = ['TinySentenceCompressor', 'build_vocab_from_chunks']
