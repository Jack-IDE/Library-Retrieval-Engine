"""Compatibility answer synthesis helper.

This file is a library/example artifact, not the primary controller implementation.
It intentionally accepts either RetrievedChunk-like objects or plain dicts so it can
be used safely in examples without assuming one concrete runtime type.
"""

from __future__ import annotations

from typing import Any, Iterable


def _chunk_id(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("chunk_id") or item.get("id") or "")
    chunk = getattr(item, "chunk", None)
    if chunk is not None:
        return str(getattr(chunk, "chunk_id", "") or getattr(chunk, "id", ""))
    return str(getattr(item, "chunk_id", "") or getattr(item, "id", ""))


def synthesize_answer(top_chunks: Iterable[Any], evidence_summary: str) -> dict:
    """Return a cited answer payload from retrieved evidence.

    Notes:
    - This is a lightweight compatibility/sample helper.
    - The main runtime answer synthesis lives in ``brain_core/controller.py``.
    """
    citations = [cid for cid in (_chunk_id(chunk) for chunk in top_chunks) if cid][:3]
    return {
        "answer": evidence_summary,
        "citations": citations,
    }
