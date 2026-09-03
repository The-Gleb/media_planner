"""HTTP-клиент к Go-симулятору (services/simulator): reset → почасовые step → пакеты факта."""

import dataclasses
import os
import time
import typing
import uuid

import httpx
import numpy as np
import numpy.typing as npt

from mediaplan.contracts import HourlyPacket


SIMULATOR_URL_ENV: typing.Final = "SIMULATOR_URL"
DEFAULT_SIMULATOR_URL: typing.Final = "http://127.0.0.1:8080"
DEFAULT_START_HOUR: typing.Final = "2026-09-06T21:00:00Z"
"""Понедельник 00:00 по Москве: недельная сезонность мира стартует с начала недели."""
DEFAULT_TIME_ZONE: typing.Final = "Europe/Moscow"

ScenarioMetric = typing.Literal["supply", "cpm", "ctr", "cr", "pause"]


@typing.final
@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ScenarioEvent:
    """Управляемое событие мира: «CTR канала × 0.6 с часа 252 на 252 часа»."""

    channel_id: str
    metric: ScenarioMetric
    start_hour: int
    duration_hours: int
    multiplier: float = 1.0

    def to_payload(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "metric": self.metric,
            "start_index": self.start_hour,
            "duration_hours": self.duration_hours,
            "multiplier": self.multiplier,
        }


def resolve_simulator_url() -> str:
    return os.environ.get(SIMULATOR_URL_ENV, DEFAULT_SIMULATOR_URL)


class SimulatorError(RuntimeError):
    pass


@typing.final
class SimulatorClient:
    """Одна активная симуляция на сервис: reset создаёт или атомарно пересоздаёт её."""

    def __init__(
        self,
        channel_ids: tuple[str, ...],
        base_url: str | None = None,
        simulation_id: str = "planner",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._channel_ids = channel_ids
        self._simulation_id = simulation_id
        self._http = httpx.Client(base_url=base_url or resolve_simulator_url(), timeout=timeout_seconds)
        self._etag = ""
        self._next_hour = 0

    def reset(
        self,
        world_seed: int,
        campaign_seed: int,
        horizon_hours: int,
        events: tuple[ScenarioEvent, ...] = (),
        disable_random_events: bool = True,
    ) -> None:
        payload: dict[str, object] = {
            "world_seed": str(world_seed),
            "campaign_seed": str(campaign_seed),
            "start_hour": DEFAULT_START_HOUR,
            "duration_hours": horizon_hours,
            "time_zone": DEFAULT_TIME_ZONE,
            "disable_random_events": disable_random_events,
            "scenario_events": [event.to_payload() for event in events],
        }
        headers = {"If-Match": self._etag} if self._etag else {"If-None-Match": "*"}
        response = self._http.put(f"/v1/simulations/{self._simulation_id}", json=payload, headers=headers)
        if response.status_code == httpx.codes.PRECONDITION_FAILED:
            current = self._http.get(f"/v1/simulations/{self._simulation_id}/current-hour")
            response = self._http.put(
                f"/v1/simulations/{self._simulation_id}",
                json=payload,
                headers={"If-Match": current.headers.get("ETag", "")},
            )
        self._raise_for_status(response)
        body = response.json()
        if tuple(body["channel_ids"]) != self._channel_ids:
            raise SimulatorError(
                f"каналы симулятора {body['channel_ids']} не совпадают с каталогом {self._channel_ids}"
            )
        self._etag = response.headers.get("ETag", "")
        self._next_hour = 0

    def simulate_hour(self, hour: int, spend_targets: npt.NDArray[np.float64]) -> tuple[HourlyPacket, ...]:
        if hour != self._next_hour:
            raise SimulatorError(f"ожидался час {self._next_hour}, запрошен {hour}")
        actions = [
            {"channel_id": channel_id, "budget_cap": f"{max(float(spend_targets[index]), 0.0):.6f}"}
            for index, channel_id in enumerate(self._channel_ids)
        ]
        response = self._http.post(
            f"/v1/simulations/{self._simulation_id}/steps",
            json={"step_id": str(uuid.uuid4()), "actions": actions},
            headers={"If-Match": self._etag},
        )
        self._raise_for_status(response)
        self._etag = response.headers.get("ETag", self._etag)
        self._next_hour += 1
        observations = {item["channel_id"]: item for item in response.json()["observations"]}
        return tuple(_to_packet(observations[channel_id], hour) for channel_id in self._channel_ids)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "SimulatorClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        raise SimulatorError(f"симулятор ответил {response.status_code}: {response.text[:500]}")


def _to_packet(observation: dict[str, typing.Any], hour: int) -> HourlyPacket:
    ecpm = observation.get("ecpm")
    return HourlyPacket(
        channel_id=observation["channel_id"],
        hour=hour,
        requests=int(observation["requests"]),
        impressions=int(observation["impressions"]),
        unique_reach=int(observation["unique_reach"]),
        clicks=int(observation["clicks"]),
        conversions=int(observation["conversions"]),
        spend_rub=float(observation["spend"]),
        ecpm_rub=float(ecpm) if ecpm is not None else 0.0,
    )


def wait_until_ready(base_url: str | None = None, attempts: int = 50, delay_seconds: float = 0.2) -> bool:
    url = (base_url or resolve_simulator_url()).rstrip("/") + "/health/ready"
    for _ in range(attempts):
        try:
            if httpx.get(url, timeout=2.0).is_success:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(delay_seconds)
    return False
