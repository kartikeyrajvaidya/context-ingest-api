def test_health_returns_data_envelope(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}
