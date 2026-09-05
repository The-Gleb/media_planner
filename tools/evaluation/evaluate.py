"""Frozen-versus-adaptive evaluation harness for the Media Planner.

The harness reproduces the dashboard loop headlessly: it approves one optimized plan at revision
zero, then executes it in the Simulator either with frozen caps (the approved schedule is never
changed) or adaptively (every committed hour is fed back to Planner and the returned caps are used
for the next hour). Both modes run on identical world and campaign seeds and identical controlled
shocks, so the only difference between them is the hourly replanning.

Planner is exercised through its HTTP boundary in-process (FastAPI test client) to keep the run
fast; Simulator runs as the real Go binary, one process per worker, because a Simulator process
holds a single simulation resource.

Example:

    cd services/planner
    uv run --group dev python ../../tools/evaluation/evaluate.py \
        --world-seeds 1-5 --campaign-seeds 1,2 --workers 4 --out ../../tools/evaluation/results
"""

from __future__ import annotations

import argparse
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
from decimal import Decimal
from multiprocessing import Process
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIMULATOR_BIN = REPO_ROOT / "services/simulator/bin/simulator"
DEFAULT_WORLD_CONFIG = REPO_ROOT / "services/simulator/configs/world-config.mediaplan.json"
MICROS = 1_000_000
SCENARIOS = ("none", "ctr_drop", "cpm_spike", "supply_drop", "pause")
MODES = ("frozen", "adaptive")
SHOCK_MULTIPLIERS = {"ctr_drop": 0.6, "cpm_spike": 1.6, "supply_drop": 0.5}


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


@dataclass(frozen=True)
class RunSpec:
    world_seed: int
    campaign_seed: int
    scenario: str
    mode: str

    @property
    def run_id(self) -> str:
        return f"w{self.world_seed}-c{self.campaign_seed}-{self.scenario}-{self.mode}"


@dataclass
class RunResult:
    run_id: str
    world_seed: int
    campaign_seed: int
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

    def __init__(self, body: dict[str, Any], channels: Sequence[str], optimize: str) -> None:
        self.plan_id: str = body["plan_id"]
        self.channels = list(channels)
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


def mape(plan: Sequence[float], fact: Sequence[float]) -> float:
    errors = [abs(f - p) / p for p, f in zip(plan, fact, strict=True) if p > 0]
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


# --------------------------------------------------------------------------------------
# Campaign execution
# --------------------------------------------------------------------------------------


def scenario_events(
    scenario: str, channel: str, duration: int, pause_hours: int
) -> list[dict[str, Any]]:
    if scenario == "none":
        return []
    start = duration // 2
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


def plan_request(
    brief: Brief,
    simulation: dict[str, Any],
    channels: Sequence[str],
    facts: dict[str, dict[str, int]],
    current_hour: int,
    last_step_id: str | None,
    last_observed_at: str | None,
) -> dict[str, Any]:
    totals = {
        key: sum(facts[c][key] for c in channels)
        for key in ("spent", "unique_reach", "clicks", "conversions")
    }
    return {
        "request_id": str(uuid.uuid4()),
        "type": "fixed_budget",
        "strategy": "optimized",
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
                    "requests": str(facts[c]["requests"]),
                    "impressions": str(facts[c]["impressions"]),
                    "unique_reach": str(facts[c]["unique_reach"]),
                    "clicks": str(facts[c]["clicks"]),
                    "conversions": str(facts[c]["conversions"]),
                }
                for c in channels
            },
        },
        "budget": money(brief.budget_micros),
        "optimize": brief.optimize,
        "target": None,
    }


