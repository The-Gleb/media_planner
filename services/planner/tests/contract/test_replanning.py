from copy import deepcopy
from typing import Any

from fastapi.testclient import TestClient

from planner.domain.values import money_to_micros


def test_later_campaign_state_is_acknowledged_without_changing_plan(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    first = client.post("/v1/plans", json=fixed_request).json()
    current = fixed_request["current"]
    current.update(
        {
            "current_hour": 1,
            "state_revision": 1,
            "last_step_id": "67db5e95-52bb-42cb-9ef6-fc823f2e6077",
            "last_observed_at": "2026-09-03T06:00:00Z",
            "spent": "3.500000",
            "unique_reach": "110",
            "clicks": "11",
            "conversions": "2",
        }
    )
    current["channels"]["search_1"].update(
        {
            "spent": "1.500000",
            "impressions": "1000",
            "unique_reach": "50",
            "clicks": "5",
            "conversions": "1",
        }
    )
    current["channels"]["social_1"].update(
        {
            "spent": "2.000000",
            "impressions": "2000",
            "unique_reach": "60",
            "clicks": "6",
            "conversions": "1",
        }
    )
    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 200, response.text
    second = response.json()
    assert second["state_revision"] == 1
    assert second["plan_id"] == first["plan_id"]
    assert second["allocations"] == first["allocations"]


def test_finished_snapshot_is_accepted(client: TestClient, fixed_request: dict[str, Any]) -> None:
    current = fixed_request["current"]
    current.update(
        {
            "current_hour": 2,
            "state_revision": 2,
            "last_step_id": "67db5e95-52bb-42cb-9ef6-fc823f2e6077",
            "last_observed_at": "2026-09-03T07:00:00Z",
        }
    )
    response = client.post("/v1/plans", json=fixed_request)
    assert response.status_code == 200, response.text
    assert response.json()["state_revision"] == 2


def test_optimized_reallocates_remaining_budget_from_every_committed_state(
    client: TestClient, fixed_request: dict[str, Any]
) -> None:
    request = deepcopy(fixed_request)
    request["strategy"] = "optimized"
    request["optimize"] = "conversions"
    request["budget"] = "100000.000000"
    request["horizon"] = {"from_hour": 0, "to_hour": 24}
    channels = ["programmatic", "social_1"]
    zero = next(iter(request["current"]["channels"].values()))
    request["channels"] = channels
    request["current"]["channels"] = {channel: dict(zero) for channel in channels}
    first = client.post("/v1/plans", json=request).json()

    request["current"].update(
        {
            "current_hour": 1,
            "state_revision": 1,
            "last_step_id": "67db5e95-52bb-42cb-9ef6-fc823f2e6077",
            "last_observed_at": "2026-09-03T06:00:00Z",
            "spent": "2000.000000",
            "unique_reach": "48000",
            "clicks": "1001",
            "conversions": "100",
        }
    )
    request["current"]["channels"] = {
        "programmatic": {
            "spent": "1000.000000",
            "requests": "1000000",
            "impressions": "50000",
            "unique_reach": "40000",
            "clicks": "1000",
            "conversions": "100",
        },
        "social_1": {
            "spent": "1000.000000",
            "requests": "100000",
            "impressions": "10000",
            "unique_reach": "8000",
            "clicks": "1",
            "conversions": "0",
        },
    }
    second_response = client.post("/v1/plans", json=request)
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()

    assert second["plan_id"] != first["plan_id"]
    assert second["allocations"] != first["allocations"]
    assert sum(
        money_to_micros(item["budget_cap"]) for item in second["allocations"]
    ) == money_to_micros(request["budget"])
