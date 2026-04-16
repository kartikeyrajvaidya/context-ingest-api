"""Typed input and output schemas for the ingestion action.

In v0, ingestion has no HTTP route — these schemas are the typed input and
output of `core/actions/ingest_document.ingest_document`, which is called from
`scripts/ingest_url.py` and `scripts/ingest_batch.py`. A future batch may add a
manifest-triggered `POST /v1/refresh` endpoint that reuses the same action and
schemas unchanged. See `docs/scaffolding-plan.md` for the rationale.
"""

from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl
from pydantic import model_validator


class IngestRequestSchema(BaseModel):
    """Typed input of the ingestion action."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl | None = Field(
        default=None,
        description="Public URL to fetch and ingest. Required unless `text` is provided.",
    )
    text: str | None = Field(
        default=None,
        description="Raw text body to ingest directly. Required unless `url` is provided.",
        min_length=1,
    )
    title: str | None = Field(
        default=None,
        description="Optional title. Falls back to the document's HTML title if omitted.",
    )
    source_url: str | None = Field(
        default=None,
        description=(
            "Stable canonical identifier for text-path ingestion "
            "(e.g. `internal://faq-setup`). Ignored when `url` is set, since "
            "the URL itself is the identifier. When omitted on the text path, "
            "a content-derived `text://<hash>` identifier is synthesized."
        ),
    )

    @model_validator(mode="after")
    def _require_url_or_text(self) -> "IngestRequestSchema":
        if self.url is None and (self.text is None or not self.text.strip()):
            raise ValueError("one of `url` or `text` is required")
        return self


class IngestResponseSchema(BaseModel):
    """Typed result of the ingestion action.

    `document_id` is `None` only when `status == "failed"`, because no row was
    written. On `ingested` and `unchanged` it is always set.
    """

    document_id: str | None
    status: Literal["ingested", "unchanged", "failed"]
    chunks: int
