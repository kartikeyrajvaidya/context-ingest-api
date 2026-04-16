"""LLM and embedding configuration for ContextIngest API."""

import os


class LLMConfig:
    """OpenAI model selection and request budgets."""

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

    OPENAI_ANSWER_MODEL = os.environ.get("OPENAI_ANSWER_MODEL", "gpt-5.4-mini")
    OPENAI_EMBEDDING_MODEL = os.environ.get(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    OPENAI_EMBEDDING_DIMENSIONS = int(os.environ.get("OPENAI_EMBEDDING_DIMENSIONS", "1536"))
    OPENAI_TIMEOUT_SECONDS = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "20"))

    CHUNK_TOKEN_SIZE = int(os.environ.get("CHUNK_TOKEN_SIZE", "500"))
    CHUNK_TOKEN_OVERLAP = int(os.environ.get("CHUNK_TOKEN_OVERLAP", "75"))

    RETRIEVAL_VECTOR_CANDIDATES = int(os.environ.get("RETRIEVAL_VECTOR_CANDIDATES", "20"))
    RETRIEVAL_FULLTEXT_CANDIDATES = int(
        os.environ.get("RETRIEVAL_FULLTEXT_CANDIDATES", "20")
    )
    RETRIEVAL_TOP_K = int(os.environ.get("RETRIEVAL_TOP_K", "5"))

    CONVERSATION_HISTORY_TURN_LIMIT = int(
        os.environ.get("CONVERSATION_HISTORY_TURN_LIMIT", "10")
    )
