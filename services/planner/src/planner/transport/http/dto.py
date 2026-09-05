from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    model_validator,
)

from planner.domain.models import KPI, Strategy
from planner.domain.values import count_to_int, money_to_micros, validate_int64_text


def _valid_money(value: str) -> str:
    money_to_micros(value)
    return value


def _valid_count(value: str) -> str:
    count_to_int(value)
    return value


def _valid_positive_count(value: str) -> str:
    count_to_int(value, positive=True)
    return value


def _valid_int64(value: str) -> str:
    validate_int64_text(value)
    return value


MoneyText = Annotated[
    str,
    StringConstraints(pattern=r"^(0|[1-9][0-9]*)(?:\.[0-9]{1,6})?$"),
    AfterValidator(_valid_money),
]
CountText = Annotated[
    str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)$"), AfterValidator(_valid_count)
]
PositiveCountText = Annotated[
    str, StringConstraints(pattern=r"^[1-9][0-9]*$"), AfterValidator(_valid_positive_count)
]
Int64Text = Annotated[
    str,
    StringConstraints(pattern=r"^-?(0|[1-9][0-9]*)$"),
    AfterValidator(_valid_int64),
]
DecimalText = Annotated[
    str,
    StringConstraints(pattern=r"^(0|[1-9][0-9]*)(?:\.[0-9]{1,6})?$"),
]
ChannelID = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$", min_length=1, max_length=64)
]
SimulationID = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", max_length=128),
]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$", min_length=3, max_length=3)]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$", min_length=64, max_length=64)]
PlanID = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$", min_length=64, max_length=64)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HorizonDTO(StrictModel):
    from_hour: StrictInt = Field(ge=0, le=2159)
    to_hour: StrictInt = Field(ge=1, le=2160)

    @property
    def duration(self) -> int:
        return self.to_hour - self.from_hour

    @model_validator(mode="after")
    def valid_range(self) -> HorizonDTO:
        if self.to_hour <= self.from_hour:
            raise ValueError("to_hour must be greater than from_hour")
        return self


