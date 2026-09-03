"""Сервис исполнения: ведёт кампанию по утверждённому плану час за часом.

Две стратегии:
- frozen: распределение заморожено, каждый час тратим ровно по плану. Это бейзлайн, который надо обыграть.
- adaptive: трекер плана. Расход всегда ведём к плановой траектории (множитель темпа на остаток бюджета).
  Если накопленный KPI отстал от плана, калибруем каталог по факту и заново раскидываем остаток бюджета
  на оставшиеся часы, чтобы догнать. Если идём по плану или выше — держим утверждённое распределение,
  а не гонимся за лишним KPI: цель сервиса — минимальное отклонение от плана, а не максимум.
"""

import dataclasses
import math
import typing

import numpy as np
import numpy.typing as npt

from mediaplan import planner, response
from mediaplan.contracts import HOURS_PER_DAY, Catalog, ChannelCatalogEntry, HourlyPacket, HourlySimulator, MediaPlan


Strategy = typing.Literal["frozen", "adaptive"]

CALIBRATION_SMOOTHING: typing.Final = 0.2
"""Сглаживание отношения наблюдаемого eCPM к предсказанному каталогом (eCPM почти не шумит)."""
CALIBRATION_WINDOW_HOURS: typing.Final = 72
"""Окно агрегирования кликов и конверсий для калибровки CTR и CR."""
PRIOR_CLICKS: typing.Final = 50.0
PRIOR_CONVERSIONS: typing.Final = 20.0
"""Псевдонаблюдения, стягивающие оценки CTR и CR к каталогу, пока фактов мало."""
REPLAN_GRID_SIZE: typing.Final = 100
REPLAN_INTERVAL_HOURS: typing.Final = 6
"""Переоптимизация остатка — раз в шесть часов: чаще нет смысла, калибровка агрегирует окно в 72 часа."""
KPI_LAG_TOLERANCE: typing.Final = 0.02
"""Отставание накопленного KPI от плана, с которого включается переоптимизация."""
EXPLORATION_SHARE: typing.Final = 0.1
"""Минимальная доля планового часового расхода, которую канал плана получает всегда, чтобы не выпадать из наблюдений."""


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class CampaignResult:
    strategy: Strategy
    packets: tuple[HourlyPacket, ...]
    cumulative_spend: npt.NDArray[np.float64]
    cumulative_kpi: npt.NDArray[np.float64]
    hourly_budget: npt.NDArray[np.float64]
    """Фактически поставленные часовые цели, форма [часы, каналы]."""


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True)
class CatalogCalibration:
    """Отношения «факт / прогноз каталога» по CTR, CR и eCPM для каждого канала.

    CTR и CR считаются по суммам кликов и конверсий за скользящее окно с усадкой к каталогу
    через псевдонаблюдения: сырые часовые отношения слишком шумные (единицы конверсий в час),
    а жадный переоптимизатор на шуме выбирает «везучий» канал и пересаживает на него весь бюджет.
    """

    channel_count: int
    window_hours: int = CALIBRATION_WINDOW_HOURS
    ecpm_ratio: npt.NDArray[np.float64] = dataclasses.field(init=False)
    _impressions: npt.NDArray[np.float64] = dataclasses.field(init=False)
    _clicks: npt.NDArray[np.float64] = dataclasses.field(init=False)
    _conversions: npt.NDArray[np.float64] = dataclasses.field(init=False)
    _cursor: int = dataclasses.field(init=False, default=0)

    def __post_init__(self) -> None:
        self.ecpm_ratio = np.ones(self.channel_count, dtype=np.float64)
        window_shape = (self.window_hours, self.channel_count)
        self._impressions = np.zeros(window_shape, dtype=np.float64)
        self._clicks = np.zeros(window_shape, dtype=np.float64)
        self._conversions = np.zeros(window_shape, dtype=np.float64)

    def update(
        self, channel_index: int, channel: ChannelCatalogEntry, hour: int, packet: HourlyPacket, catalog: Catalog
    ) -> None:
        window_row = hour % self.window_hours
        if window_row != self._cursor:
            self._cursor = window_row
            self._impressions[window_row] = 0.0
            self._clicks[window_row] = 0.0
            self._conversions[window_row] = 0.0
        self._impressions[window_row, channel_index] = packet.impressions * channel.delivery_rate
        self._clicks[window_row, channel_index] = packet.clicks
        self._conversions[window_row, channel_index] = packet.conversions

        if packet.impressions == 0 or packet.spend_rub <= 0:
            return
        hourly_capacity = channel.daily_capacity * catalog.hourly_profile[hour % HOURS_PER_DAY]
        expected_impressions = response.compute_impressions(
            packet.spend_rub, channel.cpm_rub, hourly_capacity, channel.price_growth
        )
        if expected_impressions <= 0:
            return
        expected_ecpm = 1000.0 * packet.spend_rub / expected_impressions
        self.ecpm_ratio[channel_index] += CALIBRATION_SMOOTHING * (
            packet.ecpm_rub / expected_ecpm - self.ecpm_ratio[channel_index]
        )

    def apply(self, catalog: Catalog) -> Catalog:
        delivered = self._impressions.sum(axis=0)
        clicks = self._clicks.sum(axis=0)
        conversions = self._conversions.sum(axis=0)
        catalog_ctr = np.array([channel.ctr for channel in catalog.channels], dtype=np.float64)
        catalog_cr = np.array([channel.cr for channel in catalog.channels], dtype=np.float64)
        ctr_ratio = (clicks + PRIOR_CLICKS) / (delivered * catalog_ctr + PRIOR_CLICKS)
        cr_ratio = (conversions + PRIOR_CONVERSIONS) / (clicks * catalog_cr + PRIOR_CONVERSIONS)
        return Catalog(
            channels=tuple(
                dataclasses.replace(
                    channel,
                    ctr=min(channel.ctr * float(ctr_ratio[channel_index]), 0.99),
                    cr=min(channel.cr * float(cr_ratio[channel_index]), 0.99),
                    cpm_rub=channel.cpm_rub * float(self.ecpm_ratio[channel_index]),
                )
                for channel_index, channel in enumerate(catalog.channels)
            ),
            hourly_profile=catalog.hourly_profile,
        )


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class CampaignProgress:
    hour: int
    spent_total: float
    kpi_total: float


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True)
class ReplanState:
    daily_allocation: npt.NDArray[np.float64] | None = None


