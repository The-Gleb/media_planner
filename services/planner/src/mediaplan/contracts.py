"""Контракты данных между модулями: бриф, каталог, медиаплан, почасовой пакет факта."""

import dataclasses
import typing

import numpy as np
import numpy.typing as npt


Objective = typing.Literal["clicks", "conversions"]
ChannelKind = typing.Literal["social", "programmatic", "marketplace", "sms"]

HOURS_PER_DAY: typing.Final = 24


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class Brief:
    budget_rub: float
    horizon_days: int
    objective: Objective

    @property
    def horizon_hours(self) -> int:
        return self.horizon_days * HOURS_PER_DAY


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class SaturationParams:
    """Публичные (середины диапазонов) правила насыщения аудитории: рост цены, спад охвата, усталость CTR."""

    start_threshold: float
    price_growth: float
    reach_decay: float
    frequency_reach_decay: float
    ctr_fatigue: float
    frequency_fatigue: float


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ChannelCatalogEntry:
    """Публичная витрина канала: бенчмарки и кривая, доступные планировщику."""

    channel_id: str
    kind: ChannelKind
    cpm_rub: float
    ctr: float
    cr: float
    daily_capacity: float
    """Дневной спрос (запросов в день) — потолок показов за сутки."""
    audience_capacity: float
    """Размер аудитории канала — потолок уникального охвата за кампанию."""
    saturation: SaturationParams
    price_growth: float
    delivery_rate: float


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class Catalog:
    channels: tuple[ChannelCatalogEntry, ...]
    hourly_profile: npt.NDArray[np.float64]
    """Публичный суточный профиль активности аудитории, форма [24], сумма 1."""

    @property
    def channel_ids(self) -> tuple[str, ...]:
        return tuple(channel.channel_id for channel in self.channels)


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ChannelForecast:
    """Прогноз по каналу на всю кампанию."""

    channel_id: str
    budget_rub: float
    impressions: float
    clicks: float
    conversions: float

    @property
    def cpm_rub(self) -> float:
        return 1000.0 * self.budget_rub / self.impressions if self.impressions > 0 else 0.0

    @property
    def cpc_rub(self) -> float:
        return self.budget_rub / self.clicks if self.clicks > 0 else 0.0

    @property
    def cpa_rub(self) -> float:
        return self.budget_rub / self.conversions if self.conversions > 0 else 0.0

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions > 0 else 0.0

    @property
    def cr(self) -> float:
        return self.conversions / self.clicks if self.clicks > 0 else 0.0


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class MediaPlan:
    brief: Brief
    channel_ids: tuple[str, ...]
    channel_forecasts: tuple[ChannelForecast, ...]
    hourly_budget: npt.NDArray[np.float64]
    """Плановый расход, форма [часы, каналы]."""
    cumulative_spend: npt.NDArray[np.float64]
    """Плановая накопительная траектория расходов, форма [часы]."""
    cumulative_kpi: npt.NDArray[np.float64]
    """Плановая накопительная траектория целевого KPI, форма [часы]."""

    @property
    def total_budget_rub(self) -> float:
        return float(self.hourly_budget.sum())


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class HourlyPacket:
    """Агрегированная статистика канала за один час кампании."""

    channel_id: str
    hour: int
    requests: int
    impressions: int
    unique_reach: int
    clicks: int
    conversions: int
    spend_rub: float
    ecpm_rub: float


class HourlySimulator(typing.Protocol):
    """Источник факта: по целевому расходу часа возвращает пакет по каждому каналу в порядке каталога."""

    def simulate_hour(self, hour: int, spend_targets: npt.NDArray[np.float64]) -> tuple[HourlyPacket, ...]: ...
