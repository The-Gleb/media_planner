from datetime import UTC, datetime

from planner.application.planning import create_fixed_budget_plan
from planner.domain.models import Horizon


def _simulation() -> dict[str, object]:
    return {
        "simulation_id": "demo",
        "world_seed": "42",
        "campaign_seed": "77",
        "start_hour": datetime(2026, 9, 3, 6, tzinfo=UTC).isoformat(),
        "time_zone": "Europe/Moscow",
        "currency": "RUB",
        "world_config_digest": "a" * 64,
    }


def test_plan_fingerprint_is_deterministic_and_channel_order_independent() -> None:
    first = create_fixed_budget_plan(
        budget_micros=5,
        horizon=Horizon(0, 2),
        channels=["b", "a"],
        simulation=_simulation(),
        optimize="clicks",
    )
    second = create_fixed_budget_plan(
        budget_micros=5,
        horizon=Horizon(0, 2),
        channels=["a", "b"],
        simulation=_simulation(),
        optimize="clicks",
    )
    assert first == second
    assert len(first.plan_id) == 64


def test_every_plan_defining_input_changes_fingerprint() -> None:
    base = create_fixed_budget_plan(
        budget_micros=5,
        horizon=Horizon(0, 2),
        channels=["a"],
        simulation=_simulation(),
        optimize="clicks",
    )
    variants = [
        create_fixed_budget_plan(
            budget_micros=6,
            horizon=Horizon(0, 2),
            channels=["a"],
            simulation=_simulation(),
            optimize="clicks",
        ),
        create_fixed_budget_plan(
            budget_micros=5,
            horizon=Horizon(0, 1),
            channels=["a"],
            simulation=_simulation(),
            optimize="clicks",
        ),
        create_fixed_budget_plan(
            budget_micros=5,
            horizon=Horizon(0, 2),
            channels=["a", "b"],
            simulation=_simulation(),
            optimize="clicks",
        ),
        create_fixed_budget_plan(
            budget_micros=5,
            horizon=Horizon(0, 2),
            channels=["a"],
            simulation={**_simulation(), "currency": "USD"},
            optimize="clicks",
        ),
        create_fixed_budget_plan(
            budget_micros=5,
            horizon=Horizon(0, 2),
            channels=["a"],
            simulation=_simulation(),
            optimize="conversions",
        ),
    ]
    assert all(item.plan_id != base.plan_id for item in variants)
