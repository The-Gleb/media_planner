from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import planner.transport.http.app as app_module


def _assert_problem(
    response: Any, status: int, code: str, instance: str = "/v1/plans"
) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = response.json()
    assert body["status"] == status
    assert body["code"] == code
    assert str(body["type"]).startswith("https://")
    assert body["instance"] == instance
    assert body["trace_id"] == response.headers["X-Request-ID"]
    UUID(body["trace_id"])
    return body


def test_malformed_json_is_bad_request(client: TestClient) -> None:
    response = client.post("/v1/plans", content="{", headers={"Content-Type": "application/json"})
    _assert_problem(response, 400, "invalid_json")


@pytest.mark.parametrize("content_type", ["", "text/plain", "application/xml"])
def test_non_json_media_type_is_rejected(client: TestClient, content_type: str) -> None:
    headers = {"Content-Type": content_type} if content_type else {}
    response = client.post("/v1/plans", content="{}", headers=headers)
    _assert_problem(response, 415, "unsupported_media_type")


def test_validation_problem_has_named_field_errors(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    fixed_request["unexpected"] = True
    body = _assert_problem(client.post("/v1/plans", json=fixed_request), 422, "validation_failed")
    assert body["errors"]
    assert any("unexpected" in item["field"] for item in body["errors"])


def test_framework_http_errors_are_rfc9457(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    _assert_problem(response, 404, "validation_failed", "/does-not-exist")


def test_unexpected_exception_is_sanitized(
    client: TestClient, fixed_request: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(**_kwargs: object) -> None:
        raise RuntimeError("secret internal text")

    monkeypatch.setattr(app_module, "create_fixed_budget_plan", fail)
    response = client.post("/v1/plans", json=fixed_request)
    body = _assert_problem(response, 500, "internal_error")
    assert "secret" not in response.text
    assert body["detail"] == "An unexpected error occurred."
