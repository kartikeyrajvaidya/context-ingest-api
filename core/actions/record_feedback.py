"""Record-feedback action.

Single callable behind `POST /v1/feedback`. Verifies the referenced
`query_id` exists in `query_requests`, then atomically upserts the
feedback row via `Feedback.upsert_by_query_id` — one row per `query_id`,
last write wins (replace semantics frozen in Batch 2b).

Raises `QueryNotFoundError` — a plain domain exception — when the
`query_id` does not reference any row in `query_requests`. The route
layer maps it to HTTP 404. The action never imports `fastapi` so the
core layer stays free of HTTP concerns.
"""

from core.schema.feedback import FeedbackRequestSchema
from db.models.feedback import Feedback
from db.models.query_requests import QueryRequest
from db.sqlalchemy.transaction import commit_transaction_async
from libs.logger import get_logger

logger = get_logger(__name__)


class QueryNotFoundError(Exception):
    """Raised when a feedback POST references an unknown `query_id`."""


async def record_feedback(request: FeedbackRequestSchema) -> None:
    """Persist feedback for a prior query with replace semantics."""
    existing = await QueryRequest.get_by_id(request.query_id)
    if existing is None:
        raise QueryNotFoundError(request.query_id)

    async with commit_transaction_async():
        await Feedback.upsert_by_query_id(
            query_id=request.query_id,
            rating=request.rating,
            reason=request.reason,
        )

    logger.info(
        "Recorded feedback query_id=%s rating=%s has_reason=%s",
        request.query_id,
        request.rating,
        request.reason is not None,
    )
