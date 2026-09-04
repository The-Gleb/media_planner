"""Планировщик задачи A: фиксированный бюджет и горизонт, максимизируем клики или конверсии.

Кривая отклика канала считается ожидаемой репликой динамики рынка по публичным серединам диапазонов:
день за днём показы упираются в дневной спрос, а по мере выкупа аудитории растёт цена, падает доля новых
пользователей и устаёт CTR. Это даёт «точечную кривую дневной бюджет → KPI за кампанию» без единого скрытого
параметра мира. Распределение — water-filling по ломтикам этой кривой: следующий ломтик бюджета уходит в канал
с наибольшим приростом KPI на рубль.
"""

import dataclasses
import typing

import numpy as np
import numpy.typing as npt

from mediaplan.contracts import Brief, Catalog, ChannelForecast, MediaPlan, Objective


DEFAULT_GRID_SIZE: typing.Final = 200
SATURATION_EPSILON: typing.Final = 1e-9
FloatArray = npt.NDArray[np.float64]


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ChannelDailyForecast:
    """Ожидаемые показатели канала по дням при фиксированном дневном бюджете, форма [дни]."""

    impressions: FloatArray
    clicks: FloatArray
    conversions: FloatArray
    spend: FloatArray


def _catalog_arrays(catalog: Catalog) -> dict[str, FloatArray]:
    def column(attribute: str) -> FloatArray:
        return np.array([getattr(channel, attribute) for channel in catalog.channels], dtype=np.float64)

    def saturation_column(attribute: str) -> FloatArray:
        return np.array([getattr(channel.saturation, attribute) for channel in catalog.channels], dtype=np.float64)

    return {
        "cpm": column("cpm_rub"),
        "ctr": column("ctr") * column("delivery_rate"),
        "cr": column("cr"),
        "requests": column("daily_capacity"),
        "audience": column("audience_capacity"),
        "threshold": saturation_column("start_threshold"),
        "price_growth": saturation_column("price_growth"),
        "reach_decay": saturation_column("reach_decay"),
        "frequency_reach_decay": saturation_column("frequency_reach_decay"),
        "ctr_fatigue": saturation_column("ctr_fatigue"),
        "frequency_fatigue": saturation_column("frequency_fatigue"),
    }


def simulate_expected_days(daily_budget: FloatArray, catalog: Catalog, horizon_days: int) -> ChannelDailyForecast:
    """Детерминированная ожидаемая динамика по дням. `daily_budget` — форма [..., каналы], любое число ведущих осей."""
    params = _catalog_arrays(catalog)
    budget = np.asarray(daily_budget, dtype=np.float64)
    reach = np.zeros_like(budget)
    impressions_total = np.zeros_like(budget)
    days_impressions, days_clicks, days_conversions, days_spend = [], [], [], []
    for _ in range(horizon_days):
        saturation = np.clip(reach / params["audience"], 0.0, 1.0)
        frequency = np.where(reach > 0, np.maximum(1.0, impressions_total / np.maximum(reach, 1.0)), 1.0)
        depth = np.clip((saturation - params["threshold"]) / (1.0 - params["threshold"]), 0.0, 1.0)
        price_factor = 1.0 + params["price_growth"] * depth**2
        fatigue = np.exp(
            -params["ctr_fatigue"] * depth - params["frequency_fatigue"] * np.maximum(frequency - 1.0, 0.0)
        )
        new_user = np.clip(
            (1.0 - depth) ** params["reach_decay"]
            * np.exp(-params["frequency_reach_decay"] * np.maximum(frequency - 1.0, 0.0)),
            0.0,
            1.0,
        )
        effective_cpm = params["cpm"] * price_factor
        impressions = np.minimum(params["requests"], budget * 1000.0 / effective_cpm)
        spend = impressions * effective_cpm / 1000.0
        clicks = impressions * params["ctr"] * fatigue
        reach = np.minimum(reach + impressions * new_user, params["audience"])
        impressions_total = impressions_total + impressions
        days_impressions.append(impressions)
        days_clicks.append(clicks)
        days_conversions.append(clicks * params["cr"])
        days_spend.append(spend)
    return ChannelDailyForecast(
        impressions=_stack_days(days_impressions),
        clicks=_stack_days(days_clicks),
        conversions=_stack_days(days_conversions),
        spend=_stack_days(days_spend),
    )


