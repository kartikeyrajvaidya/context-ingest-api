"""POST /v1/query — grounded, citation-first question answering."""

from fastapi import APIRouter, HTTPException

from core.actions.query_document import query_document
from core.rate_limit.session_limiter import (
    check_conversation_turn_limit,
    check_session_rate_limit,
)
from core.safety.gate import REFUSAL_USER_MESSAGE, check_input
from core.schema.query import QueryRequestSchema, QueryResponseSchema
from libs.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("")
async def post_query(request: QueryRequestSchema) -> dict:
    session_error = await check_session_rate_limit(request.session_id)
    if session_error:
        raise HTTPException(status_code=429, detail=session_error)

    conversation_error = await check_conversation_turn_limit(request.conversation_id)
    if conversation_error:
        raise HTTPException(status_code=429, detail=conversation_error)

    gate = await check_input(request.question)
    if gate.blocked:
        logger.warning(
            "Safety gate refused session_id=%s category=%s reason=%s",
            request.session_id,
            gate.category,
            gate.operator_reason,
        )
        refused = QueryResponseSchema(
            query_id=None,
            session_id=request.session_id,
            conversation_id=request.conversation_id or "",
            status="refused",
            answer=REFUSAL_USER_MESSAGE,
            citations=[],
            confidence="low",
            next_actions=[],
        )
        return {"data": refused.model_dump(mode="json")}

    response = await query_document(request)
    return {"data": response.model_dump(mode="json")}
