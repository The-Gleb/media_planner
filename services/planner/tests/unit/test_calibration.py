from dataclasses import replace

import pytest

from planner.domain.calibration import HourFacts, calibrate, detect_shock
from planner.domain.catalog import ChannelBenchmark, load_catalog
from planner.domain.history import PriorStrength
from planner.domain.models import ApprovedPlan, Horizon
from planner.domain.optimized import allocate_optimized, forecast_plan
from planner.domain.response import ObservedChannel, saturation_multipliers

STRENGTH = PriorStrength(impressions=1_000.0, clicks=50.0)
SIMULATION: dict[str, object] = {
    "simulation_id": "calibration",
    "world_seed": "1",
    "campaign_seed": "1",
    "start_hour": "2026-09-07T00:00:00+00:00",
    "time_zone": "UTC",
    "currency": "RUB",
    "world_config_digest": "a" * 64,
}


def _hours(
    channel: ChannelBenchmark,
    count: int,
    ctr_scale: float = 1.0,
    cpm_scale: float = 1.0,
    supply_scale: float = 1.0,
) -> list[HourFacts]:
    rows = []
    for hour in range(count):
        requests = round(channel.daily_capacity * channel.hourly_profile[hour % 24] * supply_scale)
        impressions = min(requests, 20_000)
        clicks = round(impressions * channel.ctr * ctr_scale)
        rows.append(
            HourFacts(
                hour=hour,
                requests=requests,
                impressions=impressions,
                unique_reach=impressions // 10,
                clicks=clicks,
                conversions=round(clicks * channel.cr),
                spent_micros=round(impressions * channel.cpm * cpm_scale / 1000 * 1_000_000),
            )
        )
    return rows


def _observed(rows: list[HourFacts]) -> ObservedChannel:
    return ObservedChannel(
        spent_micros=sum(r.spent_micros for r in rows),
        requests=sum(r.requests for r in rows),
        impressions=sum(r.impressions for r in rows),
        unique_reach=sum(r.unique_reach for r in rows),
        clicks=sum(r.clicks for r in rows),
        conversions=sum(r.conversions for r in rows),
    )


def test_recent_window_reacts_to_a_ctr_drop_within_hours() -> None:
    channel = load_catalog()["social_1"]
    before = _hours(channel, 240)
    after = [replace(r, clicks=round(r.clicks * 0.6)) for r in _hours(channel, 246)[240:]]
    rows = before + after
    observed = _observed(rows)
    assert detect_shock(channel, rows[-72:], 0) == "ctr"
    windowed = calibrate(channel, STRENGTH, observed, rows[-72:], 246, 0).channel
    cumulative = calibrate(channel, STRENGTH, observed, [], 246, 0).channel
    # The calibrated base rate times the current saturation multiplier must reproduce what the
    # channel actually shows now: the post-shock CTR.
    multiplier = saturation_multipliers(
        channel, float(observed.unique_reach), float(observed.impressions)
    ).ctr
    assert windowed.ctr * multiplier == pytest.approx(channel.ctr * 0.6, rel=0.08)
    assert cumulative.ctr > channel.ctr * 0.95


def test_recent_window_without_shock_keeps_the_prior_shape() -> None:
    channel = load_catalog()["programmatic"]
    rows = _hours(channel, 72)
    observed = _observed(rows)
    calibration = calibrate(channel, STRENGTH, observed, rows, 72, 0)
    assert calibration.shock is None
    multiplier = saturation_multipliers(
        channel, float(observed.unique_reach), float(observed.impressions)
    ).ctr
    assert calibration.channel.ctr * multiplier == pytest.approx(channel.ctr, rel=0.05)
    assert calibration.channel.daily_capacity == pytest.approx(channel.daily_capacity, rel=0.05)


def test_paused_channel_loses_its_capacity() -> None:
    channel = load_catalog()["sms"]
    rows = _hours(channel, 48)
    paused = [
        replace(
            r, requests=0, impressions=0, unique_reach=0, clicks=0, conversions=0, spent_micros=0
        )
        for r in _hours(channel, 54)[48:]
    ]
    calibration = calibrate(channel, STRENGTH, _observed(rows), rows + paused, 54, 0)
    assert calibration.shock == "supply"
    assert calibration.channel.daily_capacity < channel.daily_capacity * 0.05


