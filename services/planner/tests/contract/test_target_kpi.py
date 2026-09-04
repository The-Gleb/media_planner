from typing import Any

import pytest
from fastapi.testclient import TestClient


def test_valid_target_shape_is_explicitly_unsupported(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    fixed_request.update(
        {
            "type": "target_kpi",
            "budget": None,
            "optimize": None,
            "target": {"metric": "clicks", "value": "100"},
        }
    )
    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "unsupported_plan_type"
    assert "allocations" not in response.json()


@pytest.mark.parametrize(
    "target", [None, {}, {"metric": "clicks", "value": "0"}, {"metric": "bad", "value": "1"}]
)
def test_invalid_target_shape_is_validation_failure(
    client: TestClient, fixed_request: dict[str, Any], target: object
) -> None:
    fixed_request.update({"type": "target_kpi", "budget": None, "optimize": None, "target": target})
    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
