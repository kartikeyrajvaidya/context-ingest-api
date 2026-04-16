"""Request schema for POST /v1/feedback.

The contract is frozen for v0. See `docs/api/feedback.md` for the canonical spec.

Feedback is recorded with replace semantics: one row per `query_id`. A POST
against a `query_id` that already has feedback overwrites the existing row
(implemented via `INSERT ... ON CONFLICT (query_id) DO UPDATE` in the action
layer, so the write is atomic).

`rating` is intentionally free-form text — operators pick their own vocabulary
(thumbs, stars, labels, emojis). ContextIngest does not validate the value
beyond length and non-blank checks. The only cost operators pay for
flexibility is that mixed vocabularies in the `feedback` table make analysis
harder; pick one convention per deployment and stick with it.

The endpoint returns `204 No Content` on success, so there is no response
model.
"""

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator


class FeedbackRequestSchema(BaseModel):
    """Inner payload for POST /v1/feedback."""

    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(min_length=1)
    rating: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("query_id", "rating")
    @classmethod
    def _non_blank_trimmed(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("reason")
    @classmethod
    def _reason_trimmed_or_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None
