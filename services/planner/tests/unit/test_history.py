from dataclasses import replace

import pytest

from planner.domain.catalog import ChannelBenchmark, load_catalog
from planner.domain.history import (
    HourBin,
    PastCampaign,
    PastCampaignChannel,
    channel_prior,
    recency_weights,
)
from planner.domain.models import Horizon
from planner.domain.optimized import allocate_optimized, forecast_plan
from planner.domain.response import ObservedChannel, forecast_hourly

SIMULATION: dict[str, object] = {
    "simulation_id": "history",
    "world_seed": "1",
    "campaign_seed": "1",
    "start_hour": "2026-09-07T00:00:00+00:00",
    "time_zone": "UTC",
    "currency": "RUB",
    "world_config_digest": "a" * 64,
}


def _campaign_from_world(
    world: ChannelBenchmark, hours: int, cap_micros: int
) -> PastCampaignChannel:
    """Bins a past campaign would have reported if ``world`` were the hidden truth."""
    steps = forecast_hourly(world, ObservedChannel(), [cap_micros] * hours, Horizon(0, hours), 0)
    bins = []
    for hour_of_day in range(24):
        own = [(index, step) for index, step in enumerate(steps) if index % 24 == hour_of_day]
        bins.append(
            HourBin(
                hours=len(own),
                requests=round(
                    sum(world.daily_capacity * world.hourly_profile[hour_of_day] for _ in own)
                ),
                impressions=round(sum(step.impressions for _, step in own)),
                unique_reach=round(sum(step.unique_reach for _, step in own)),
                clicks=round(sum(step.clicks for _, step in own)),
                conversions=round(sum(step.conversions for _, step in own)),
                spent_micros=sum(step.spend_micros for _, step in own),
            )
        )
    return PastCampaignChannel(bins=tuple(bins))


def _shifted_profile(profile: tuple[float, ...], shift: int) -> tuple[float, ...]:
    return tuple(profile[(hour - shift) % 24] for hour in range(24))


def test_prior_recovers_a_market_that_differs_from_the_catalog() -> None:
    catalog = load_catalog()["social_1"]
    world = replace(
        catalog,
        ctr=catalog.ctr * 1.5,
        cr=catalog.cr * 1.3,
        cpm=catalog.cpm * 0.8,
        daily_capacity=catalog.daily_capacity * 1.4,
        hourly_profile=_shifted_profile(catalog.hourly_profile, 6),
    )
    history = [_campaign_from_world(world, 336, 2_000_000_000)]
    prior = channel_prior(catalog, history)

    assert prior.ctr == pytest.approx(world.ctr, rel=0.1)
    assert prior.cr == pytest.approx(world.cr, rel=0.1)
    assert prior.cpm == pytest.approx(world.cpm, rel=0.1)
    assert prior.daily_capacity == pytest.approx(world.daily_capacity, rel=0.1)
    peak_world = max(range(24), key=lambda hour: world.hourly_profile[hour])
    peak_prior = max(range(24), key=lambda hour: prior.hourly_profile[hour])
    assert peak_prior == peak_world
    assert sum(prior.hourly_profile) == pytest.approx(1.0)


def test_recent_campaigns_dominate_older_ones() -> None:
    catalog = load_catalog()["programmatic"]
    weak = _campaign_from_world(replace(catalog, ctr=catalog.ctr * 0.5), 168, 1_000_000_000)
    strong = _campaign_from_world(replace(catalog, ctr=catalog.ctr * 1.5), 168, 1_000_000_000)
    assert recency_weights(3) == pytest.approx([0.49, 0.7, 1.0])
    old_strong = channel_prior(catalog, [strong, weak])
    new_strong = channel_prior(catalog, [weak, strong])
    assert new_strong.ctr > old_strong.ctr


def test_empty_history_and_unknown_channel_leave_the_catalog_unchanged() -> None:
    catalog = load_catalog()["sms"]
    assert channel_prior(catalog, []) == catalog
    history = [PastCampaign(horizon_hours=168, channels={})]
    horizon = Horizon(0, 48)
    channels = ["sms", "social_1"]
    cold = allocate_optimized(50_000_000_000, horizon, channels, "clicks", simulation=SIMULATION)
    warm = allocate_optimized(
        50_000_000_000, horizon, channels, "clicks", simulation=SIMULATION, history=history
    )
    assert cold == warm


