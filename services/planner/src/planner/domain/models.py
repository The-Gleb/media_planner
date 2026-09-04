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
class MediaPlan:
    plan_id: str
    horizon: Horizon
    allocations: tuple[Allocation, ...]