def _stack_days(items: list[FloatArray]) -> FloatArray:
    """Ось дней ставится перед осью каналов."""
    return np.stack(items, axis=-2)


def campaign_kpi_curves(
    catalog: Catalog,
    horizon_days: int,
    objective: Objective,
    daily_budget_max: float,
    grid_size: int = DEFAULT_GRID_SIZE,
) -> tuple[FloatArray, FloatArray]:
    """Сетка дневных бюджетов [G] и KPI за кампанию на ней [G, каналы]."""
    channel_count = len(catalog.channels)
    budget_grid = np.linspace(0.0, daily_budget_max, grid_size + 1)
    budget_matrix = np.repeat(budget_grid[:, None], channel_count, axis=1)
    forecast = simulate_expected_days(budget_matrix, catalog, horizon_days)
    kpi_days = forecast.conversions if objective == "conversions" else forecast.clicks
    return budget_grid, kpi_days.sum(axis=-2)


def allocate_daily_budget(
    daily_budget_total: float,
    catalog: Catalog,
    objective: Objective,
    horizon_days: int,
    grid_size: int = DEFAULT_GRID_SIZE,
) -> FloatArray:
    """Water-filling по ломтикам кривых: каждый ломтик бюджета — каналу с наибольшим приростом KPI."""
    channel_count = len(catalog.channels)
    allocation = np.zeros(channel_count, dtype=np.float64)
    if daily_budget_total <= 0:
        return allocation
    budget_grid, kpi_curves = campaign_kpi_curves(catalog, horizon_days, objective, daily_budget_total, grid_size)
    slice_size = float(budget_grid[1] - budget_grid[0])
    marginal = np.diff(kpi_curves, axis=0)
    pointers = np.zeros(channel_count, dtype=np.int64)
    for _ in range(grid_size):
        candidates = np.array(
            [marginal[pointers[c], c] if pointers[c] < grid_size else -np.inf for c in range(channel_count)]
        )
        best_channel = int(np.argmax(candidates))
        if candidates[best_channel] <= SATURATION_EPSILON:
            break
        allocation[best_channel] += slice_size
        pointers[best_channel] += 1
    return allocation


def build_media_plan(brief: Brief, catalog: Catalog, grid_size: int = DEFAULT_GRID_SIZE) -> MediaPlan:
    daily_allocation = allocate_daily_budget(
        brief.budget_rub / brief.horizon_days, catalog, brief.objective, brief.horizon_days, grid_size
    )
    forecast = simulate_expected_days(daily_allocation, catalog, brief.horizon_days)

    channel_forecasts = tuple(
        ChannelForecast(
            channel_id=channel.channel_id,
            budget_rub=float(forecast.spend[:, index].sum()),
            impressions=float(forecast.impressions[:, index].sum()),
            clicks=float(forecast.clicks[:, index].sum()),
            conversions=float(forecast.conversions[:, index].sum()),
        )
        for index, channel in enumerate(catalog.channels)
    )

    hourly_share = np.tile(catalog.hourly_profile, brief.horizon_days)
    hourly_budget = np.outer(hourly_share, daily_allocation)
    kpi_days = forecast.conversions if brief.objective == "conversions" else forecast.clicks
    hourly_kpi = (kpi_days.sum(axis=1)[:, None] * catalog.hourly_profile[None, :]).reshape(-1)
    hourly_spend = (forecast.spend.sum(axis=1)[:, None] * catalog.hourly_profile[None, :]).reshape(-1)
    return MediaPlan(
        brief=brief,
        channel_ids=catalog.channel_ids,
        channel_forecasts=channel_forecasts,
        hourly_budget=hourly_budget,
        cumulative_spend=np.cumsum(hourly_spend),
        cumulative_kpi=np.cumsum(hourly_kpi),
    )