class SimulationContextDTO(StrictModel):
    simulation_id: SimulationID
    world_seed: Int64Text
    campaign_seed: Int64Text
    start_hour: AwareDatetime
    time_zone: str = Field(min_length=1, max_length=64)
    currency: Currency
    world_config_digest: Digest

    @model_validator(mode="after")
    def validate_context(self) -> SimulationContextDTO:
        if any((self.start_hour.minute, self.start_hour.second, self.start_hour.microsecond)):
            raise ValueError("start_hour must be aligned to the start of an hour")
        try:
            ZoneInfo(self.time_zone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("time_zone must be a recognized IANA time zone") from exc
        return self


class MarketForecastDTO(StrictModel):
    status: Literal["unavailable"]


class ChannelStateDTO(StrictModel):
    spent: MoneyText
    requests: CountText = "0"
    impressions: CountText
    unique_reach: CountText
    clicks: CountText
    conversions: CountText


class RecentHourDTO(StrictModel):
    """Facts of one committed campaign hour per channel; feeds the windowed calibration."""

    hour: StrictInt = Field(ge=0, le=2159)
    channels: dict[ChannelID, ChannelStateDTO] = Field(min_length=1, max_length=20)


class CampaignStateDTO(StrictModel):
    current_hour: StrictInt = Field(ge=0, le=2160)
    state_revision: StrictInt = Field(ge=0, le=2160)
    last_step_id: UUID | None
    last_observed_at: AwareDatetime | None
    spent: MoneyText
    unique_reach: CountText
    clicks: CountText
    conversions: CountText
    channels: dict[ChannelID, ChannelStateDTO] = Field(min_length=1, max_length=20)
    recent_hours: list[RecentHourDTO] = Field(default_factory=list, max_length=168)

    @model_validator(mode="after")
    def validate_snapshot(self) -> CampaignStateDTO:
        has_step = self.last_step_id is not None
        has_observation = self.last_observed_at is not None
        if has_step != has_observation:
            raise ValueError("last_step_id and last_observed_at must both be null or both be set")
        if self.state_revision == 0 and has_step:
            raise ValueError("zero revision cannot have last-step metadata")
        if self.state_revision > 0 and not has_step:
            raise ValueError("non-zero revision requires last-step metadata")
        if self.state_revision == 0:
            all_values = [
                money_to_micros(self.spent),
                count_to_int(self.unique_reach),
                count_to_int(self.clicks),
                count_to_int(self.conversions),
            ]
            for channel in self.channels.values():
                all_values.extend(
                    [
                        money_to_micros(channel.spent),
                        count_to_int(channel.requests),
                        count_to_int(channel.impressions),
                        count_to_int(channel.unique_reach),
                        count_to_int(channel.clicks),
                        count_to_int(channel.conversions),
                    ]
                )
            if any(all_values):
                raise ValueError("revision zero requires zero campaign and channel facts")
        if self.last_observed_at is not None and any(
            (
                self.last_observed_at.minute,
                self.last_observed_at.second,
                self.last_observed_at.microsecond,
            )
        ):
            raise ValueError("last_observed_at must be aligned to the start of an hour")

        hours = [item.hour for item in self.recent_hours]
        if hours != sorted(hours) or len(set(hours)) != len(hours):
            raise ValueError("recent_hours must be strictly ascending")
        if hours and hours[-1] != self.current_hour - 1:
            raise ValueError("recent_hours must end with the latest committed hour")
        for item in self.recent_hours:
            if set(item.channels) - set(self.channels):
                raise ValueError("recent_hours may only mention campaign channels")
        channel_values = tuple(self.channels.values())
        if money_to_micros(self.spent) != sum(
            money_to_micros(item.spent) for item in channel_values
        ):
            raise ValueError("campaign spent must equal the sum of channel spent")
        for field in ("unique_reach", "clicks", "conversions"):
            total = count_to_int(getattr(self, field))
            channel_total = sum(count_to_int(getattr(item, field)) for item in channel_values)
            if total != channel_total:
                raise ValueError(f"campaign {field} must equal the sum of channel {field}")
        return self


class TargetKPIDTO(StrictModel):
    metric: KPI
    value: PositiveCountText


class HourBinDTO(StrictModel):
    """Facts of one channel over the past-campaign hours sharing this hour of local day."""

    hour: StrictInt = Field(ge=0, le=23)
    hours: StrictInt = Field(ge=0, le=90)
    requests: CountText
    impressions: CountText
    unique_reach: CountText
    clicks: CountText
    conversions: CountText
    spent: MoneyText

    @model_validator(mode="after")
    def validate_funnel(self) -> HourBinDTO:
        impressions = count_to_int(self.impressions)
        clicks = count_to_int(self.clicks)
        if clicks > impressions or count_to_int(self.conversions) > clicks:
            raise ValueError(
                "clicks cannot exceed impressions and conversions cannot exceed clicks"
            )
        if count_to_int(self.unique_reach) > impressions:
            raise ValueError("unique reach cannot exceed impressions")
        if self.hours == 0 and any(
            (
                count_to_int(self.requests),
                impressions,
                money_to_micros(self.spent),
            )
        ):
            raise ValueError("a bin without observed hours cannot carry facts")
        return self


class PastCampaignChannelDTO(StrictModel):
    bins: list[HourBinDTO] = Field(min_length=24, max_length=24)

    @model_validator(mode="after")
    def validate_bins(self) -> PastCampaignChannelDTO:
        if [item.hour for item in self.bins] != list(range(24)):
            raise ValueError("bins must cover hours 0..23 exactly once in order")
        return self


class PastCampaignDTO(StrictModel):
    """Observable outcome of one finished campaign on the same market, oldest first."""

    horizon_hours: StrictInt = Field(ge=1, le=2160)
    channels: dict[ChannelID, PastCampaignChannelDTO] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_hours(self) -> PastCampaignDTO:
        for channel_id, channel in self.channels.items():
            if sum(item.hours for item in channel.bins) > self.horizon_hours:
                raise ValueError(f"channel {channel_id} observed more hours than the horizon")
        return self


class RequestBase(StrictModel):
    request_id: UUID
    strategy: Strategy
    horizon: HorizonDTO
    channels: list[ChannelID] = Field(
        min_length=1, max_length=20, json_schema_extra={"uniqueItems": True}
    )
    simulation: SimulationContextDTO
    market: MarketForecastDTO
    current: CampaignStateDTO
    history: list[PastCampaignDTO] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_relationships(self) -> RequestBase:
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("channels must be unique")
        if set(self.current.channels) != set(self.channels):
            raise ValueError("current channel keys must exactly match channels")
        if not self.horizon.from_hour <= self.current.current_hour <= self.horizon.to_hour:
            raise ValueError("current_hour must be within the horizon")
        expected_revision = self.current.current_hour - self.horizon.from_hour
        if self.current.state_revision != expected_revision:
            raise ValueError("state_revision must equal current_hour minus from_hour")
        slots = self.horizon.duration * len(self.channels)
        if slots > 43_200:
            raise ValueError("plan exceeds the maximum of 43200 allocations")
        if self.current.last_observed_at is not None:
            expected_observed_at = self.simulation.start_hour + timedelta(
                hours=self.current.current_hour - 1
            )
            if self.current.last_observed_at != expected_observed_at:
                raise ValueError(
                    "last_observed_at must identify the latest committed campaign hour"
                )
        return self


class ApprovedPlanDTO(StrictModel):
    """Approved plan that adaptive replanning keeps the campaign on."""

    kpi_target: PositiveCountText
    channel_budgets: dict[ChannelID, MoneyText] = Field(min_length=1, max_length=20)


class FixedBudgetPlanRequestDTO(RequestBase):
    type: Literal["fixed_budget"]
    budget: MoneyText
    optimize: KPI
    target: None = None
    approved: ApprovedPlanDTO | None = None

    @model_validator(mode="after")
    def validate_budget_balance(self) -> FixedBudgetPlanRequestDTO:
        if money_to_micros(self.current.spent) > money_to_micros(self.budget):
            raise ValueError("campaign spent cannot exceed the approved budget")
        if self.approved is not None:
            if set(self.approved.channel_budgets) - set(self.channels):
                raise ValueError("approved channel budgets may only mention campaign channels")
            if self.strategy is not Strategy.OPTIMIZED:
                raise ValueError("an approved plan can only be tracked by the optimized strategy")
        return self


class TargetKPIPlanRequestDTO(RequestBase):
    type: Literal["target_kpi"]
    budget: None = None
    optimize: None = None
    target: TargetKPIDTO


PlanRequestDTO = Annotated[
    FixedBudgetPlanRequestDTO | TargetKPIPlanRequestDTO,
    Field(discriminator="type", title="PlanRequest"),
]


class HourlyExpectedDTO(StrictModel):
    """Benchmark expectation of one channel hour; fractional counts keep trajectories exact."""

    spend: MoneyText
    impressions: DecimalText
    unique_reach: DecimalText
    clicks: DecimalText
    conversions: DecimalText


class AllocationDTO(StrictModel):
    channel_id: ChannelID
    hour: StrictInt = Field(ge=0, le=2159)
    budget_cap: MoneyText
    expected: HourlyExpectedDTO | None


class ExpectedOutcomeDTO(StrictModel):
    spend: MoneyText
    impressions: CountText
    unique_reach: CountText
    clicks: CountText
    conversions: CountText


class InfeasibilityReasonDTO(StrictModel):
    code: Literal["target_exceeds_capacity"]
    detail: str
    max_achievable: CountText
    recommended_target: CountText


class MediaPlanDTO(StrictModel):
    request_id: UUID
    state_revision: StrictInt = Field(ge=0, le=2160)
    plan_id: PlanID
    feasible: Literal[True]
    type: Literal["fixed_budget"]
    strategy: Strategy
    optimize: KPI
    currency: Currency
    budget: MoneyText
    unallocated_budget: MoneyText
    horizon: HorizonDTO
    expected: ExpectedOutcomeDTO | None
    allocations: list[AllocationDTO] = Field(min_length=1, max_length=43_200)
    required_budget: None
    reason: None
    target: None


class TargetKPIPlanDTO(StrictModel):
    request_id: UUID
    state_revision: Literal[0]
    plan_id: PlanID
    feasible: Literal[True]
    type: Literal["target_kpi"]
    strategy: Literal[Strategy.OPTIMIZED]
    optimize: KPI
    currency: Currency
    budget: MoneyText
    unallocated_budget: MoneyText
    horizon: HorizonDTO
    expected: ExpectedOutcomeDTO
    allocations: list[AllocationDTO] = Field(min_length=1, max_length=43_200)
    required_budget: MoneyText
    reason: None
    target: TargetKPIDTO


class InfeasibleTargetKPIPlanDTO(StrictModel):
    request_id: UUID
    state_revision: Literal[0]
    plan_id: None
    feasible: Literal[False]
    type: Literal["target_kpi"]
    strategy: Literal[Strategy.OPTIMIZED]
    optimize: KPI
    currency: Currency
    budget: None
    unallocated_budget: None
    horizon: HorizonDTO
    expected: ExpectedOutcomeDTO
    allocations: list[AllocationDTO] = Field(max_length=0)
    required_budget: None
    reason: InfeasibilityReasonDTO
    target: TargetKPIDTO


PlanResultDTO = MediaPlanDTO | TargetKPIPlanDTO | InfeasibleTargetKPIPlanDTO


class HealthDTO(StrictModel):
    status: Literal["ok"]
