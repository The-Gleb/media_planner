import heapq
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from zoneinfo import ZoneInfo

from planner.domain.catalog import ChannelBenchmark, load_catalog
from planner.domain.history import PastCampaign, channel_history, channel_prior
from planner.domain.models import (
    ZERO_FORECAST,
    Allocation,
    Forecast,
    Horizon,
    PlanForecast,
    sum_forecasts,
)
from planner.domain.response import (
    ObservedChannel,
    _forecast_step,
    _hour_weights,
    _initial_state,
    forecast_hourly,
)
from planner.domain.values import MAX_MICROS, money_to_micros

CURVE_POINTS = 128
MODEL_MAX_STEPS = 240
WEIGHT_SCALE = 10**15
CTR_PRIOR_IMPRESSIONS = 1_000.0
CR_PRIOR_CLICKS = 50.0
MIN_MARGINAL_KPI_PER_RUBLE = 1e-12


@dataclass(frozen=True, slots=True)
class ResponseSegment:
    cost_micros: int
    marginal_kpi_per_ruble: float


@dataclass(frozen=True, slots=True)
class PreparedOptimization:
    horizon: Horizon
    future: Horizon | None
    channels: tuple[ChannelBenchmark, ...]
    curves: tuple[tuple[ResponseSegment, ...], ...]
    past_allocations: tuple[Allocation, ...]
    spent_micros: int
    start_clock_hour: int


@dataclass(slots=True)
class _SlopeBlock:
    costs: list[int]
    gain: float

    @property
    def cost(self) -> int:
        return sum(self.costs)

    @property
    def slope(self) -> float:
        return self.gain * 1_000_000 / self.cost


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


def _elapsed_hours(current: Mapping[str, object] | None, horizon: Horizon) -> int:
    elapsed = (
        int(str(current.get("current_hour", horizon.from_hour))) - horizon.from_hour
        if current
        else 0
    )
    return min(max(elapsed, 0), horizon.duration)


def _start_clock_hour(simulation: Mapping[str, object] | None) -> int:
    if simulation is None:
        return 0
    start = datetime.fromisoformat(str(simulation["start_hour"]).replace("Z", "+00:00"))
    return start.astimezone(ZoneInfo(str(simulation["time_zone"]))).hour


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


def _model_buckets(weights: Sequence[float]) -> list[float]:
    """Bound forecast cost while retaining exact hourly steps for short campaigns."""
    if len(weights) <= MODEL_MAX_STEPS:
        return list(weights)
    bucket_size = math.ceil(len(weights) / MODEL_MAX_STEPS)
    return [
        sum(weights[index : index + bucket_size]) for index in range(0, len(weights), bucket_size)
    ]


def _channel_capacity_micros(
    channel: ChannelBenchmark, horizon: Horizon, start_clock_hour: int
) -> int:
    supply = channel.daily_capacity * sum(_hour_weights(channel, horizon, start_clock_hour))
    maximum_cpm = channel.cpm * (1.0 + channel.price_growth)
    units = supply * maximum_cpm / 1_000.0
    return min(MAX_MICROS, max(0, math.ceil(units * 1_000_000)))


def _campaign_forecast(
    channel: ChannelBenchmark,
    observed: ObservedChannel,
    total_budget: float,
    horizon: Horizon,
    start_clock_hour: int,
) -> Forecast:
    """Bucketed future forecast for a channel budget spread by the supply profile.

    Impressions, clicks, conversions and spend are future-only; ``unique_reach`` is the
    cumulative reach at the end of the horizon, including already observed reach.
    """
    weights = _model_buckets(_hour_weights(channel, horizon, start_clock_hour))
    total_weight = sum(weights)
    state = _initial_state(channel, observed)
    if total_weight <= 0:
        return Forecast(0, 0.0, state.reach, 0.0, 0.0)
    steps = [
        _forecast_step(channel, state, total_budget * weight / total_weight, weight)
        for weight in weights
    ]
    total = sum_forecasts(steps)
    return replace(total, unique_reach=state.reach)


def _campaign_kpi(
    channel: ChannelBenchmark,
    observed: ObservedChannel,
    total_budget: float,
    horizon: Horizon,
    start_clock_hour: int,
    metric: str,
) -> float:
    forecast = _campaign_forecast(channel, observed, total_budget, horizon, start_clock_hour)
    return (
        forecast.unique_reach
        if metric == "unique_reach"
        else forecast.clicks
        if metric == "clicks"
        else forecast.conversions
    )


def _curve_points(capacity_micros: int) -> list[int]:
    if capacity_micros <= 0:
        return [0]
    points = [0]
    denominator = CURVE_POINTS * CURVE_POINTS
    for index in range(1, CURVE_POINTS + 1):
        point = math.ceil(capacity_micros * index * index / denominator)
        if point > points[-1]:
            points.append(point)
    if points[-1] != capacity_micros:
        points.append(capacity_micros)
    return points


