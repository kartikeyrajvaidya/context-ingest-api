"""Ingestion pipeline: hash, rerun-check, chunk, embed, persist.

Pure orchestration. The action owns the transaction; this module runs
inside it and relies on the task-scoped session that the model classmethods
reach through `db.get_session()`.
"""

import hashlib
from datetime import datetime
from datetime import timezone
from typing import Literal
from typing import NamedTuple

from configs.llm import LLMConfig
from core.ingestion.chunker import chunk_text
from core.ingestion.cleaner import EmptyContentError
from core.services.embeddings import embed_texts
from db.models.chunks import Chunk
from db.models.documents import Document


class IngestOutcome(NamedTuple):
    document_id: str
    status: Literal["ingested", "unchanged"]
    chunks: int


async def ingest(
    source_url: str,
    source_type: str,
    text: str,
    title: str | None,
) -> IngestOutcome:
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    existing = await Document.get_by_source_url(source_url)
    if existing and existing.content_hash == content_hash:
        return IngestOutcome(existing.id, "unchanged", existing.chunk_count)

    chunks = chunk_text(
        text,
        chunk_size=LLMConfig.CHUNK_TOKEN_SIZE,
        overlap=LLMConfig.CHUNK_TOKEN_OVERLAP,
    )
    if not chunks:
        raise EmptyContentError("chunker produced zero chunks")

    embeddings = await embed_texts(chunks)

    now = datetime.now(timezone.utc)
    if existing:
        await Chunk.delete_by_document_id(existing.id)
        existing.content_hash = content_hash
        existing.title = title
        existing.chunk_count = len(chunks)
        existing.last_ingested_at = now
        existing.source_type = source_type
        document_id = existing.id
    else:
        created = await Document.create(
            Document(
                source_url=source_url,
                source_type=source_type,
                title=title,
                content_hash=content_hash,
                chunk_count=len(chunks),
                is_active=True,
                last_ingested_at=now,
            )
        )
        document_id = created.id

    for idx, (chunk_str, embedding) in enumerate(zip(chunks, embeddings)):
        await Chunk.create(
            Chunk(
                document_id=document_id,
                chunk_order=idx,
                chunk_text=chunk_str,
                embedding=embedding,
            )
        )

    return IngestOutcome(document_id, "ingested", len(chunks))