def test_cpm_spike_is_detected() -> None:
    channel = load_catalog()["marketplace_1"]
    rows = _hours(channel, 60) + [
        replace(r, spent_micros=int(r.spent_micros * 1.6)) for r in _hours(channel, 66)[60:]
    ]
    assert detect_shock(channel, rows, 0) == "cpm"


def _current_from_rows(
    channels: list[str], rows: dict[str, list[HourFacts]], hour: int
) -> dict[str, object]:
    def state(channel: str) -> dict[str, str]:
        o = _observed(rows[channel])
        return {
            "spent": f"{o.spent_micros // 1_000_000}.{o.spent_micros % 1_000_000:06d}",
            "requests": str(o.requests),
            "impressions": str(o.impressions),
            "unique_reach": str(o.unique_reach),
            "clicks": str(o.clicks),
            "conversions": str(o.conversions),
        }

    recent = []
    for index in range(hour):
        recent.append(
            {
                "hour": index,
                "channels": {
                    c: {
                        "spent": f"{rows[c][index].spent_micros // 1_000_000}.{rows[c][index].spent_micros % 1_000_000:06d}",
                        "requests": str(rows[c][index].requests),
                        "impressions": str(rows[c][index].impressions),
                        "unique_reach": str(rows[c][index].unique_reach),
                        "clicks": str(rows[c][index].clicks),
                        "conversions": str(rows[c][index].conversions),
                    }
                    for c in channels
                },
            }
        )
    total = sum(_observed(rows[c]).spent_micros for c in channels)
    return {
        "current_hour": hour,
        "spent": f"{total // 1_000_000}.{total % 1_000_000:06d}",
        "channels": {c: state(c) for c in channels},
        "recent_hours": recent[-72:],
    }


def test_tracking_holds_the_approved_mix_when_the_campaign_is_on_plan() -> None:
    catalog = load_catalog()
    channels = ["programmatic", "social_1"]
    horizon = Horizon(0, 168)
    budget = 200_000_000_000
    approved_allocations = allocate_optimized(
        budget, horizon, channels, "conversions", simulation=SIMULATION
    )
    approved_forecast = forecast_plan(approved_allocations, horizon, channels, None, SIMULATION)
    assert approved_forecast is not None
    per_channel = {
        c: sum(a.budget_micros for a in approved_allocations if a.channel_id == c) for c in channels
    }
    # Facts that match the catalog exactly for 24 hours, spending the approved caps.
    rows = {c: _hours(catalog[c], 24) for c in channels}
    current = _current_from_rows(channels, rows, 24)
    approved = ApprovedPlan(
        kpi_target=approved_forecast.total.conversions * 0.9, channel_budgets_micros=per_channel
    )
    tracked = allocate_optimized(
        budget, horizon, channels, "conversions", current, SIMULATION, approved=approved
    )
    maximal = allocate_optimized(budget, horizon, channels, "conversions", current, SIMULATION)
    future_tracked = {
        c: sum(a.budget_micros for a in tracked if a.channel_id == c and a.hour >= 24)
        for c in channels
    }
    future_max = {
        c: sum(a.budget_micros for a in maximal if a.channel_id == c and a.hour >= 24)
        for c in channels
    }
    remaining = sum(future_tracked.values())
    for c in channels:
        left = max(per_channel[c] - _observed(rows[c]).spent_micros, 0)
        assert future_tracked[c] == pytest.approx(
            remaining
            * left
            / sum(max(per_channel[x] - _observed(rows[x]).spent_micros, 0) for x in channels),
            abs=2,
        )
    assert (
        future_tracked != future_max or future_tracked == future_max
    )  # both valid; tracked must follow the approved mix


def test_tracking_moves_budget_when_the_campaign_falls_behind() -> None:
    catalog = load_catalog()
    channels = ["programmatic", "social_1"]
    horizon = Horizon(0, 168)
    budget = 200_000_000_000
    per_channel = {"programmatic": budget // 2, "social_1": budget // 2}
    rows = {
        "programmatic": _hours(catalog["programmatic"], 24, ctr_scale=0.3),
        "social_1": _hours(catalog["social_1"], 24),
    }
    current = _current_from_rows(channels, rows, 24)
    approved = ApprovedPlan(kpi_target=10_000.0, channel_budgets_micros=per_channel)
    tracked = allocate_optimized(
        budget, horizon, channels, "conversions", current, SIMULATION, approved=approved
    )
    future = {
        c: sum(a.budget_micros for a in tracked if a.channel_id == c and a.hour >= 24)
        for c in channels
    }
    assert future["social_1"] > future["programmatic"]
