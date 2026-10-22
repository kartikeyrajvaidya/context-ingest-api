import pytest


@pytest.mark.parametrize(
    "body",
    [
        {"session_id": "s1"},
        {"question": "", "session_id": "s1"},
        {"question": "What is RAG?", "session_id": "s1", "unexpected": True},
    ],
    ids=["missing-question", "empty-question", "unknown-field"],
)
def test_query_rejects_invalid_body_with_message_envelope(client, body):
    response = client.post("/v1/query", json=body)

    assert response.status_code == 400
    payload = response.json()
    assert payload["message"] == "Validation failed"
    assert payload["errors"]
    assert all({"type", "loc", "msg"} <= error.keys() for error in payload["errors"])
    assert "data" not in payload


def test_feedback_rejects_invalid_body_with_message_envelope(client):
    response = client.post("/v1/feedback", json={})

    assert response.status_code == 400
    assert response.json()["message"] == "Validation failed"
