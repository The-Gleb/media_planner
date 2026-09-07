"""Frozen-versus-adaptive and cold-versus-warm evaluation harness for the Media Planner.

The harness reproduces the dashboard loop headlessly. For every world seed it can first play a
number of earlier campaigns ("warm-up") whose observable facts become the planner's history; it
then approves one optimized plan and executes it in the Simulator either with frozen caps (the
approved schedule is never changed) or adaptively (every committed hour is fed back to Planner and
the returned caps are used for the next hour). All variants of one cell run on identical world and
campaign seeds and identical controlled shocks, so paired differences are attributable to the
single factor that changed: hourly replanning, or history.

Planner is exercised through its HTTP contract in-process (FastAPI test client); Simulator runs as
the real Go binary, one process per worker, because a Simulator process holds a single simulation
resource. Every simulated hour is also appended to a training dataset (one row per channel-hour
with the cap and the cumulative state before the hour) for offline response models.

Example:
    cd services/planner
    uv run --group dev python ../../tools/evaluation/evaluate.py \\
        --world-seeds 1-5 --history-levels 0,3 --workers 4 --out ../../tools/evaluation/results
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from multiprocessing import Process
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIMULATOR_BIN = REPO_ROOT / "services/simulator/bin/simulator"
DEFAULT_WORLD_CONFIG = REPO_ROOT / "services/simulator/configs/world-config.audience.json"
DEFAULT_PLANNER_CONFIG = REPO_ROOT / "services/simulator/configs/world-config.mediaplan.json"
MICROS = 1_000_000
SCENARIOS = ("none", "ctr_drop", "cpm_spike", "supply_drop", "pause")
MODES = ("frozen", "manual", "adaptive", "adaptive_max")
MANUAL_SHIFT = 0.2
MANUAL_MAX_STEP = 0.3
RECENT_HOURS = 72
SHOCK_MULTIPLIERS = {"ctr_drop": 0.6, "cpm_spike": 1.6, "supply_drop": 0.5}
FACT_KEYS = ("requests", "impressions", "unique_reach", "clicks", "conversions")
HISTORY_SEED_BASE = 1000
DATASET_COLUMNS = (
    "kind",
    "world_seed",
    "campaign_seed",
    "history_level",
    "scenario",
    "mode",
    "channel_id",
    "hour_index",
    "hour_of_day",
    "weekday",
    "cap",
    "requests",
    "impressions",
    "unique_reach",
    "clicks",
    "conversions",
    "spend",
    "cum_impressions_before",
    "cum_reach_before",
    "cum_spend_before",
)


# --------------------------------------------------------------------------------------
# Money helpers
# --------------------------------------------------------------------------------------


def to_micros(text: str) -> int:
    return int((Decimal(text) * MICROS).to_integral_value())


def money(micros: int) -> str:
    return f"{micros // MICROS}.{micros % MICROS:06d}"


# --------------------------------------------------------------------------------------
# Specs and results
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Brief:
    budget_micros: int
    duration_hours: int
    optimize: str
    start_hour: str
    time_zone: str
    replan_every: int
    pause_hours: int
    random_events: bool
    trajectory_skip_hours: int
    history_mode: str
    history_random_events: bool
    history_budget_factors: tuple[float, ...]
    strategy: str = "optimized"
    target_value: int | None = None
    shock_start: int | None = None
    send_recent: bool = True


@dataclass(frozen=True)
class RunSpec:
    world_seed: int
    campaign_seed: int
    history: int
    scenario: str
    mode: str

    @property
    def run_id(self) -> str:
        return (
            f"w{self.world_seed}-c{self.campaign_seed}-h{self.history}-{self.scenario}-{self.mode}"
        )


@dataclass
class RunResult:
    run_id: str
    world_seed: int
    campaign_seed: int
    history: int
    scenario: str
    mode: str
    shocked_channel: str | None
    budget: float
    plan_spend: float
    plan_kpi: float
    fact_spend: float
    fact_kpi: float
    mape_spend: float
    mape_kpi: float
    final_ape_spend: float
    final_ape_kpi: float
    final_dev_spend: float
    final_dev_kpi: float
    within_20: bool
    budget_utilization: float
    reallocated_share: float
    replans: int
    seconds: float
    channel_spend: dict[str, float] = field(default_factory=dict)
    channel_facts: dict[str, dict[str, int]] = field(default_factory=dict)
    target: int | None = None
    required_budget: float | None = None
    shock_start: int | None = None
    top_channel: str | None = None
    top_spend_after: float | None = None


# --------------------------------------------------------------------------------------
# Clients
# --------------------------------------------------------------------------------------


class HTTPError(RuntimeError):
    pass


class SimulatorClient:
    """One Simulator process holds one simulation resource, so the client reuses a single id."""

    def __init__(self, base_url: str, simulation_id: str = "eval") -> None:
        self.base_url = base_url.rstrip("/")
        self.simulation_id = simulation_id
        self.etag: str | None = None

    def _call(
        self, method: str, path: str, body: object | None = None, headers: Mapping[str, str] = {}
    ) -> tuple[dict[str, Any], str | None]:
        data = json.dumps(body).encode() if body is not None else None
        request = urlrequest.Request(self.base_url + path, data=data, method=method)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urlrequest.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read() or b"{}")
                return payload, response.headers.get("ETag")
        except urlerror.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise HTTPError(f"{method} {path} -> {exc.code}: {detail}") from exc

    def ready(self) -> bool:
        try:
            self._call("GET", "/health/ready")
            return True
        except HTTPError, urlerror.URLError, ConnectionError, OSError:
            return False

    def metadata(self) -> dict[str, Any]:
        return self._call("GET", "/v1/world-metadata")[0]

    def reset(self, payload: dict[str, Any]) -> None:
        headers = {"If-Match": self.etag} if self.etag else {"If-None-Match": "*"}
        self.etag = self._call("PUT", f"/v1/simulations/{self.simulation_id}", payload, headers)[1]

    def step(self, actions: list[dict[str, str]]) -> dict[str, Any]:
        headers = {"If-Match": self.etag} if self.etag else {}
        body = {"step_id": str(uuid.uuid4()), "actions": actions}
        response, self.etag = self._call(
            "POST", f"/v1/simulations/{self.simulation_id}/steps", body, headers
        )
        return response


class PlannerClient:
    """Planner through its HTTP contract; in-process by default, remote when a URL is given."""

    def __init__(self, base_url: str | None) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self._client: Any = None
        if self.base_url is None:
            from fastapi.testclient import TestClient

            from planner.transport.http.app import app

            self._client = TestClient(app, raise_server_exceptions=True)
            self._client.__enter__()

    def plan(self, body: dict[str, Any]) -> dict[str, Any]:
        if self._client is not None:
            response = self._client.post("/v1/plans", json=body)
            if response.status_code != 200:
                raise HTTPError(f"planner -> {response.status_code}: {response.text}")
            return dict(response.json())
        if self.base_url is None:
            raise RuntimeError("planner client has neither an app nor a base URL")
        request = urlrequest.Request(
            self.base_url + "/v1/plans",
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urlrequest.urlopen(request, timeout=60) as response:
                return dict(json.loads(response.read()))
        except urlerror.HTTPError as exc:
            raise HTTPError(
                f"planner -> {exc.code}: {exc.read().decode(errors='replace')}"
            ) from exc


# --------------------------------------------------------------------------------------
# Plan view
# --------------------------------------------------------------------------------------


class PlanView:
    """Caps and hourly expectations of one Planner response, indexed by hour and channel."""

    def __init__(
        self, body: dict[str, Any], channels: Sequence[str], optimize: str, budget_micros: int
    ) -> None:
        self.plan_id: str = body["plan_id"]
        self.channels = list(channels)
        self.budget_micros = budget_micros
        self.caps: dict[int, dict[str, int]] = {}
        self.expected_spend: dict[int, int] = {}
        self.expected_kpi: dict[int, float] = {}
        self.channel_budget: dict[str, int] = dict.fromkeys(channels, 0)
        for item in body["allocations"]:
            hour = int(item["hour"])
            cap = to_micros(item["budget_cap"])
            self.caps.setdefault(hour, {})[item["channel_id"]] = cap
            self.channel_budget[item["channel_id"]] += cap
            expected = item["expected"]
            if expected is not None:
                self.expected_spend[hour] = self.expected_spend.get(hour, 0) + to_micros(
                    expected["spend"]
                )
                self.expected_kpi[hour] = self.expected_kpi.get(hour, 0.0) + float(
                    expected[optimize]
                )
        total = body["expected"]
        self.total_spend = to_micros(total["spend"]) if total else 0
        self.total_kpi = float(total[optimize]) if total else 0.0

    def actions(self, hour: int) -> list[dict[str, str]]:
        caps = self.caps[hour]
        return [{"channel_id": c, "budget_cap": money(caps[c])} for c in self.channels]

    def cumulative(self, duration: int) -> tuple[list[float], list[float]]:
        spend: list[float] = []
        kpi: list[float] = []
        running_spend = 0
        running_kpi = 0.0
        for hour in range(duration):
            running_spend += self.expected_spend.get(hour, 0)
            running_kpi += self.expected_kpi.get(hour, 0.0)
            spend.append(running_spend / MICROS)
            kpi.append(running_kpi)
        return spend, kpi

    @property
    def top_channel(self) -> str:
        return max(self.channel_budget, key=lambda c: (self.channel_budget[c], c))


# --------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------


def trajectory_error(plan: Sequence[float], fact: Sequence[float], skip_hours: int) -> float:
    """Mean |fact − plan| / plan over the cumulative trajectory after the warm-up hours."""
    errors = [
        abs(f - p) / p
        for hour, (p, f) in enumerate(zip(plan, fact, strict=True))
        if hour >= skip_hours and p > 0
    ]
    return sum(errors) / len(errors) if errors else 0.0


def final_dev(plan: Sequence[float], fact: Sequence[float]) -> float:
    return (fact[-1] - plan[-1]) / plan[-1] if plan and plan[-1] > 0 else 0.0


def quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _median(values: Iterable[float]) -> float:
    items = list(values)
    return statistics.median(items) if items else float("nan")


# --------------------------------------------------------------------------------------
# Requests
# --------------------------------------------------------------------------------------


def zero_facts(channels: Sequence[str]) -> dict[str, dict[str, int]]:
    return {c: dict.fromkeys(("spent", *FACT_KEYS), 0) for c in channels}


def scenario_events(
    scenario: str, channel: str, duration: int, pause_hours: int, start: int | None = None
) -> list[dict[str, Any]]:
    if scenario == "none":
        return []
    start = duration // 2 if start is None else min(max(start, 0), duration - 1)
    if scenario == "pause":
        return [
            {
                "channel_id": channel,
                "metric": "pause",
                "start_index": start,
                "duration_hours": min(pause_hours, duration - start),
                "multiplier": 0.0,
            }
        ]
    metric = {"ctr_drop": "ctr", "cpm_spike": "cpm", "supply_drop": "supply"}[scenario]
    return [
        {
            "channel_id": channel,
            "metric": metric,
            "start_index": start,
            "duration_hours": duration - start,
            "multiplier": SHOCK_MULTIPLIERS[scenario],
        }
    ]


def simulation_context(
    brief: Brief, metadata: dict[str, Any], simulation_id: str, world_seed: int, campaign_seed: int
) -> dict[str, Any]:
    return {
        "simulation_id": simulation_id,
        "world_seed": str(world_seed),
        "campaign_seed": str(campaign_seed),
        "start_hour": brief.start_hour,
        "time_zone": brief.time_zone,
        "currency": metadata["currency"],
        "world_config_digest": metadata["world_config_digest"],
    }


def plan_request(
    brief: Brief,
    simulation: dict[str, Any],
    channels: Sequence[str],
    facts: dict[str, dict[str, int]],
    current_hour: int,
    last_step_id: str | None,
    last_observed_at: str | None,
    history: Sequence[dict[str, Any]],
    strategy: str = "optimized",
    budget_micros: int | None = None,
    recent: Sequence[dict[str, Any]] = (),
    approved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    totals = {
        key: sum(facts[c][key] for c in channels)
        for key in ("spent", "unique_reach", "clicks", "conversions")
    }
    return {
        "request_id": str(uuid.uuid4()),
        "type": "fixed_budget",
        "strategy": strategy,
        "horizon": {"from_hour": 0, "to_hour": brief.duration_hours},
        "channels": list(channels),
        "simulation": simulation,
        "market": {"status": "unavailable"},
        "current": {
            "current_hour": current_hour,
            "state_revision": current_hour,
            "last_step_id": last_step_id,
            "last_observed_at": last_observed_at,
            "spent": money(totals["spent"]),
            "unique_reach": str(totals["unique_reach"]),
            "clicks": str(totals["clicks"]),
            "conversions": str(totals["conversions"]),
            "channels": {
                c: {
                    "spent": money(facts[c]["spent"]),
                    **{key: str(facts[c][key]) for key in FACT_KEYS},
                }
                for c in channels
            },
            "recent_hours": list(recent),
        },
        "history": list(history),
        "approved": approved,
        "budget": money(brief.budget_micros if budget_micros is None else budget_micros),
        "optimize": brief.optimize,
        "target": None,
    }


# --------------------------------------------------------------------------------------
# Campaign execution
# --------------------------------------------------------------------------------------


@dataclass
class Execution:
    """Everything one simulated campaign produced."""

    plan_spend: list[float]
    plan_kpi: list[float]
    fact_spend: list[float]
    fact_kpi: list[float]
    facts: dict[str, dict[str, int]]
    bins: dict[str, list[dict[str, int]]]
    daily: dict[str, list[dict[str, int]]]
    replans: int
    reallocated: int
    top_caps: list[float] = field(default_factory=list)
    top_spend: list[float] = field(default_factory=list)


def manual_rebalance(
    current: PlanView, hour: int, facts_yesterday: dict[str, dict[str, int]], optimize: str
) -> PlanView:
    """Daily hand rebalancing, the way a traffic manager without a model does it.

    Once a day the manager looks at yesterday's cost per KPI of every funded channel and moves
    MANUAL_SHIFT of the remaining budget from channels worse than the average toward the better
    ones, at most MANUAL_MAX_STEP per channel per day. Hourly shapes stay as approved; nothing
    unspent is carried over; channels the plan never funded stay closed."""
    remaining_hours = [h for h in current.caps if h >= hour]
    planned = {c: sum(current.caps[h][c] for h in remaining_hours) for c in current.channels}
    funded = [c for c in current.channels if planned[c] > 0 and facts_yesterday[c]["spent"] > 0]
    if len(funded) < 2:
        return current
    efficiency = {
        c: facts_yesterday[c][optimize] / (facts_yesterday[c]["spent"] / MICROS) for c in funded
    }
    total_spent = sum(facts_yesterday[c]["spent"] for c in funded) / MICROS
    average = sum(facts_yesterday[c][optimize] for c in funded) / total_spent
    if average <= 0:
        return current
    factors = {
        c: min(
            1 + MANUAL_MAX_STEP,
            max(1 - MANUAL_MAX_STEP, 1 + MANUAL_SHIFT * (efficiency[c] / average - 1)),
        )
        for c in funded
    }
    before = sum(planned[c] for c in funded)
    after = sum(planned[c] * factors[c] for c in funded)
    scale = before / after if after > 0 else 1.0
    view = copy.copy(current)
    view.caps = {h: dict(caps) for h, caps in current.caps.items()}
    for h in remaining_hours:
        for c in funded:
            view.caps[h][c] = int(round(current.caps[h][c] * factors[c] * scale))
    return view


def _local(observed_hour: str, time_zone: str) -> datetime:
    return datetime.fromisoformat(observed_hour.replace("Z", "+00:00")).astimezone(
        ZoneInfo(time_zone)
    )


def execute_campaign(
    *,
    brief: Brief,
    channels: Sequence[str],
    simulator: SimulatorClient,
    planner: PlannerClient,
    approved: PlanView,
    simulation: dict[str, Any],
    world_seed: int,
    campaign_seed: int,
    events: list[dict[str, Any]],
    random_events: bool,
    adaptive: bool,
    tracking: bool,
    manual: bool,
    history: Sequence[dict[str, Any]],
    dataset: Any,
    dataset_tags: Mapping[str, object],
    tracked: str | None = None,
) -> Execution:
    duration = brief.duration_hours
    reset_payload: dict[str, Any] = {
        "world_seed": str(world_seed),
        "campaign_seed": str(campaign_seed),
        "start_hour": brief.start_hour,
        "duration_hours": duration,
        "time_zone": brief.time_zone,
        "disable_random_events": not random_events,
    }
    if events:
        reset_payload["scenario_events"] = events
    simulator.reset(reset_payload)

    facts = zero_facts(channels)
    recent: list[dict[str, Any]] = []
    approved_payload = (
        {
            "kpi_target": str(max(1, round(approved.total_kpi))),
            "channel_budgets": {c: money(approved.channel_budget[c]) for c in channels},
        }
        if tracking
        else None
    )
    bins = {
        c: [dict.fromkeys(("hours", "spent", *FACT_KEYS), 0) for _ in range(24)] for c in channels
    }
    daily: dict[str, list[dict[str, int]]] = {c: [] for c in channels}
    plan_spend, plan_kpi = approved.cumulative(duration)
    fact_spend: list[float] = []
    fact_kpi: list[float] = []
    current = approved
    replans = 0
    reallocated = 0
    top_caps: list[float] = []
    top_spend: list[float] = []
    for hour in range(duration):
        actions = current.actions(hour)
        for c in channels:
            reallocated += abs(current.caps[hour][c] - approved.caps[hour][c])
        if tracked is not None:
            top_caps.append(current.caps[hour][tracked] / MICROS)
        response = simulator.step(actions)
        local = _local(response["observed_hour"], brief.time_zone)
        hour_row: dict[str, Any] = {"hour": hour, "channels": {}}
        for observation in response["observations"]:
            channel_id = observation["channel_id"]
            record = facts[channel_id]
            spend = to_micros(observation["spend"])
            if dataset is not None:
                dataset.writerow(
                    [
                        *dataset_tags.values(),
                        channel_id,
                        hour,
                        local.hour,
                        local.weekday(),
                        money(current.caps[hour][channel_id]),
                        *(observation[key] for key in FACT_KEYS),
                        observation["spend"],
                        record["impressions"],
                        record["unique_reach"],
                        money(record["spent"]),
                    ]
                )
            day_index = hour // 24
            if len(daily[channel_id]) <= day_index:
                daily[channel_id].append(
                    {
                        "day": day_index,
                        "hours": 0,
                        "spent": 0,
                        **dict.fromkeys(FACT_KEYS, 0),
                        "reach_before": record["unique_reach"],
                        "impressions_before": record["impressions"],
                    }
                )
            day_row = daily[channel_id][day_index]
            day_row["hours"] += 1
            day_row["spent"] += spend
            for key in FACT_KEYS:
                day_row[key] += int(observation[key])
            record["spent"] += spend
            if channel_id == tracked:
                top_spend.append(spend / MICROS)
            hour_row["channels"][channel_id] = {
                "spent": observation["spend"],
                **{key: str(observation[key]) for key in FACT_KEYS},
            }
            hour_bin = bins[channel_id][local.hour]
            hour_bin["hours"] += 1
            hour_bin["spent"] += spend
            for key in FACT_KEYS:
                record[key] += int(observation[key])
                hour_bin[key] += int(observation[key])
        recent.append(hour_row)
        del recent[:-RECENT_HOURS]
        fact_spend.append(sum(facts[c]["spent"] for c in channels) / MICROS)
        fact_kpi.append(float(sum(facts[c][brief.optimize] for c in channels)))
        next_hour = hour + 1
        if manual and next_hour < duration and next_hour % 24 == 0:
            yesterday = {
                c: {
                    "spent": sum(x["spent"] for x in daily[c][-1:]),
                    **{k: sum(x[k] for x in daily[c][-1:]) for k in FACT_KEYS},
                }
                for c in channels
            }
            current = manual_rebalance(current, next_hour, yesterday, brief.optimize)
            replans += 1
        if adaptive and next_hour < duration and next_hour % brief.replan_every == 0:
            body = plan_request(
                brief,
                simulation,
                channels,
                facts,
                next_hour,
                response["step_id"],
                response["observed_hour"],
                history,
                budget_micros=approved.budget_micros,
                recent=recent if brief.send_recent else (),
                approved=approved_payload,
            )
            current = PlanView(planner.plan(body), channels, brief.optimize, approved.budget_micros)
            replans += 1
    return Execution(
        plan_spend,
        plan_kpi,
        fact_spend,
        fact_kpi,
        facts,
        bins,
        daily,
        replans,
        reallocated,
        top_caps,
        top_spend,
    )


def past_campaign(execution: Execution, horizon_hours: int) -> dict[str, Any]:
    """Planner `history` entry built from what a finished campaign observed."""
    return {
        "horizon_hours": horizon_hours,
        "channels": {
            channel_id: {
                "bins": [
                    {
                        "hour": hour,
                        "hours": item["hours"],
                        **{key: str(item[key]) for key in FACT_KEYS},
                        "spent": money(item["spent"]),
                    }
                    for hour, item in enumerate(channel_bins)
                ],
                "daily": [
                    {
                        "day": item["day"],
                        "hours": item["hours"],
                        **{key: str(item[key]) for key in FACT_KEYS},
                        "spent": money(item["spent"]),
                        "reach_before": str(item["reach_before"]),
                        "impressions_before": str(item["impressions_before"]),
                    }
                    for item in execution.daily[channel_id]
                ],
            }
            for channel_id, channel_bins in execution.bins.items()
        },
    }


# --------------------------------------------------------------------------------------
# History warm-up
# --------------------------------------------------------------------------------------


def load_or_generate_history(
    *,
    world_seed: int,
    count: int,
    brief: Brief,
    channels: Sequence[str],
    metadata: dict[str, Any],
    simulator: SimulatorClient,
    planner: PlannerClient,
    out_dir: Path,
    dataset: Any,
) -> list[dict[str, Any]]:
    """Earlier campaigns on the same world, oldest first, cached per world seed."""
    if count <= 0:
        return []
    path = out_dir / "history" / f"world-{world_seed}.json"
    if path.exists():
        cached = json.loads(path.read_text())
        if len(cached) >= count:
            return list(cached[-count:])
    history: list[dict[str, Any]] = []
    for index in range(count):
        campaign_seed = HISTORY_SEED_BASE + index
        factor = brief.history_budget_factors[index % len(brief.history_budget_factors)]
        budget = int(brief.budget_micros * factor)
        simulation = simulation_context(
            brief, metadata, simulator.simulation_id, world_seed, campaign_seed
        )
        body = plan_request(
            brief,
            simulation,
            channels,
            zero_facts(channels),
            0,
            None,
            None,
            history,
            strategy="uniform" if brief.history_mode == "uniform" else "optimized",
            budget_micros=budget,
        )
        plan = PlanView(planner.plan(body), channels, brief.optimize, budget)
        execution = execute_campaign(
            brief=brief,
            channels=channels,
            simulator=simulator,
            planner=planner,
            approved=plan,
            simulation=simulation,
            world_seed=world_seed,
            campaign_seed=campaign_seed,
            events=[],
            random_events=brief.history_random_events,
            adaptive=brief.history_mode in ("adaptive", "adaptive_max"),
            tracking=brief.history_mode == "adaptive",
            manual=brief.history_mode == "manual",
            history=history,
            dataset=dataset,
            dataset_tags={
                "kind": "history",
                "world_seed": world_seed,
                "campaign_seed": campaign_seed,
                "history_level": index,
                "scenario": "none",
                "mode": brief.history_mode,
            },
        )
        history.append(past_campaign(execution, brief.duration_hours))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history))
    return history


# --------------------------------------------------------------------------------------
# Evaluated run
# --------------------------------------------------------------------------------------


def approve_plan(
    planner: PlannerClient,
    brief: Brief,
    channels: Sequence[str],
    metadata: dict[str, Any],
    history: Sequence[dict[str, Any]],
) -> tuple[PlanView, dict[str, Any]]:
    simulation = simulation_context(brief, metadata, "eval-approval", 0, 0)
    request = plan_request(
        brief,
        simulation,
        channels,
        zero_facts(channels),
        0,
        None,
        None,
        history,
        strategy=brief.strategy,
    )
    if brief.target_value is not None:
        # Task B: the planner finds the least budget whose forecast reaches the target; the
        # campaign is then executed on that budget.
        request.update(
            {
                "type": "target_kpi",
                "strategy": "optimized",
                "budget": None,
                "optimize": None,
                "target": {"metric": brief.optimize, "value": str(brief.target_value)},
            }
        )
        request.pop("approved", None)
    body = planner.plan(request)
    if not body.get("feasible", True):
        raise RuntimeError(
            f"target {brief.target_value} {brief.optimize} is infeasible: max achievable "
            f"{body['reason']['max_achievable']}"
        )
    budget_micros = (
        to_micros(body["budget"]) if brief.target_value is not None else brief.budget_micros
    )
    return PlanView(body, channels, brief.optimize, budget_micros), body


def run_campaign(
    spec: RunSpec,
    brief: Brief,
    channels: Sequence[str],
    metadata: dict[str, Any],
    simulator: SimulatorClient,
    planner: PlannerClient,
    approved: PlanView,
    history: Sequence[dict[str, Any]],
    trajectories_dir: Path,
    dataset: Any,
) -> RunResult:
    started = time.perf_counter()
    duration = brief.duration_hours
    simulation = simulation_context(
        brief, metadata, simulator.simulation_id, spec.world_seed, spec.campaign_seed
    )
    shocked = approved.top_channel if spec.scenario != "none" else None
    events = scenario_events(
        spec.scenario, approved.top_channel, duration, brief.pause_hours, brief.shock_start
    )
    shock_start = int(events[0]["start_index"]) if events else None
    execution = execute_campaign(
        brief=brief,
        channels=channels,
        simulator=simulator,
        planner=planner,
        approved=approved,
        simulation=simulation,
        world_seed=spec.world_seed,
        campaign_seed=spec.campaign_seed,
        events=events,
        random_events=brief.random_events,
        adaptive=spec.mode in ("adaptive", "adaptive_max"),
        tracking=spec.mode == "adaptive",
        manual=spec.mode == "manual",
        history=history,
        dataset=dataset,
        dataset_tags={
            "kind": "eval",
            "world_seed": spec.world_seed,
            "campaign_seed": spec.campaign_seed,
            "history_level": spec.history,
            "scenario": spec.scenario,
            "mode": spec.mode,
        },
        tracked=approved.top_channel,
    )

    trajectories_dir.mkdir(parents=True, exist_ok=True)
    with (trajectories_dir / f"{spec.run_id}.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "hour",
                "plan_spend",
                "fact_spend",
                "plan_kpi",
                "fact_kpi",
                "top_cap",
                "top_spend",
            ]
        )
        for hour in range(duration):
            writer.writerow(
                [
                    hour,
                    f"{execution.plan_spend[hour]:.2f}",
                    f"{execution.fact_spend[hour]:.2f}",
                    f"{execution.plan_kpi[hour]:.3f}",
                    f"{execution.fact_kpi[hour]:.0f}",
                    f"{execution.top_caps[hour]:.2f}",
                    f"{execution.top_spend[hour]:.2f}",
                ]
            )
    top_after = sum(execution.top_spend[shock_start:]) if shock_start is not None else None

    budget = approved.budget_micros / MICROS
    dev_spend = final_dev(execution.plan_spend, execution.fact_spend)
    dev_kpi = final_dev(execution.plan_kpi, execution.fact_kpi)
    skip = brief.trajectory_skip_hours
    return RunResult(
        run_id=spec.run_id,
        world_seed=spec.world_seed,
        campaign_seed=spec.campaign_seed,
        history=spec.history,
        scenario=spec.scenario,
        mode=spec.mode,
        shocked_channel=shocked,
        budget=budget,
        plan_spend=execution.plan_spend[-1],
        plan_kpi=execution.plan_kpi[-1],
        fact_spend=execution.fact_spend[-1],
        fact_kpi=execution.fact_kpi[-1],
        mape_spend=trajectory_error(execution.plan_spend, execution.fact_spend, skip),
        mape_kpi=trajectory_error(execution.plan_kpi, execution.fact_kpi, skip),
        final_ape_spend=abs(dev_spend),
        final_ape_kpi=abs(dev_kpi),
        final_dev_spend=dev_spend,
        final_dev_kpi=dev_kpi,
        within_20=abs(dev_spend) <= 0.2 and abs(dev_kpi) <= 0.2,
        budget_utilization=execution.fact_spend[-1] / budget if budget else 0.0,
        reallocated_share=execution.reallocated / approved.budget_micros
        if approved.budget_micros
        else 0.0,
        replans=execution.replans,
        seconds=time.perf_counter() - started,
        channel_spend={c: execution.facts[c]["spent"] / MICROS for c in channels},
        channel_facts={
            c: {k: v for k, v in execution.facts[c].items() if k != "spent"} for c in channels
        },
        target=brief.target_value,
        required_budget=budget if brief.target_value is not None else None,
        shock_start=shock_start,
        top_channel=approved.top_channel,
        top_spend_after=top_after,
    )


# --------------------------------------------------------------------------------------
# Worker orchestration
# --------------------------------------------------------------------------------------


def harness_binary(binary: Path, out_dir: Path) -> Path:
    """Copy of the Simulator binary under its own name, so that killing the dev-stack Simulator
    by process name never touches the harness workers."""
    target = out_dir / "simulator-eval"
    if not target.exists() or target.stat().st_size != binary.stat().st_size:
        target.write_bytes(binary.read_bytes())
        target.chmod(0o755)
    return target


def start_simulator(binary: Path, config: Path, port: int) -> subprocess.Popen[bytes]:
    env = dict(os.environ)
    env.update(
        {
            "SIMULATOR_ADDR": f"127.0.0.1:{port}",
            "SIMULATOR_CONFIG": str(config),
            "SIMULATOR_RELAX_PRECONDITIONS": "true",
            "SIMULATOR_LOG_LEVEL": "error",
        }
    )
    return subprocess.Popen(
        [str(binary)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def wait_ready(client: SimulatorClient, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if client.ready():
            return
        time.sleep(0.1)
    raise RuntimeError(f"simulator at {client.base_url} did not become ready")


def worker_main(
    index: int,
    specs: list[RunSpec],
    brief: Brief,
    args_dict: dict[str, Any],
    out_dir: Path,
) -> None:
    port = int(args_dict["simulator_port"]) + index
    process = None
    binary = None
    if not args_dict["simulator_url"]:
        binary = Path(args_dict["harness_binary"])
        process = start_simulator(binary, Path(args_dict["world_config"]), port)
    simulator = SimulatorClient(
        args_dict["simulator_url"] or f"http://127.0.0.1:{port}", f"eval-worker-{index}"
    )
    (out_dir / "dataset").mkdir(parents=True, exist_ok=True)
    results_path = out_dir / f"worker-{index}.jsonl"
    done: set[str] = set()
    if results_path.exists():
        with results_path.open() as handle:
            done = {json.loads(line)["run_id"] for line in handle if line.strip()}
    try:
        wait_ready(simulator)
        metadata = simulator.metadata()
        channels = sorted(metadata["channel_ids"])
        planner = PlannerClient(args_dict["planner_url"])
        approved_cache: dict[tuple[int, int], tuple[PlanView, list[dict[str, Any]]]] = {}
        with (
            results_path.open("a") as results_handle,
            (out_dir / "dataset" / f"worker-{index}.csv").open("a", newline="") as dataset_handle,
        ):
            dataset = csv.writer(dataset_handle)
            for position, spec in enumerate(specs, start=1):
                if spec.run_id in done:
                    continue
                key = (spec.world_seed, spec.history)
                if key not in approved_cache:
                    history = load_or_generate_history(
                        world_seed=spec.world_seed,
                        count=spec.history,
                        brief=brief,
                        channels=channels,
                        metadata=metadata,
                        simulator=simulator,
                        planner=planner,
                        out_dir=out_dir,
                        dataset=dataset,
                    )
                    approved, body = approve_plan(planner, brief, channels, metadata, history)
                    approved_cache[key] = (approved, history)
                    plans_dir = out_dir / "approved"
                    plans_dir.mkdir(parents=True, exist_ok=True)
                    (plans_dir / f"world-{spec.world_seed}-h{spec.history}.json").write_text(
                        json.dumps(body)
                    )
                approved, history = approved_cache[key]
                for attempt in range(3):
                    try:
                        result = run_campaign(
                            spec,
                            brief,
                            channels,
                            metadata,
                            simulator,
                            planner,
                            approved,
                            history,
                            out_dir / "trajectories",
                            dataset,
                        )
                        break
                    except (urlerror.URLError, ConnectionError, OSError) as exc:
                        if process is None or binary is None or attempt == 2:
                            raise
                        print(
                            f"[worker {index}] simulator lost ({exc}); restarting and retrying "
                            f"{spec.run_id}",
                            file=sys.stderr,
                            flush=True,
                        )
                        process.terminate()
                        process.wait(timeout=5)
                        process = start_simulator(binary, Path(args_dict["world_config"]), port)
                        simulator.etag = None
                        wait_ready(simulator)
                results_handle.write(json.dumps(asdict(result)) + "\n")
                results_handle.flush()
                dataset_handle.flush()
                print(
                    f"[worker {index}] {position}/{len(specs)} {spec.run_id}: "
                    f"final spend {result.final_dev_spend:+.1%} kpi {result.final_dev_kpi:+.1%} "
                    f"traj kpi {result.mape_kpi:.1%} ({result.seconds:.0f}s)",
                    file=sys.stderr,
                    flush=True,
                )
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=5)


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------


def shortfall(result: RunResult) -> float:
    return max(0.0, -result.final_dev_kpi)


def _group(results: list[RunResult], **match: object) -> list[RunResult]:
    return [r for r in results if all(getattr(r, key) == value for key, value in match.items())]


def summarize(results: list[RunResult], brief: Brief) -> str:
    """Two roles, two questions: how honest is the plan, how much KPI does live execution deliver."""
    levels = sorted({r.history for r in results})
    live_modes = [m for m in MODES if m != "frozen" and any(r.mode == m for r in results)]
    lines: list[str] = []
    lines.append("# Media Planner evaluation\n")
    lines.append(
        f"Budget {brief.budget_micros / MICROS:,.0f}, horizon {brief.duration_hours} h, "
        f"KPI `{brief.optimize}`, replan every {brief.replan_every} h, "
        f"random market events {'on' if brief.random_events else 'off'}, history levels "
        f"{', '.join(map(str, levels))} ({brief.history_mode} warm-up campaigns), "
        f"{len(results)} runs.\n"
    )

    lines.append("## Planner: forecast accuracy under frozen execution\n")
    lines.append(
        "The approved plan is executed exactly as approved, so the deviation of the fact from the "
        "plan is the planner's forecast error. Symmetric: over-forecasting reserves money for "
        "nothing, under-forecasting hides achievable KPI.\n"
    )
    lines.append(
        "| History | Scenario | Runs | Final dev spend p50 | Final dev KPI p50 "
        "| |Final dev KPI| p90 | Within 20% | Trajectory error KPI p50 |"
    )
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|")
    for level in levels:
        for scenario in SCENARIOS:
            group = _group(results, history=level, scenario=scenario, mode="frozen")
            if not group:
                continue
            lines.append(
                f"| {level} | {scenario} | {len(group)} "
                f"| {_median(r.final_dev_spend for r in group):+.1%} "
                f"| {_median(r.final_dev_kpi for r in group):+.1%} "
                f"| {quantile([r.final_ape_kpi for r in group], 0.9):.1%} "
                f"| {sum(r.within_20 for r in group) / len(group):.0%} "
                f"| {quantile([r.mape_kpi for r in group], 0.5):.1%} |"
            )

    by_key = {(r.history, r.scenario, r.world_seed, r.campaign_seed, r.mode): r for r in results}
    lines.append("\n## Traffic manager: KPI delivered on the approved plan\n")
    lines.append(
        "Same plan, same world, same shock; the live mode is the only difference. KPI uplift is "
        "the fact KPI of the live mode relative to frozen execution; budget use is fact spend "
        "over the approved budget; reallocated is the share of budget moved away from approved "
        "caps; closeness is the absolute final deviation from the plan.\n"
    )
    lines.append(
        "| History | Scenario | Live mode | Pairs | KPI uplift vs frozen p50 | More KPI than frozen "
        "| Budget use p50 | Reallocated p50 | Closeness to plan p50 | Frozen closeness p50 |"
    )
    lines.append("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for level in levels:
        for scenario in SCENARIOS:
            for mode in live_modes:
                pairs = [
                    (by_key[(level, scenario, r.world_seed, r.campaign_seed, "frozen")], r)
                    for r in _group(results, history=level, scenario=scenario, mode=mode)
                    if (level, scenario, r.world_seed, r.campaign_seed, "frozen") in by_key
                ]
                if not pairs:
                    continue
                uplift = [a.fact_kpi / f.fact_kpi - 1.0 for f, a in pairs if f.fact_kpi > 0]
                lines.append(
                    f"| {level} | {scenario} | {mode} | {len(pairs)} "
                    f"| {_median(uplift):+.1%} "
                    f"| {sum(u > 0 for u in uplift) / len(pairs):.0%} "
                    f"| {_median(a.budget_utilization for _, a in pairs):.1%} "
                    f"| {_median(a.reallocated_share for _, a in pairs):.1%} "
                    f"| {_median(a.final_ape_kpi for _, a in pairs):.1%} "
                    f"| {_median(f.final_ape_kpi for f, _ in pairs):.1%} |"
                )

    if len(live_modes) >= 2:
        lines.append("\n## Live modes head to head (same seeds, shock and history)\n")
        lines.append(
            "| History | Scenario | Pairs | "
            + " | ".join(f"{m} KPI p50" for m in live_modes)
            + " | Best mode by KPI |"
        )
        lines.append("|---:|---|---:|" + "---:|" * len(live_modes) + "---|")
        for level in levels:
            for scenario in SCENARIOS:
                keys = {
                    (r.world_seed, r.campaign_seed)
                    for r in _group(results, history=level, scenario=scenario, mode=live_modes[0])
                }
                keys = {
                    k
                    for k in keys
                    if all((level, scenario, k[0], k[1], m) in by_key for m in live_modes)
                }
                if not keys:
                    continue
                medians = {
                    m: _median(by_key[(level, scenario, w, c, m)].fact_kpi for w, c in keys)
                    for m in live_modes
                }
                wins = {
                    m: sum(
                        max(live_modes, key=lambda x: by_key[(level, scenario, w, c, x)].fact_kpi)
                        == m
                        for w, c in keys
                    )
                    for m in live_modes
                }
                best = max(wins, key=lambda m: wins[m])
                lines.append(
                    f"| {level} | {scenario} | {len(keys)} | "
                    + " | ".join(f"{medians[m]:,.0f}" for m in live_modes)
                    + f" | {best} ({wins[best]}/{len(keys)}) |"
                )

    lines.append(
        "\nFinal dev is (fact − plan) / plan at the end of the campaign; the case threshold of 20% "
        "applies to its absolute value for spend and KPI at once (Within 20%). Trajectory error "
        f"is the mean of |fact_t − plan_t| / plan_t over hours after the first "
        f"{brief.trajectory_skip_hours} h. History N means the plan was built with the observable "
        "facts of N earlier campaigns on the same world seed; 0 is the public catalog alone. "
        "Live modes: adaptive_max maximises the remaining KPI every hour (primary live "
        "algorithm); adaptive keeps the approved channel mix while the projected finish is on "
        "plan and moves budget only to get back on plan or to spend what a paused channel cannot "
        "take (conservative variant)."
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def parse_int_list(text: str) -> list[int]:
    values: list[int] = []
    for raw in text.split(","):
        part = raw.strip()
        if not part:
            continue
        if "-" in part:
            low, high = part.split("-", 1)
            values.extend(range(int(low), int(high) + 1))
        else:
            values.append(int(part))
    return values


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--budget", default="1200000", help="campaign budget in currency units")
    parser.add_argument("--days", type=int, default=21)
    parser.add_argument(
        "--optimize", choices=("clicks", "conversions", "unique_reach"), default="conversions"
    )
    parser.add_argument("--start-hour", default="2026-09-07T06:00:00Z")
    parser.add_argument("--time-zone", default="Europe/Moscow")
    parser.add_argument("--world-seeds", default="1-3", help="e.g. 1-5 or 1,4,9")
    parser.add_argument("--campaign-seeds", default="1")
    parser.add_argument("--scenarios", default=",".join(SCENARIOS))
    parser.add_argument("--modes", default=",".join(MODES))
    parser.add_argument(
        "--history-levels",
        default="0,3",
        help="numbers of earlier campaigns the planner learns from; 0 is the catalog alone",
    )
    parser.add_argument(
        "--history-mode",
        choices=(*MODES, "uniform"),
        default="frozen",
        help="how warm-up campaigns were planned and executed; frozen = optimized plans held",
    )
    parser.add_argument(
        "--history-budget-factors",
        default="0.6,1.0,1.4",
        help="budget multipliers cycled over warm-up campaigns",
    )
    parser.add_argument(
        "--history-no-random-events",
        action="store_true",
        help="disable random drift and shocks in warm-up campaigns (on by default)",
    )
    parser.add_argument("--replan-every", type=int, default=1, help="hours between replans")
    parser.add_argument("--pause-hours", type=int, default=72)
    parser.add_argument(
        "--shock-start",
        type=int,
        default=None,
        help="hour the scenario shock starts (default: middle of the campaign)",
    )
    parser.add_argument(
        "--no-recent",
        action="store_true",
        help="ablation: replan without current.recent_hours, so calibration sees no live facts",
    )
    parser.add_argument(
        "--trajectory-skip-hours",
        type=int,
        default=24,
        help="hours excluded from the trajectory error while the cumulative plan is still tiny",
    )
    parser.add_argument(
        "--random-events", action="store_true", help="keep Simulator random drift and shocks"
    )
    parser.add_argument(
        "--strategy",
        choices=("optimized", "uniform"),
        default="optimized",
        help="how the evaluated campaign is planned",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="task B: plan the least budget for this KPI target instead of --budget",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--simulator-bin", default=str(DEFAULT_SIMULATOR_BIN))
    parser.add_argument(
        "--world-config",
        default=str(DEFAULT_WORLD_CONFIG),
        help="Simulator world (Compose default)",
    )
    parser.add_argument(
        "--planner-world-config",
        default=str(DEFAULT_PLANNER_CONFIG),
        help="public catalog the planner reads (Compose default)",
    )
    parser.add_argument("--simulator-port", type=int, default=18080)
    parser.add_argument(
        "--simulator-url", default=None, help="running Simulator instead of spawning (1 worker)"
    )
    parser.add_argument(
        "--planner-url", default=None, help="running Planner instead of the in-process app"
    )
    parser.add_argument("--out", default=str(REPO_ROOT / "tools/evaluation/results"))
    parser.add_argument(
        "--resume", action="store_true", help="keep finished runs in --out and run only the rest"
    )
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="rewrite summary.md from an existing runs.json in --out without running anything",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    os.environ["PLANNER_WORLD_CONFIG"] = args.planner_world_config
    brief = Brief(
        budget_micros=to_micros(args.budget),
        duration_hours=args.days * 24,
        optimize=args.optimize,
        start_hour=args.start_hour,
        time_zone=args.time_zone,
        replan_every=args.replan_every,
        pause_hours=args.pause_hours,
        random_events=args.random_events,
        shock_start=args.shock_start,
        send_recent=not args.no_recent,
        trajectory_skip_hours=args.trajectory_skip_hours,
        history_mode=args.history_mode,
        history_random_events=not args.history_no_random_events,
        history_budget_factors=tuple(float(x) for x in args.history_budget_factors.split(",")),
        strategy=args.strategy,
        target_value=args.target,
    )
    scenarios = [s for s in args.scenarios.split(",") if s]
    modes = [m for m in args.modes.split(",") if m]
    unknown = [s for s in scenarios if s not in SCENARIOS] + [m for m in modes if m not in MODES]
    if unknown:
        raise SystemExit(f"unknown scenario or mode: {unknown}")
    worlds = parse_int_list(args.world_seeds)
    specs = [
        RunSpec(world, campaign, level, scenario, mode)
        for level in parse_int_list(args.history_levels)
        for scenario in scenarios
        for world in worlds
        for campaign in parse_int_list(args.campaign_seeds)
        for mode in modes
    ]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.summarize_only:
        with (out_dir / "runs.json").open() as handle:
            stored = [RunResult(**item) for item in json.load(handle)]
        summary = summarize(stored, brief)
        (out_dir / "summary.md").write_text(summary)
        print(summary)
        return 0
    if not args.resume:
        for stale in out_dir.glob("worker-*.jsonl"):
            stale.unlink()
        for stale in (
            (out_dir / "dataset").glob("worker-*.csv") if (out_dir / "dataset").exists() else []
        ):
            stale.unlink()
    workers = 1 if args.simulator_url else max(1, min(args.workers, len(specs)))
    args_dict = vars(args)
    if not args.simulator_url:
        # Copied once here: workers copying it concurrently raced against each other.
        args_dict["harness_binary"] = str(harness_binary(Path(args.simulator_bin), out_dir))
    started = time.perf_counter()
    print(f"{len(specs)} runs on {workers} worker(s) -> {out_dir}", file=sys.stderr)
    if workers == 1:
        worker_main(0, specs, brief, args_dict, out_dir)
    else:
        # Keep every world seed on one worker so its warm-up history is generated once, and
        # deal adaptive runs (30x slower than frozen) first so that workers finish together.
        buckets: list[list[RunSpec]] = [[] for _ in range(workers)]
        for position, world in enumerate(sorted(worlds)):
            buckets[position % workers].extend(
                sorted(
                    (s for s in specs if s.world_seed == world), key=lambda s: s.mode != "adaptive"
                )
            )
        processes = [
            Process(target=worker_main, args=(index, bucket, brief, args_dict, out_dir))
            for index, bucket in enumerate(buckets)
            if bucket
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join()
        failed = [p.exitcode for p in processes if p.exitcode]
        if failed:
            raise SystemExit(f"worker failures: {failed}")

    results: list[RunResult] = []
    for path in sorted(out_dir.glob("worker-*.jsonl")):
        with path.open() as handle:
            results.extend(RunResult(**json.loads(line)) for line in handle if line.strip())
    results.sort(
        key=lambda r: (
            r.history,
            SCENARIOS.index(r.scenario),
            r.world_seed,
            r.campaign_seed,
            r.mode,
        )
    )
    with (out_dir / "runs.json").open("w") as handle:
        json.dump([asdict(r) for r in results], handle, indent=2)
    with (out_dir / "dataset" / "hourly.csv").open("w", newline="") as merged:
        writer = csv.writer(merged)
        writer.writerow(DATASET_COLUMNS)
        for part in sorted((out_dir / "dataset").glob("worker-*.csv")):
            with part.open() as handle:
                for row in csv.reader(handle):
                    writer.writerow(row)
            part.unlink()
    summary = summarize(results, brief)
    (out_dir / "summary.md").write_text(summary)
    print(summary)
    print(f"done in {time.perf_counter() - started:.0f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
