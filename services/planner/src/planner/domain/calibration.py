"""Calibration of a channel benchmark from the facts of the running campaign.

Two sources of evidence exist. Cumulative totals are always present and drive the saturation
state. A window of recent hourly facts is optional; when present, rates are estimated from it with
exponentially decaying weights and a change-point test, so that a market shock changes the
calibrated rates within hours instead of being diluted by everything observed since launch.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

from planner.domain.catalog import ChannelBenchmark
from planner.domain.history import PriorStrength
from planner.domain.response import ObservedChannel, saturation_multipliers

HALF_LIFE_HOURS = 24.0
SHOCK_WINDOW_HOURS = 6
SHOCK_MIN_REFERENCE_HOURS = 12
SHOCK_MIN_IMPRESSIONS = 200
SHOCK_Z_THRESHOLD = 3.0
SHOCK_CPM_RELATIVE = 0.25
SHOCK_SUPPLY_RELATIVE = 0.35
CPM_FULL_CONFIDENCE_IMPRESSIONS = 10_000.0
SUPPLY_FULL_CONFIDENCE_HOURS = 24.0
MAX_CONFIDENCE = 0.9
PAUSED_CAPACITY_RATIO = 0.01


@dataclass(frozen=True, slots=True)
class HourFacts:
    """Observation of one channel in one committed campaign hour."""

    hour: int
    requests: int
    impressions: int
    unique_reach: int
    clicks: int
    conversions: int
    spent_micros: int


@dataclass(frozen=True, slots=True)
class Calibration:
    channel: ChannelBenchmark
    shock: str | None
    """Metric whose recent behaviour contradicts the longer window, if any."""


def _blend_log(
    base: float, observed: float, confidence: float, floor: float, ceiling: float
) -> float:
    ratio = min(max(observed / base, floor), ceiling)
    return base * math.exp(confidence * math.log(ratio))


def _expected_requests(
    channel: ChannelBenchmark, hours: Sequence[int], start_clock_hour: int
) -> float:
    return channel.daily_capacity * sum(
        channel.hourly_profile[(start_clock_hour + hour) % 24] for hour in hours
    )


def _cumulative(
    channel: ChannelBenchmark,
    strength: PriorStrength,
    observed: ObservedChannel,
    elapsed_hours: int,
    start_clock_hour: int,
) -> ChannelBenchmark:
    """Legacy calibration from cumulative totals when no hourly window is available."""
    ctr = (observed.clicks + strength.impressions * channel.ctr) / (
        observed.impressions + strength.impressions
    )
    cr = (observed.conversions + strength.clicks * channel.cr) / (observed.clicks + strength.clicks)
    cpm = channel.cpm
    if observed.impressions > 0 and observed.spent_micros > 0:
        observed_cpm = observed.spent_micros / 1_000_000 * 1_000 / observed.impressions
        confidence = min(observed.impressions / CPM_FULL_CONFIDENCE_IMPRESSIONS, 0.8)
        cpm = _blend_log(channel.cpm, observed_cpm, confidence, 0.25, 4.0)
    daily_capacity = channel.daily_capacity
    expected = _expected_requests(channel, range(elapsed_hours), start_clock_hour)
    if expected > 0:
        confidence = min(elapsed_hours / SUPPLY_FULL_CONFIDENCE_HOURS, 0.8)
        daily_capacity = _blend_log(
            channel.daily_capacity,
            channel.daily_capacity * observed.requests / expected,
            confidence,
            0.05,
            5.0,
        )
    return replace(
        channel,
        cpm=max(cpm, 0.000001),
        ctr=min(max(ctr, 0.0), 0.99),
        cr=min(max(cr, 0.0), 0.99),
        daily_capacity=max(daily_capacity, 0.0),
    )


def detect_shock(
    channel: ChannelBenchmark, recent: Sequence[HourFacts], start_clock_hour: int
) -> str | None:
    """Compare the last hours with the preceding window; return the metric that jumped."""
    if len(recent) < SHOCK_WINDOW_HOURS + SHOCK_MIN_REFERENCE_HOURS:
        return None
    tail = recent[-SHOCK_WINDOW_HOURS:]
    head = recent[:-SHOCK_WINDOW_HOURS]
    tail_requests = sum(item.requests for item in tail)
    head_requests = sum(item.requests for item in head)
    tail_expected = _expected_requests(channel, [item.hour for item in tail], start_clock_hour)
    head_expected = _expected_requests(channel, [item.hour for item in head], start_clock_hour)
    if head_requests > 0 and tail_expected > 0 and head_expected > 0:
        tail_ratio = tail_requests / tail_expected
        head_ratio = head_requests / head_expected
        if abs(tail_ratio - head_ratio) > SHOCK_SUPPLY_RELATIVE * head_ratio:
            return "supply"
    tail_impressions = sum(item.impressions for item in tail)
    head_impressions = sum(item.impressions for item in head)
    if tail_impressions < SHOCK_MIN_IMPRESSIONS or head_impressions < SHOCK_MIN_IMPRESSIONS:
        return None
    head_ctr = sum(item.clicks for item in head) / head_impressions
    if 0.0 < head_ctr < 1.0:
        expected_clicks = tail_impressions * head_ctr
        deviation = math.sqrt(tail_impressions * head_ctr * (1.0 - head_ctr))
        if abs(sum(item.clicks for item in tail) - expected_clicks) > SHOCK_Z_THRESHOLD * deviation:
            return "ctr"
    tail_spend = sum(item.spent_micros for item in tail)
    head_spend = sum(item.spent_micros for item in head)
    if tail_spend > 0 and head_spend > 0:
        tail_cpm = tail_spend / tail_impressions
        head_cpm = head_spend / head_impressions
        if abs(tail_cpm - head_cpm) > SHOCK_CPM_RELATIVE * head_cpm:
            return "cpm"
    return None


def calibrate(
    channel: ChannelBenchmark,
    strength: PriorStrength,
    observed: ObservedChannel,
    recent: Sequence[HourFacts],
    elapsed_hours: int,
    start_clock_hour: int,
) -> Calibration:
    """Calibrate rates and supply from recent hours, falling back to cumulative totals.

    Recent hours are weighted with a 24-hour half-life. When the last hours contradict the
    preceding window, only the post-shock hours are used, so the prior is overridden by fresh
    evidence within hours. Observed CTR and eCPM are corrected for the saturation multipliers
    of the current state, because the forward model applies those multipliers again.
    """
    if elapsed_hours <= 0:
        return Calibration(channel, None)
    if not recent:
        return Calibration(
            _cumulative(channel, strength, observed, elapsed_hours, start_clock_hour), None
        )

    ordered = sorted(recent, key=lambda item: item.hour)
    shock = detect_shock(channel, ordered, start_clock_hour)
    window = ordered[-SHOCK_WINDOW_HOURS:] if shock else ordered
    latest = window[-1].hour
    weights = [0.5 ** ((latest - item.hour) / HALF_LIFE_HOURS) for item in window]

    impressions = sum(w * item.impressions for w, item in zip(weights, window, strict=True))
    clicks = sum(w * item.clicks for w, item in zip(weights, window, strict=True))
    conversions = sum(w * item.conversions for w, item in zip(weights, window, strict=True))
    spend = sum(w * item.spent_micros for w, item in zip(weights, window, strict=True)) / 1e6
    requests = sum(w * item.requests for w, item in zip(weights, window, strict=True))
    hours = sum(weights)
    expected_requests = sum(
        w * channel.daily_capacity * channel.hourly_profile[(start_clock_hour + item.hour) % 24]
        for w, item in zip(weights, window, strict=True)
    )

    multipliers = saturation_multipliers(
        channel, float(observed.unique_reach), float(observed.impressions)
    )
    base_clicks = clicks / max(multipliers.ctr, 1e-6)
    base_conversions = conversions / max(multipliers.ctr * multipliers.cr, 1e-6)
    ctr = (base_clicks + strength.impressions * channel.ctr) / (impressions + strength.impressions)
    cr = (base_conversions + strength.clicks * channel.cr) / (base_clicks + strength.clicks)

    cpm = channel.cpm
    if impressions > 0 and spend > 0:
        observed_cpm = spend * 1_000.0 / impressions / max(multipliers.cpm, 1e-6)
        confidence = min(impressions / CPM_FULL_CONFIDENCE_IMPRESSIONS, MAX_CONFIDENCE)
        cpm = _blend_log(channel.cpm, observed_cpm, confidence, 0.25, 4.0)

    daily_capacity = channel.daily_capacity
    if expected_requests > 0 and hours > 0:
        confidence = min(hours / SUPPLY_FULL_CONFIDENCE_HOURS, MAX_CONFIDENCE)
        ratio = requests / expected_requests
        if sum(item.requests for item in window[-SHOCK_WINDOW_HOURS:]) == 0:
            ratio = PAUSED_CAPACITY_RATIO
            confidence = MAX_CONFIDENCE
        daily_capacity = _blend_log(
            channel.daily_capacity, channel.daily_capacity * ratio, confidence, 0.01, 5.0
        )

    return Calibration(
        replace(
            channel,
            cpm=max(cpm, 0.000001),
            ctr=min(max(ctr, 0.0), 0.99),
            cr=min(max(cr, 0.0), 0.99),
            daily_capacity=max(daily_capacity, 0.0),
        ),
        shock,
    )
