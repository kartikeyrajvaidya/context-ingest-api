"""Shared async OpenAI client factory.

Batch 3a deferred this extraction because only `embeddings.py` needed a
client. Batch 3b adds `llm.py` as the second consumer, so the factory
lives here now and both services import from it.
"""

from openai import AsyncOpenAI

from configs.llm import LLMConfig

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Return the process-wide async OpenAI client, constructing it on first use."""
    global _client
    if _client is not None:
        return _client

    if not LLMConfig.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    _client = AsyncOpenAI(
        api_key=LLMConfig.OPENAI_API_KEY,
        timeout=LLMConfig.OPENAI_TIMEOUT_SECONDS,
    )
    return _client
