from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import re

from .text_utils import keywords, normalize_text

CODE_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp', '.rs', '.go', '.kt', '.swift'}
CODE_SYMBOL_RE = re.compile(
    r'^(?:def|class|async\s+def)\s+([A-Za-z_][A-Za-z0-9_]*)|'
    r'^(?:function)\s+([A-Za-z_][A-Za-z0-9_]*)|'
    r'^(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(?|'
    r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(?|'
    r'^(?:export\s+)?(?:interface|type|enum)\s+([A-Za-z_][A-Za-z0-9_]*)',
    re.MULTILINE,
)
LIBRARY_ID_RE = re.compile(r'[^a-z0-9._-]+')


@dataclass
class Chunk:
    chunk_id: str
    source_path: str
    source_type: str
    heading: str
    text: str
    token_count: int
    keyword_list: List[str]
    chunk_kind: str = 'prose'
    symbol_name: str = ''
    line_start: int = 1
    line_end: int = 1
    library_id: str = ''


def sanitize_library_id(value: str) -> str:
    value = str(value or '').strip().lower()
    value = value.replace(' ', '-')
    value = LIBRARY_ID_RE.sub('-', value).strip('-')
    return value or 'library'


def derive_library_id(path: Path) -> str:
    return sanitize_library_id(path.name)


def derive_source_type(relative_path: Path) -> str:
    parts = [p.strip().lower() for p in relative_path.parts if p and p not in {'.', '..'}]
    return parts[0] if parts else 'root'


def make_chunk_id(library_id: str, relative_path: Path | str, counter: int) -> str:
    rel = str(relative_path).replace('\\', '/').lstrip('./')
    return f'{sanitize_library_id(library_id)}::{rel}::{counter}'


def _line_offsets(text: str) -> List[int]:
    offsets = [0]
    total = 0
    for line in text.splitlines(True):
        total += len(line)
        offsets.append(total)
    return offsets


def _line_for_char(offsets: List[int], char_index: int) -> int:
    lo, hi = 0, len(offsets) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if offsets[mid] <= char_index:
            lo = mid
        else:
            hi = mid - 1
    return max(1, lo + 1)


def _split_prose_sections(text: str) -> List[tuple[str, str, int, int]]:
    text = normalize_text(text)
    lines = text.split('\n')
    sections: List[tuple[str, List[str], int]] = []
    current_heading = 'root'
    current_lines: List[str] = []
    current_start_line = 1
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith('#'):
            if current_lines:
                sections.append((current_heading, current_lines, current_start_line))
                current_lines = []
            current_heading = stripped.lstrip('#').strip() or 'section'
            current_start_line = idx + 1
        else:
            if not current_lines:
                current_start_line = idx
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, current_lines, current_start_line))

    out: List[tuple[str, str, int, int]] = []
    for heading, sec_lines, start_line in sections:
        body = '\n'.join(sec_lines).strip()
        if body:
            end_line = start_line + len(sec_lines) - 1
            out.append((heading, body, start_line, end_line))
    return out


def _paragraph_windows(text: str, chunk_chars: int, overlap_paragraphs: int = 1) -> List[tuple[str, int, int]]:
    text = normalize_text(text).strip()
    if not text:
        return []

    lines = text.split("\n")
    paragraph_rows: List[tuple[str, int, int]] = []
    current_lines: List[str] = []
    start_line = 1
    for idx, line in enumerate(lines, start=1):
        if line.strip():
            if not current_lines:
                start_line = idx
            current_lines.append(line)
        elif current_lines:
            paragraph_rows.append(("\n".join(current_lines).strip(), start_line, idx - 1))
            current_lines = []
    if current_lines:
        paragraph_rows.append(("\n".join(current_lines).strip(), start_line, len(lines)))

    if not paragraph_rows:
        return [(text, 1, text.count("\n") + 1)]

    windows: List[tuple[str, int, int]] = []
    i = 0
    while i < len(paragraph_rows):
        current: List[str] = []
        chars = 0
        start = i
        start_line = paragraph_rows[i][1]
        end_line = start_line
        while i < len(paragraph_rows):
            paragraph_text, _, paragraph_end = paragraph_rows[i]
            extra = len(paragraph_text) + (2 if current else 0)
            if current and chars + extra > chunk_chars:
                break
            current.append(paragraph_text)
            chars += extra
            end_line = paragraph_end
            i += 1
        windows.append(("\n\n".join(current), start_line, end_line))
        if i >= len(paragraph_rows):
            break
        rewind = min(overlap_paragraphs, max(0, i - start - 1))
        if rewind > 0:
            i -= rewind
    return windows

