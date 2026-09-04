from uuid import UUID

from fastapi.testclient import TestClient

from planner.transport.http.app import app


def test_health_is_exact_and_dependency_free(client: TestClient) -> None:
    for path in ("/health/live", "/health/ready"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        UUID(response.headers["X-Request-ID"])


def test_valid_request_id_is_preserved(client: TestClient) -> None:
    request_id = "5ca761eb-a701-4c91-9dd7-47c9f709e00d"
    response = client.get("/health/live", headers={"X-Request-ID": request_id})
    assert response.headers["X-Request-ID"] == request_id


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "invalid"})
    assert response.headers["X-Request-ID"] != "invalid"
    UUID(response.headers["X-Request-ID"])


def test_not_ready_is_an_rfc9457_problem(client: TestClient) -> None:
    app.state.ready = False
    try:
        response = client.get("/health/ready")
    finally:
        app.state.ready = True
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "not_ready"
