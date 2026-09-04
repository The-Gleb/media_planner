"""Каталог — публичная витрина каналов, построенная из ДИАПАЗОНОВ конфига симулятора.

Симулятор сэмплит конкретные значения параметров по seed мира и держит их у себя.
Планировщик видит только границы диапазонов из того же JSON и берёт их середины как бенчмарк.
Так исключается утечка: в Python вообще нет истинных параметров мира.
"""

import json
import math
import os
import pathlib
import typing

import numpy as np
import numpy.typing as npt
import pydantic

from mediaplan.contracts import HOURS_PER_DAY, Catalog, ChannelCatalogEntry, ChannelKind, SaturationParams


DEFAULT_WORLD_CONFIG_PATH: typing.Final = (
    pathlib.Path(__file__).resolve().parents[3] / "simulator" / "configs" / "world-config.mediaplan.json"
)
WORLD_CONFIG_ENV: typing.Final = "SIMULATOR_CONFIG"


def _logit(probability: float) -> float:
    return math.log(probability / (1.0 - probability))


class FloatRange(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="ignore")

    min: float
    max: float

    @property
    def geometric_mid(self) -> float:
        return math.sqrt(self.min * self.max)

    @property
    def logit_mid(self) -> float:
        mid = (_logit(self.min) + _logit(self.max)) / 2.0
        return 1.0 / (1.0 + math.exp(-mid))

    @property
    def mid(self) -> float:
        return (self.min + self.max) / 2.0


class IntRange(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="ignore")

    min: int
    max: int


class BaseSpec(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="ignore")

    range: FloatRange


class BaseBlock(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="ignore")

    cpm: BaseSpec
    ctr: BaseSpec
    cr: BaseSpec
    requests_per_day: BaseSpec
    audience_capacity: BaseSpec


class SaturationBlock(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="ignore")

    start_threshold: FloatRange
    price_growth_strength: FloatRange
    reach_decay_strength: FloatRange
    frequency_reach_decay_strength: FloatRange
    ctr_fatigue_strength: FloatRange
    frequency_fatigue_strength: FloatRange


class HourlyPatternSpec(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="ignore")

    peaks_count: IntRange
    peak_center_hour: FloatRange
    peak_width_hours: FloatRange
    peak_amplitude: FloatRange


class HourlyPatterns(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="ignore")

    supply: HourlyPatternSpec


class ChannelSpec(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="ignore")

    id: str
    type: ChannelKind
    base: BaseBlock
    hourly_patterns: HourlyPatterns
    saturation: SaturationBlock


class WorldConfig(pydantic.BaseModel):
    """Только публичная часть конфига симулятора: диапазоны. Остальные блоки игнорируются."""

    model_config = pydantic.ConfigDict(frozen=True, extra="ignore")

    channels: tuple[ChannelSpec, ...]


def resolve_world_config_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get(WORLD_CONFIG_ENV, DEFAULT_WORLD_CONFIG_PATH))


def load_world_config(config_path: pathlib.Path | None = None) -> WorldConfig:
    path = config_path or resolve_world_config_path()
    return WorldConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))


def expected_hourly_profile(spec: HourlyPatternSpec) -> npt.NDArray[np.float64]:
    """Ожидаемый суточный профиль спроса по серединам диапазонов пиков, нормирован на сумму 1."""
    hours = np.arange(HOURS_PER_DAY, dtype=np.float64)
    profile = np.ones(HOURS_PER_DAY, dtype=np.float64)
    distance = np.abs(hours - spec.peak_center_hour.mid)
    distance = np.minimum(distance, HOURS_PER_DAY - distance)
    width = spec.peak_width_hours.mid
    profile += spec.peaks_count.min * spec.peak_amplitude.mid * np.exp(-(distance**2) / (2.0 * width**2))
    return profile / profile.sum()


def build_catalog(world_config: WorldConfig) -> Catalog:
    """Середины диапазонов как бенчмарк. Симулятор сортирует каналы по id, каталог — тоже."""
    channels = sorted(world_config.channels, key=lambda spec: spec.id)
    entries = tuple(
        ChannelCatalogEntry(
            channel_id=spec.id,
            kind=spec.type,
            cpm_rub=spec.base.cpm.range.geometric_mid,
            ctr=spec.base.ctr.range.logit_mid,
            cr=spec.base.cr.range.logit_mid,
            daily_capacity=spec.base.requests_per_day.range.geometric_mid,
            audience_capacity=spec.base.audience_capacity.range.geometric_mid,
            saturation=SaturationParams(
                start_threshold=spec.saturation.start_threshold.mid,
                price_growth=spec.saturation.price_growth_strength.mid,
                reach_decay=spec.saturation.reach_decay_strength.mid,
                frequency_reach_decay=spec.saturation.frequency_reach_decay_strength.mid,
                ctr_fatigue=spec.saturation.ctr_fatigue_strength.mid,
                frequency_fatigue=spec.saturation.frequency_fatigue_strength.mid,
            ),
            price_growth=0.0,
            delivery_rate=1.0,
        )
        for spec in channels
    )
    profiles = np.stack([expected_hourly_profile(spec.hourly_patterns.supply) for spec in channels])
    return Catalog(channels=entries, hourly_profile=profiles.mean(axis=0))
