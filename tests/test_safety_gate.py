"""Safety gate fails closed on classifier errors and missing verdicts."""

import asyncio

from configs.safety import SafetyConfig
from core.safety import gate


def test_missing_verdict_is_refused(monkeypatch):
    async def _no_verdict(_question: str):
        return None

    monkeypatch.setattr(SafetyConfig, "ENABLED", True)
    monkeypatch.setattr(gate, "classify_question", _no_verdict)

    result = asyncio.run(gate.check_input("What is retrieval-augmented generation?"))

    assert result.blocked is True
    assert result.category == "error"


def test_classifier_exception_is_refused(monkeypatch):
    async def _boom(_question: str):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(SafetyConfig, "ENABLED", True)
    monkeypatch.setattr(gate, "classify_question", _boom)

    result = asyncio.run(gate.check_input("What is retrieval-augmented generation?"))

    assert result.blocked is True
    assert result.category == "error"


def test_refused_query_returns_refused_envelope(client, monkeypatch):
    async def _no_verdict(_question: str):
        return None

    async def _no_limit(*_args):
        return None

    monkeypatch.setattr(SafetyConfig, "ENABLED", True)
    monkeypatch.setattr(gate, "classify_question", _no_verdict)
    monkeypatch.setattr("api.routes.query.check_session_rate_limit", _no_limit)
    monkeypatch.setattr("api.routes.query.check_conversation_turn_limit", _no_limit)

    response = client.post("/v1/query", json={"question": "What is RAG?", "session_id": "s1"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "refused"
    assert data["answer"] == gate.REFUSAL_USER_MESSAGE
