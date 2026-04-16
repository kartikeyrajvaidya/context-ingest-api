"""Chunk model — one row per embedded chunk.

Each chunk carries the raw text, a 1536-dim embedding, and a generated
tsvector for hybrid retrieval. The `tsv` column is DB-generated — never
set it from the app side; the `Computed(..., persisted=True)` declaration
is informational for SQLAlchemy but the storage is owned by Postgres.

`hybrid_search` runs vector + full-text in parallel and fuses the two
rankings with Reciprocal Rank Fusion. Both CTEs are bounded by their own
candidate limits, then the top_k of the fused ranking is returned.
"""

from collections.abc import AsyncIterator

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlalchemy import Computed
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.engine import Row

from configs.db import DBConfig
from db import db
from db.models.base import BaseModel


class Chunk(BaseModel):
    __tablename__ = "chunks"

    id = Column(Text, primary_key=True)
    document_id = Column(
        Text,
        ForeignKey(f"{DBConfig.SCHEMA_NAME}.documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_order = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    tsv = Column(
        TSVECTOR,
        Computed("to_tsvector('english', chunk_text)", persisted=True),
    )

    @classmethod
    def get_id_prefix(cls) -> str:
        return "chk_"

    @classmethod
    async def delete_by_document_id(cls, document_id: str) -> int:
        db_session = await db.get_session()
        stmt = delete(cls).where(cls.document_id == document_id)
        result = await db_session.execute(stmt)
        return result.rowcount

    @classmethod
    async def count_by_document_id(cls, document_id: str) -> int:
        db_session = await db.get_session()
        stmt = select(func.count(cls.id)).filter(cls.document_id == document_id)
        result = await db_session.execute(stmt)
        return result.scalar_one()

    @classmethod
    async def count_all(cls) -> int:
        db_session = await db.get_session()
        result = await db_session.execute(select(func.count()).select_from(cls))
        return int(result.scalar_one())

    @classmethod
    async def iter_for_reembed(
        cls, batch_size: int
    ) -> AsyncIterator[list[tuple[str, str]]]:
        last_id: str | None = None
        while True:
            db_session = await db.get_session()
            stmt = (
                select(cls.id, cls.chunk_text)
                .order_by(cls.id.asc())
                .limit(batch_size)
            )
            if last_id is not None:
                stmt = stmt.where(cls.id > last_id)
            result = await db_session.execute(stmt)
            rows = result.all()
            if not rows:
                return
            yield [(row.id, row.chunk_text) for row in rows]
            last_id = rows[-1].id

    @classmethod
    async def update_embeddings_bulk(
        cls, updates: list[tuple[str, list[float]]]
    ) -> int:
        if not updates:
            return 0
        schema = DBConfig.SCHEMA_NAME
        db_session = await db.get_session()
        values_clause = ", ".join(
            f"(:id_{i}, CAST(:emb_{i} AS vector))" for i in range(len(updates))
        )
        params: dict[str, object] = {}
        for i, (chunk_id, emb) in enumerate(updates):
            params[f"id_{i}"] = chunk_id
            params[f"emb_{i}"] = "[" + ",".join(str(v) for v in emb) + "]"
        stmt = text(
            f"""
            UPDATE {schema}.chunks AS c
            SET embedding = v.embedding
            FROM (VALUES {values_clause}) AS v(id, embedding)
            WHERE c.id = v.id
            """
        )
        result = await db_session.execute(stmt, params)
        return result.rowcount or 0

    @classmethod
    async def hybrid_search(
        cls,
        query_embedding: list[float],
        question: str,
        vector_candidates: int,
        fulltext_candidates: int,
        top_k: int,
    ) -> list[Row]:
        """Run hybrid vector + full-text search with RRF fusion.

        Returns rows with chunk_id, document_id, document_title,
        source_url, source_type, chunk_text, chunk_order, last_ingested_at,
        and rrf_score columns. Only chunks from active documents are
        considered.
        """
        schema = DBConfig.SCHEMA_NAME
        db_session = await db.get_session()

        sql = text(f"""
        WITH vector_results AS (
            SELECT c.id AS chunk_id,
                   ROW_NUMBER() OVER (
                       ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
                   ) AS rank
            FROM {schema}.chunks c
            JOIN {schema}.documents d ON d.id = c.document_id
            WHERE d.is_active = TRUE
            ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :vector_candidates
        ),
        fulltext_results AS (
            SELECT c.id AS chunk_id,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank(c.tsv, plainto_tsquery('english', :question)) DESC
                   ) AS rank
            FROM {schema}.chunks c
            JOIN {schema}.documents d ON d.id = c.document_id
            WHERE d.is_active = TRUE
              AND c.tsv @@ plainto_tsquery('english', :question)
            ORDER BY ts_rank(c.tsv, plainto_tsquery('english', :question)) DESC
            LIMIT :fulltext_candidates
        )
        SELECT
            c.id AS chunk_id,
            c.document_id,
            d.title AS document_title,
            d.source_url,
            d.source_type,
            d.last_ingested_at,
            c.chunk_text,
            c.chunk_order,
            (1.0 / (60 + COALESCE(vr.rank, :vector_fallback))
             + 1.0 / (60 + COALESCE(fr.rank, :fulltext_fallback))) AS rrf_score
        FROM vector_results vr
        FULL OUTER JOIN fulltext_results fr ON vr.chunk_id = fr.chunk_id
        JOIN {schema}.chunks c
            ON c.id = COALESCE(vr.chunk_id, fr.chunk_id)
        JOIN {schema}.documents d ON d.id = c.document_id
        ORDER BY rrf_score DESC
        LIMIT :top_k
        """)

        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        result = await db_session.execute(
            sql,
            {
                "query_embedding": embedding_str,
                "question": question,
                "vector_candidates": vector_candidates,
                "fulltext_candidates": fulltext_candidates,
                "vector_fallback": vector_candidates + 1,
                "fulltext_fallback": fulltext_candidates + 1,
                "top_k": top_k,
            },
        )
        return result.all()
