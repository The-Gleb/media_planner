import math
from dataclasses import replace

import pytest

from planner.application.planning import create_fixed_budget_plan
from planner.domain.catalog import load_catalog
from planner.domain.models import Horizon
from planner.domain.optimized import allocate_optimized, forecast_allocations, forecast_plan
from planner.domain.response import ObservedChannel, forecast_hourly

SIMULATION: dict[str, object] = {
    "simulation_id": "forecast",
    "world_seed": "42",
    "campaign_seed": "7",
    "start_hour": "2026-09-03T06:00:00+00:00",
    "time_zone": "Europe/Moscow",
    "currency": "RUB",
    "world_config_digest": "a" * 64,
}
CHANNELS = ["programmatic", "social_1", "sms"]


def _current(hour: int, spent: str, impressions: str, clicks: str) -> dict[str, object]:
    return {
        "current_hour": hour,
        "state_revision": hour,
        "spent": spent,
        "channels": {
            channel: {
                "spent": spent if channel == "programmatic" else "0.000000",
                "requests": "500000" if channel == "programmatic" else "0",
                "impressions": impressions if channel == "programmatic" else "0",
                "unique_reach": impressions if channel == "programmatic" else "0",
                "clicks": clicks if channel == "programmatic" else "0",
                "conversions": "0",
            }
            for channel in CHANNELS
        },
    }


def test_hourly_forecast_sums_to_the_campaign_total() -> None:
    horizon = Horizon(0, 504)
    allocations = allocate_optimized(
        1_200_000_000_000, horizon, CHANNELS, "conversions", simulation=SIMULATION
    )
    forecast = forecast_plan(allocations, horizon, CHANNELS, None, SIMULATION)
    assert forecast is not None
    assert set(forecast.hourly) == {(c, h) for c in CHANNELS for h in range(504)}
    hourly = list(forecast.hourly.values())
    assert forecast.total.spend_micros == sum(item.spend_micros for item in hourly)
    assert math.isclose(forecast.total.clicks, sum(item.clicks for item in hourly))
    assert math.isclose(forecast.total.conversions, sum(item.conversions for item in hourly))
    assert forecast.total.spend_micros <= 1_200_000_000_000
    assert forecast.total.spend_micros > 1_100_000_000_000
    assert forecast_allocations(allocations, horizon, CHANNELS, SIMULATION) == forecast.total


def test_hourly_spend_never_exceeds_the_cap_and_reach_saturates() -> None:
    # Small explicit fixture: the production SMS base need not saturate at this budget.
    channel = replace(load_catalog()["sms"], audience_capacity=200_000)
    caps = [50_000_000_000] * 240
    steps = forecast_hourly(channel, ObservedChannel(), caps, Horizon(0, 240), 0)
    assert all(step.spend_micros <= cap for step, cap in zip(steps, caps, strict=True))
    assert sum(step.unique_reach for step in steps) <= channel.audience_capacity
    early = sum(step.unique_reach for step in steps[:24])
    late = sum(step.unique_reach for step in steps[-24:])
    assert late < early


def test_replan_forecast_starts_from_observed_facts() -> None:
    horizon = Horizon(0, 48)
    current = _current(12, "6000.000000", "120000", "300")
    allocations = allocate_optimized(
        100_000_000_000, horizon, CHANNELS, "clicks", current, SIMULATION
    )
    forecast = forecast_plan(allocations, horizon, CHANNELS, current, SIMULATION)
    assert forecast is not None
    assert all(hour >= 12 for _, hour in forecast.hourly)
    assert len(forecast.hourly) == 36 * len(CHANNELS)
    future_spend = sum(item.spend_micros for item in forecast.hourly.values())
    assert forecast.total.spend_micros == 6_000_000_000 + future_spend
    future_clicks = sum(item.clicks for item in forecast.hourly.values())
    assert math.isclose(forecast.total.clicks, 300 + future_clicks)


def test_forecast_uses_the_same_calibration_as_the_optimizer() -> None:
    horizon = Horizon(0, 48)
    weak = _current(12, "6000.000000", "120000", "30")
    strong = _current(12, "6000.000000", "120000", "3000")
    # Ensure the calibrated channel receives budget regardless of competing catalog channels.
    channels = ["programmatic"]
    allocations = allocate_optimized(100_000_000_000, horizon, channels, "clicks", weak, SIMULATION)
    weak_forecast = forecast_plan(allocations, horizon, channels, weak, SIMULATION)
    strong_forecast = forecast_plan(allocations, horizon, channels, strong, SIMULATION)
    assert weak_forecast is not None and strong_forecast is not None
    weak_clicks = sum(f.clicks for (c, _), f in weak_forecast.hourly.items() if c == "programmatic")
    strong_clicks = sum(
        f.clicks for (c, _), f in strong_forecast.hourly.items() if c == "programmatic"
    )
    assert strong_clicks > weak_clicks


def test_unknown_catalog_channel_yields_no_forecast() -> None:
    plan = create_fixed_budget_plan(
        budget_micros=12_000_000,
        horizon=Horizon(0, 2),
        channels=["search_1", "social_1"],
        simulation=SIMULATION,
        optimize="clicks",
        strategy="uniform",
    )
    assert plan.forecast is None


@pytest.mark.parametrize("strategy", ["uniform", "optimized"])
def test_every_catalog_strategy_carries_a_trajectory(strategy: str) -> None:
    plan = create_fixed_budget_plan(
        budget_micros=500_000_000_000,
        horizon=Horizon(0, 336),
        channels=list(load_catalog()),
        simulation=SIMULATION,
        optimize="conversions",
        strategy=strategy,
        current=None,
    )
    assert plan.forecast is not None
    assert len(plan.forecast.hourly) == len(plan.allocations)
    assert plan.forecast.total.conversions > 0
