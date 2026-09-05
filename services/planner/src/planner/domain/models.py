from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class KPI(StrEnum):
    UNIQUE_REACH = "unique_reach"
    CLICKS = "clicks"
    CONVERSIONS = "conversions"


class PlanType(StrEnum):
    FIXED_BUDGET = "fixed_budget"
    TARGET_KPI = "target_kpi"


class Strategy(StrEnum):
    UNIFORM = "uniform"
    OPTIMIZED = "optimized"


@dataclass(frozen=True, slots=True)
class Horizon:
    from_hour: int
    to_hour: int

    @property
    def duration(self) -> int:
        return self.to_hour - self.from_hour


@dataclass(frozen=True, slots=True)
class SimulationContext:
    simulation_id: str
    world_seed: str
    campaign_seed: str
    start_hour: datetime
    time_zone: str
    currency: str
    world_config_digest: str


@dataclass(frozen=True, slots=True)
class ChannelState:
    spent_micros: int
    impressions: int
    unique_reach: int
    clicks: int
    conversions: int


@dataclass(frozen=True, slots=True)
class CampaignState:
    current_hour: int
    state_revision: int
    channels: tuple[tuple[str, ChannelState], ...]
    spent_micros: int
    unique_reach: int
    clicks: int
    conversions: int


@dataclass(frozen=True, slots=True)
class Allocation:
    channel_id: str
    hour: int
    budget_micros: int


@dataclass(frozen=True, slots=True)
class Forecast:
    """Benchmark expectation for one allocation slot or for a whole campaign.

    ``unique_reach`` counts users first reached in the covered period, matching the
    Simulator observation semantics, so hourly values can be summed into a trajectory.
    """

    spend_micros: int
    impressions: float
    unique_reach: float
    clicks: float
    conversions: float


ZERO_FORECAST = Forecast(0, 0.0, 0.0, 0.0, 0.0)


def sum_forecasts(items: list[Forecast]) -> Forecast:
    return Forecast(
        spend_micros=sum(item.spend_micros for item in items),
        impressions=sum(item.impressions for item in items),
        unique_reach=sum(item.unique_reach for item in items),
        clicks=sum(item.clicks for item in items),
        conversions=sum(item.conversions for item in items),
    )


@dataclass(frozen=True, slots=True)
class PlanForecast:
    """Hourly benchmark trajectory of a plan plus the projected campaign total.

    ``hourly`` is keyed by ``(channel_id, hour)`` and covers only hours that are still
    ahead of the observed campaign state; already committed hours carry no expectation.
    ``total`` adds the observed cumulative facts to the future forecast, so at revision
    zero it is the approved plan target and later it is the projected end-of-campaign
    outcome.
    """

    hourly: Mapping[tuple[str, int], Forecast]
    total: Forecast


@dataclass(frozen=True, slots=True)
class MediaPlan:
    plan_id: str
    horizon: Horizon
    allocations: tuple[Allocation, ...]
    unallocated_budget_micros: int
    forecast: PlanForecast | None = None


@dataclass(frozen=True, slots=True)
class ApprovedPlan:
    """Target that adaptive replanning tracks: the approved KPI total and channel budgets.

    ``channel_budgets_micros`` are the approved whole-campaign budgets per channel; the future
    approved mix is what remains of them after actual spend.
    """

    kpi_target: float
    channel_budgets_micros: Mapping[str, int]
