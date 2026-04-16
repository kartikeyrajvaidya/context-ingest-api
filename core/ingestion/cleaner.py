"""HTML and raw-text cleaner.

Two entry points:

- `extract_content(html, url)` — trafilatura-based body + title extraction
  from already-fetched HTML, used on the URL ingest path.
- `clean_raw_text(raw, is_markdown)` — Unicode / whitespace normalization
  plus optional markdown stripping, used on the text ingest path.
"""

import re
import unicodedata
from dataclasses import dataclass

import trafilatura

_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]+")
_HTML_TAG = re.compile(r"<[^>]+>")

_MD_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_MD_HEADING = re.compile(r"^#{1,6}\s+", flags=re.MULTILINE)
_MD_BOLD_ITALIC_STAR = re.compile(r"\*{1,3}([^*]+)\*{1,3}")
_MD_BOLD_ITALIC_UNDER = re.compile(r"_{1,3}([^_]+)_{1,3}")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_MD_INLINE_CODE = re.compile(r"`([^`]+)`")
_MD_BLOCKQUOTE = re.compile(r"^>\s*", flags=re.MULTILINE)
_MD_UL_BULLET = re.compile(r"^[\s]*[-*+]\s+", flags=re.MULTILINE)
_MD_OL_BULLET = re.compile(r"^[\s]*\d+\.\s+", flags=re.MULTILINE)
_MD_HR = re.compile(r"^[-*_]{3,}\s*$", flags=re.MULTILINE)


class EmptyContentError(Exception):
    """Cleaner extracted nothing usable — body was empty, navigation-only, or paywalled."""


@dataclass(frozen=True)
class CleanedContent:
    text: str
    title: str | None


def extract_content(html: str, url: str | None = None) -> CleanedContent:
    body = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    if not body or not body.strip():
        raise EmptyContentError("no extractable content")

    metadata = trafilatura.extract_metadata(html)
    title = metadata.title if metadata else None

    return CleanedContent(text=_collapse_whitespace(body), title=title)


def clean_raw_text(raw: str, is_markdown: bool = False) -> str:
    text = unicodedata.normalize("NFC", raw)

    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2026", "...")

    if is_markdown:
        text = _strip_markdown(text)

    text = _HTML_TAG.sub("", text)
    text = _collapse_whitespace(text)

    if not text:
        raise EmptyContentError("no content after normalization")
    return text


def _collapse_whitespace(text: str) -> str:
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def _strip_markdown(text: str) -> str:
    text = _MD_CODE_FENCE.sub("", text)
    text = _MD_HEADING.sub("", text)
    text = _MD_BOLD_ITALIC_STAR.sub(r"\1", text)
    text = _MD_BOLD_ITALIC_UNDER.sub(r"\1", text)
    text = _MD_IMAGE.sub(r"\1", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_INLINE_CODE.sub(r"\1", text)
    text = _MD_BLOCKQUOTE.sub("", text)
    text = _MD_UL_BULLET.sub("", text)
    text = _MD_OL_BULLET.sub("", text)
    text = _MD_HR.sub("", text)
    return text
