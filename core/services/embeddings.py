"""OpenAI embeddings adapter.

Wraps batching and the per-request timeout. Knows nothing about documents,
chunks, or URLs. The OpenAI client itself comes from
`core/services/openai_client.py`.
"""

from configs.llm import LLMConfig
from core.services.openai_client import get_openai_client

OPENAI_EMBEDDING_BATCH_LIMIT = 2048


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return a dense vector for each input string, preserving order.

    Splits into sub-batches of at most `OPENAI_EMBEDDING_BATCH_LIMIT` items
    (OpenAI's hard cap on the embeddings endpoint). For typical documents
    the loop executes once.
    """
    if not texts:
        raise ValueError("embed_texts called with empty input")

    client = get_openai_client()
    all_embeddings: list[list[float]] = []
    for start in range(0, len(texts), OPENAI_EMBEDDING_BATCH_LIMIT):
        batch = texts[start : start + OPENAI_EMBEDDING_BATCH_LIMIT]
        response = await client.embeddings.create(
            model=LLMConfig.OPENAI_EMBEDDING_MODEL,
            input=batch,
        )
        all_embeddings.extend(item.embedding for item in response.data)
    return all_embeddings
