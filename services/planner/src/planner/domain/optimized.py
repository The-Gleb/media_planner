import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from zoneinfo import ZoneInfo

from planner.domain.catalog import ChannelBenchmark, load_catalog
from planner.domain.models import Allocation, Horizon
from planner.domain.values import money_to_micros

GRID_SIZE = 200
CTR_PRIOR_IMPRESSIONS = 1_000.0
CR_PRIOR_CLICKS = 50.0


@dataclass(frozen=True, slots=True)
class ObservedChannel:
    spent_micros: int = 0
    requests: int = 0
    impressions: int = 0
    unique_reach: int = 0
    clicks: int = 0
    conversions: int = 0


def _observed(current: Mapping[str, object] | None, channel_id: str) -> ObservedChannel:
    if current is None:
        return ObservedChannel()
    channels = current.get("channels")
    if not isinstance(channels, Mapping):
        return ObservedChannel()
    raw = channels.get(channel_id)
    if not isinstance(raw, Mapping):
        return ObservedChannel()
    return ObservedChannel(
        spent_micros=money_to_micros(str(raw.get("spent", "0"))),
        requests=int(str(raw.get("requests", "0"))),
        impressions=int(str(raw.get("impressions", "0"))),
        unique_reach=int(str(raw.get("unique_reach", "0"))),
        clicks=int(str(raw.get("clicks", "0"))),
        conversions=int(str(raw.get("conversions", "0"))),
    )


def _calibrate(
    channel: ChannelBenchmark,
    observed: ObservedChannel,
    elapsed_hours: int,
    start_clock_hour: int,
) -> ChannelBenchmark:
    if elapsed_hours <= 0:
        return channel

    ctr = (observed.clicks + CTR_PRIOR_IMPRESSIONS * channel.ctr) / (
        observed.impressions + CTR_PRIOR_IMPRESSIONS
    )
    cr = (observed.conversions + CR_PRIOR_CLICKS * channel.cr) / (observed.clicks + CR_PRIOR_CLICKS)

    cpm = channel.cpm
    if observed.impressions > 0 and observed.spent_micros > 0:
        observed_cpm = observed.spent_micros / 1_000_000 * 1_000 / observed.impressions
        confidence = min(observed.impressions / 10_000.0, 0.8)
        ratio = min(max(observed_cpm / channel.cpm, 0.25), 4.0)
        cpm = channel.cpm * math.exp(confidence * math.log(ratio))

    daily_capacity = channel.daily_capacity
    expected_requests = channel.daily_capacity * sum(
        channel.hourly_profile[hour % 24]
        for hour in range(start_clock_hour, start_clock_hour + elapsed_hours)
    )
    if expected_requests > 0 and observed.requests >= 0:
        ratio = min(max(observed.requests / expected_requests, 0.05), 5.0)
        confidence = min(elapsed_hours / 24.0, 0.8)
        daily_capacity *= math.exp(confidence * math.log(ratio))

    return replace(
        channel,
        cpm=max(cpm, 0.000001),
        ctr=min(max(ctr, 0.0), 0.99),
        cr=min(max(cr, 0.0), 0.99),
        daily_capacity=max(daily_capacity, 0.0),
    )


def _campaign_kpi(
    channel: ChannelBenchmark,
    observed: ObservedChannel,
    daily_budget: float,
    days: int,
    metric: str,
) -> float:
    reach = min(float(observed.unique_reach), channel.audience_capacity)
    impressions_total = float(observed.impressions)
    clicks_total = 0.0
    conversions_total = 0.0
    for _ in range(days):
        saturation = min(reach / channel.audience_capacity, 1.0)
        depth = max(
            (saturation - channel.saturation_threshold) / (1.0 - channel.saturation_threshold),
            0.0,
        )
        frequency = max(impressions_total / max(reach, 1.0), 1.0)
        cpm = channel.cpm * (1.0 + channel.price_growth * depth**2)
        impressions = min(channel.daily_capacity, daily_budget * 1_000.0 / cpm)
        fatigue = math.exp(-channel.ctr_fatigue * depth - 0.03 * max(frequency - 1.0, 0.0))
        new_probability = max(
            (1.0 - depth) ** channel.reach_decay * math.exp(-0.05 * max(frequency - 1.0, 0.0)),
            0.0,
        )
        clicks = impressions * channel.ctr * fatigue
        reach = min(reach + impressions * new_probability, channel.audience_capacity)
        impressions_total += impressions
        clicks_total += clicks
        conversions_total += clicks * channel.cr
    return (
        reach
        if metric == "unique_reach"
        else clicks_total
        if metric == "clicks"
        else conversions_total
    )


