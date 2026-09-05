import hashlib
import json
import re
from collections.abc import Mapping, Sequence

from planner.domain.catalog import load_catalog
from planner.domain.history import PastCampaign
from planner.domain.models import KPI, ApprovedPlan, Horizon, MediaPlan, Strategy
from planner.domain.optimized import allocate_optimized, forecast_plan
from planner.domain.target import TargetBudgetSolution, solve_target_budget
from planner.domain.uniform import allocate_uniformly
from planner.domain.values import MAX_MICROS

_CHANNEL_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

FINGERPRINT_VERSION = "fixed-budget-v3"
TARGET_FINGERPRINT_VERSION = "target-kpi-v3"


def history_payload(history: Sequence[PastCampaign]) -> list[dict[str, object]]:
    """Canonical, JSON-serialisable form of the history for plan fingerprints."""
    return [
        {
            "horizon_hours": campaign.horizon_hours,
            "channels": {
                channel_id: {
                    "bins": [
                        [
                            item.hours,
                            item.requests,
                            item.impressions,
                            item.unique_reach,
                            item.clicks,
                            item.conversions,
                            item.spent_micros,
                        ]
                        for item in channel.bins
                    ],
                    "daily": [
                        [
                            item.day,
                            item.hours,
                            item.requests,
                            item.impressions,
                            item.unique_reach,
                            item.clicks,
                            item.conversions,
                            item.spent_micros,
                            item.reach_before,
                            item.impressions_before,
                        ]
                        for item in channel.daily
                    ],
                }
                for channel_id, channel in sorted(campaign.channels.items())
            },
        }
        for campaign in history
    ]


def plan_fingerprint(defining_inputs: Mapping[str, object]) -> str:
    canonical = json.dumps(
        {"version": FINGERPRINT_VERSION, **defining_inputs},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_fixed_budget_plan(
    *,
    budget_micros: int,
    horizon: Horizon,
    channels: Sequence[str],
    simulation: Mapping[str, object],
    optimize: str,
    strategy: str = "uniform",
    current: Mapping[str, object] | None = None,
    history: Sequence[PastCampaign] = (),
    approved: ApprovedPlan | None = None,
) -> MediaPlan:
    if not 0 <= budget_micros <= MAX_MICROS:
        raise ValueError("budget must fit the signed int64 micro-unit range")
    if not 0 <= horizon.from_hour < horizon.to_hour <= 2160:
        raise ValueError("horizon must be a non-empty subset of [0, 2160)")
    if not 1 <= len(channels) <= 20:
        raise ValueError("between 1 and 20 channels are required")
    if len(set(channels)) != len(channels):
        raise ValueError("channels must be unique")
    if any(_CHANNEL_RE.fullmatch(channel) is None for channel in channels):
        raise ValueError("channel identifier is invalid")
    if horizon.duration * len(channels) > 43_200:
        raise ValueError("plan exceeds the maximum allocation count")
    if strategy not in {item.value for item in Strategy}:
        raise ValueError("unsupported allocation strategy")
    if optimize not in {item.value for item in KPI}:
        raise ValueError("unsupported optimization KPI")
    ordered_channels = sorted(channels)
    defining: dict[str, object] = {
        "type": "fixed_budget",
        "strategy": strategy,
        "optimize": optimize,
        "budget_micros": budget_micros,
        "horizon": {"from_hour": horizon.from_hour, "to_hour": horizon.to_hour},
        "channels": ordered_channels,
        "simulation": dict(simulation),
    }
    if strategy == Strategy.OPTIMIZED.value and current is not None:
        defining["current"] = dict(current)
    if strategy == Strategy.OPTIMIZED.value and history:
        defining["history"] = history_payload(history)
    if strategy == Strategy.OPTIMIZED.value and approved is not None:
        defining["approved"] = {
            "kpi_target": approved.kpi_target,
            "channel_budgets_micros": dict(sorted(approved.channel_budgets_micros.items())),
        }
    allocations = (
        allocate_uniformly(budget_micros, horizon, ordered_channels)
        if strategy == Strategy.UNIFORM.value
        else allocate_optimized(
            budget_micros,
            horizon,
            ordered_channels,
            optimize,
            current,
            simulation,
            history,
            approved,
        )
    )
    return MediaPlan(
        plan_id=plan_fingerprint(defining),
        horizon=horizon,
        allocations=allocations,
        unallocated_budget_micros=budget_micros
        - sum(allocation.budget_micros for allocation in allocations),
        forecast=forecast_plan(
            allocations, horizon, ordered_channels, current, simulation, history
        ),
    )


def create_target_kpi_plan(
    *,
    target_value: int,
    target_metric: str,
    horizon: Horizon,
    channels: Sequence[str],
    simulation: Mapping[str, object],
    strategy: str,
    history: Sequence[PastCampaign] = (),
) -> tuple[MediaPlan | None, TargetBudgetSolution]:
    if target_value <= 0:
        raise ValueError("target must be positive")
    if target_metric not in {item.value for item in KPI}:
        raise ValueError("unsupported target KPI")
    if strategy != Strategy.OPTIMIZED.value:
        raise ValueError("target KPI planning requires optimized strategy")
    if not 0 <= horizon.from_hour < horizon.to_hour <= 2160:
        raise ValueError("horizon must be a non-empty subset of [0, 2160)")
    if not 1 <= len(channels) <= 20 or len(set(channels)) != len(channels):
        raise ValueError("between 1 and 20 unique channels are required")
    ordered_channels = sorted(channels)
    catalog = load_catalog()
    unknown = [channel for channel in ordered_channels if channel not in catalog]
    if unknown:
        raise ValueError(f"unknown catalog channel: {unknown[0]}")

    solution = solve_target_budget(
        target_value=target_value,
        metric=target_metric,
        horizon=horizon,
        channel_ids=ordered_channels,
        simulation=dict(simulation),
        history=history,
    )
    if not solution.feasible or solution.required_budget_micros is None:
        return None, solution
    defining: dict[str, object] = {
        "version": TARGET_FINGERPRINT_VERSION,
        "type": "target_kpi",
        "strategy": strategy,
        "target": {"metric": target_metric, "value": target_value},
        "required_budget_micros": solution.required_budget_micros,
        "horizon": {"from_hour": horizon.from_hour, "to_hour": horizon.to_hour},
        "channels": ordered_channels,
        "simulation": dict(simulation),
        "history": history_payload(history),
    }
    return (
        MediaPlan(
            plan_id=plan_fingerprint(defining),
            horizon=horizon,
            allocations=solution.allocations,
            unallocated_budget_micros=solution.required_budget_micros
            - sum(allocation.budget_micros for allocation in solution.allocations),
            forecast=forecast_plan(
                solution.allocations, horizon, ordered_channels, None, simulation
            ),
        ),
        solution,
    )