def _concave_segments(
    points: Sequence[int], values: Sequence[float]
) -> tuple[ResponseSegment, ...]:
    """Project non-negative finite differences onto non-increasing marginal slopes."""
    blocks: list[_SlopeBlock] = []
    for index in range(len(points) - 1):
        cost = points[index + 1] - points[index]
        gain = max(values[index + 1] - values[index], 0.0)
        blocks.append(_SlopeBlock([cost], gain))
        while len(blocks) >= 2 and blocks[-2].slope < blocks[-1].slope:
            right = blocks.pop()
            left = blocks.pop()
            blocks.append(_SlopeBlock(left.costs + right.costs, left.gain + right.gain))

    result: list[ResponseSegment] = []
    for block in blocks:
        result.extend(ResponseSegment(cost, block.slope) for cost in block.costs)
    return tuple(result)


def _response_segments(
    channel: ChannelBenchmark,
    observed: ObservedChannel,
    horizon: Horizon,
    start_clock_hour: int,
    metric: str,
) -> tuple[ResponseSegment, ...]:
    capacity = _channel_capacity_micros(channel, horizon, start_clock_hour)
    points = _curve_points(capacity)
    values = [
        _campaign_kpi(
            channel,
            observed,
            point / 1_000_000,
            horizon,
            start_clock_hour,
            metric,
        )
        for point in points
    ]
    return _concave_segments(points, values)


def _waterfill(
    budget_micros: int,
    curves: Sequence[tuple[ResponseSegment, ...]],
) -> list[int]:
    allocated = [0] * len(curves)
    pointers = [0] * len(curves)
    heap: list[tuple[float, int]] = []
    for index, curve in enumerate(curves):
        if curve:
            heapq.heappush(heap, (-curve[0].marginal_kpi_per_ruble, index))

    remaining = budget_micros
    while remaining > 0 and heap:
        negative_marginal, index = heapq.heappop(heap)
        marginal = -negative_marginal
        if marginal <= MIN_MARGINAL_KPI_PER_RUBLE:
            break
        segment = curves[index][pointers[index]]
        used = min(segment.cost_micros, remaining)
        allocated[index] += used
        remaining -= used
        if used < segment.cost_micros:
            break
        pointers[index] += 1
        if pointers[index] < len(curves[index]):
            next_segment = curves[index][pointers[index]]
            heapq.heappush(heap, (-next_segment.marginal_kpi_per_ruble, index))
    return allocated


def _exact_weighted_allocations(
    horizon: Horizon,
    channels: Sequence[ChannelBenchmark],
    channel_budgets: Sequence[int],
    start_clock_hour: int,
) -> list[Allocation]:
    by_channel: dict[str, list[int]] = {}
    for channel, channel_budget in zip(channels, channel_budgets, strict=True):
        weights = [
            max(0, round(weight * WEIGHT_SCALE))
            for weight in _hour_weights(channel, horizon, start_clock_hour)
        ]
        total_weight = sum(weights)
        if total_weight <= 0:
            by_channel[channel.channel_id] = [0] * horizon.duration
            continue
        quotients = [divmod(channel_budget * weight, total_weight) for weight in weights]
        micros = [quotient for quotient, _ in quotients]
        remainder = channel_budget - sum(micros)
        order = sorted(range(len(weights)), key=lambda index: (-quotients[index][1], index))
        for index in order[:remainder]:
            micros[index] += 1
        by_channel[channel.channel_id] = micros

    return [
        Allocation(
            channel.channel_id,
            hour,
            by_channel[channel.channel_id][hour - horizon.from_hour],
        )
        for hour in range(horizon.from_hour, horizon.to_hour)
        for channel in channels
    ]


def forecast_plan(
    allocations: Sequence[Allocation],
    horizon: Horizon,
    channel_ids: Sequence[str],
    current: Mapping[str, object] | None = None,
    simulation: Mapping[str, object] | None = None,
    history: Sequence[PastCampaign] = (),
) -> PlanForecast | None:
    """Hourly benchmark trajectory for the future caps of a plan.

    Channels are calibrated from the cumulative facts in ``current`` exactly as the
    optimizer does, so the trajectory is what Planner itself believes. Returns ``None``
    when a channel is missing from the public catalog, because no benchmark exists then.
    """
    catalog = load_catalog()
    ordered_ids = sorted(channel_ids)
    if any(channel_id not in catalog for channel_id in ordered_ids):
        return None
    start_clock_hour = _start_clock_hour(simulation)
    elapsed = _elapsed_hours(current, horizon)
    future_from = horizon.from_hour + elapsed
    caps: dict[str, dict[int, int]] = {channel_id: {} for channel_id in ordered_ids}
    for allocation in allocations:
        if allocation.hour >= future_from:
            caps[allocation.channel_id][allocation.hour] = allocation.budget_micros

    hourly: dict[tuple[str, int], Forecast] = {}
    totals: list[Forecast] = []
    for channel_id in ordered_ids:
        observed = _observed(current, channel_id)
        totals.append(observed.as_forecast())
        if future_from >= horizon.to_hour:
            continue
        prior = channel_prior(catalog[channel_id], channel_history(history, channel_id))
        channel = _calibrate(prior, observed, elapsed, start_clock_hour)
        future = Horizon(future_from, horizon.to_hour)
        budgets = [caps[channel_id].get(hour, 0) for hour in range(future_from, horizon.to_hour)]
        steps = forecast_hourly(channel, observed, budgets, future, start_clock_hour)
        for hour, step in zip(range(future_from, horizon.to_hour), steps, strict=True):
            hourly[(channel_id, hour)] = step
        totals.extend(steps)
    return PlanForecast(hourly=hourly, total=sum_forecasts(totals) if totals else ZERO_FORECAST)


