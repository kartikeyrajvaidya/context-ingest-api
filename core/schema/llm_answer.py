"""Internal structured-output schema for the answer-composition LLM call.

Produced by `core/services/llm.generate_answer` and consumed by
`core/actions/query_document`. Field names intentionally match the public
`QueryResponseSchema` so mapping is a dict spread, but the two live apart
so the LLM contract can evolve without touching the public API.
"""

from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class LLMAnswer(BaseModel):
    """Structured-output envelope returned by the answer-composition call."""

    model_config = ConfigDict(extra="forbid")

    answer: str | None = Field(
        description=(
            "Final grounded answer in the user's language. MUST be null when "
            "the retrieved chunks do not contain enough information to answer "
            "the question. Never an empty string — use null for no-answer."
        ),
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Self-assessed confidence in the grounded answer.",
    )
    next_actions: list[str] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "0-3 suggested follow-up questions grounded in the retrieved "
            "chunks. Empty when answer is null or the context is too thin."
        ),
    )
