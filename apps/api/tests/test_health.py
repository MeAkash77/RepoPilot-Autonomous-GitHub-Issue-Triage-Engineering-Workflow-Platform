from fastapi.testclient import TestClient

from repopilot_api.main import create_app


def test_healthz() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz() -> None:
    client = TestClient(create_app())
    response = client.get("/readyz")
    assert response.status_code == 200