def _code_blocks(text: str, chunk_chars: int, overlap_chars: int) -> List[tuple[str, str, int, int]]:
    text = normalize_text(text)
    if not text.strip():
        return []
    offsets = _line_offsets(text)
    matches = list(CODE_SYMBOL_RE.finditer(text))
    blocks: List[tuple[str, str, int, int]] = []

    if not matches:
        start = 0
        block_index = 0
        while start < len(text):
            end = min(len(text), start + chunk_chars)
            if end < len(text):
                cut = text.rfind('\n', start, end)
                if cut > start + (chunk_chars // 3):
                    end = cut
            piece = text[start:end].strip('\n')
            if piece.strip():
                ls = _line_for_char(offsets, start)
                le = _line_for_char(offsets, max(start, end - 1))
                blocks.append((f'code block {block_index}', piece, ls, le))
                block_index += 1
            if end >= len(text):
                break
            start = max(end - overlap_chars, start + 1)
        return blocks

    spans: List[tuple[int, int, str]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        symbol = next((g for g in match.groups() if g), '')
        spans.append((start, end, symbol))

    for idx, (start, end, symbol) in enumerate(spans):
        piece = text[start:end].strip('\n')
        if not piece.strip():
            continue
        ls = _line_for_char(offsets, start)
        le = _line_for_char(offsets, max(start, end - 1))
        title = symbol or f'code symbol {idx}'
        if len(piece) <= chunk_chars:
            blocks.append((title, piece, ls, le))
            continue
        local_start = 0
        while local_start < len(piece):
            local_end = min(len(piece), local_start + chunk_chars)
            if local_end < len(piece):
                cut = piece.rfind('\n', local_start, local_end)
                if cut > local_start + (chunk_chars // 3):
                    local_end = cut
            sub = piece[local_start:local_end].strip('\n')
            if sub.strip():
                sub_ls = ls + piece[:local_start].count('\n')
                sub_le = ls + piece[:max(local_start, local_end - 1)].count('\n')
                blocks.append((title, sub, sub_ls, sub_le))
            if local_end >= len(piece):
                break
            local_start = max(local_end - overlap_chars, local_start + 1)
    return blocks


def chunk_file(
    path: Path,
    chunk_chars: int = 700,
    overlap: int = 120,
    library_root: Path | None = None,
    library_id: str = '',
) -> List[Chunk]:
    library_root = library_root.resolve() if library_root is not None else path.parent.resolve()
    resolved_path = path.resolve()
    try:
        rel_path_obj = resolved_path.relative_to(library_root)
    except ValueError:
        rel_path_obj = Path(path.name)
    rel_path = rel_path_obj.as_posix()
    normalized_library_id = sanitize_library_id(library_id or derive_library_id(library_root))
    source_type = derive_source_type(rel_path_obj)
    text = path.read_text(encoding='utf-8', errors='ignore')
    chunks: List[Chunk] = []
    counter = 0

    if path.suffix.lower() in CODE_EXTENSIONS or source_type == 'code':
        for heading, body, line_start, line_end in _code_blocks(text, chunk_chars=max(420, chunk_chars), overlap_chars=max(60, overlap)):
            chunk_id = make_chunk_id(normalized_library_id, rel_path_obj, counter)
            kws = keywords(f'{heading} {body}', limit=18)
            symbol_name = heading if heading and not heading.startswith('code block') else ''
            chunks.append(Chunk(
                chunk_id=chunk_id,
                source_path=rel_path,
                source_type=source_type,
                heading=heading,
                text=body,
                token_count=len(body.split()),
                keyword_list=kws,
                chunk_kind='code',
                symbol_name=symbol_name,
                line_start=line_start,
                line_end=line_end,
                library_id=normalized_library_id,
            ))
            counter += 1
        return chunks

    for heading, body, section_start, _section_end in _split_prose_sections(text):
        for piece, line_start, line_end in _paragraph_windows(body, chunk_chars=max(420, chunk_chars), overlap_paragraphs=1):
            chunk_id = make_chunk_id(normalized_library_id, rel_path_obj, counter)
            kws = keywords(f'{heading} {piece}', limit=16)
            chunks.append(Chunk(
                chunk_id=chunk_id,
                source_path=rel_path,
                source_type=source_type,
                heading=heading,
                text=piece,
                token_count=len(piece.split()),
                keyword_list=kws,
                chunk_kind='prose',
                symbol_name='',
                line_start=max(1, section_start + line_start - 1),
                line_end=max(1, section_start + line_end - 1),
                library_id=normalized_library_id,
            ))
            counter += 1
    return chunks
