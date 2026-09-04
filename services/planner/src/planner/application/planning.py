import hashlib
import json
import re
from collections.abc import Mapping, Sequence

from planner.domain.models import KPI, Horizon, MediaPlan, Strategy
from planner.domain.optimized import allocate_optimized
from planner.domain.uniform import allocate_uniformly
from planner.domain.values import MAX_MICROS

_CHANNEL_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

FINGERPRINT_VERSION = "fixed-budget-v0"


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
    allocations = (
        allocate_uniformly(budget_micros, horizon, ordered_channels)
        if strategy == Strategy.UNIFORM.value
        else allocate_optimized(
            budget_micros, horizon, ordered_channels, optimize, current, simulation
        )
    )
    return MediaPlan(
        plan_id=plan_fingerprint(defining),
        horizon=horizon,
        allocations=allocations,
    )