def run_campaign(
    spec: RunSpec,
    brief: Brief,
    channels: Sequence[str],
    metadata: dict[str, Any],
    simulator: SimulatorClient,
    planner: PlannerClient,
    approved: PlanView,
    trajectories_dir: Path,
) -> RunResult:
    started = time.perf_counter()
    duration = brief.duration_hours
    simulation = {
        "simulation_id": simulator.simulation_id,
        "world_seed": str(spec.world_seed),
        "campaign_seed": str(spec.campaign_seed),
        "start_hour": brief.start_hour,
        "time_zone": brief.time_zone,
        "currency": metadata["currency"],
        "world_config_digest": metadata["world_config_digest"],
    }
    shocked = approved.top_channel if spec.scenario != "none" else None
    events = scenario_events(spec.scenario, approved.top_channel, duration, brief.pause_hours)
    reset_payload: dict[str, Any] = {
        "world_seed": str(spec.world_seed),
        "campaign_seed": str(spec.campaign_seed),
        "start_hour": brief.start_hour,
        "duration_hours": duration,
        "time_zone": brief.time_zone,
        "disable_random_events": not brief.random_events,
    }
    if events:
        reset_payload["scenario_events"] = events
    simulator.reset(reset_payload)

    facts = {
        c: dict.fromkeys(
            ("spent", "requests", "impressions", "unique_reach", "clicks", "conversions"), 0
        )
        for c in channels
    }
    plan_spend, plan_kpi = approved.cumulative(duration)
    fact_spend: list[float] = []
    fact_kpi: list[float] = []
    current = approved
    replans = 0
    reallocated = 0
    for hour in range(duration):
        actions = current.actions(hour)
        for c in channels:
            reallocated += abs(current.caps[hour][c] - approved.caps[hour][c])
        response = simulator.step(actions)
        for observation in response["observations"]:
            record = facts[observation["channel_id"]]
            record["spent"] += to_micros(observation["spend"])
            for key in ("requests", "impressions", "unique_reach", "clicks", "conversions"):
                record[key] += int(observation[key])
        fact_spend.append(sum(facts[c]["spent"] for c in channels) / MICROS)
        fact_kpi.append(float(sum(facts[c][brief.optimize] for c in channels)))
        next_hour = hour + 1
        if spec.mode == "adaptive" and next_hour < duration and next_hour % brief.replan_every == 0:
            body = plan_request(
                brief,
                simulation,
                channels,
                facts,
                next_hour,
                response["step_id"],
                response["observed_hour"],
            )
            current = PlanView(planner.plan(body), channels, brief.optimize)
            replans += 1

    trajectories_dir.mkdir(parents=True, exist_ok=True)
    with (trajectories_dir / f"{spec.run_id}.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["hour", "plan_spend", "fact_spend", "plan_kpi", "fact_kpi"])
        for hour in range(duration):
            writer.writerow(
                [
                    hour,
                    f"{plan_spend[hour]:.2f}",
                    f"{fact_spend[hour]:.2f}",
                    f"{plan_kpi[hour]:.3f}",
                    f"{fact_kpi[hour]:.0f}",
                ]
            )

    budget = brief.budget_micros / MICROS
    final_spend = abs(final_dev(plan_spend, fact_spend))
    final_kpi = abs(final_dev(plan_kpi, fact_kpi))
    return RunResult(
        run_id=spec.run_id,
        world_seed=spec.world_seed,
        campaign_seed=spec.campaign_seed,
        scenario=spec.scenario,
        mode=spec.mode,
        shocked_channel=shocked,
        budget=budget,
        plan_spend=plan_spend[-1],
        plan_kpi=plan_kpi[-1],
        fact_spend=fact_spend[-1],
        fact_kpi=fact_kpi[-1],
        mape_spend=mape(plan_spend, fact_spend),
        mape_kpi=mape(plan_kpi, fact_kpi),
        final_ape_spend=final_spend,
        final_ape_kpi=final_kpi,
        final_dev_spend=final_dev(plan_spend, fact_spend),
        final_dev_kpi=final_dev(plan_kpi, fact_kpi),
        within_20=final_spend <= 0.2 and final_kpi <= 0.2,
        budget_utilization=fact_spend[-1] / budget if budget else 0.0,
        reallocated_share=reallocated / brief.budget_micros if brief.budget_micros else 0.0,
        replans=replans,
        seconds=time.perf_counter() - started,
        channel_spend={c: facts[c]["spent"] / MICROS for c in channels},
        channel_facts={c: {k: v for k, v in facts[c].items() if k != "spent"} for c in channels},
    )


# --------------------------------------------------------------------------------------
# Worker orchestration
# --------------------------------------------------------------------------------------


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


def approve_plan(
    planner: PlannerClient, brief: Brief, channels: Sequence[str], metadata: dict[str, Any]
) -> tuple[PlanView, dict[str, Any]]:
    simulation = {
        "simulation_id": "eval-approval",
        "world_seed": "0",
        "campaign_seed": "0",
        "start_hour": brief.start_hour,
        "time_zone": brief.time_zone,
        "currency": metadata["currency"],
        "world_config_digest": metadata["world_config_digest"],
    }
    facts = {
        c: dict.fromkeys(
            ("spent", "requests", "impressions", "unique_reach", "clicks", "conversions"), 0
        )
        for c in channels
    }
    body = planner.plan(plan_request(brief, simulation, channels, facts, 0, None, None))
    return PlanView(body, channels, brief.optimize), body


def worker_main(
    index: int,
    specs: list[RunSpec],
    brief: Brief,
    args_dict: dict[str, Any],
    out_dir: Path,
) -> None:
    port = int(args_dict["simulator_port"]) + index
    process = None
    if not args_dict["simulator_url"]:
        process = start_simulator(
            Path(args_dict["simulator_bin"]), Path(args_dict["world_config"]), port
        )
    simulator = SimulatorClient(
        args_dict["simulator_url"] or f"http://127.0.0.1:{port}", f"eval-worker-{index}"
    )
    try:
        wait_ready(simulator)
        metadata = simulator.metadata()
        channels = sorted(metadata["channel_ids"])
        planner = PlannerClient(args_dict["planner_url"])
        approved, _ = approve_plan(planner, brief, channels, metadata)
        with (out_dir / f"worker-{index}.jsonl").open("w") as handle:
            for position, spec in enumerate(specs, start=1):
                result = run_campaign(
                    spec,
                    brief,
                    channels,
                    metadata,
                    simulator,
                    planner,
                    approved,
                    out_dir / "trajectories",
                )
                handle.write(json.dumps(asdict(result)) + "\n")
                handle.flush()
                print(
                    f"[worker {index}] {position}/{len(specs)} {spec.run_id}: "
                    f"MAPE spend {result.mape_spend:.1%} kpi {result.mape_kpi:.1%} "
                    f"final kpi {result.final_dev_kpi:+.1%} ({result.seconds:.0f}s)",
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


def _median(values: Iterable[float]) -> float:
    items = list(values)
    return statistics.median(items) if items else float("nan")


def summarize(results: list[RunResult], brief: Brief, approved_body: dict[str, Any] | None) -> str:
    lines: list[str] = []
    lines.append("# Frozen vs adaptive evaluation\n")
    lines.append(
        f"Budget {brief.budget_micros / MICROS:,.0f}, horizon {brief.duration_hours} h, "
        f"KPI `{brief.optimize}`, replan every {brief.replan_every} h, "
        f"random market events {'on' if brief.random_events else 'off'}, {len(results)} runs.\n"
    )
    if approved_body is not None:
        expected = approved_body["expected"]
        lines.append(
            f"Approved plan: expected spend {float(expected['spend']):,.0f}, "
            f"expected {brief.optimize} {int(expected[brief.optimize]):,}.\n"
        )
    lines.append("## Per scenario and mode\n")
    lines.append(
        "| Scenario | Mode | Runs | MAPE spend p50 | MAPE spend p90 | MAPE KPI p50 | MAPE KPI p90 "
        "| Final dev spend p50 | Final dev KPI p50 | Within 20% | Reallocated p50 |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for scenario in SCENARIOS:
        for mode in MODES:
            group = [r for r in results if r.scenario == scenario and r.mode == mode]
            if not group:
                continue
            lines.append(
                f"| {scenario} | {mode} | {len(group)} "
                f"| {quantile([r.mape_spend for r in group], 0.5):.1%} "
                f"| {quantile([r.mape_spend for r in group], 0.9):.1%} "
                f"| {quantile([r.mape_kpi for r in group], 0.5):.1%} "
                f"| {quantile([r.mape_kpi for r in group], 0.9):.1%} "
                f"| {_median(r.final_dev_spend for r in group):+.1%} "
                f"| {_median(r.final_dev_kpi for r in group):+.1%} "
                f"| {sum(r.within_20 for r in group) / len(group):.0%} "
                f"| {_median(r.reallocated_share for r in group):.1%} |"
            )
    lines.append("\n## Paired comparison (same seeds and shock)\n")
    lines.append(
        "| Scenario | Pairs | Δ MAPE KPI p50 (adaptive − frozen) | Δ MAPE spend p50 "
        "| Adaptive closer on KPI | Adaptive closer on spend |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    by_key = {(r.scenario, r.world_seed, r.campaign_seed, r.mode): r for r in results}
    for scenario in SCENARIOS:
        pairs = [
            (by_key[(scenario, r.world_seed, r.campaign_seed, "frozen")], r)
            for r in results
            if r.scenario == scenario
            and r.mode == "adaptive"
            and (scenario, r.world_seed, r.campaign_seed, "frozen") in by_key
        ]
        if not pairs:
            continue
        delta_kpi = [a.mape_kpi - f.mape_kpi for f, a in pairs]
        delta_spend = [a.mape_spend - f.mape_spend for f, a in pairs]
        lines.append(
            f"| {scenario} | {len(pairs)} | {_median(delta_kpi):+.1%} | {_median(delta_spend):+.1%} "
            f"| {sum(d < 0 for d in delta_kpi) / len(pairs):.0%} "
            f"| {sum(d < 0 for d in delta_spend) / len(pairs):.0%} |"
        )
    lines.append(
        "\nMAPE is the mean absolute percentage error of the cumulative fact against the cumulative "
        "approved-plan trajectory over all hours; final dev is the signed deviation at the end of "
        "the campaign; reallocated is the share of the budget moved away from approved caps."
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def parse_int_list(text: str) -> list[int]:
    values: list[int] = []
    for part in text.split(","):
        part = part.strip()
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
        "--replan-every", type=int, default=1, help="hours between adaptive replans"
    )
    parser.add_argument("--pause-hours", type=int, default=72)
    parser.add_argument(
        "--random-events", action="store_true", help="keep Simulator random drift and shocks"
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--simulator-bin", default=str(DEFAULT_SIMULATOR_BIN))
    parser.add_argument("--world-config", default=str(DEFAULT_WORLD_CONFIG))
    parser.add_argument(
        "--simulator-port", type=int, default=18080, help="first port for spawned Simulators"
    )
    parser.add_argument(
        "--simulator-url",
        default=None,
        help="use a running Simulator instead of spawning (forces --workers 1)",
    )
    parser.add_argument(
        "--planner-url", default=None, help="use a running Planner instead of the in-process app"
    )
    parser.add_argument("--out", default=str(REPO_ROOT / "tools/evaluation/results"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    os.environ.setdefault("PLANNER_WORLD_CONFIG", args.world_config)
    brief = Brief(
        budget_micros=to_micros(args.budget),
        duration_hours=args.days * 24,
        optimize=args.optimize,
        start_hour=args.start_hour,
        time_zone=args.time_zone,
        replan_every=args.replan_every,
        pause_hours=args.pause_hours,
        random_events=args.random_events,
    )
    scenarios = [s for s in args.scenarios.split(",") if s]
    modes = [m for m in args.modes.split(",") if m]
    unknown = [s for s in scenarios if s not in SCENARIOS] + [m for m in modes if m not in MODES]
    if unknown:
        raise SystemExit(f"unknown scenario or mode: {unknown}")
    specs = [
        RunSpec(world, campaign, scenario, mode)
        for scenario in scenarios
        for world in parse_int_list(args.world_seeds)
        for campaign in parse_int_list(args.campaign_seeds)
        for mode in modes
    ]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("worker-*.jsonl"):
        stale.unlink()
    workers = 1 if args.simulator_url else max(1, min(args.workers, len(specs)))
    args_dict = vars(args)
    started = time.perf_counter()
    print(f"{len(specs)} runs on {workers} worker(s) -> {out_dir}", file=sys.stderr)
    if workers == 1:
        worker_main(0, specs, brief, args_dict, out_dir)
    else:
        # Adaptive runs are ~30x slower than frozen ones; deal them out first so that every
        # worker receives an equal share of the slow runs.
        balanced = sorted(specs, key=lambda item: item.mode != "adaptive")
        processes = [
            Process(
                target=worker_main,
                args=(index, balanced[index::workers], brief, args_dict, out_dir),
            )
            for index in range(workers)
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
    results.sort(key=lambda r: (SCENARIOS.index(r.scenario), r.world_seed, r.campaign_seed, r.mode))
    with (out_dir / "runs.json").open("w") as handle:
        json.dump([asdict(r) for r in results], handle, indent=2)

    approved_body: dict[str, Any] | None = None
    if not args.simulator_url:
        planner = PlannerClient(args.planner_url)
        probe = start_simulator(
            Path(args.simulator_bin), Path(args.world_config), args.simulator_port
        )
        try:
            client = SimulatorClient(f"http://127.0.0.1:{args.simulator_port}")
            wait_ready(client)
            metadata = client.metadata()
            _, approved_body = approve_plan(
                planner, brief, sorted(metadata["channel_ids"]), metadata
            )
            with (out_dir / "approved-plan.json").open("w") as handle:
                json.dump(approved_body, handle)
        finally:
            probe.terminate()
            probe.wait(timeout=5)
    summary = summarize(results, brief, approved_body)
    (out_dir / "summary.md").write_text(summary)
    print(summary)
    print(f"done in {time.perf_counter() - started:.0f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
