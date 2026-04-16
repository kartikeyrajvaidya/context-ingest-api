"""Token-bounded recursive chunker with overlap.

Uses a separator hierarchy (paragraph → line → sentence → word →
token-level fallback) so that messy HTML text degrades gracefully.
Overlap is applied as a post pass over the produced chunks.
"""

import tiktoken

from configs.llm import LLMConfig
from libs.logger import get_logger

logger = get_logger(__name__)

_ENCODING = tiktoken.get_encoding("cl100k_base")
_SEPARATORS = ["\n\n", "\n", ". ", " "]
_MIN_CHUNK_TOKENS = 50


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def chunk_text(
    text: str,
    chunk_size: int = LLMConfig.CHUNK_TOKEN_SIZE,
    overlap: int = LLMConfig.CHUNK_TOKEN_OVERLAP,
    min_chunk_size: int = _MIN_CHUNK_TOKENS,
) -> list[str]:
    if not text.strip():
        return []

    raw_chunks = _recursive_split(text, chunk_size, _SEPARATORS)
    with_overlap = _apply_overlap(raw_chunks, overlap)

    result = [c for c in with_overlap if count_tokens(c) >= min_chunk_size]

    dropped = len(with_overlap) - len(result)
    if dropped:
        logger.info("Dropped %d chunks below %d-token minimum", dropped, min_chunk_size)

    logger.info("Chunked text into %d chunks", len(result))
    return result


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if count_tokens(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    if not separators:
        return _split_by_tokens(text, chunk_size)

    separator = separators[0]
    remaining = separators[1:]

    parts = text.split(separator)
    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = current + separator + part if current else part
        if count_tokens(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current.strip())
        if count_tokens(part) > chunk_size:
            chunks.extend(_recursive_split(part, chunk_size, remaining))
            current = ""
        else:
            current = part

    if current and current.strip():
        chunks.append(current.strip())
    return chunks


def _split_by_tokens(text: str, chunk_size: int) -> list[str]:
    tokens = _ENCODING.encode(text)
    chunks: list[str] = []
    for i in range(0, len(tokens), chunk_size):
        decoded = _ENCODING.decode(tokens[i : i + chunk_size]).strip()
        if decoded:
            chunks.append(decoded)
    return chunks


def _apply_overlap(chunks: list[str], overlap_tokens: int) -> list[str]:
    if len(chunks) <= 1 or overlap_tokens <= 0:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tokens = _ENCODING.encode(chunks[i - 1])
        overlap_text = _ENCODING.decode(prev_tokens[-overlap_tokens:]).strip()
        result.append(f"{overlap_text} {chunks[i]}" if overlap_text else chunks[i])
    return result
