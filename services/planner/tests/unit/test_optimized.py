from planner.domain.models import Horizon
from planner.domain.optimized import allocate_optimized


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

    assert sum(item.budget_micros for item in replanned) == 100_000_000_000
    assert sum(item.budget_micros for item in replanned if item.hour == 0) == 2_000_000_000
    assert [item.budget_micros for item in replanned if item.hour == 1] != [
        item.budget_micros for item in initial if item.hour == 1
    ]
