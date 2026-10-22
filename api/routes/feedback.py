"""POST /v1/feedback — record user feedback against a prior query."""

from fastapi import APIRouter, HTTPException, Response

from core.actions.record_feedback import QueryNotFoundError, record_feedback
from core.schema.feedback import FeedbackRequestSchema

router = APIRouter()


@router.post("", status_code=204)
async def post_feedback(request: FeedbackRequestSchema) -> Response:
    try:
        await record_feedback(request)
    except QueryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="query not found") from exc
    return Response(status_code=204)
