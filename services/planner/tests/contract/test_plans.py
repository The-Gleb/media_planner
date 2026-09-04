from copy import deepcopy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from planner.domain.values import money_to_micros


def test_documented_uniform_plan(client: TestClient, fixed_request: dict[str, Any]) -> None:
    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "request_id": fixed_request["request_id"],
        "state_revision": 0,
        "plan_id": body["plan_id"],
        "feasible": True,
        "type": "fixed_budget",
        "strategy": "uniform",
        "optimize": "unique_reach",
        "currency": "RUB",
        "budget": "12.000000",
        "horizon": {"from_hour": 0, "to_hour": 2},
        "expected": None,
        "allocations": body["allocations"],
        "required_budget": None,
        "reason": None,
        "target": None,
    }
    assert [item["budget_cap"] for item in body["allocations"]] == ["3.000000"] * 4
    assert [(item["hour"], item["channel_id"]) for item in body["allocations"]] == [
        (0, "search_1"),
        (0, "social_1"),
        (1, "search_1"),
        (1, "social_1"),
    ]
    assert all(item["expected"] is None for item in body["allocations"])
    assert sum(money_to_micros(item["budget_cap"]) for item in body["allocations"]) == 12_000_000


def test_smallest_remainder_uses_stable_order(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    fixed_request["budget"] = "0.000001"
    body = client.post("/v1/plans", json=fixed_request).json()
    assert [item["budget_cap"] for item in body["allocations"]] == [
        "0.000001",
        "0.000000",
        "0.000000",
        "0.000000",
    ]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("budget",), 12),
        (("budget",), "01"),
        (("horizon", "from_hour"), "0"),
        (("horizon", "to_hour"), 0),
        (("channels",), []),
        (("channels",), ["search_1", "search_1"]),
        (("channels",), ["UPPER"]),
        (("simulation", "world_seed"), str(2**63)),
        (("simulation", "start_hour"), "2026-09-03T06:00:01Z"),
        (("simulation", "time_zone"), "Not/AZone"),
        (("simulation", "currency"), "rub"),
        (("simulation", "world_config_digest"), "abc"),
        (("current", "current_hour"), 3),
        (("current", "state_revision"), 1),
    ],
)
def test_invalid_fixed_request_is_rejected(
    client: TestClient, fixed_request: dict[str, Any], path: tuple[str, ...], value: object
) -> None:
    target: dict[str, Any] = fixed_request
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
    assert "allocations" not in response.json()


def test_channel_and_campaign_totals_must_be_exact(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    fixed_request["current"]["spent"] = "1.000000"
    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 422


def test_request_id_does_not_change_plan_id(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    first = client.post("/v1/plans", json=fixed_request).json()
    second_request = deepcopy(fixed_request)
    second_request["request_id"] = "67db5e95-52bb-42cb-9ef6-fc823f2e6077"
    second = client.post("/v1/plans", json=second_request).json()
    assert second["request_id"] != first["request_id"]
    assert second["plan_id"] == first["plan_id"]
    assert second["allocations"] == first["allocations"]


def test_optimized_strategy_uses_catalog_and_keeps_exact_budget(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    channels = ["programmatic", "social_1", "marketplace_3"]
    zero = next(iter(fixed_request["current"]["channels"].values()))
    fixed_request["strategy"] = "optimized"
    fixed_request["channels"] = channels
    fixed_request["current"]["channels"] = {channel: dict(zero) for channel in channels}
    fixed_request["budget"] = "100000.000007"

    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["strategy"] == "optimized"
    assert sum(
        money_to_micros(item["budget_cap"]) for item in body["allocations"]
    ) == money_to_micros(body["budget"])
    totals = {
        channel: sum(
            money_to_micros(item["budget_cap"])
            for item in body["allocations"]
            if item["channel_id"] == channel
        )
        for channel in channels
    }
    assert len(set(totals.values())) > 1
