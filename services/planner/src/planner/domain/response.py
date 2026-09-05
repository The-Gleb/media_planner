"""Forward response model shared by the optimizer, the plan forecast and the history prior."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from planner.domain.catalog import ChannelBenchmark
from planner.domain.models import Forecast, Horizon

CR_FATIGUE_RATIO = 0.0
"""Simulator `sim-v0` applies fatigue to CTR only; a non-zero ratio would double-count once the
CR prior is learned from observed facts, so the benchmark mirrors the Simulator here."""


@dataclass(frozen=True, slots=True)
class ObservedChannel:
    spent_micros: int = 0
    requests: int = 0
    impressions: int = 0
    unique_reach: int = 0
    clicks: int = 0
    conversions: int = 0

    def as_forecast(self) -> Forecast:
        return Forecast(
            spend_micros=self.spent_micros,
            impressions=float(self.impressions),
            unique_reach=float(self.unique_reach),
            clicks=float(self.clicks),
            conversions=float(self.conversions),
        )


@dataclass(slots=True)
class _SaturationState:
    """Cumulative reach and impressions that drive the saturation mechanics."""

    reach: float
    impressions_total: float


def _hour_weights(
    channel: ChannelBenchmark, horizon: Horizon, start_clock_hour: int
) -> list[float]:
    return [
        channel.hourly_profile[(start_clock_hour + hour) % 24]
        for hour in range(horizon.from_hour, horizon.to_hour)
    ]


def _initial_state(channel: ChannelBenchmark, observed: ObservedChannel) -> _SaturationState:
    return _SaturationState(
        reach=min(float(observed.unique_reach), channel.audience_capacity),
        impressions_total=float(observed.impressions),
    )


def _forecast_step(
    channel: ChannelBenchmark,
    state: _SaturationState,
    budget: float,
    weight: float,
) -> Forecast:
    """Advance the saturation state by one period and return that period's expectation.

    ``weight`` is the share of daily supply available in the period; ``budget`` is in
    whole currency units. The returned ``unique_reach`` is the new reach of the period.
    """
    saturation = min(state.reach / channel.audience_capacity, 1.0)
    depth = max(
        (saturation - channel.saturation_threshold) / (1.0 - channel.saturation_threshold),
        0.0,
    )
    frequency = max(state.impressions_total / max(state.reach, 1.0), 1.0)
    excess_frequency = max(frequency - 1.0, 0.0)
    cpm = channel.cpm * (1.0 + channel.price_growth * depth**2)
    supply = channel.daily_capacity * weight
    impressions = min(supply, budget * 1_000.0 / cpm)
    fatigue_exponent = channel.ctr_fatigue * depth + channel.frequency_fatigue * excess_frequency
    ctr = channel.ctr * math.exp(-fatigue_exponent)
    cr = channel.cr * math.exp(-CR_FATIGUE_RATIO * fatigue_exponent)
    new_probability = max(
        (1.0 - depth) ** channel.reach_decay
        * math.exp(-channel.frequency_reach_decay * excess_frequency),
        0.0,
    )
    clicks = impressions * ctr
    new_reach = min(impressions * new_probability, channel.audience_capacity - state.reach)
    state.reach += new_reach
    state.impressions_total += impressions
    return Forecast(
        spend_micros=max(0, round(impressions * cpm / 1_000.0 * 1_000_000)),
        impressions=impressions,
        unique_reach=new_reach,
        clicks=clicks,
        conversions=clicks * cr,
    )


def forecast_hourly(
    channel: ChannelBenchmark,
    observed: ObservedChannel,
    budgets_micros: Sequence[int],
    future: Horizon,
    start_clock_hour: int,
) -> list[Forecast]:
    """Exact hourly forecast for the given per-hour caps starting from the observed state."""
    weights = _hour_weights(channel, future, start_clock_hour)
    if len(weights) != len(budgets_micros):
        raise ValueError("one budget cap per future hour is required")
    state = _initial_state(channel, observed)
    return [
        _forecast_step(channel, state, budget_micros / 1_000_000, weight)
        for budget_micros, weight in zip(budgets_micros, weights, strict=True)
    ]