def test_history_moves_budget_toward_the_channel_that_proved_better() -> None:
    catalog = load_catalog()
    channels = ["programmatic", "social_1"]
    horizon = Horizon(0, 168)
    budget = 200_000_000_000
    cold = allocate_optimized(budget, horizon, channels, "conversions", simulation=SIMULATION)
    better_programmatic = PastCampaign(
        horizon_hours=336,
        channels={
            "programmatic": _campaign_from_world(
                replace(catalog["programmatic"], cr=catalog["programmatic"].cr * 3.0),
                336,
                1_000_000_000,
            ),
            "social_1": _campaign_from_world(catalog["social_1"], 336, 1_000_000_000),
        },
    )
    warm = allocate_optimized(
        budget,
        horizon,
        channels,
        "conversions",
        simulation=SIMULATION,
        history=[better_programmatic],
    )
    programmatic_cold = sum(a.budget_micros for a in cold if a.channel_id == "programmatic")
    programmatic_warm = sum(a.budget_micros for a in warm if a.channel_id == "programmatic")
    assert programmatic_warm > programmatic_cold
    forecast_cold = forecast_plan(cold, horizon, channels, None, SIMULATION)
    forecast_warm = forecast_plan(warm, horizon, channels, None, SIMULATION, [better_programmatic])
    assert forecast_cold is not None and forecast_warm is not None
    assert forecast_warm.total.conversions > forecast_cold.total.conversions


def _daily_from_world(world: ChannelBenchmark, hours: int, cap_micros: int) -> PastCampaignChannel:
    """Past campaign with hour bins and daily saturation rows generated by ``world``."""
    from planner.domain.history import DailyFacts

    steps = forecast_hourly(world, ObservedChannel(), [cap_micros] * hours, Horizon(0, hours), 0)
    daily = []
    reach = impressions = 0.0
    for day in range(hours // 24):
        own = steps[day * 24 : (day + 1) * 24]
        daily.append(
            DailyFacts(
                day=day,
                hours=24,
                requests=round(world.daily_capacity),
                impressions=round(sum(s.impressions for s in own)),
                unique_reach=round(sum(s.unique_reach for s in own)),
                clicks=round(sum(s.clicks for s in own)),
                conversions=round(sum(s.conversions for s in own)),
                spent_micros=sum(s.spend_micros for s in own),
                reach_before=round(reach),
                impressions_before=round(impressions),
            )
        )
        reach += sum(s.unique_reach for s in own)
        impressions += sum(s.impressions for s in own)
    return replace(_campaign_from_world(world, hours, cap_micros), daily=tuple(daily))


def test_daily_rows_teach_the_saturation_parameters() -> None:
    from planner.domain.history import fit_saturation

    catalog = load_catalog()["social_1"]
    world = replace(
        catalog,
        ctr_fatigue=catalog.ctr_fatigue * 2.5,
        price_growth=catalog.price_growth * 0.3,
        reach_decay=catalog.reach_decay * 1.8,
    )
    # A heavy campaign that buys deep into the audience so that saturation is observable.
    history = [_daily_from_world(world, 504, 3_000_000_000)]
    fitted = fit_saturation(catalog, history)
    for name in ("ctr_fatigue", "price_growth", "reach_decay"):
        catalog_value = getattr(catalog, name)
        world_value = getattr(world, name)
        fitted_value = getattr(fitted, name)
        assert abs(fitted_value - world_value) < abs(catalog_value - world_value), name


def test_shallow_campaigns_leave_saturation_parameters_at_the_catalog() -> None:
    from planner.domain.history import fit_saturation

    catalog = load_catalog()["social_1"]
    world = replace(catalog, ctr_fatigue=catalog.ctr_fatigue * 2.5)
    history = [_daily_from_world(world, 168, 100_000_000)]
    fitted = fit_saturation(catalog, history)
    assert fitted.ctr_fatigue == pytest.approx(catalog.ctr_fatigue, rel=0.15)
