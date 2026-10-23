"""Every request releases its task-scoped DB session, including early exits.

`db.session` is an `async_scoped_session` keyed on the current task. A
session that is read from and never removed keeps its transaction and
connection open after the request ends. These tests assert the registry is
empty once each response is back, and that no session is held while the
query path waits on the embeddings or LLM call.
"""

import asyncio
import uuid

from fastapi.testclient import TestClient

from api.server.run_api import app
from configs.rate_limit import RateLimitConfig
from core.safety.gate import GateResult
from core.schema.ingest import IngestRequestSchema
from core.schema.llm_answer import LLMAnswer
from db import db
from tests.test_ingest_and_query import _cleanup, _fake_embed_texts, _ingest


def _open_sessions() -> int:
    """Number of task-scoped sessions still registered."""
    if db.session is None:
        return 0
    return len(db.session.registry.registry)


def _task_has_session() -> bool:
    """True when the current task holds a scoped session."""
    return db.session is not None and db.session.registry.has()


def test_session_rate_limit_429_releases_session(database, monkeypatch):
    monkeypatch.setattr(RateLimitConfig, "SESSION_PER_HOUR", 0)
    with TestClient(app) as client:
        response = client.post(
            "/v1/query",
            json={"question": "What is RAG?", "session_id": f"test-{uuid.uuid4().hex}"},
        )
        assert response.status_code == 429
        assert _open_sessions() == 0


def test_conversation_limit_429_releases_session(database, monkeypatch):
    monkeypatch.setattr(RateLimitConfig, "CONVERSATION_MAX_TURNS", 0)
    with TestClient(app) as client:
        response = client.post(
            "/v1/query",
            json={
                "question": "What is RAG?",
                "session_id": f"test-{uuid.uuid4().hex}",
                "conversation_id": "cnv_doesnotexist",
            },
        )
        assert response.status_code == 429
        assert _open_sessions() == 0


def test_refused_query_releases_session(database, monkeypatch):
    async def _refuse(_question: str) -> GateResult:
        return GateResult(True, "refuse", "test")

    monkeypatch.setattr("api.routes.query.check_input", _refuse)
    with TestClient(app) as client:
        response = client.post(
            "/v1/query",
            json={"question": "What is RAG?", "session_id": f"test-{uuid.uuid4().hex}"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "refused"
        assert _open_sessions() == 0


def test_feedback_404_releases_session(database):
    with TestClient(app) as client:
        response = client.post(
            "/v1/feedback",
            json={"query_id": f"qry_{uuid.uuid4().hex[:10]}", "rating": "up"},
        )
        assert response.status_code == 404
        assert _open_sessions() == 0


def test_query_holds_no_session_during_network_calls(database, monkeypatch):
    held: dict[str, bool] = {}

    async def _recording_embed(texts: list[str]) -> list[list[float]]:
        held["embed"] = _task_has_session()
        return await _fake_embed_texts(texts)

    async def _recording_answer(question, conversation_turns, retrieved_chunks):
        held["llm"] = _task_has_session()
        return LLMAnswer(answer="Grounded answer.", confidence="high", next_actions=[])

    monkeypatch.setattr("core.ingestion.pipeline.embed_texts", _fake_embed_texts)
    monkeypatch.setattr("core.services.retrieval.embed_texts", _recording_embed)
    monkeypatch.setattr("core.actions.query_document.generate_answer", _recording_answer)

    run_id = uuid.uuid4().hex
    session_id = f"test-{run_id}"
    document_id = None
    try:
        outcome = asyncio.run(
            _ingest(
                IngestRequestSchema(
                    text=(
                        f"Test run {run_id}. "
                        "Hybrid retrieval combines vector similarity with full-text search "
                        "and fuses the two ranked lists with reciprocal rank fusion. Chunking "
                        "splits long documents into overlapping windows so each passage fits "
                        "the model context, and every answer cites the passages it used."
                    ),
                    title="Session release",
                    source_url=f"internal://test-{run_id}",
                )
            )
        )
        document_id = outcome.document_id

        with TestClient(app) as client:
            response = client.post(
                "/v1/query",
                json={"question": "What does hybrid retrieval fuse?", "session_id": session_id},
            )
            assert response.status_code == 200
            assert response.json()["data"]["status"] == "answered"
            assert _open_sessions() == 0

        assert held == {"embed": False, "llm": False}
    finally:
        asyncio.run(_cleanup(document_id, session_id))
