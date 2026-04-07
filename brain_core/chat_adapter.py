from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Candidate:
    rank: int
    title: str
    source_label: str
    source_id: str
    lines: str
    scores: Dict[str, float]
    fields: Dict[str, Any]
    raw_preview: str


@dataclass
class ParsedBrainOutput:
    query: str
    confidence: Optional[float]
    stop_reason: Optional[str]
    expanded_terms: List[str]
    evidence_summary: str
    pass_trace: List[Dict[str, Any]]
    candidates: List[Candidate]
    raw_text: str


def _search(pattern: str, text: str, flags: int = 0) -> Optional[str]:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def _safe_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _normalize_key(key: str) -> str:
    key = key.strip().lower()
    key = key.replace('/', '_').replace('-', '_')
    key = re.sub(r'\s+', '_', key)
    key = re.sub(r'[^a-z0-9_]+', '', key)
    return key


def _split_csvish(value: str) -> List[str]:
    parts = [part.strip() for part in value.split(',')]
    return [part for part in parts if part and part.lower() != '(none)']


_KNOWN_FIELD_LABELS = [
    'Dietary Tags', 'Required Terms', 'Expanded Terms', 'Meal Type', 'Tech Stack',
    'Time', 'Prep', 'Cook', 'Serves', 'Cuisine', 'Technique', 'Difficulty',
    'Season', 'Vibe', 'Diet', 'Constraints', 'Dependencies', 'Ingredients',
    'Instructions', 'Pattern', 'Complexity', 'Snippet', 'Code',
]


