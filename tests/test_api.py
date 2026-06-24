from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Supplier Onboarding Agent" in response.text


def test_chat_rejects_empty_message():
    response = client.post("/chat", json={"message": "", "session_id": "api-empty"})
    assert response.status_code == 422


def test_chat_rejects_invalid_session_id():
    response = client.post("/chat", json={"message": "hello", "session_id": "bad session!"})
    assert response.status_code == 422


def test_chat_stream_returns_sse_events():
    with client.stream(
        "POST",
        "/chat",
        json={"message": "What can you help me with?", "session_id": "api-stream"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        body = "".join(response.iter_text())
        assert "type" in body
        assert "done" in body
        assert "message" in body
