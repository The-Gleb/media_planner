"""Prior from the observable history of earlier campaigns on the same market.

A past campaign contributes, per channel, twenty-four hour-of-day bins of the facts it could
observe: how many campaign hours fell into the bin, requests, impressions, new unique reach,
clicks, conversions and spend. Nothing hidden from the Simulator world is present, so the prior
cannot leak world parameters; it only sharpens the public catalog benchmark toward what this
market actually showed. Recent campaigns weigh more than old ones.
"""

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import lru_cache

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
class DailyFacts:
    """Facts of one channel over one campaign day plus the saturation state at its start.

    ``reach_before`` and ``impressions_before`` are the channel's cumulative unique reach and
    impressions when the day began; together with the day's outcome they reveal how CTR, price
    and the share of new users moved as the audience was bought out.
    """

    day: int
    hours: int
    requests: int
    impressions: int
    unique_reach: int
    clicks: int
    conversions: int
    spent_micros: int
    reach_before: int
    impressions_before: int


@dataclass(frozen=True, slots=True)
class PastCampaignChannel:
    bins: tuple[HourBin, ...]
    daily: tuple[DailyFacts, ...] = ()

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


RIDGE_SHARE = 0.5
"""Ridge weight toward catalog saturation parameters, as a share of the total row weight."""
MIN_FIT_IMPRESSIONS = 500.0
BASE_DEPTH = 0.05


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting for the tiny normal-equation systems here."""
    size = len(vector)
    rows = [list(row) + [value] for row, value in zip(matrix, vector, strict=True)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda index: abs(rows[index][column]))
        if abs(rows[pivot][column]) < 1e-12:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for index in range(size):
            if index == column:
                continue
            factor = rows[index][column] / rows[column][column]
            rows[index] = [a - factor * b for a, b in zip(rows[index], rows[column], strict=True)]
    return [rows[index][size] / rows[index][index] for index in range(size)]


def _ridge(
    rows: list[tuple[list[float], float, float]],
    prior: list[float],
    penalised: list[bool],
) -> list[float]:
    """Weighted least squares with a ridge pull toward ``prior`` on the penalised coefficients."""
    size = len(prior)
    total_weight = sum(weight for _, _, weight in rows)
    if total_weight <= 0:
        return list(prior)
    ridge = RIDGE_SHARE * total_weight
    matrix = [[0.0] * size for _ in range(size)]
    vector = [0.0] * size
    for features, target, weight in rows:
        for i in range(size):
            vector[i] += weight * features[i] * target
            for j in range(size):
                matrix[i][j] += weight * features[i] * features[j]
    for i in range(size):
        if penalised[i]:
            matrix[i][i] += ridge
            vector[i] += ridge * prior[i]
    solution = _solve(matrix, vector)
    return solution if solution is not None else list(prior)


def _depth(channel: ChannelBenchmark, reach_before: int) -> float:
    saturation = min(reach_before / channel.audience_capacity, 1.0)
    return max(
        (saturation - channel.saturation_threshold) / (1.0 - channel.saturation_threshold), 0.0
    )


def _excess_frequency(reach_before: int, impressions_before: int) -> float:
    return max(impressions_before / max(reach_before, 1) - 1.0, 0.0)


def fit_saturation(
    channel: ChannelBenchmark, history: Sequence[PastCampaignChannel]
) -> ChannelBenchmark:
    """Learn the saturation mechanics from daily rows of past campaigns.

    Three separate regressions, each pulled toward the catalog value by a ridge term so that
    campaigns that never bought deep into the audience leave the catalog untouched:

    * ``log CTR_d = b − α·depth_d − α_f·excess_frequency_d`` gives CTR fatigue and frequency
      fatigue (the intercept is the base CTR, used by the caller);
    * ``CPM_d / P0 − 1 = g·depth_d²`` gives price growth, with ``P0`` the price at low depth;
    * ``log(new_reach_d / impressions_d) = ρ·log(1 − depth_d) − ρ_f·excess_frequency_d`` gives
      the reach decay and the frequency reach decay.
    """
    weights = recency_weights(len(history))
    ctr_rows: list[tuple[list[float], float, float]] = []
    reach_rows: list[tuple[list[float], float, float]] = []
    price_rows: list[tuple[float, float, float]] = []
    for weight, campaign in zip(weights, history, strict=True):
        for day in campaign.daily:
            if day.impressions < MIN_FIT_IMPRESSIONS:
                continue
            depth = _depth(channel, day.reach_before)
            excess = _excess_frequency(day.reach_before, day.impressions_before)
            row_weight = weight * day.impressions
            if day.clicks > 0:
                ctr_rows.append(
                    ([1.0, -depth, -excess], math.log(day.clicks / day.impressions), row_weight)
                )
            if day.unique_reach > 0 and depth < 1.0:
                reach_rows.append(
                    (
                        [math.log(1.0 - depth), -excess],
                        math.log(day.unique_reach / day.impressions),
                        row_weight,
                    )
                )
            if day.spent_micros > 0:
                price_rows.append(
                    (depth, day.spent_micros / 1e6 * 1_000.0 / day.impressions, row_weight)
                )
    if not ctr_rows and not reach_rows and not price_rows:
        return channel

    ctr_fatigue, frequency_fatigue = channel.ctr_fatigue, channel.frequency_fatigue
    if ctr_rows:
        _, alpha, alpha_f = _ridge(
            ctr_rows,
            [0.0, channel.ctr_fatigue, channel.frequency_fatigue],
            [False, True, True],
        )
        ctr_fatigue, frequency_fatigue = max(alpha, 0.0), max(alpha_f, 0.0)

    reach_decay, frequency_reach_decay = channel.reach_decay, channel.frequency_reach_decay
    if reach_rows:
        rho, rho_f = _ridge(
            reach_rows, [channel.reach_decay, channel.frequency_reach_decay], [True, True]
        )
        reach_decay, frequency_reach_decay = max(rho, 0.0), max(rho_f, 0.0)

    price_growth = channel.price_growth
    if price_rows:
        shallow = [(cpm, w) for depth, cpm, w in price_rows if depth <= BASE_DEPTH]
        base_weight = sum(w for _, w in shallow)
        if base_weight > 0:
            base_cpm = sum(cpm * w for cpm, w in shallow) / base_weight
            growth_rows = [
                ([depth**2], cpm / base_cpm - 1.0, w) for depth, cpm, w in price_rows if depth > 0
            ]
            if growth_rows:
                (g,) = _ridge(growth_rows, [channel.price_growth], [True])
                price_growth = max(g, 0.0)

    return replace(
        channel,
        ctr_fatigue=ctr_fatigue,
        frequency_fatigue=frequency_fatigue,
        reach_decay=reach_decay,
        frequency_reach_decay=frequency_reach_decay,
        price_growth=price_growth,
    )


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
    channel = fit_saturation(channel, history)

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


@dataclass(frozen=True, slots=True)
class PriorStrength:
    """Pseudo-counts that say how much current-campaign evidence it takes to move the prior."""

    impressions: float
    clicks: float


BASE_PRIOR_IMPRESSIONS = 1_000.0
BASE_PRIOR_CLICKS = 50.0
MAX_HISTORY_PRIOR_IMPRESSIONS = 30_000.0
MAX_HISTORY_PRIOR_CLICKS = 1_500.0


def prior_strength(history: Sequence[PastCampaignChannel]) -> PriorStrength:
    """Catalog pseudo-counts plus recency-weighted history evidence, capped.

    The cap keeps the prior movable: a shock in the current campaign must still be able to
    override three campaigns of history within a day or two of fresh facts.
    """
    weights = recency_weights(len(history))
    impressions = sum(w * c.impressions for w, c in zip(weights, history, strict=True))
    clicks = sum(w * c.clicks for w, c in zip(weights, history, strict=True))
    return PriorStrength(
        impressions=BASE_PRIOR_IMPRESSIONS + min(impressions, MAX_HISTORY_PRIOR_IMPRESSIONS),
        clicks=BASE_PRIOR_CLICKS + min(clicks, MAX_HISTORY_PRIOR_CLICKS),
    )


def history_key(history: Sequence[PastCampaignChannel]) -> str:
    """Canonical text of a channel's history, used to memoise the prior across hourly replans."""
    return json.dumps(
        [
            [
                [
                    [
                        b.hours,
                        b.requests,
                        b.impressions,
                        b.unique_reach,
                        b.clicks,
                        b.conversions,
                        b.spent_micros,
                    ]
                    for b in c.bins
                ],
                [
                    [
                        d.day,
                        d.hours,
                        d.requests,
                        d.impressions,
                        d.unique_reach,
                        d.clicks,
                        d.conversions,
                        d.spent_micros,
                        d.reach_before,
                        d.impressions_before,
                    ]
                    for d in c.daily
                ],
            ]
            for c in history
        ],
        separators=(",", ":"),
    )


@lru_cache(maxsize=256)
def _cached_prior(
    channel: ChannelBenchmark, key: str, history: tuple[PastCampaignChannel, ...]
) -> ChannelBenchmark:
    return channel_prior(channel, history)


def cached_channel_prior(
    channel: ChannelBenchmark, history: Sequence[PastCampaignChannel]
) -> ChannelBenchmark:
    """``channel_prior`` memoised on the catalog channel and the history content.

    The history of a campaign does not change between its hourly replans, while the prior costs
    a forward replay per past campaign; the cache turns that into a dictionary lookup.
    """
    if not history:
        return channel
    return _cached_prior(channel, history_key(history), tuple(history))


def channel_history(history: Sequence[PastCampaign], channel_id: str) -> list[PastCampaignChannel]:
    return [
        campaign.channels[channel_id] for campaign in history if channel_id in campaign.channels
    ]
