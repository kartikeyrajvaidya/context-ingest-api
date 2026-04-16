"""QueryRequest model — one row per inbound POST /v1/query call.

The PK is the public `query_id` eventually returned to the caller and
referenced by `feedback.query_id`. Written BEFORE the retrieval + LLM
pipeline runs, so a crash mid-pipeline leaves a durable "we were asked
this" record. The response lives in a separate table (`query_responses`)
that joins 1:1 by `request_id`.

`session_id` is caller-owned and required on every request. It is the
rate-limit key and the access-control scope for conversations — a
conversation cannot be continued from a different session.

`conversation_id` is server-minted if the caller omits it or supplies one
that doesn't belong to their `session_id`. The `cnv_` prefix follows the
`<prefix><random10>` convention shared by every id in the schema, using
the same `_generate_random_string(10)` helper as `BaseModel.create`.
"""

from sqlalchemy import Column
from sqlalchemy import Text
from sqlalchemy import func
from sqlalchemy import select

from db import db
from db.models.base import BaseModel
from db.models.base import _generate_random_string


class QueryRequest(BaseModel):
    __tablename__ = "query_requests"

    id = Column(Text, primary_key=True)
    question = Column(Text, nullable=False)
    session_id = Column(Text, nullable=False)
    conversation_id = Column(Text, nullable=False)

    @classmethod
    def get_id_prefix(cls) -> str:
        return "qry_"

    @classmethod
    def generate_conversation_id(cls) -> str:
        return f"cnv_{_generate_random_string(10)}"

    @classmethod
    async def conversation_belongs_to_session(
        cls,
        session_id: str,
        conversation_id: str,
    ) -> bool:
        existing = await cls.filter_first(
            cls.session_id == session_id,
            cls.conversation_id == conversation_id,
        )
        return existing is not None

    @classmethod
    async def count_session_requests_since(
        cls,
        session_id: str,
        since,
    ) -> int:
        db_session = await db.get_session()
        stmt = select(func.count(cls.id)).filter(
            cls.session_id == session_id,
            cls.created_at >= since,
        )
        result = await db_session.execute(stmt)
        return result.scalar_one()

    @classmethod
    async def count_conversation_turns(cls, conversation_id: str) -> int:
        db_session = await db.get_session()
        stmt = select(func.count(cls.id)).filter(
            cls.conversation_id == conversation_id,
        )
        result = await db_session.execute(stmt)
        return result.scalar_one()
