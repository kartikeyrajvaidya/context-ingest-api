"""End-to-end ingest then query against a real Postgres, with OpenAI mocked."""

import asyncio
import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from api.server.run_api import app
from core.actions.ingest_document import ingest_document
from core.schema.ingest import IngestRequestSchema
from core.schema.llm_answer import LLMAnswer
from db import db

EMBEDDING_DIMENSIONS = 1536


async def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    """Deterministic, non-zero vectors so cosine distance is defined."""
    vectors = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vectors.append([(digest[i % len(digest)] + 1) / 256 for i in range(EMBEDDING_DIMENSIONS)])
    return vectors


async def _fake_generate_answer(question, conversation_turns, retrieved_chunks):
    return LLMAnswer(
        answer="Retrieval-augmented generation grounds answers in retrieved text.",
        confidence="high",
        next_actions=["How is retrieval scored?"],
    )


@pytest.fixture
def mocked_openai(monkeypatch):
    monkeypatch.setattr("core.ingestion.pipeline.embed_texts", _fake_embed_texts)
    monkeypatch.setattr("core.services.retrieval.embed_texts", _fake_embed_texts)
    monkeypatch.setattr("core.actions.query_document.generate_answer", _fake_generate_answer)


async def _ingest(request: IngestRequestSchema):
    try:
        return await ingest_document(request)
    finally:
        await db.disconnect()


def test_ingest_then_query_returns_cited_answer(database, mocked_openai):
    source_url = f"internal://test-{uuid.uuid4().hex}"
    text = (
        "Retrieval-augmented generation, or RAG, retrieves relevant passages from a "
        "knowledge base and passes them to a language model so answers cite sources. "
        "Hybrid retrieval combines vector similarity with full-text search and fuses "
        "the two ranked lists with reciprocal rank fusion. Chunking splits long "
        "documents into overlapping windows so each passage fits the model context."
    )
    request = IngestRequestSchema(text=text, title="RAG basics", source_url=source_url)

    first = asyncio.run(_ingest(request))
    assert first.status == "ingested"
    assert first.chunks >= 1
    assert first.document_id

    second = asyncio.run(_ingest(request))
    assert second.status == "unchanged"
    assert second.document_id == first.document_id

    with TestClient(app) as client:
        response = client.post(
            "/v1/query",
            json={"question": "What is retrieval-augmented generation?", "session_id": "test"},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "answered"
    assert data["answer"]
    assert data["query_id"]
    assert data["conversation_id"]
    assert any(c["document_id"] == first.document_id for c in data["citations"])
