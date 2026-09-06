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
        "unallocated_budget": "0.000000",
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


def test_campaign_spend_cannot_exceed_approved_budget(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    fixed_request["current"].update(
        {
            "current_hour": 1,
            "state_revision": 1,
            "last_step_id": "2917c89e-4936-4ddf-b167-90555465cb01",
            "last_observed_at": "2026-09-03T06:00:00Z",
            "spent": "13.000000",
        }
    )
    fixed_request["current"]["channels"]["search_1"]["spent"] = "13.000000"
    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"


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


def test_optimized_strategy_uses_catalog_and_accounts_for_reserve(
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
    ) + money_to_micros(body["unallocated_budget"]) == money_to_micros(body["budget"])
    totals = {
        channel: sum(
            money_to_micros(item["budget_cap"])
            for item in body["allocations"]
            if item["channel_id"] == channel
        )
        for channel in channels
    }
    assert len(set(totals.values())) > 1


def test_catalog_plans_return_hourly_and_total_expectations(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    channels = ["programmatic", "social_1", "sms"]
    zero = next(iter(fixed_request["current"]["channels"].values()))
    fixed_request["strategy"] = "optimized"
    fixed_request["optimize"] = "conversions"
    fixed_request["channels"] = channels
    fixed_request["horizon"] = {"from_hour": 0, "to_hour": 48}
    fixed_request["current"]["channels"] = {channel: dict(zero) for channel in channels}
    fixed_request["budget"] = "100000.000000"

    body = client.post("/v1/plans", json=fixed_request).json()
    assert body["expected"] is not None
    assert set(body["expected"]) == {
        "spend",
        "impressions",
        "unique_reach",
        "clicks",
        "conversions",
    }
    hourly = [item["expected"] for item in body["allocations"]]
    assert all(item is not None for item in hourly)
    for item, allocation in zip(hourly, body["allocations"], strict=True):
        assert money_to_micros(item["spend"]) <= money_to_micros(allocation["budget_cap"])
    spend = sum(money_to_micros(item["spend"]) for item in hourly)
    assert spend == money_to_micros(body["expected"]["spend"])
    clicks = sum(float(item["clicks"]) for item in hourly)
    assert int(body["expected"]["clicks"]) == int(clicks)


def test_replan_keeps_committed_hours_without_expectations(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    channels = ["programmatic", "social_1"]
    fixed_request["strategy"] = "optimized"
    fixed_request["channels"] = channels
    fixed_request["horizon"] = {"from_hour": 0, "to_hour": 24}
    fixed_request["budget"] = "10000.000000"
    fixed_request["current"] = {
        "current_hour": 6,
        "state_revision": 6,
        "last_step_id": "2917c89e-4936-4ddf-b167-90555465cb01",
        "last_observed_at": "2026-09-03T11:00:00Z",
        "spent": "2000.000000",
        "unique_reach": "20000",
        "clicks": "150",
        "conversions": "3",
        "channels": {
            "programmatic": {
                "spent": "1500.000000",
                "requests": "300000",
                "impressions": "30000",
                "unique_reach": "15000",
                "clicks": "100",
                "conversions": "2",
            },
            "social_1": {
                "spent": "500.000000",
                "requests": "50000",
                "impressions": "5000",
                "unique_reach": "5000",
                "clicks": "50",
                "conversions": "1",
            },
        },
    }
    body = client.post("/v1/plans", json=fixed_request).json()
    past = [item for item in body["allocations"] if item["hour"] < 6]
    future = [item for item in body["allocations"] if item["hour"] >= 6]
    assert len(past) == 12 and all(item["expected"] is None for item in past)
    assert all(item["expected"] is not None for item in future)
    future_spend = sum(money_to_micros(item["expected"]["spend"]) for item in future)
    assert money_to_micros(body["expected"]["spend"]) == 2_000_000_000 + future_spend
    assert int(body["expected"]["conversions"]) >= 3


def _history_entry(channels: list[str], hours: int = 336) -> dict[str, Any]:
    per_bin = hours // 24
    bins = [
        {
            "hour": hour,
            "hours": per_bin,
            "requests": str(per_bin * 20_000),
            "impressions": str(per_bin * 4_000),
            "unique_reach": str(per_bin * 3_000),
            "clicks": str(per_bin * 60),
            "conversions": str(per_bin * 3),
            "spent": f"{per_bin * 400}.000000",
        }
        for hour in range(24)
    ]
    return {"horizon_hours": hours, "channels": {channel: {"bins": bins} for channel in channels}}


def test_history_changes_optimized_plan_and_fingerprint(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    channels = ["programmatic", "social_1"]
    zero = next(iter(fixed_request["current"]["channels"].values()))
    fixed_request["strategy"] = "optimized"
    fixed_request["optimize"] = "conversions"
    fixed_request["channels"] = channels
    fixed_request["horizon"] = {"from_hour": 0, "to_hour": 72}
    fixed_request["current"]["channels"] = {channel: dict(zero) for channel in channels}
    fixed_request["budget"] = "300000.000000"
    cold = client.post("/v1/plans", json=fixed_request).json()

    fixed_request["history"] = [_history_entry(["social_1"])]
    warm_response = client.post("/v1/plans", json=fixed_request)
    assert warm_response.status_code == 200, warm_response.text
    warm = warm_response.json()
    assert warm["plan_id"] != cold["plan_id"]
    assert warm["allocations"] != cold["allocations"]
    assert warm["expected"] != cold["expected"]


def test_history_does_not_change_uniform_plan_id(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    cold = client.post("/v1/plans", json=fixed_request).json()
    fixed_request["history"] = [_history_entry(["social_1"])]
    warm = client.post("/v1/plans", json=fixed_request).json()
    assert warm["plan_id"] == cold["plan_id"]
    assert warm["allocations"] == cold["allocations"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda entry: entry["channels"]["social_1"]["bins"].pop(),
        lambda entry: entry["channels"]["social_1"]["bins"][3].__setitem__("hour", 4),
        lambda entry: entry["channels"]["social_1"]["bins"][0].__setitem__("clicks", "999999"),
        lambda entry: entry.__setitem__("horizon_hours", 24),
        lambda entry: entry.__setitem__("hidden_cpm", "1.0"),
    ],
)
def test_invalid_history_is_rejected(
    client: TestClient, fixed_request: dict[str, Any], mutate: Any
) -> None:
    entry = _history_entry(["social_1"])
    mutate(entry)
    fixed_request["history"] = [entry]
    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