def _daily_waterfill(
    total_daily_budget: float,
    channels: list[ChannelBenchmark],
    observations: list[ObservedChannel],
    days: int,
    metric: str,
) -> list[float]:
    if total_daily_budget <= 0:
        return [0.0] * len(channels)
    slice_size = total_daily_budget / GRID_SIZE
    curves = [
        [
            _campaign_kpi(channel, observations[index], slice_size * point, days, metric)
            for point in range(GRID_SIZE + 1)
        ]
        for index, channel in enumerate(channels)
    ]
    allocation = [0.0] * len(channels)
    pointers = [0] * len(channels)
    for _ in range(GRID_SIZE):
        marginal = [
            curves[index][pointer + 1] - curves[index][pointer]
            for index, pointer in enumerate(pointers)
        ]
        best = max(range(len(channels)), key=lambda index: (marginal[index], -index))
        allocation[best] += slice_size
        pointers[best] += 1
    return allocation


def _exact_weighted_allocations(
    budget_micros: int,
    horizon: Horizon,
    channels: list[ChannelBenchmark],
    daily: list[float],
    start_clock_hour: int,
) -> list[Allocation]:
    slots = [
        (
            hour,
            channel.channel_id,
            daily[index] * channel.hourly_profile[(start_clock_hour + hour) % 24],
        )
        for hour in range(horizon.from_hour, horizon.to_hour)
        for index, channel in enumerate(channels)
    ]
    total_weight = sum(weight for _, _, weight in slots)
    if total_weight <= 0:
        count = len(slots)
        quotient, remainder = divmod(budget_micros, count)
        return [
            Allocation(channel_id, hour, quotient + (index < remainder))
            for index, (hour, channel_id, _) in enumerate(slots)
        ]
    raw = [budget_micros * weight / total_weight for _, _, weight in slots]
    micros = [math.floor(value) for value in raw]
    remainder = budget_micros - sum(micros)
    order = sorted(range(len(raw)), key=lambda index: (-(raw[index] - micros[index]), index))
    for index in order[:remainder]:
        micros[index] += 1
    return [
        Allocation(channel_id, hour, micros[index])
        for index, (hour, channel_id, _) in enumerate(slots)
    ]


def allocate_optimized(
    budget_micros: int,
    horizon: Horizon,
    channel_ids: list[str],
    metric: str,
    current: Mapping[str, object] | None = None,
    simulation: Mapping[str, object] | None = None,
) -> tuple[Allocation, ...]:
    catalog = load_catalog()
    ordered_ids = sorted(channel_ids)
    elapsed = (
        int(str(current.get("current_hour", horizon.from_hour))) - horizon.from_hour
        if current
        else 0
    )
    elapsed = min(max(elapsed, 0), horizon.duration)
    start_clock_hour = 0
    if simulation:
        start = datetime.fromisoformat(str(simulation["start_hour"]).replace("Z", "+00:00"))
        start_clock_hour = start.astimezone(ZoneInfo(str(simulation["time_zone"]))).hour
    observations = [_observed(current, channel_id) for channel_id in ordered_ids]
    channels = [
        _calibrate(catalog[channel_id], observations[index], elapsed, start_clock_hour)
        for index, channel_id in enumerate(ordered_ids)
    ]

    allocations: list[Allocation] = []
    for hour_offset in range(elapsed):
        for index, channel_id in enumerate(ordered_ids):
            quotient, remainder = divmod(observations[index].spent_micros, max(elapsed, 1))
            allocations.append(
                Allocation(
                    channel_id,
                    horizon.from_hour + hour_offset,
                    quotient + (hour_offset < remainder),
                )
            )

    spent_micros = sum(item.spent_micros for item in observations)
    remaining_micros = max(budget_micros - spent_micros, 0)
    future_from = horizon.from_hour + elapsed
    if future_from < horizon.to_hour:
        future = Horizon(future_from, horizon.to_hour)
        days = max(1, math.ceil(future.duration / 24))
        daily = _daily_waterfill(
            remaining_micros / 1_000_000 / days,
            channels,
            observations,
            days,
            metric,
        )
        allocations.extend(
            _exact_weighted_allocations(remaining_micros, future, channels, daily, start_clock_hour)
        )
    elif allocations:
        unassigned = budget_micros - sum(item.budget_micros for item in allocations)
        quotient, remainder = divmod(max(unassigned, 0), len(allocations))
        allocations = [
            replace(item, budget_micros=item.budget_micros + quotient + (index < remainder))
            for index, item in enumerate(allocations)
        ]

    return tuple(allocations)