def _extract_key_values(text: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    key_pattern = re.compile(
        r'(' + '|'.join(re.escape(label) for label in sorted(_KNOWN_FIELD_LABELS, key=len, reverse=True)) + r'):\s*',
        re.IGNORECASE,
    )
    matches = list(key_pattern.finditer(text))
    if not matches:
        return result

    for idx, match in enumerate(matches):
        key = _normalize_key(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        value = text[start:end].strip().strip('|').strip()
        value = re.sub(r'\s+\|\s+$', '', value).strip()
        if not value:
            continue

        if key in {'diet', 'dietary_tags', 'constraints', 'dependencies', 'ingredients', 'expanded_terms', 'required_terms', 'vibe', 'meal_type'}:
            result[key] = _split_csvish(value)
        elif key in {'time', 'prep', 'cook'}:
            time_match = re.search(r'(\d+)\s*min', value, re.IGNORECASE)
            result[f'{key}_min'] = int(time_match.group(1)) if time_match else value
        elif key == 'serves':
            serves_match = re.search(r'(\d+)', value)
            result[key] = int(serves_match.group(1)) if serves_match else value
        else:
            result[key] = value
    return result


def _parse_pass_trace(block: str) -> List[Dict[str, Any]]:
    passes: List[Dict[str, Any]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith('- pass '):
            continue
        match = re.match(
            r'- pass\s+(\d+):\s+conf=([0-9.]+)\s+top=(.*?)\s+new_terms=(.*?)\s+uncovered=(.*)$',
            line,
        )
        if not match:
            passes.append({'raw': line})
            continue
        passes.append(
            {
                'pass': int(match.group(1)),
                'confidence': _safe_float(match.group(2)),
                'top': [item.strip() for item in match.group(3).split(',') if item.strip()],
                'new_terms': [] if match.group(4).strip() == '(none)' else [item.strip() for item in match.group(4).split(',') if item.strip()],
                'uncovered': [] if match.group(5).strip() == '(none)' else [item.strip() for item in match.group(5).split(',') if item.strip()],
            }
        )
    return passes


def parse_brain_output(text: str) -> ParsedBrainOutput:
    query = _search(r'^Query:\s*(.+)$', text, re.MULTILINE) or ''
    confidence = _safe_float(_search(r'^Controller confidence:\s*([0-9.]+)$', text, re.MULTILINE))
    stop_reason = _search(r'^Stop reason:\s*(.+)$', text, re.MULTILINE)

    expanded_terms_raw = _search(r'^Expanded terms:\s*(.+)$', text, re.MULTILINE) or ''
    expanded_terms = [] if expanded_terms_raw.lower() == '(none)' else [item.strip() for item in expanded_terms_raw.split(',') if item.strip()]

    evidence_summary = _search(
        r'Working evidence summary:\n(.*?)\n\nTop cited chunks:',
        text,
        re.DOTALL,
    ) or ''

    pass_trace_block = _search(
        r'Pass trace:\n(.*?)\n\nDetailed top results:',
        text,
        re.DOTALL,
    ) or ''
    pass_trace = _parse_pass_trace(pass_trace_block)

    short_pattern = re.compile(
        r'^- \[(.*?)\]\s+(.*?)\s+\(lex=([0-9.\-]+),\s*vec=([0-9.\-]+),\s*rerank=([0-9.\-]+),\s*final=([0-9.\-]+)\)$',
        re.MULTILINE,
    )
    short_entries: Dict[str, Dict[str, Any]] = {}
    for idx, match in enumerate(short_pattern.finditer(text), start=1):
        source_label = match.group(1).strip()
        title = match.group(2).strip()
        source_id = ''
        source_id_match = re.search(r'::\s*([^:\]]+::\d+)\s*::\s*lines', source_label)
        if source_id_match:
            source_id = source_id_match.group(1).strip()
        else:
            tokens = [token.strip() for token in source_label.split('::') if token.strip()]
            if len(tokens) >= 2:
                source_id = '::'.join(tokens[-2:])
        lines_match = re.search(r'lines\s+([0-9\-]+)', source_label)
        short_entries[source_label] = {
            'rank': idx,
            'title': title,
            'source_label': source_label,
            'source_id': source_id,
            'lines': lines_match.group(1) if lines_match else '',
            'scores': {
                'lexical': float(match.group(3)),
                'vector': float(match.group(4)),
                'rerank': float(match.group(5)),
                'final': float(match.group(6)),
            },
        }

    detailed_pattern = re.compile(
        r'^- (.*?) :: (.*?) :: (.*?) :: (.*?) :: lines ([0-9\-]+)\n'
        r'\s+lexical=([0-9.\-]+)\s+vector=([0-9.\-]+)\s+rerank=([0-9.\-]+)\s+final=([0-9.\-]+)\n'
        r'\s+(.*?)(?=\n- .*? :: .*? :: .*? :: .*? :: lines [0-9\-]+|\Z)',
        re.MULTILINE | re.DOTALL,
    )

    candidates: List[Candidate] = []
    for idx, match in enumerate(detailed_pattern.finditer(text), start=1):
        source_group_a = match.group(1).strip()
        source_group_b = match.group(2).strip()
        source_id = match.group(3).strip()
        title = match.group(4).strip()
        lines = match.group(5).strip()
        preview = re.sub(r'\s+', ' ', match.group(10)).strip()
        candidates.append(
            Candidate(
                rank=idx,
                title=title,
                source_label=f'{source_group_a} :: {source_group_b} :: {source_id} :: lines {lines}',
                source_id=source_id,
                lines=lines,
                scores={
                    'lexical': float(match.group(6)),
                    'vector': float(match.group(7)),
                    'rerank': float(match.group(8)),
                    'final': float(match.group(9)),
                },
                fields=_extract_key_values(preview),
                raw_preview=preview,
            )
        )

    if candidates:
        for candidate in candidates:
            for short in short_entries.values():
                if short['source_id'] and candidate.source_id == short['source_id']:
                    candidate.rank = short['rank']
                    candidate.scores = short['scores']
                    break
        candidates.sort(key=lambda item: item.rank)
    else:
        for short in short_entries.values():
            candidates.append(
                Candidate(
                    rank=short['rank'],
                    title=short['title'],
                    source_label=short['source_label'],
                    source_id=short['source_id'],
                    lines=short['lines'],
                    scores=short['scores'],
                    fields={},
                    raw_preview='',
                )
            )

    return ParsedBrainOutput(
        query=query,
        confidence=confidence,
        stop_reason=stop_reason,
        expanded_terms=expanded_terms,
        evidence_summary=evidence_summary.strip(),
        pass_trace=pass_trace,
        candidates=candidates,
        raw_text=text,
    )


FOOD_HINTS = {
    'steak', 'lunch', 'dinner', 'breakfast', 'brunch', 'snack', 'recipe', 'recipes',
    'cook', 'cooking', 'make', 'eat', 'food', 'meal', 'meals', 'bake', 'baked',
    'cuban', 'italian', 'mexican', 'chicken', 'beef', 'pasta', 'beans', 'soup',
    'egg', 'eggs', 'bread', 'toast', 'pumpkin', 'squash', 'apple', 'oatmeal',
    'mushroom', 'mushrooms', 'potato', 'potatoes', 'autumn', 'fall', 'cozy',
    'comfort', 'comforting', 'seasonal', 'morning',
}
CODE_HINTS = {
    'python', 'react', 'node', 'javascript', 'typescript', 'java', 'kotlin', 'rust',
    'error', 'bug', 'exception', 'traceback', 'function', 'class', 'compile', 'build',
    'api', 'sql', 'query', 'render', 'state', 'hook', 'memo', 'component', 'server',
    'website', 'web', 'html', 'css', 'spa', 'router', 'route', 'refresh', 'modal',
    'dialog', 'nav', 'scroll', 'listener', 'event', 'frontend', 'backend', '404',
}


def infer_domain(parsed: ParsedBrainOutput, forced_mode: str = 'auto') -> str:
    if forced_mode != 'auto':
        return forced_mode

    haystack = ' '.join(
        [
            parsed.query,
            parsed.evidence_summary,
            ' '.join(candidate.title for candidate in parsed.candidates),
            ' '.join(candidate.raw_preview for candidate in parsed.candidates[:5]),
        ]
    ).lower()
    food_hits = sum(1 for token in FOOD_HINTS if token in haystack)
    code_hits = sum(1 for token in CODE_HINTS if token in haystack)

    if code_hits > food_hits and code_hits >= 2:
        return 'code_assistant'
    if food_hits >= 2:
        return 'chatbot_food'
    return 'chatbot_general'





META_SOURCE_STEMS = {'library_input_notes', 'retrieval_notes', 'readme'}


def _source_path_from_label(source_label: str) -> str:
    parts = [part.strip() for part in str(source_label or '').split('::')]
    if len(parts) >= 2:
        return parts[1]
    return ''


def _is_meta_candidate(source_label: str, title: str = '') -> bool:
    path = _source_path_from_label(source_label).replace('\\', '/').lower()
    stem = path.rsplit('/', 1)[-1].rsplit('.', 1)[0] if path else ''
    if stem in META_SOURCE_STEMS:
        return True
    lowered_title = str(title or '').strip().lower()
    return lowered_title in {'root', 'result'} and stem in META_SOURCE_STEMS


def _candidate_source_type_from_label(source_label: str, source_id: str = '') -> str:
    blob = f"{source_label} {source_id}".lower()
    for token in ('recipes', 'code', 'docs', 'specs'):
        if f'/{token}/' in blob or f'::{token}/' in blob or blob.startswith(token + '/'):
            return token
    return ''


def _filter_candidates_for_domain(candidates: List[Candidate], domain: str) -> tuple[List[Candidate], List[str]]:
    if not candidates:
        return candidates, []

    preferred_sources: set[str]
    if domain == 'code_assistant':
        preferred_sources = {'code', 'docs', 'specs'}
    elif domain == 'chatbot_food':
        preferred_sources = {'recipes'}
    else:
        return candidates, []

    preferred_non_meta = []
    preferred_meta = []
    non_preferred = []
    reasons: List[str] = []
    for candidate in candidates:
        source_type = _candidate_source_type_from_label(candidate.source_label, candidate.source_id)
        is_meta = _is_meta_candidate(candidate.source_label, candidate.title)
        if source_type in preferred_sources:
            if is_meta:
                preferred_meta.append(candidate)
            else:
                preferred_non_meta.append(candidate)
        else:
            non_preferred.append(candidate)

    if preferred_non_meta or preferred_meta:
        if non_preferred:
            reasons.append(f'filtered {len(non_preferred)} off-domain result(s) for {domain}')
        if preferred_non_meta and preferred_meta:
            reasons.append(f'demoted {len(preferred_meta)} meta note result(s) for {domain}')
        return preferred_non_meta + preferred_meta + non_preferred, reasons
    return candidates, reasons


def build_structured_output_from_trace(trace_payload: Dict[str, Any], mode: str = 'auto') -> Dict[str, Any]:
    query = str(trace_payload.get('query', '')).strip()
    state = trace_payload.get('state', {}) or {}
    pass_records = state.get('pass_records', []) or []
    confidence = state.get('final_confidence')
    stop_reason = state.get('stop_reason') or ''
    expanded_terms = state.get('expanded_terms', []) or []
    summary = str(trace_payload.get('working_memory', '') or '').strip()
    brain_decision = trace_payload.get('brain_decision', {}) or {}

    candidates: List[Candidate] = []
    for idx, item in enumerate(trace_payload.get('top_results', []) or [], start=1):
        source_path = str(item.get('source_path', '')).strip()
        library_id = str(item.get('library_id', '')).strip()
        chunk_id = str(item.get('chunk_id', '')).strip()
        heading = str(item.get('heading', '')).strip() or 'result'
        line_hint = ''
        if 'reasoning_trace' in item and isinstance(item['reasoning_trace'], dict):
            rt = item['reasoning_trace']
            line_hint = str(rt.get('chunk_line_span', '')).strip()
        raw_lines = str(item.get('line_start', '')).strip()
        if not line_hint and raw_lines:
            line_hint = raw_lines
        preview = ''
        reasoning_trace = item.get('reasoning_trace') or {}
        if isinstance(reasoning_trace, dict):
            preview = str(reasoning_trace.get('chunk_preview', '')).strip()
        if not preview:
            preview = str(item.get('preview', '')).strip()
        fields = _extract_key_values(preview)
        source_label = ' :: '.join(part for part in [library_id, source_path, chunk_id, f'lines {line_hint}' if line_hint else ''] if part)
        candidates.append(Candidate(
            rank=idx,
            title=heading,
            source_label=source_label,
            source_id=chunk_id,
            lines=line_hint,
            scores={
                'lexical': float(item.get('lexical_score', 0.0) or 0.0),
                'vector': float(item.get('vector_score', 0.0) or 0.0),
                'rerank': float(item.get('rerank_score', 0.0) or 0.0),
                'final': float(item.get('final_score', 0.0) or 0.0),
            },
            fields=fields,
            raw_preview=preview,
        ))

    parsed = ParsedBrainOutput(
        query=query,
        confidence=float(confidence) if confidence is not None else None,
        stop_reason=stop_reason or None,
        expanded_terms=[str(x) for x in expanded_terms if str(x).strip()],
        evidence_summary=summary,
        pass_trace=pass_records,
        candidates=candidates,
        raw_text=str(trace_payload.get('answer', '') or ''),
    )
    structured = build_structured_output(parsed, mode=mode)
    if brain_decision:
        structured['brain'] = brain_decision
        structured.setdefault('retrieval_notes', {})['brain_decision'] = brain_decision
    return structured

def detect_noise(parsed: ParsedBrainOutput, domain: str) -> Dict[str, Any]:
    notes: Dict[str, Any] = {'noise_detected': False, 'reasons': [], 'safety_flags': []}
    query_text = parsed.query.lower()

    if domain == 'chatbot_food':
        asked_for_drink = any(token in query_text for token in ('drink', 'cocktail', 'beverage', 'coffee', 'tea'))
        for candidate in parsed.candidates[:5]:
            blob = f'{candidate.title} {candidate.source_label} {candidate.raw_preview}'.lower()
            if not asked_for_drink and any(token in blob for token in ('martini', 'mojito', 'daiquiri', 'cocktail', 'beverages.md')):
                notes['noise_detected'] = True
                notes['reasons'].append(f'beverage result surfaced for non-drink query: {candidate.title}')
            if 'breakfast' in query_text and any(token in blob for token in ('mojito', 'daiquiri', 'cocktail')):
                notes['noise_detected'] = True
                notes['reasons'].append(f'cocktail surfaced for breakfast query: {candidate.title}')

    if domain == 'code_assistant':
        joined = ' '.join(f'{candidate.title} {candidate.raw_preview}' for candidate in parsed.candidates[:5]).lower()
        if 'react' in query_text and any(token in joined for token in ('vue', 'angular', 'svelte')):
            notes['noise_detected'] = True
            notes['reasons'].append('non-React frontend framework surfaced in React query')
        query_tokens = set(re.findall(r'[a-z0-9_+#.-]+', query_text))
        joined_tokens = set(re.findall(r'[a-z0-9_+#.-]+', joined))
        if 'python' in query_tokens and 'java' in joined_tokens:
            notes['noise_detected'] = True
            notes['reasons'].append('Java result surfaced in Python query')
        if 'dangerouslysetinnerhtml' in joined and 'sanitize' not in joined:
            notes['safety_flags'].append('unsanitized_html_rendering')
        if re.search(r'\bselect \* from\b', joined) and any(token in query_text for token in ('user input', 'search', 'query builder')):
            notes['safety_flags'].append('possible_sql_injection_risk')

    return notes


def _clean_summary(text: str, domain: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    if domain == 'chatbot_food':
        cleaned = re.sub(
            r'\bAdd primary ingredients and cook using the listed technique until done\.?\s*',
            '',
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r'\bSeason to taste and finish with any fresh herbs/acid\.?\s*',
            '',
            cleaned,
            flags=re.IGNORECASE,
        )
    return re.sub(r'\s+', ' ', cleaned).strip()


def build_structured_output(parsed: ParsedBrainOutput, mode: str = 'auto') -> Dict[str, Any]:
    domain = infer_domain(parsed, forced_mode=mode)
    filtered_candidates, filter_reasons = _filter_candidates_for_domain(parsed.candidates, domain)
    if filtered_candidates is not parsed.candidates:
        parsed = ParsedBrainOutput(
            query=parsed.query,
            confidence=parsed.confidence,
            stop_reason=parsed.stop_reason,
            expanded_terms=parsed.expanded_terms,
            evidence_summary=parsed.evidence_summary,
            pass_trace=parsed.pass_trace,
            candidates=filtered_candidates,
            raw_text=parsed.raw_text,
        )
    notes = detect_noise(parsed, domain)
    if filter_reasons:
        notes['noise_detected'] = True
        notes['reasons'].extend(filter_reasons)
    top = parsed.candidates[0] if parsed.candidates else None

    key_attributes: Dict[str, Any] = {}
    if top:
        for key in (
            'cuisine', 'technique', 'time_min', 'prep_min', 'cook_min',
            'diet', 'dietary_tags', 'season', 'vibe', 'difficulty', 'meal_type',
            'tech_stack', 'pattern', 'complexity', 'constraints',
            'dependencies', 'ingredients', 'instructions', 'snippet',
        ):
            if key in top.fields:
                key_attributes[key] = top.fields[key]

    query_text = parsed.query.lower()
    intent = 'general_query'
    if domain == 'chatbot_food':
        if any(token in query_text for token in ('make', 'cook', 'recipe')):
            intent = 'recipe_request'
        elif any(token in query_text for token in ('recommend', 'lunch', 'dinner', 'breakfast', 'eat')):
            intent = 'food_recommendation'
        else:
            intent = 'food_query'
    elif domain == 'code_assistant':
        if any(token in query_text for token in ('fix', 'error', 'bug', 'exception')):
            intent = 'debug_request'
        elif any(token in query_text for token in ('recommend', 'best way', 'pattern', 'architecture')):
            intent = 'code_recommendation'
        else:
            intent = 'code_solution'

    return {
        'query': parsed.query,
        'domain': domain,
        'intent': intent,
        'confidence': {
            'controller': parsed.confidence,
            'stop_reason': parsed.stop_reason,
        },
        'answer': {
            'summary': _clean_summary(parsed.evidence_summary, domain),
            'key_attributes': key_attributes,
        },
        'candidates': [
            {
                'rank': candidate.rank,
                'title': candidate.title,
                'source': {
                    'label': candidate.source_label,
                    'id': candidate.source_id,
                    'lines': candidate.lines,
                },
                'scores': candidate.scores,
                'fields': candidate.fields,
                'preview': candidate.raw_preview,
            }
            for candidate in parsed.candidates[:5]
        ],
        'retrieval_notes': {
            'expanded_terms': parsed.expanded_terms,
            'passes': parsed.pass_trace,
            **notes,
        },
    }


def _join_items(items: List[str], max_items: int = 5) -> str:
    items = [item for item in items if item]
    if not items:
        return ''
    items = items[:max_items]
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f'{items[0]} and {items[1]}'
    return ', '.join(items[:-1]) + f', and {items[-1]}'


def _short_snippet(snippet: str, max_len: int = 700) -> str:
    snippet = snippet.strip()
    if len(snippet) <= max_len:
        return snippet
    return snippet[: max_len - 3].rstrip() + '...'


def _value_as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if ',' in text:
        return _split_csvish(text)
    return [text]


def _format_profile_bits(*, cuisine: Any = None, technique: Any = None, season: Any = None, vibe: Any = None, meal_type: Any = None, difficulty: Any = None) -> str:
    bits: List[str] = []
    if cuisine:
        bits.append(f'cuisine {str(cuisine).strip()}')
    if technique:
        bits.append(f'technique {str(technique).strip()}')
    season_items = _value_as_list(season)
    if season_items:
        bits.append(f'season {_join_items(season_items, max_items=4)}')
    vibe_items = _value_as_list(vibe)
    if vibe_items:
        bits.append(f'vibe {_join_items(vibe_items, max_items=5)}')
    meal_items = _value_as_list(meal_type)
    if meal_items:
        bits.append(f'meal {_join_items(meal_items, max_items=4)}')
    if difficulty:
        bits.append(f'{str(difficulty).strip()} difficulty')
    return '; '.join(bits)


def _clean_code_preview(preview: str) -> str:
    preview = re.sub(r'\s+', ' ', (preview or '').strip())
    preview = preview.replace('**.', '.').replace('**', '')
    return preview


def _truncate_code_summary(text: str, max_len: int = 420) -> str:
    text = _clean_code_preview(text)
    if not text:
        return ''
    text = re.sub(r'Library input notes?:.*$', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'If this is going into a real code path.*$', '', text, flags=re.IGNORECASE).strip()
    cut_markers = [
        ' const ', ' let ', ' var ', ' export ', ' function ', ' class ', ' ```',
    ]
    for marker in cut_markers:
        idx = text.find(marker)
        if idx > 120:
            text = text[:idx].rstrip()
            break
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) > 2:
        text = ' '.join(sentences[:2]).strip()
    if len(text) > max_len:
        text = text[:max_len - 3].rstrip() + '...'
    return text

def generate_response(structured: Dict[str, Any]) -> str:
    domain = structured['domain']
    if domain == 'code_assistant':
        return _generate_code_response(structured)
    if domain == 'chatbot_food':
        return _generate_food_response(structured)
    return _generate_general_response(structured)


def _generate_food_response(structured: Dict[str, Any]) -> str:
    query = structured['query']
    summary = structured['answer']['summary']
    attrs = structured['answer']['key_attributes']
    candidates = structured['candidates']
    notes = structured['retrieval_notes']

    pieces: List[str] = []
    title = candidates[0]['title'] if candidates else ''
    cuisine = attrs.get('cuisine')
    technique = attrs.get('technique')
    time_min = attrs.get('time_min')
    prep_min = attrs.get('prep_min')
    cook_min = attrs.get('cook_min')
    season = attrs.get('season')
    vibe = attrs.get('vibe')
    difficulty = attrs.get('difficulty')
    meal_type = attrs.get('meal_type')
    ingredients = attrs.get('ingredients', [])

    if 'how do i make' in query.lower() or 'how to make' in query.lower():
        if title:
            pieces.append(f'Best match here is **{title}**.')
        if summary:
            pieces.append(summary)
        if ingredients:
            pieces.append(f'You\'ll mainly need {_join_items(ingredients, max_items=6)}.')
        if technique:
            low_technique = str(technique).lower()
            if 'grill' in low_technique:
                pieces.append('Get the grill or pan properly hot before the meat goes in, then let it rest before slicing.')
            elif 'sear' in low_technique:
                pieces.append('Use high heat for the crust, then back off so you don\'t overshoot the center.')
        profile = _format_profile_bits(
            cuisine=cuisine,
            technique=technique,
            season=season,
            vibe=vibe,
            meal_type=meal_type,
            difficulty=difficulty,
        )
        if profile:
            pieces.append('Profile: ' + profile + '.')
    else:
        if title:
            pieces.append(f'Top pick is **{title}**.')
        profile = _format_profile_bits(
            cuisine=cuisine,
            technique=technique,
            season=season,
            vibe=vibe,
            meal_type=meal_type,
            difficulty=difficulty,
        )
        if profile:
            pieces.append('That comes through as ' + profile + '.')
        if summary:
            pieces.append(summary)

    if time_min:
        pieces.append(f'Estimated time: {time_min} minutes.')
    elif prep_min or cook_min:
        timing_bits = []
        if prep_min:
            timing_bits.append(f'prep {prep_min} min')
        if cook_min:
            timing_bits.append(f'cook {cook_min} min')
        pieces.append('Estimated time: ' + ' + '.join(timing_bits) + '.')

    if notes.get('noise_detected') and notes.get('reasons'):
        pieces.append('I ignored a couple noisy hits in the retrieval set: ' + '; '.join(notes['reasons'][:2]) + '.')

    return ' '.join(pieces).strip()


def _generate_code_response(structured: Dict[str, Any]) -> str:
    summary = structured['answer']['summary']
    attrs = structured['answer']['key_attributes']
    candidates = structured['candidates']
    notes = structured['retrieval_notes']

    pieces: List[str] = []
    title = candidates[0]['title'] if candidates else ''
    tech_stack = attrs.get('tech_stack')
    pattern = attrs.get('pattern')
    complexity = attrs.get('complexity')
    dependencies = attrs.get('dependencies', [])
    constraints = attrs.get('constraints', [])
    snippet = attrs.get('snippet') or attrs.get('code') or ''

    top_source = ''
    top_preview = ''
    if candidates:
        top_source = _candidate_source_type_from_label(candidates[0].get('source', {}).get('label', ''), candidates[0].get('source', {}).get('id', ''))
        top_preview = _clean_code_preview(str(candidates[0].get('preview', '') or ''))

    code_summary = _truncate_code_summary(summary)
    if top_source in {'code', 'docs', 'specs'} and top_preview and not _is_meta_candidate(candidates[0].get('source', {}).get('label', '') if candidates else '', title):
        code_summary = _truncate_code_summary(top_preview)

    top_label = candidates[0].get('source', {}).get('label', '') if candidates else ''
    if _is_meta_candidate(top_label, title) and candidates:
        source_path = _source_path_from_label(top_label).replace('\\', '/').lower()
        stem = source_path.rsplit('/', 1)[-1].rsplit('.', 1)[0] if source_path else ''
        if stem:
            title = stem.replace('_', ' ').title()
    if title:
        pieces.append(f'Best match is **{title}**.')
    if code_summary:
        pieces.append(code_summary)
    if tech_stack:
        pieces.append(f'Stack context: {tech_stack}.')
    if pattern:
        pieces.append(f'Use the {pattern} approach here.')
    if dependencies:
        pieces.append(f'Dependencies in play: {_join_items([str(dep) for dep in dependencies], max_items=6)}.')
    if constraints:
        pieces.append(f'Constraints: {_join_items([str(item) for item in constraints], max_items=6)}.')
    if snippet:
        pieces.append('Drop-in shape:')
        pieces.append('```')
        pieces.append(_short_snippet(str(snippet)))
        pieces.append('```')
    if complexity:
        pieces.append(f'Complexity looks {complexity}.')
    if notes.get('safety_flags'):
        pieces.append('Safety flags: ' + ', '.join(notes['safety_flags']) + '.')
    if top_source not in {'code', 'docs', 'specs'} and not snippet and not pattern:
        pieces.append('This still does not look like a strong code-specific match, so I would treat it as weak retrieval rather than trusted guidance.')
    pieces.append('If this is going into a real code path, test the happy path and one failure path before you lock it in.')
    return ' '.join(pieces).strip()


def _generate_general_response(structured: Dict[str, Any]) -> str:
    summary = structured['answer']['summary']
    candidates = structured['candidates']
    notes = structured['retrieval_notes']
    pieces: List[str] = []
    title = candidates[0]['title'] if candidates else ''
    if title:
        pieces.append(f'Top result is **{title}**.')
    if summary:
        pieces.append(summary)
    if notes.get('noise_detected'):
        pieces.append('There was some retrieval noise, so I biased toward the highest-confidence match.')
    return ' '.join(pieces).strip()
