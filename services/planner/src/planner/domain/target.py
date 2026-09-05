import math
from dataclasses import dataclass

from planner.domain.models import Allocation, Horizon
from planner.domain.optimized import (
    Forecast,
    allocate_prepared,
    forecast_allocations,
    prepare_optimized,
    useful_budget_capacity_micros,
)
from planner.domain.values import MAX_MICROS, MICROS_PER_UNIT


@dataclass(frozen=True, slots=True)
class TargetBudgetSolution:
    feasible: bool
    required_budget_micros: int | None
    allocations: tuple[Allocation, ...]
    expected: Forecast
    max_achievable: int


def _metric_value(forecast: Forecast, metric: str) -> float:
    return float(getattr(forecast, metric))


def solve_target_budget(
    *,
    target_value: int,
    metric: str,
    horizon: Horizon,
    channel_ids: list[str],
    simulation: dict[str, object],
    quantum_micros: int = MICROS_PER_UNIT,
) -> TargetBudgetSolution:
    """Find the least quantum-sized budget whose benchmark forecast reaches target."""
    if target_value <= 0:
        raise ValueError("target must be positive")
    if quantum_micros <= 0:
        raise ValueError("search quantum must be positive")

    cache: dict[int, tuple[tuple[Allocation, ...], Forecast]] = {}
    prepared = prepare_optimized(
        horizon,
        channel_ids,
        metric,
        current=None,
        simulation=simulation,
    )

    def solve(budget_micros: int) -> tuple[tuple[Allocation, ...], Forecast]:
        cached = cache.get(budget_micros)
        if cached is not None:
            return cached
        allocations = allocate_prepared(prepared, budget_micros)
        result = (
            allocations,
            forecast_allocations(allocations, horizon, channel_ids, simulation),
        )
        cache[budget_micros] = result
        return result

    capacity = useful_budget_capacity_micros(horizon, channel_ids, simulation)
    upper = min(MAX_MICROS, max(quantum_micros, capacity))
    upper = min(MAX_MICROS, ((upper + quantum_micros - 1) // quantum_micros) * quantum_micros)
    upper_allocations, upper_forecast = solve(upper)
    max_achievable = math.floor(_metric_value(upper_forecast, metric))
    if max_achievable < target_value:
        return TargetBudgetSolution(
            feasible=False,
            required_budget_micros=None,
            allocations=(),
            expected=upper_forecast,
            max_achievable=max_achievable,
        )

    low_units = 0
    high_units = upper // quantum_micros
    while low_units + 1 < high_units:
        middle_units = (low_units + high_units) // 2
        _, forecast = solve(middle_units * quantum_micros)
        if _metric_value(forecast, metric) >= target_value:
            high_units = middle_units
        else:
            low_units = middle_units

    required = high_units * quantum_micros
    allocations, expected = solve(required)
    if _metric_value(expected, metric) < target_value:
        raise RuntimeError("target solver failed its feasibility invariant")
    return TargetBudgetSolution(
        feasible=True,
        required_budget_micros=required,
        allocations=allocations,
        expected=expected,
        max_achievable=max_achievable,
    )
