from fastapi.testclient import TestClient
import main


def test_controller_requires_internal_bearer_token():
    client = TestClient(main.app)
    response = client.get("/containers/demo-postgres/status")
    assert response.status_code == 401


def test_controller_rejects_unlisted_container(monkeypatch):
    monkeypatch.setattr(main, "TOKEN", "test-secret")
    client = TestClient(main.app)
    response = client.get("/containers/production-db/status", headers={"Authorization": "Bearer test-secret"})
    assert response.status_code == 403


def test_controller_stressor_schema_rejects_arbitrary_kind(monkeypatch):
    monkeypatch.setattr(main, "TOKEN", "test-secret")
    client = TestClient(main.app)
    response = client.post("/stressors/cpu-stressor/run", json={"kind": "shell"}, headers={"Authorization": "Bearer test-secret"})
    assert response.status_code == 422