def forecast_allocations(
    allocations: tuple[Allocation, ...],
    horizon: Horizon,
    channel_ids: list[str],
    simulation: Mapping[str, object] | None = None,
    history: Sequence[PastCampaign] = (),
) -> Forecast:
    """Forecast an initial plan from the public catalog sharpened by campaign history."""
    forecast = forecast_plan(allocations, horizon, channel_ids, None, simulation, history)
    if forecast is None:
        raise ValueError("every channel must exist in the public catalog")
    return forecast.total


def useful_budget_capacity_micros(
    horizon: Horizon,
    channel_ids: list[str],
    simulation: Mapping[str, object] | None = None,
) -> int:
    catalog = load_catalog()
    start_clock_hour = _start_clock_hour(simulation)
    return min(
        MAX_MICROS,
        sum(
            _channel_capacity_micros(catalog[channel_id], horizon, start_clock_hour)
            for channel_id in channel_ids
        ),
    )


def allocate_optimized(
    budget_micros: int,
    horizon: Horizon,
    channel_ids: list[str],
    metric: str,
    current: Mapping[str, object] | None = None,
    simulation: Mapping[str, object] | None = None,
    history: Sequence[PastCampaign] = (),
) -> tuple[Allocation, ...]:
    prepared = prepare_optimized(horizon, channel_ids, metric, current, simulation, history)
    return allocate_prepared(prepared, budget_micros)


def prepare_optimized(
    horizon: Horizon,
    channel_ids: list[str],
    metric: str,
    current: Mapping[str, object] | None = None,
    simulation: Mapping[str, object] | None = None,
    history: Sequence[PastCampaign] = (),
) -> PreparedOptimization:
    catalog = load_catalog()
    ordered_ids = sorted(channel_ids)
    elapsed = _elapsed_hours(current, horizon)
    start_clock_hour = _start_clock_hour(simulation)
    observations = [_observed(current, channel_id) for channel_id in ordered_ids]
    channels = [
        _calibrate(
            channel_prior(catalog[channel_id], channel_history(history, channel_id)),
            observations[index],
            elapsed,
            start_clock_hour,
        )
        for index, channel_id in enumerate(ordered_ids)
    ]

    past_allocations: list[Allocation] = []
    for hour_offset in range(elapsed):
        for index, channel_id in enumerate(ordered_ids):
            quotient, remainder = divmod(observations[index].spent_micros, max(elapsed, 1))
            past_allocations.append(
                Allocation(
                    channel_id,
                    horizon.from_hour + hour_offset,
                    quotient + (hour_offset < remainder),
                )
            )

    spent_micros = sum(item.spent_micros for item in observations)
    future_from = horizon.from_hour + elapsed
    future = Horizon(future_from, horizon.to_hour) if future_from < horizon.to_hour else None
    curves = (
        tuple(
            _response_segments(
                channel,
                observations[index],
                future,
                start_clock_hour,
                metric,
            )
            for index, channel in enumerate(channels)
        )
        if future is not None
        else ()
    )
    return PreparedOptimization(
        horizon=horizon,
        future=future,
        channels=tuple(channels),
        curves=curves,
        past_allocations=tuple(past_allocations),
        spent_micros=spent_micros,
        start_clock_hour=start_clock_hour,
    )


def allocate_prepared(prepared: PreparedOptimization, budget_micros: int) -> tuple[Allocation, ...]:
    allocations = list(prepared.past_allocations)
    remaining_micros = max(budget_micros - prepared.spent_micros, 0)
    future = prepared.future
    if future is not None:
        channel_budgets = _waterfill(remaining_micros, prepared.curves)
        allocations.extend(
            _exact_weighted_allocations(
                future,
                prepared.channels,
                channel_budgets,
                prepared.start_clock_hour,
            )
        )

    return tuple(allocations)
