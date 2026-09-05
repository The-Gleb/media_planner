from copy import deepcopy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from planner.domain.catalog import load_catalog
from planner.domain.values import money_to_micros


def _target_request(fixed_request: dict[str, Any], value: str = "50000") -> dict[str, Any]:
    request = deepcopy(fixed_request)
    channels = list(load_catalog())
    zero = next(iter(request["current"]["channels"].values()))
    request.update(
        {
            "type": "target_kpi",
            "strategy": "optimized",
            "horizon": {"from_hour": 0, "to_hour": 336},
            "channels": channels,
            "budget": None,
            "optimize": None,
            "target": {"metric": "clicks", "value": value},
        }
    )
    request["current"]["channels"] = {channel: dict(zero) for channel in channels}
    return request


def test_reachable_target_returns_executable_minimum_budget(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    response = client.post("/v1/plans", json=_target_request(fixed_request))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["feasible"] is True
    assert body["type"] == "target_kpi"
    assert body["target"] == {"metric": "clicks", "value": "50000"}
    assert body["required_budget"] == body["budget"]
    assert int(body["expected"]["clicks"]) >= 50_000
    assert sum(
        money_to_micros(item["budget_cap"]) for item in body["allocations"]
    ) == money_to_micros(body["budget"])


def test_unreachable_target_is_a_domain_result(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    response = client.post("/v1/plans", json=_target_request(fixed_request, "999999999"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["feasible"] is False
    assert body["allocations"] == []
    assert body["reason"]["code"] == "target_exceeds_capacity"
    assert body["reason"]["recommended_target"] == body["reason"]["max_achievable"]


def test_target_requires_optimized_strategy(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    request = _target_request(fixed_request)
    request["strategy"] = "uniform"
    response = client.post("/v1/plans", json=request)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"


@pytest.mark.parametrize(
    "target", [None, {}, {"metric": "clicks", "value": "0"}, {"metric": "bad", "value": "1"}]
)
def test_invalid_target_shape_is_validation_failure(
    client: TestClient, fixed_request: dict[str, Any], target: object
) -> None:
    request = _target_request(fixed_request)
    request["target"] = target
    response = client.post("/v1/plans", json=request)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