def _choose_adaptive_targets(
    plan: MediaPlan,
    catalog: Catalog,
    calibration: CatalogCalibration,
    progress: CampaignProgress,
    replan_state: ReplanState,
) -> npt.NDArray[np.float64]:
    hour = progress.hour
    remaining_budget = max(plan.total_budget_rub - progress.spent_total, 0.0)
    planned_kpi_so_far = float(plan.cumulative_kpi[hour - 1]) if hour > 0 else 0.0
    is_behind_plan = progress.kpi_total < planned_kpi_so_far * (1.0 - KPI_LAG_TOLERANCE)

    if not is_behind_plan:
        planned_spend_so_far = float(plan.cumulative_spend[hour - 1]) if hour > 0 else 0.0
        planned_remaining_spend = plan.total_budget_rub - planned_spend_so_far
        pace_multiplier = remaining_budget / planned_remaining_spend if planned_remaining_spend > 0 else 1.0
        return np.asarray(plan.hourly_budget[hour] * pace_multiplier, dtype=np.float64)

    remaining_hours = plan.brief.horizon_hours - hour
    remaining_days = remaining_hours / HOURS_PER_DAY
    exploration_floor = plan.hourly_budget[hour] * EXPLORATION_SHARE
    if hour % REPLAN_INTERVAL_HOURS == 0 or replan_state.daily_allocation is None:
        replan_state.daily_allocation = planner.allocate_daily_budget(
            max(remaining_budget / remaining_days - float(exploration_floor.sum()) * HOURS_PER_DAY, 0.0),
            calibration.apply(catalog),
            plan.brief.objective,
            max(1, math.ceil(remaining_days)),
            REPLAN_GRID_SIZE,
        )
    reoptimized = replan_state.daily_allocation * catalog.hourly_profile[hour % HOURS_PER_DAY]
    return np.asarray(reoptimized + exploration_floor, dtype=np.float64)


def run_campaign(plan: MediaPlan, catalog: Catalog, simulator: HourlySimulator, strategy: Strategy) -> CampaignResult:
    horizon_hours = plan.brief.horizon_hours
    channel_count = len(catalog.channels)
    objective = plan.brief.objective

    packets: list[HourlyPacket] = []
    cumulative_spend = np.zeros(horizon_hours, dtype=np.float64)
    cumulative_kpi = np.zeros(horizon_hours, dtype=np.float64)
    hourly_targets = np.zeros((horizon_hours, channel_count), dtype=np.float64)
    calibration = CatalogCalibration(channel_count=channel_count)
    replan_state = ReplanState()

    spent_total = 0.0
    kpi_total = 0.0
    for hour in range(horizon_hours):
        if strategy == "frozen":
            spend_targets = plan.hourly_budget[hour]
        else:
            progress = CampaignProgress(hour=hour, spent_total=spent_total, kpi_total=kpi_total)
            spend_targets = _choose_adaptive_targets(plan, catalog, calibration, progress, replan_state)
        hourly_targets[hour] = spend_targets

        hour_packets = simulator.simulate_hour(hour, spend_targets)
        packets.extend(hour_packets)
        for channel_index, packet in enumerate(hour_packets):
            spent_total += packet.spend_rub
            kpi_total += packet.conversions if objective == "conversions" else packet.clicks
            calibration.update(channel_index, catalog.channels[channel_index], hour, packet, catalog)
        cumulative_spend[hour] = spent_total
        cumulative_kpi[hour] = kpi_total

    return CampaignResult(
        strategy=strategy,
        packets=tuple(packets),
        cumulative_spend=cumulative_spend,
        cumulative_kpi=cumulative_kpi,
        hourly_budget=hourly_targets,
    )
