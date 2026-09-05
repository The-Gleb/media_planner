"""Prior from the observable history of earlier campaigns on the same market.

A past campaign contributes, per channel, twenty-four hour-of-day bins of the facts it could
observe: how many campaign hours fell into the bin, requests, impressions, new unique reach,
clicks, conversions and spend. Nothing hidden from the Simulator world is present, so the prior
cannot leak world parameters; it only sharpens the public catalog benchmark toward what this
market actually showed. Recent campaigns weigh more than old ones.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

from planner.domain.catalog import ChannelBenchmark
from planner.domain.models import Horizon
from planner.domain.response import ObservedChannel, forecast_hourly

HOURS_PER_DAY = 24
RECENCY_DECAY = 0.7
"""Weight multiplier applied to a campaign for every more recent campaign after it."""
CTR_PRIOR_IMPRESSIONS = 1_000.0
CR_PRIOR_CLICKS = 50.0
CPM_FULL_CONFIDENCE_IMPRESSIONS = 100_000.0
SUPPLY_FULL_CONFIDENCE_HOURS = 168.0
MAX_HISTORY_CONFIDENCE = 0.95
RATIO_FLOOR = 0.1
RATIO_CEILING = 10.0


@dataclass(frozen=True, slots=True)
class HourBin:
    """Facts of one channel accumulated over the campaign hours with this hour of day."""

    hours: int
    requests: int
    impressions: int
    unique_reach: int
    clicks: int
    conversions: int
    spent_micros: int


@dataclass(frozen=True, slots=True)
class PastCampaignChannel:
    bins: tuple[HourBin, ...]

    def __post_init__(self) -> None:
        if len(self.bins) != HOURS_PER_DAY:
            raise ValueError("a past campaign channel needs exactly 24 hour-of-day bins")

    @property
    def hours(self) -> int:
        return sum(item.hours for item in self.bins)

    @property
    def impressions(self) -> int:
        return sum(item.impressions for item in self.bins)

    @property
    def clicks(self) -> int:
        return sum(item.clicks for item in self.bins)

    @property
    def conversions(self) -> int:
        return sum(item.conversions for item in self.bins)

    @property
    def spent_micros(self) -> int:
        return sum(item.spent_micros for item in self.bins)


@dataclass(frozen=True, slots=True)
class PastCampaign:
    """One finished campaign, oldest campaigns first in a history sequence."""

    horizon_hours: int
    channels: dict[str, PastCampaignChannel]


def recency_weights(count: int) -> list[float]:
    """Oldest campaign first; the most recent campaign has weight one."""
    return [RECENCY_DECAY ** (count - 1 - index) for index in range(count)]


def _blend_log(catalog_value: float, observed_value: float, confidence: float) -> float:
    ratio = min(max(observed_value / catalog_value, RATIO_FLOOR), RATIO_CEILING)
    return catalog_value * math.exp(confidence * math.log(ratio))


def saturation_ratios(
    channel: ChannelBenchmark, campaign: PastCampaignChannel
) -> tuple[float, float]:
    """Effective-to-base CTR and CPM ratios the campaign would have shown on the catalog market.

    A past campaign observed CTR and eCPM under its own saturation path: fatigue lowers CTR and
    price growth raises CPM as reach accumulates. Replaying the campaign's hour-of-day spend
    through the benchmark response model estimates those multipliers, so the prior learns the
    base rates rather than rates depressed or inflated by that campaign's saturation.
    """
    hours = campaign.hours
    if hours <= 0:
        return 1.0, 1.0
    caps = [item.spent_micros // item.hours if item.hours > 0 else 0 for item in campaign.bins]
    steps = forecast_hourly(
        channel, ObservedChannel(), [caps[hour % 24] for hour in range(hours)], Horizon(0, hours), 0
    )
    impressions = sum(step.impressions for step in steps)
    if impressions <= 0:
        return 1.0, 1.0
    clicks = sum(step.clicks for step in steps)
    spend = sum(step.spend_micros for step in steps) / 1_000_000
    ctr_ratio = clicks / impressions / channel.ctr if channel.ctr > 0 else 1.0
    cpm_ratio = spend * 1_000.0 / impressions / channel.cpm if channel.cpm > 0 else 1.0
    return max(ctr_ratio, 1e-6), max(cpm_ratio, 1e-6)


def channel_prior(
    channel: ChannelBenchmark, history: Sequence[PastCampaignChannel]
) -> ChannelBenchmark:
    """Sharpen the catalog benchmark with recency-weighted facts of past campaigns.

    CTR and CR are Beta-Binomial posteriors whose prior strength is the catalog pseudo-count;
    CPM and daily supply are log-space blends whose confidence grows with the evidence; the
    hourly supply profile is a linear blend of the observed per-hour request rates with the
    catalog profile. Missing history returns the catalog unchanged.
    """
    if not history:
        return channel
    weights = recency_weights(len(history))

    impressions = clicks = conversions = spent = hours = 0.0
    bin_hours = [0.0] * HOURS_PER_DAY
    bin_requests = [0.0] * HOURS_PER_DAY
    for weight, campaign in zip(weights, history, strict=True):
        ctr_ratio, cpm_ratio = saturation_ratios(channel, campaign)
        impressions += weight * campaign.impressions
        clicks += weight * campaign.clicks / ctr_ratio
        conversions += weight * campaign.conversions / ctr_ratio
        spent += weight * campaign.spent_micros / 1_000_000 / cpm_ratio
        hours += weight * campaign.hours
        for hour, item in enumerate(campaign.bins):
            bin_hours[hour] += weight * item.hours
            bin_requests[hour] += weight * item.requests

    ctr = (clicks + CTR_PRIOR_IMPRESSIONS * channel.ctr) / (impressions + CTR_PRIOR_IMPRESSIONS)
    cr = (conversions + CR_PRIOR_CLICKS * channel.cr) / (clicks + CR_PRIOR_CLICKS)

    cpm = channel.cpm
    if impressions > 0 and spent > 0:
        confidence = min(impressions / CPM_FULL_CONFIDENCE_IMPRESSIONS, MAX_HISTORY_CONFIDENCE)
        cpm = _blend_log(channel.cpm, spent * 1_000.0 / impressions, confidence)

    daily_capacity = channel.daily_capacity
    profile = channel.hourly_profile
    if hours > 0:
        # Requests per hour at every hour of day; bins never observed keep the catalog shape.
        rates = [
            bin_requests[hour] / bin_hours[hour]
            if bin_hours[hour] > 0
            else channel.daily_capacity * channel.hourly_profile[hour]
            for hour in range(HOURS_PER_DAY)
        ]
        observed_daily = sum(rates)
        confidence = min(hours / SUPPLY_FULL_CONFIDENCE_HOURS, MAX_HISTORY_CONFIDENCE)
        if observed_daily > 0:
            daily_capacity = _blend_log(channel.daily_capacity, observed_daily, confidence)
            blended = [
                (1.0 - confidence) * catalog_share + confidence * rate / observed_daily
                for catalog_share, rate in zip(channel.hourly_profile, rates, strict=True)
            ]
            total = sum(blended)
            profile = tuple(value / total for value in blended)

    return replace(
        channel,
        cpm=max(cpm, 0.000001),
        ctr=min(max(ctr, 0.0), 0.99),
        cr=min(max(cr, 0.0), 0.99),
        daily_capacity=max(daily_capacity, 0.0),
        hourly_profile=profile,
    )


def channel_history(history: Sequence[PastCampaign], channel_id: str) -> list[PastCampaignChannel]:
    return [
        campaign.channels[channel_id] for campaign in history if channel_id in campaign.channels
    ]
