"""Hybrid retrieval service — one function, thin wrapper over the model."""

from configs.llm import LLMConfig
from core.schema.retrieval_result import RetrievedChunk
from core.services.embeddings import embed_texts
from db.models.chunks import Chunk
from libs.logger import get_logger

logger = get_logger(__name__)


async def retrieve_relevant_chunks(question: str) -> list[RetrievedChunk]:
    """Embed a question and retrieve the top-K chunks via hybrid search.

    Returns an empty list if the knowledge base contains no relevant
    chunks. The action treats empty-list as the no-answer short-circuit.
    """
    [query_embedding] = await embed_texts([question])

    rows = await Chunk.hybrid_search(
        query_embedding=query_embedding,
        question=question,
        vector_candidates=LLMConfig.RETRIEVAL_VECTOR_CANDIDATES,
        fulltext_candidates=LLMConfig.RETRIEVAL_FULLTEXT_CANDIDATES,
        top_k=LLMConfig.RETRIEVAL_TOP_K,
    )

    results = [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            chunk_order=row.chunk_order,
            text=row.chunk_text,
            source_url=row.source_url,
            title=row.document_title,
            ingested_at=row.last_ingested_at,
            score=float(row.rrf_score),
        )
        for row in rows
    ]

    logger.info(
        "Retrieved %d chunks for question top_score=%.4f",
        len(results),
        results[0].score if results else 0.0,
    )
    return results
