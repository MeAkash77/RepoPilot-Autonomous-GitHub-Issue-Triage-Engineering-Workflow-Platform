"""Source-type-aware chunking.

Token counts are approximated as chars/4 — close enough for budget caps,
and avoids a tokenizer dependency. Each chunk carries a metadata header
prepended into the text itself so the embedding captures provenance.
"""

import re
from dataclasses import dataclass

CHARS_PER_TOKEN = 4

ISSUE_MAX_TOKENS = 800
ISSUE_OVERLAP_FRACTION = 0.15
MARKDOWN_MAX_TOKENS = 600
CODE_MAX_TOKENS = 400


@dataclass
class TextChunk:
    content: str
    chunk_index: int


def _approx_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def _split_with_overlap(text: str, max_tokens: int, overlap_fraction: float) -> list[str]:
    """Greedy paragraph-then-line packing with tail overlap between chunks."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    overlap_chars = int(max_chars * overlap_fraction)
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # Prefer breaking on a paragraph, then a newline, then a space.
            for separator in ("\n\n", "\n", " "):
                cut = text.rfind(separator, start + max_chars // 2, end)
                if cut != -1:
                    end = cut
                    break
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
    return [p for p in pieces if p]


def chunk_issue(
    issue_number: int, title: str, body: str, issue_type: str = "", state: str = ""
) -> list[TextChunk]:
    """One chunk if small; otherwise split with 15% overlap. Metadata header
    is prepended to every chunk so each embedding is self-describing."""
    header_tags = " | ".join(tag for tag in (issue_type, state) if tag)
    header = f"[ISSUE #{issue_number}{' | ' + header_tags if header_tags else ''}] Title: {title}"
    full = f"{header}\n{body}".strip()
    if _approx_tokens(full) <= ISSUE_MAX_TOKENS:
        return [TextChunk(content=full, chunk_index=0)]
    parts = _split_with_overlap(body, ISSUE_MAX_TOKENS, ISSUE_OVERLAP_FRACTION)
    return [TextChunk(content=f"{header}\n{part}", chunk_index=i) for i, part in enumerate(parts)]


_HEADING_RE = re.compile(r"^#{1,6} ", re.MULTILINE)


def chunk_markdown(path: str, text: str) -> list[TextChunk]:
    """Split on headings, packing sections up to the cap."""
    boundaries = [m.start() for m in _HEADING_RE.finditer(text)]
    if not boundaries or boundaries[0] != 0:
        boundaries.insert(0, 0)
    sections = [
        text[start:end].strip()
        for start, end in zip(boundaries, [*boundaries[1:], len(text)], strict=True)
    ]
    sections = [s for s in sections if s]

    chunks: list[TextChunk] = []
    buffer = ""
    for section in sections:
        candidate = f"{buffer}\n\n{section}".strip() if buffer else section
        if buffer and _approx_tokens(candidate) > MARKDOWN_MAX_TOKENS:
            chunks.append(TextChunk(content=f"[DOC {path}]\n{buffer}", chunk_index=len(chunks)))
            buffer = section
        else:
            buffer = candidate
        # An oversized single section still needs splitting.
        if _approx_tokens(buffer) > MARKDOWN_MAX_TOKENS:
            for part in _split_with_overlap(buffer, MARKDOWN_MAX_TOKENS, 0.1):
                chunks.append(TextChunk(content=f"[DOC {path}]\n{part}", chunk_index=len(chunks)))
            buffer = ""
    if buffer:
        chunks.append(TextChunk(content=f"[DOC {path}]\n{buffer}", chunk_index=len(chunks)))
    return chunks


def chunk_code(path: str, text: str) -> list[TextChunk]:
    """Line-window split at top-level definition boundaries when possible.

    tree-sitter symbol splitting is a deliberate non-dependency for now;
    the def/class/function regex boundary heuristic covers the common case.
    """
    max_chars = CODE_MAX_TOKENS * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return [TextChunk(content=f"[CODE {path}]\n{text.strip()}", chunk_index=0)]

    boundary_re = re.compile(
        r"^(def |class |async def |function |export |const |public |private )", re.MULTILINE
    )
    lines = text.splitlines(keepends=True)
    chunks: list[TextChunk] = []
    buffer: list[str] = []
    size = 0
    for line in lines:
        starts_symbol = bool(boundary_re.match(line))
        if buffer and (size + len(line) > max_chars or (starts_symbol and size > max_chars // 2)):
            chunks.append(
                TextChunk(
                    content=f"[CODE {path}]\n{''.join(buffer).strip()}", chunk_index=len(chunks)
                )
            )
            buffer, size = [], 0
        buffer.append(line)
        size += len(line)
    if buffer:
        content = "".join(buffer).strip()
        if content:
            chunks.append(TextChunk(content=f"[CODE {path}]\n{content}", chunk_index=len(chunks)))
    return chunks
