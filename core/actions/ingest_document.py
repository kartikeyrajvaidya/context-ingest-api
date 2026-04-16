"""Ingest-document action.

Single callable shared by the CLI scripts (and the future refresh route).
Owns the transaction boundary. Maps non-fatal failures (`FetchError`,
`EmptyContentError`) to `status: "failed"` on the response envelope; every
other exception propagates so the transaction rolls back and the script
exits non-zero.
"""

import hashlib

from core.ingestion import cleaner
from core.ingestion import fetcher
from core.ingestion import pipeline
from core.ingestion.cleaner import EmptyContentError
from core.ingestion.fetcher import FetchError
from core.schema.ingest import IngestRequestSchema
from core.schema.ingest import IngestResponseSchema
from db.sqlalchemy.transaction import commit_transaction_async
from libs.logger import get_logger

logger = get_logger(__name__)


def _failed() -> IngestResponseSchema:
    return IngestResponseSchema(document_id=None, status="failed", chunks=0)


async def ingest_document(request: IngestRequestSchema) -> IngestResponseSchema:
    if request.url is not None:
        try:
            page = await fetcher.fetch_url(str(request.url))
        except FetchError as exc:
            logger.warning("Ingest failed (fetch): url=%s reason=%s", request.url, exc)
            return _failed()

        try:
            cleaned = cleaner.extract_content(page.html, url=page.url)
        except EmptyContentError as exc:
            logger.warning("Ingest failed (empty): url=%s reason=%s", request.url, exc)
            return _failed()

        source_url = page.url
        source_type = "url"
        text = cleaned.text
        title = request.title or cleaned.title
    else:
        try:
            text = cleaner.clean_raw_text(request.text, is_markdown=False)
        except EmptyContentError as exc:
            logger.warning("Ingest failed (empty text): reason=%s", exc)
            return _failed()

        if request.source_url:
            source_url = request.source_url
        else:
            content_preview = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            source_url = f"text://{content_preview}"
        source_type = "text"
        title = request.title

    try:
        async with commit_transaction_async():
            outcome = await pipeline.ingest(
                source_url=source_url,
                source_type=source_type,
                text=text,
                title=title,
            )
    except EmptyContentError as exc:
        logger.warning(
            "Ingest failed (empty after chunk): source=%s reason=%s", source_url, exc
        )
        return _failed()

    logger.info(
        "Ingested document id=%s source=%s status=%s chunks=%d",
        outcome.document_id,
        source_url,
        outcome.status,
        outcome.chunks,
    )
    return IngestResponseSchema(
        document_id=outcome.document_id,
        status=outcome.status,
        chunks=outcome.chunks,
    )
