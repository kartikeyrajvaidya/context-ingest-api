"""Query-document action.

Single callable behind `POST /v1/query`. Owns both transaction boundaries:
one `commit_transaction_async` block around the `query_requests` insert,
a second around the `query_responses` insert. Retrieval and the LLM call
happen between the two, with no session held open — a crash mid-pipeline
leaves a durable "we were asked this" record that the history fetcher
(`QueryResponse.fetch_recent_completed_turns`) skips over via its inner
join.

Maps internal `LLMAnswer` into the public `QueryResponseSchema`. The LLM
only decides `answer`, `confidence`, and `next_actions`; the other public
fields (`query_id`, `session_id`, `conversation_id`, `citations`) are
assembled server-side from known state.
"""

from configs.llm import LLMConfig
from core.schema.query import CitationSchema
from core.schema.query import ClientStatus
from core.schema.query import QueryRequestSchema
from core.schema.query import QueryResponseSchema
from core.schema.retrieval_result import RetrievedChunk
from core.services.llm import LLMParseError
from core.services.llm import generate_answer
from core.services.retrieval import retrieve_relevant_chunks
from db.models.query_requests import QueryRequest
from db.models.query_responses import QueryResponse
from db.sqlalchemy.transaction import commit_transaction_async
from libs.logger import get_logger

logger = get_logger(__name__)

_STATUS_MAP: dict[str, ClientStatus] = {
    "answered": "answered",
    "no_answer": "no_answer",
    "no_context": "no_answer",
    "retrieval_failed": "error",
    "llm_failed": "error",
}


def _client_status(internal: str) -> ClientStatus:
    return _STATUS_MAP.get(internal, "error")


async def _resolve_conversation_id(request: QueryRequestSchema) -> str:
    """Return a conversation_id for this request, silently re-minting if stale."""
    if request.conversation_id is None:
        return QueryRequest.generate_conversation_id()

    belongs = await QueryRequest.conversation_belongs_to_session(
        session_id=request.session_id,
        conversation_id=request.conversation_id,
    )
    if belongs:
        return request.conversation_id

    return QueryRequest.generate_conversation_id()


def _chunks_to_citations(chunks: list[RetrievedChunk]) -> list[CitationSchema]:
    return [
        CitationSchema(
            document_id=c.document_id,
            chunk_id=c.chunk_id,
            chunk_order=c.chunk_order,
            source_url=c.source_url,
            title=c.title,
            text=c.text,
            ingested_at=c.ingested_at,
        )
        for c in chunks
    ]


async def query_document(request: QueryRequestSchema) -> QueryResponseSchema:
    """Run the full query path: persist request, retrieve, answer, persist response."""
    conversation_id = await _resolve_conversation_id(request)

    async with commit_transaction_async():
        query_request = await QueryRequest.create(
            QueryRequest(
                id=None,
                question=request.question,
                session_id=request.session_id,
                conversation_id=conversation_id,
            )
        )

    logger.info(
        "Stored query request_id=%s session_id=%s conversation_id=%s",
        query_request.id,
        request.session_id,
        conversation_id,
    )

    turns = await QueryResponse.fetch_recent_completed_turns(
        session_id=request.session_id,
        conversation_id=conversation_id,
        limit=LLMConfig.CONVERSATION_HISTORY_TURN_LIMIT,
    )

    retrieval_ok = True
    try:
        chunks = await retrieve_relevant_chunks(question=request.question)
    except Exception:  # noqa: BLE001
        logger.warning(
            "Retrieval failed for request_id=%s, falling back to no-answer",
            query_request.id,
            exc_info=True,
        )
        chunks = []
        retrieval_ok = False

    answer: str | None = None
    confidence: str = "low"
    next_actions: list[str] = []
    citations: list[CitationSchema] = []

    if not chunks:
        response_status = "no_context" if retrieval_ok else "retrieval_failed"
    else:
        try:
            llm_answer = await generate_answer(
                question=request.question,
                conversation_turns=turns,
                retrieved_chunks=chunks,
            )
        except LLMParseError:
            logger.warning(
                "LLM parse failed for request_id=%s, falling back to no-answer",
                query_request.id,
            )
            response_status = "llm_failed"
        else:
            if llm_answer.answer is None:
                response_status = "no_answer"
                confidence = llm_answer.confidence
            else:
                response_status = "answered"
                answer = llm_answer.answer
                confidence = llm_answer.confidence
                next_actions = list(llm_answer.next_actions)
                citations = _chunks_to_citations(chunks)

    response_payload = {
        "answer": answer,
        "citations": [c.model_dump(mode="json") for c in citations],
        "confidence": confidence,
        "retrieved_chunk_ids": [c.chunk_id for c in chunks],
        "next_actions": list(next_actions),
    }

    async with commit_transaction_async():
        query_response = await QueryResponse.create(
            QueryResponse(
                id=None,
                request_id=query_request.id,
                session_id=request.session_id,
                conversation_id=conversation_id,
                status=response_status,
                response_payload=response_payload,
            )
        )

    logger.info(
        "Completed query request_id=%s response_id=%s status=%s "
        "confidence=%s citations=%d next_actions=%d history_turns=%d",
        query_request.id,
        query_response.id,
        response_status,
        confidence,
        len(citations),
        len(next_actions),
        len(turns),
    )

    return QueryResponseSchema(
        query_id=query_request.id,
        session_id=request.session_id,
        conversation_id=conversation_id,
        status=_client_status(response_status),
        answer=answer,
        citations=citations,
        confidence=confidence,
        next_actions=list(next_actions),
    )
