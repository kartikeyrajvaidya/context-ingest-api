"""Document model — one row per logical source.

A "document" is one URL (or one `internal://slug` for raw-text ingestion)
that has been fetched, cleaned, chunked, and embedded. The `source_url` is
`UNIQUE`, so re-ingesting the same URL updates the existing row in place
and cascades a chunk replacement via the FK on `chunks.document_id`.
"""

from sqlalchemy import TIMESTAMP
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import select

from db import db
from db.models.base import BaseModel


class Document(BaseModel):
    __tablename__ = "documents"

    id = Column(Text, primary_key=True)
    source_url = Column(Text, nullable=False, unique=True)
    source_type = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    content_hash = Column(Text, nullable=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    last_ingested_at = Column(TIMESTAMP(timezone=True), nullable=True)

    @classmethod
    def get_id_prefix(cls) -> str:
        return "doc_"

    @classmethod
    async def get_by_source_url(cls, source_url: str) -> "Document | None":
        return await cls.filter_first(cls.source_url == source_url)

    @classmethod
    async def find_active_ids(cls) -> list[str]:
        db_session = await db.get_session()
        stmt = select(cls.id).filter(cls.is_active.is_(True))
        result = await db_session.execute(stmt)
        return list(result.scalars().all())
