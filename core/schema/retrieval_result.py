"""Internal retrieval data structures shared by retrieval modules and the composer.

These are not part of the public API contract — they are the in-process shape
that flows from `core/retrieval/` into `core/orchestrator/answer_composer.py`.
Field names intentionally match `CitationSchema` so the composer can map one
into the other without renaming.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict


class RetrievedChunk(BaseModel):
    """A single chunk produced by retrieval, plus the score that ranked it."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    document_id: str
    chunk_order: int
    text: str
    source_url: str
    title: str | None = None
    ingested_at: datetime
    score: float


class RetrievalResult(BaseModel):
    """The fused result of vector + full-text retrieval, top-K only."""

    model_config = ConfigDict(extra="forbid")

    chunks: list[RetrievedChunk]
