"""
phrase_engine.py
----------------
Phrase-based natural language renderer for brain_library synthesis.

Loads english_phrases_db.json and maps brain decision signals
(composition_mode, intent, reason_flags, confidence, activation_terms)
to natural English phrases — replacing hardcoded boilerplate in the
synthesis renderers.

Zero external dependencies. Lazy-loaded on first use.
Stable selection: same (query, slot) pair always picks the same phrase,
but different queries get different phrases from the same pool.

Usage
-----
    from .phrase_engine import configure, connector, context_frame, ...

    configure('/path/to/english_phrases_db.json')   # optional: call once at startup
    seed = query_seed(query)
    conn = connector(reason_flags, seed)             # "Building on what was said..."
    frame = context_frame(terms, mode, seed)         # "On a related note... butter, fond."
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

# category -> {tone -> [phrase], '__all__' -> [phrase], '__prefix__' -> [phrase]}
_INDEX: Dict[str, Dict[str, List[str]]] = {}
_LOADED = False
_CONFIGURED_PATH: Optional[str] = None


# ---------------------------------------------------------------------------
# Configuration & loading
# ---------------------------------------------------------------------------

def configure(path: str) -> None:
    """Set the path to english_phrases_db.json before first use."""
    global _CONFIGURED_PATH
    _CONFIGURED_PATH = path


def load(path: str) -> None:
    """Parse and index english_phrases_db.json."""
    global _LOADED
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    for cat in data.get('categories', []):
        name = str(cat.get('name') or '').strip()
        if not name:
            continue
        _INDEX[name] = {'__all__': [], '__prefix__': []}
        for entry in cat.get('phrases', []):
            phrase = str(entry.get('phrase') or '').strip()
            tone = str(entry.get('tone_intent') or '').strip()
            if not phrase:
                continue
            _INDEX[name]['__all__'].append(phrase)
            if phrase.endswith('...'):
                _INDEX[name]['__prefix__'].append(phrase)
            if tone:
                _INDEX[name].setdefault(tone, []).append(phrase)
    _LOADED = True


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    candidates: List[str] = []
    if _CONFIGURED_PATH:
        candidates.append(_CONFIGURED_PATH)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates += [
        os.path.join(here, '..', 'library', 'phrases', 'english_phrases_db.json'),
        os.path.join(here, 'english_phrases_db.json'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            load(path)
            return
    _LOADED = True   # mark loaded so we don't retry on every call


# ---------------------------------------------------------------------------
# Primitive selection
# ---------------------------------------------------------------------------

def _pick(items: List[str], seed: int) -> str:
    if not items:
        return ''
    return items[seed % len(items)]


def _pick_tone(category: str, tone: Optional[str], seed: int) -> str:
    _ensure_loaded()
    cat = _INDEX.get(category, {})
    if tone and tone in cat and cat[tone]:
        return _pick(cat[tone], seed)
    return _pick(cat.get('__all__', []), seed)


def _pick_prefix(category: str, tone: Optional[str], seed: int) -> str:
    """Return a phrase that ends with '...' (a sentence-prefix completer)."""
    _ensure_loaded()
    cat = _INDEX.get(category, {})
    pool: List[str] = []
    if tone and tone in cat:
        pool = [p for p in cat[tone] if p.endswith('...')]
    if not pool:
        pool = cat.get('__prefix__', [])
    return _pick(pool, seed)


def _pool_from(options: List[Tuple[str, Optional[str], bool]], seed: int) -> str:
    """
    Build a unified phrase pool from all matching options, then pick one.

    This gives real variety — the seed cycles across the full combined
    candidate set rather than locking onto the first non-empty tone bucket.
    """
    _ensure_loaded()
    pool: List[str] = []
    seen: set[str] = set()
    for cat, tone, prefix_only in options:
        cat_data = _INDEX.get(cat, {})
        if prefix_only:
            if tone and tone in cat_data:
                candidates = [p for p in cat_data[tone] if p.endswith('...')]
            else:
                candidates = cat_data.get('__prefix__', [])
        else:
            if tone and tone in cat_data:
                candidates = cat_data[tone]
            else:
                candidates = cat_data.get('__all__', [])
        for phrase in candidates:
            if phrase not in seen:
                pool.append(phrase)
                seen.add(phrase)
    return _pick(pool, seed)


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def query_seed(query: str, slot: str = '') -> int:
    """
    Stable, bounded seed derived from query + slot name.
    Same (query, slot) always selects the same phrase.
    Different queries select different phrases from the same pool.
    """
    raw = hashlib.md5(f'{query}\x00{slot}'.encode('utf-8')).hexdigest()
    return int(raw[:8], 16) % 997


# ---------------------------------------------------------------------------
# Brain signal → phrase mappings
# ---------------------------------------------------------------------------
# Each tuple: (category, tone_or_None, prefix_only)

_CONNECTOR_COMPLEMENTARY: List[Tuple[str, Optional[str], bool]] = [
    ('Transition', 'Expanding',    True),
    ('Transition', 'Additive',     True),
    ('Transition', 'Connecting',   True),
    ('Transition', 'Bridging',     True),
    ('Transition', 'Logical Flow', False),
]

_CONNECTOR_ADDITIVE: List[Tuple[str, Optional[str], bool]] = [
    ('Transition', 'Additive',     True),
    ('Transition', 'Bridging',     True),
    ('Transition', 'Connecting',   True),
    ('Transition', 'Logical Flow', False),
]

_CONNECTOR_CONTRASTING: List[Tuple[str, Optional[str], bool]] = [
    ('Transition', 'Analytical',   True),
    ('Transition', 'Contrasting',  True),
    ('Transition', 'Comparative',  True),
]

_CONTEXT_FRAME_OPTIONS: List[Tuple[str, Optional[str], bool]] = [
    ('Transition', 'Connecting',   True),
    ('Transition', 'Expanding',    True),
    ('Transition', 'Bridging',     True),
    ('Transition', 'Returning',    True),
]

_REDUNDANCY_OPTIONS: List[Tuple[str, Optional[str], bool]] = [
    ('Expressing Doubt', 'Cautious',         False),
    ('Expressing Doubt', 'Skeptical',        False),
    ('Expressing Doubt', 'Measured',         False),
]

_MERGE_NOTE_OPTIONS: List[Tuple[str, Optional[str], bool]] = [
    ('Storytelling', 'Condensing',   True),
    ('Storytelling', 'Summarizing',  True),
    ('Transition',   'Conclusive',   True),
]

_INTRO_USE_ONE: List[Tuple[str, Optional[str], bool]] = [
    ('Opinion', 'Measured',   True),
    ('Opinion', 'Tentative',  True),
    ('Opinion', 'Humble',     True),
    ('Opinion', 'Analytical', True),
]

_INTRO_MERGE_CONTEXT: List[Tuple[str, Optional[str], bool]] = [
    ('Transition', 'Refocusing', True),
    ('Transition', 'Clarifying', True),
    ('Transition', 'Bridging',   True),
]

_INTRO_MERGE_SOLUTION: List[Tuple[str, Optional[str], bool]] = [
    ('Advice', 'Helpful', False),
    ('Advice', 'Direct',  True),
]

_INTRO_MERGE_STEPS: List[Tuple[str, Optional[str], bool]] = [
    ('Transition',   'Guiding',    True),
    ('Storytelling', 'Condensing', True),
    ('Storytelling', 'Summarizing',True),
]

_INTRO_MERGE: List[Tuple[str, Optional[str], bool]] = [
    ('Transition', 'Bridging',  True),
    ('Transition', 'Expanding', True),
    ('Transition', 'Connecting',True),
]

_HEDGE_OPTIONS: List[Tuple[str, Optional[str], bool]] = [
    ('Filler / Hedge',   'Candid',          True),
    ('Filler / Hedge',   'Approximating',   False),
    ('Filler / Hedge',   'Measured',        False),
    ('Expressing Doubt', 'Measured',        False),
]

_MODE_INTRO_MAP: Dict[str, List[Tuple[str, Optional[str], bool]]] = {
    'use_one':        _INTRO_USE_ONE,
    'merge':          _INTRO_MERGE,
    'merge_context':  _INTRO_MERGE_CONTEXT,
    'merge_solution': _INTRO_MERGE_SOLUTION,
    'merge_steps':    _INTRO_MERGE_STEPS,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def connector(reason_flags: Sequence[str], seed: int = 0) -> str:
    """
    Return a natural connector phrase for joining merged chunks.

    Selects from Transition or Comparison based on whether the brain
    flagged the chunks as complementary, additive, or contrasting.

    The returned phrase ends with '...' — append the following sentence
    after stripping its leading capital, or use directly as a prefix.

    Example:
        conn = connector(reason_flags, seed)
        # "Building on what was said..."
        line = conn + ' ' + sentence[0].lower() + sentence[1:]
    """
    flags = set(reason_flags)
    if 'activation_complementary' in flags:
        return _pool_from(_CONNECTOR_COMPLEMENTARY, seed)
    if 'activation_redundant' in flags:
        return _pool_from(_CONNECTOR_CONTRASTING, seed)
    return _pool_from(_CONNECTOR_ADDITIVE, seed)


def context_frame(terms: Sequence[str], mode: str, seed: int = 0) -> str:
    """
    Return a natural framing sentence for activation_expansion_terms.

    Uses a Transition prefix phrase followed by the comma-joined terms.
    Returns empty string if terms is empty.

    Example:
        context_frame(['butter', 'fond', 'sear'], 'merge_context', seed)
        # "On a related note... butter, fond, sear."
    """
    cleaned = [str(t).strip() for t in terms if str(t).strip()]
    if not cleaned:
        return ''
    phrase = _pool_from(_CONTEXT_FRAME_OPTIONS, seed)
    joined = ', '.join(cleaned[:5])
    if phrase:
        return f'{phrase} {joined}.'
    return f'Relevant signal: {joined}.'


def redundancy_note(seed: int = 0) -> str:
    """
    Return a natural standalone phrase signalling redundant candidates.

    Used in place of the hardcoded 'I kept this to one source because
    the strongest candidates were semantically redundant.'

    Example:
        redundancy_note(seed)
        # "I have my reservations."
        # "Take that with a pinch of salt."
    """
    return _pool_from(_REDUNDANCY_OPTIONS, seed)


def merge_note(seed: int = 0) -> str:
    """
    Return a natural framing phrase for the merge explanation note.

    Used in place of 'I merged complementary recipe chunks rather than
    repeating a single version of the same instructions.'

    Returns a prefix phrase ending in '...' — caller appends context.

    Example:
        merge_note(seed)
        # "Long story short..."
        # "To sum it all up..."
    """
    return _pool_from(_MERGE_NOTE_OPTIONS, seed)


def mode_intro(mode: str, seed: int = 0) -> str:
    """
    Return an intro phrase appropriate for the composition mode.

    Callers can use this as an optional sentence prefix before the
    main body of the rendered answer.

    Example:
        mode_intro('use_one', seed)
        # "I tend to think that..."
        mode_intro('merge_solution', seed)
        # "Here is what I would do in your shoes."
    """
    options = _MODE_INTRO_MAP.get(mode, _INTRO_USE_ONE)
    return _pool_from(options, seed)


def hedge(confidence: float, seed: int = 0) -> str:
    """
    Return a hedging phrase for low-confidence answers.

    Returns empty string when confidence >= 0.72 (no hedge needed).

    Example:
        hedge(0.45, seed)
        # "To be honest with you..."
        hedge(0.85, seed)
        # ''
    """
    if confidence >= 0.72:
        return ''
    return _pool_from(_HEDGE_OPTIONS, seed)
