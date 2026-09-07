import pytest

from planner.domain.catalog import load_catalog
from planner.domain.models import Horizon
from planner.domain.optimized import (
    _campaign_forecast,
    _channel_capacity_micros,
    _response_segments,
    allocate_optimized,
)
from planner.domain.response import ObservedChannel


def test_optimized_plan_is_exact_complete_and_deterministic() -> None:
    channels = ["social_1", "programmatic", "marketplace_2"]
    first = allocate_optimized(12_000_007, Horizon(0, 25), channels, "conversions")
    second = allocate_optimized(12_000_007, Horizon(0, 25), channels, "conversions")

    assert first == second
    assert len(first) == 25 * len(channels)
    assert sum(item.budget_micros for item in first) == 12_000_007
    assert [(item.hour, item.channel_id) for item in first] == sorted(
        (item.hour, item.channel_id) for item in first
    )


def test_objective_changes_optimized_distribution() -> None:
    channels = ["social_1", "programmatic", "marketplace_3"]
    clicks = allocate_optimized(100_000_000_000, Horizon(0, 72), channels, "unique_reach")
    conversions = allocate_optimized(100_000_000_000, Horizon(0, 72), channels, "conversions")

    click_totals = {
        channel: sum(item.budget_micros for item in clicks if item.channel_id == channel)
        for channel in channels
    }
    conversion_totals = {
        channel: sum(item.budget_micros for item in conversions if item.channel_id == channel)
        for channel in channels
    }
    assert click_totals != conversion_totals


def test_new_facts_reallocate_only_the_remaining_budget() -> None:
    channels = ["social_1", "programmatic"]
    current = {
        "current_hour": 1,
        "spent": "2000.000000",
        "channels": {
            "social_1": {
                "spent": "1000.000000",
                "requests": "100000",
                "impressions": "10000",
                "unique_reach": "8000",
                "clicks": "1",
                "conversions": "0",
            },
            "programmatic": {
                "spent": "1000.000000",
                "requests": "1000000",
                "impressions": "50000",
                "unique_reach": "40000",
                "clicks": "1000",
                "conversions": "100",
            },
        },
    }
    initial = allocate_optimized(100_000_000_000, Horizon(0, 24), channels, "conversions")
    replanned = allocate_optimized(
        100_000_000_000, Horizon(0, 24), channels, "conversions", current
    )

    assert sum(item.budget_micros for item in replanned) < 100_000_000_000
    assert sum(item.budget_micros for item in replanned if item.hour == 0) == 2_000_000_000
    assert [item.budget_micros for item in replanned if item.hour == 1] != [
        item.budget_micros for item in initial if item.hour == 1
    ]


def test_public_response_rates_saturate_with_channel_budget() -> None:
    channel = load_catalog()["marketplace_1"]
    horizon = Horizon(0, 336)
    capacity = _channel_capacity_micros(channel, horizon, 0)
    low = _campaign_forecast(channel, ObservedChannel(), capacity * 0.1 / 1_000_000, horizon, 0)
    high = _campaign_forecast(channel, ObservedChannel(), capacity * 0.9 / 1_000_000, horizon, 0)

    assert high.spend_micros * low.impressions > low.spend_micros * high.impressions
    assert high.clicks / high.impressions < low.clicks / low.impressions
    # sim-v0 applies fatigue to CTR only, so the benchmark keeps CR flat.
    assert high.conversions / high.clicks == pytest.approx(low.conversions / low.clicks)


def test_response_segments_have_non_increasing_non_negative_marginal_gain() -> None:
    channel = load_catalog()["social_1"]
    for metric in ("unique_reach", "clicks", "conversions"):
        segments = _response_segments(channel, ObservedChannel(), Horizon(0, 336), 0, metric)
        marginal = [segment.marginal_kpi_per_ruble for segment in segments]
        assert all(value >= 0 for value in marginal)
        assert all(
            right <= left + 1e-15 for left, right in zip(marginal, marginal[1:], strict=False)
        )


def test_exhausted_inventory_is_left_unallocated_instead_of_dumped() -> None:
    channels = list(load_catalog())
    # Deliberately exceed the whole catalog's daily supply, including a large SMS base.
    budget = int(100 * sum(
        c.daily_capacity * c.cpm * (1 + c.price_growth) * 1000
        for c in load_catalog().values()
    ))
    allocations = allocate_optimized(budget, Horizon(0, 24), channels, "conversions")
    totals = {
        channel: sum(item.budget_micros for item in allocations if item.channel_id == channel)
        for channel in channels
    }

    assert sum(totals.values()) < budget / 2
    assert max(totals.values()) < budget / 10
