import gc
import json
import time
import tracemalloc

import pytest

from planner.application.planning import create_fixed_budget_plan
from planner.domain.models import Horizon
from planner.domain.values import micros_to_money


def _simulation() -> dict[str, object]:
    return {
        "simulation_id": "performance",
        "world_seed": "1",
        "campaign_seed": "2",
        "start_hour": "2026-09-03T06:00:00+00:00",
        "time_zone": "UTC",
        "currency": "RUB",
        "world_config_digest": "a" * 64,
    }


@pytest.mark.parametrize(("hours", "channels"), [(168, 20), (2160, 20)])
def test_full_plan_time_size_and_memory_are_bounded(hours: int, channels: int) -> None:
    channel_ids = [f"channel_{index:02d}" for index in range(channels)]
    tracemalloc.start()
    started = time.perf_counter()
    plan = create_fixed_budget_plan(
        budget_micros=2**63 - 1,
        horizon=Horizon(0, hours),
        channels=channel_ids,
        simulation=_simulation(),
        optimize="unique_reach",
    )
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    payload = json.dumps(
        [
            {
                "channel_id": item.channel_id,
                "hour": item.hour,
                "budget_cap": micros_to_money(item.budget_micros),
                "expected": None,
            }
            for item in plan.allocations
        ],
        separators=(",", ":"),
    ).encode()
    assert len(plan.allocations) == hours * channels
    assert sum(item.budget_micros for item in plan.allocations) == 2**63 - 1
    assert elapsed < 1.0
    assert len(payload) < 8_000_000
    assert peak < 64_000_000


def test_prior_full_plans_are_not_retained() -> None:
    tracemalloc.start()
    for _ in range(4):
        plan = create_fixed_budget_plan(
            budget_micros=1_000_000,
            horizon=Horizon(0, 2160),
            channels=[f"channel_{index:02d}" for index in range(20)],
            simulation=_simulation(),
            optimize="clicks",
        )
        del plan
        gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert current < 2_000_000
    assert peak < 64_000_000
