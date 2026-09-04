from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from planner.transport.http.app import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def fixed_request() -> dict[str, Any]:
    channels = ["search_1", "social_1"]
    zero = {
        "spent": "0.000000",
        "impressions": "0",
        "unique_reach": "0",
        "clicks": "0",
        "conversions": "0",
    }
    return {
        "request_id": "5ca761eb-a701-4c91-9dd7-47c9f709e00d",
        "type": "fixed_budget",
        "strategy": "uniform",
        "horizon": {"from_hour": 0, "to_hour": 2},
        "channels": channels,
        "simulation": {
            "simulation_id": "simulation-demo_1",
            "world_seed": "42001",
            "campaign_seed": "77001",
            "start_hour": "2026-09-03T06:00:00Z",
            "time_zone": "Europe/Moscow",
            "currency": "RUB",
            "world_config_digest": "a" * 64,
        },
        "market": {"status": "unavailable"},
        "current": {
            "current_hour": 0,
            "state_revision": 0,
            "last_step_id": None,
            "last_observed_at": None,
            "spent": "0.000000",
            "unique_reach": "0",
            "clicks": "0",
            "conversions": "0",
            "channels": {channel: dict(zero) for channel in channels},
        },
        "budget": "12.000000",
        "optimize": "unique_reach",
        "target": None,
    }
