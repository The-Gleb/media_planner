from datetime import UTC, datetime

from planner.application.planning import create_target_kpi_plan
from planner.domain.catalog import load_catalog
from planner.domain.models import Horizon
from planner.domain.optimized import allocate_optimized, forecast_allocations
from planner.domain.values import MICROS_PER_UNIT


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


def test_target_solver_is_deterministic_exact_and_quantized() -> None:
    first_plan, first = create_target_kpi_plan(
        target_value=50_000,
        target_metric="clicks",
        horizon=Horizon(0, 336),
        channels=list(load_catalog()),
        simulation=_simulation(),
        strategy="optimized",
    )
    second_plan, second = create_target_kpi_plan(
        target_value=50_000,
        target_metric="clicks",
        horizon=Horizon(0, 336),
        channels=list(load_catalog()),
        simulation=_simulation(),
        strategy="optimized",
    )
    assert first_plan == second_plan
    assert first == second
    assert first.feasible and first.required_budget_micros is not None
    assert first.expected.clicks >= 50_000
    assert first.required_budget_micros % MICROS_PER_UNIT == 0
    assert sum(item.budget_micros for item in first.allocations) == first.required_budget_micros
    previous = allocate_optimized(
        first.required_budget_micros - MICROS_PER_UNIT,
        Horizon(0, 336),
        list(load_catalog()),
        "clicks",
        simulation=_simulation(),
    )
    assert forecast_allocations(previous, Horizon(0, 336), list(load_catalog())).clicks < 50_000


def test_impossible_target_returns_capacity_diagnosis_without_plan() -> None:
    plan, result = create_target_kpi_plan(
        target_value=999_999_999,
        target_metric="conversions",
        horizon=Horizon(0, 336),
        channels=list(load_catalog()),
        simulation=_simulation(),
        strategy="optimized",
    )
    assert plan is None
    assert not result.feasible
    assert result.required_budget_micros is None
    assert result.allocations == ()
    assert result.max_achievable < 999_999_999
