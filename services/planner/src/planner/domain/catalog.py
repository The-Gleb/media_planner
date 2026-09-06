import json
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ChannelBenchmark:
    channel_id: str
    cpm: float
    ctr: float
    cr: float
    daily_capacity: float
    audience_capacity: float
    saturation_threshold: float
    price_growth: float
    reach_decay: float
    frequency_reach_decay: float
    ctr_fatigue: float
    frequency_fatigue: float
    hourly_profile: tuple[float, ...]


def _geometric(low: float, high: float) -> float:
    return math.sqrt(low * high)


def _probability_mid(low: float, high: float) -> float:
    def logit(value: float) -> float:
        return math.log(value / (1.0 - value))

    midpoint = (logit(low) + logit(high)) / 2.0
    return 1.0 / (1.0 + math.exp(-midpoint))


def _mid(value: dict[str, float]) -> float:
    return (value["min"] + value["max"]) / 2.0


def _hourly_profile(pattern: dict[str, object]) -> tuple[float, ...]:
    center = _mid(pattern["peak_center_hour"])  # type: ignore[arg-type]
    width = _mid(pattern["peak_width_hours"])  # type: ignore[arg-type]
    amplitude = _mid(pattern["peak_amplitude"])  # type: ignore[arg-type]
    peaks = int(pattern["peaks_count"]["min"])  # type: ignore[index]
    values: list[float] = []
    for hour in range(24):
        distance = min(abs(hour - center), 24 - abs(hour - center))
        values.append(1.0 + peaks * amplitude * math.exp(-(distance**2) / (2.0 * width**2)))
    total = sum(values)
    return tuple(value / total for value in values)


@lru_cache(maxsize=4)
def _load_catalog(configured: str) -> dict[str, ChannelBenchmark]:
    config_path = Path(configured)
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    result: dict[str, ChannelBenchmark] = {}
    for item in raw["channels"]:
        base = item["base"]
        saturation = item["saturation"]
        cpm_range, ctr_range, cr_range = (base[name]["range"] for name in ("cpm", "ctr", "cr"))
        result[item["id"]] = ChannelBenchmark(
            channel_id=item["id"],
            cpm=_geometric(cpm_range["min"], cpm_range["max"]),
            ctr=_probability_mid(ctr_range["min"], ctr_range["max"]),
            cr=_probability_mid(cr_range["min"], cr_range["max"]),
            daily_capacity=_geometric(
                **{
                    "low": base["requests_per_day"]["range"]["min"],
                    "high": base["requests_per_day"]["range"]["max"],
                }
            ),
            audience_capacity=_geometric(
                **{
                    "low": base["audience_capacity"]["range"]["min"],
                    "high": base["audience_capacity"]["range"]["max"],
                }
            ),
            saturation_threshold=_mid(saturation["start_threshold"]),
            price_growth=_mid(saturation["price_growth_strength"]),
            reach_decay=_mid(saturation["reach_decay_strength"]),
            frequency_reach_decay=_mid(saturation["frequency_reach_decay_strength"]),
            ctr_fatigue=_mid(saturation["ctr_fatigue_strength"]),
            frequency_fatigue=_mid(saturation["frequency_fatigue_strength"]),
            hourly_profile=_hourly_profile(item["hourly_patterns"]["supply"]),
        )
    return result


def load_catalog(path: str | None = None) -> dict[str, ChannelBenchmark]:
    default = Path(__file__).resolve().parents[4] / "simulator/configs/world-config.mediaplan.json"
    configured = path or os.getenv("PLANNER_WORLD_CONFIG") or str(default)
    return _load_catalog(configured)
