"""QueryResponse model — one row per completed POST /v1/query call.

Joined 1:1 to `query_requests` via `request_id`. A request with no matching
response row is a dangling / crashed request and is excluded from
conversation history fetches (which use an inner join).

`session_id` and `conversation_id` are denormalized from `query_requests`
so response-only analytics queries don't need a join back to the request
table.

`response_payload` is a single JSONB column holding the full response body
(answer, citations, confidence, retrieved_chunk_ids, next_actions). Schema
changes to the response are code-only — no migration needed. `status` stays
as a top-level column because it is indexed and filtered for analytics.
"""

from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Text
from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB

from configs.db import DBConfig
from db import db
from db.models.base import BaseModel


class QueryResponse(BaseModel):
    __tablename__ = "query_responses"

    id = Column(Text, primary_key=True)
    request_id = Column(
        Text,
        ForeignKey(
            f"{DBConfig.SCHEMA_NAME}.query_requests.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )
    session_id = Column(Text, nullable=False)
    conversation_id = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    response_payload = Column(JSONB, nullable=False)

    @classmethod
    def get_id_prefix(cls) -> str:
        return "qrs_"

    @classmethod
    async def fetch_recent_completed_turns(
        cls,
        session_id: str,
        conversation_id: str,
        limit: int,
    ) -> list[dict]:
        """Fetch the last `limit` completed turns for a conversation.

        Returns a list of dicts with `question`, `answer`, and `status`,
        in chronological order (oldest first). Callers that want to render
        this into an LLM prompt can iterate directly.

        Only turns with a written `query_responses` row are returned —
        dangling requests are filtered out by the inner join.
        """
        from db.models.query_requests import QueryRequest

        db_session = await db.get_session()
        stmt = (
            select(
                QueryRequest.question,
                cls.response_payload,
                cls.status,
            )
            .join(QueryRequest, QueryRequest.id == cls.request_id)
            .filter(
                QueryRequest.session_id == session_id,
                QueryRequest.conversation_id == conversation_id,
            )
            .order_by(desc(QueryRequest.created_at))
            .limit(limit)
        )
        result = await db_session.execute(stmt)
        rows = list(result.all())

        turns: list[dict] = []
        for question, response_payload, status in reversed(rows):
            turns.append(
                {
                    "question": question,
                    "answer": response_payload.get("answer"),
                    "status": status,
                }
            )
        return turns
