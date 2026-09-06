"""Experiment B: traffic-manager quality.

The approved plan is fixed; the live mode is the only difference between paired runs on the
same world, campaign seed, history and shock. Frozen execution is the baseline. Metrics per
pair: KPI uplift over frozen, the share of the shock loss recovered, budget use, share of budget
moved away from the approved caps, reaction latency to the shock (hours until the live plan cut
the shocked channel by 20% relative to the same live mode without the shock) and the closeness
to the approved plan (the case metric). Cells cover cold and warm plans, the four scripted
shocks, a noisy world with random market events, ablations of the live loop (no recent facts,
slower replanning), the shock timing and a second KPI.

Usage (from services/planner):

    uv run --group dev python ../../tools/evaluation/tm_eval.py --out ../../tools/evaluation/runs/tm
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVALUATE = HERE / "evaluate.py"
ALL_SCENARIOS = "none,ctr_drop,cpm_spike,supply_drop,pause"
ALL_MODES = "frozen,adaptive,adaptive_max"
REACTION_CUT = 0.2
REACTION_SMOOTH_HOURS = 6


@dataclass(frozen=True)
class Cell:
    name: str
    history_levels: str = "3"
    scenarios: str = ALL_SCENARIOS
    modes: str = ALL_MODES
    optimize: str = "conversions"
    random_events: bool = False
    no_recent: bool = False
    replan_every: int = 1
    shock_start: int | None = None

    def args(self) -> list[str]:
        args = [
            "--optimize",
            self.optimize,
            "--budget",
            "1200000",
            "--days",
            "21",
            "--history-levels",
            self.history_levels,
            "--history-mode",
            "frozen",
            "--scenarios",
            self.scenarios,
            "--modes",
            self.modes,
            "--replan-every",
            str(self.replan_every),
        ]
        if self.random_events:
            args.append("--random-events")
        if self.no_recent:
            args.append("--no-recent")
        if self.shock_start is not None:
            args += ["--shock-start", str(self.shock_start)]
        return args


CELLS = [
    Cell("modes-h3"),
    Cell("modes-h0", history_levels="0"),
    Cell("noisy-h3", scenarios="none", modes="frozen,adaptive_max", random_events=True),
    Cell(
        "noisy-h0",
        history_levels="0",
        scenarios="none",
        modes="frozen,adaptive_max",
        random_events=True,
    ),
    Cell("ablate-no-recent-h3", scenarios="none,ctr_drop", modes="adaptive_max", no_recent=True),
    Cell("cadence-6h-h3", scenarios="none,ctr_drop", modes="adaptive_max", replan_every=6),
    Cell("cadence-24h-h3", scenarios="none,ctr_drop", modes="adaptive_max", replan_every=24),
    Cell("shock-early-h3", scenarios="ctr_drop", modes="frozen,adaptive_max", shock_start=120),
    Cell("shock-late-h3", scenarios="ctr_drop", modes="frozen,adaptive_max", shock_start=400),
    Cell("clicks-h3", scenarios="none,ctr_drop", modes="frozen,adaptive_max", optimize="clicks"),
]


def run_cell(cell: Cell, out_dir: Path, common: list[str]) -> None:
    target = out_dir / cell.name
    if (target / "runs.json").exists():
        print(f"[{cell.name}] cached", file=sys.stderr)
        return
    command = [sys.executable, str(EVALUATE), *cell.args(), *common, "--out", str(target)]
    print(f"[{cell.name}] {' '.join(cell.args())}", file=sys.stderr, flush=True)
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)


def load_runs(out_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in CELLS:
        path = out_dir / cell.name / "runs.json"
        if not path.exists():
            continue
        for run in json.loads(path.read_text()):
            run.update(
                cell=cell.name,
                optimize=cell.optimize,
                random_events=cell.random_events,
                no_recent=cell.no_recent,
                replan_every=cell.replan_every,
            )
            rows.append(run)
    return rows


def top_caps(out_dir: Path, run: dict[str, Any]) -> list[float]:
    path = out_dir / run["cell"] / "trajectories" / f"{run['run_id']}.csv"
    if not path.exists():
        return []
    with path.open() as handle:
        return [float(row["top_cap"] or 0.0) for row in csv.DictReader(handle)]


def reaction_hours(shocked: list[float], calm: list[float], start: int) -> int | None:
    """Hours after the shock until the smoothed cap ratio (shocked run / calm run of the same
    live mode) drops by REACTION_CUT. The two runs are identical before the shock."""
    ratio = [s / c if c > 0 else 1.0 for s, c in zip(shocked, calm, strict=False)]
    for hour in range(start, len(ratio)):
        window = ratio[max(start, hour - REACTION_SMOOTH_HOURS + 1) : hour + 1]
        if sum(window) / len(window) <= 1 - REACTION_CUT:
            return hour - start
    return None


def key(run: dict[str, Any], *fields: str) -> tuple[Any, ...]:
    return tuple(run[f] for f in fields)


PAIR_FIELDS = ("cell", "world_seed", "campaign_seed", "history", "scenario")


def pair_rows(out_dir: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per live run, joined with its frozen twin and the calm twins for reaction."""
    by_mode = {key(r, *PAIR_FIELDS, "mode"): r for r in rows}
    pairs: list[dict[str, Any]] = []
    for run in rows:
        if run["mode"] == "frozen":
            continue
        frozen = by_mode.get(key(run, *PAIR_FIELDS, "mode")[:-1] + ("frozen",))
        if frozen is None:
            continue
        calm_key = key(run, "cell", "world_seed", "campaign_seed", "history") + ("none",)
        # A cell without the calm scenario (shock timing) borrows it from the base cell: the
        # calm run does not depend on when a shock would have started.
        base_key = (f"modes-h{run['history']}",) + calm_key[1:]
        frozen_calm = by_mode.get(calm_key + ("frozen",)) or by_mode.get(base_key + ("frozen",))
        live_calm = by_mode.get(calm_key + (run["mode"],)) or by_mode.get(base_key + (run["mode"],))
        recovered = None
        if run["scenario"] != "none" and frozen_calm is not None:
            loss = frozen_calm["fact_kpi"] - frozen["fact_kpi"]
            recovered = (run["fact_kpi"] - frozen["fact_kpi"]) / loss if loss > 0 else None
        reaction = None
        if run["scenario"] != "none" and live_calm is not None and run["shock_start"] is not None:
            reaction = reaction_hours(
                top_caps(out_dir, run), top_caps(out_dir, live_calm), run["shock_start"]
            )
        pairs.append(
            {
                **{f: run[f] for f in PAIR_FIELDS},
                "mode": run["mode"],
                "optimize": run["optimize"],
                "random_events": run["random_events"],
                "no_recent": run["no_recent"],
                "replan_every": run["replan_every"],
                "shock_start": run["shock_start"],
                "kpi_frozen": frozen["fact_kpi"],
                "kpi_live": run["fact_kpi"],
                "uplift": run["fact_kpi"] / frozen["fact_kpi"] - 1 if frozen["fact_kpi"] else None,
                "recovered": recovered,
                "reaction_hours": reaction,
                "budget_use": run["budget_utilization"],
                "budget_use_frozen": frozen["budget_utilization"],
                "reallocated": run["reallocated_share"],
                "top_spend_ratio": (
                    run["top_spend_after"] / frozen["top_spend_after"]
                    if run["top_spend_after"] is not None and frozen["top_spend_after"]
                    else None
                ),
                "dev_kpi": run["final_dev_kpi"],
                "dev_kpi_frozen": frozen["final_dev_kpi"],
                "dev_spend": run["final_dev_spend"],
            }
        )
    return pairs


def q(values: list[float], share: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    position = share * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


HEADER = (
    "| Slice | Pairs | Uplift p50 | Uplift p10 | Wins | Recovered p50 | Reaction h p50 "
    "| Reacted | Reallocated p50 | Budget use p50 | |Dev KPI| p50 |\n"
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
)


def pair_row(label: str, pairs: list[dict[str, Any]]) -> str:
    if not pairs:
        return ""
    uplift = [p["uplift"] for p in pairs if p["uplift"] is not None]
    recovered = [p["recovered"] for p in pairs if p["recovered"] is not None]
    reaction = [p["reaction_hours"] for p in pairs if p["reaction_hours"] is not None]
    shocked = [p for p in pairs if p["scenario"] != "none"]
    wins = sum(v > 0 for v in uplift) / len(uplift) if uplift else float("nan")
    fmt_recovered = f"{statistics.median(recovered):+.0%}" if recovered else "—"
    fmt_reaction = f"{statistics.median(reaction):.0f}" if reaction else "—"
    fmt_reacted = f"{len(reaction) / len(shocked):.0%}" if shocked else "—"
    return (
        f"| {label} | {len(pairs)} | {q(uplift, 0.5):+.1%} | {q(uplift, 0.1):+.1%} | {wins:.0%} "
        f"| {fmt_recovered} | {fmt_reaction} | {fmt_reacted} "
        f"| {statistics.median(p['reallocated'] for p in pairs):.0%} "
        f"| {statistics.median(p['budget_use'] for p in pairs):.1%} "
        f"| {statistics.median(abs(p['dev_kpi']) for p in pairs):.1%} |"
    )


def section(lines: list[str], title: str, groups: list[tuple[str, list[dict[str, Any]]]]) -> None:
    lines.append(f"\n## {title}\n")
    lines.append(HEADER)
    for label, group in groups:
        row = pair_row(label, group)
        if row:
            lines.append(row)


def summarize(pairs: list[dict[str, Any]]) -> str:
    lines = ["# Experiment B: traffic-manager quality (paired with frozen execution)\n"]
    scenarios = ALL_SCENARIOS.split(",")
    for h in (3, 0):
        cell = f"modes-h{h}"
        section(
            lines,
            f"Live modes by shock (conversions, 1.2M, 21 d, history {h})",
            [
                (
                    f"{m} · {s}",
                    [
                        p
                        for p in pairs
                        if p["cell"] == cell and p["mode"] == m and p["scenario"] == s
                    ],
                )
                for m in ("adaptive", "adaptive_max")
                for s in scenarios
            ]
            + [
                (f"{m} · all shocks", [p for p in pairs if p["cell"] == cell and p["mode"] == m])
                for m in ("adaptive", "adaptive_max")
            ],
        )
    section(
        lines,
        "Noisy world: random market events on, no scripted shock",
        [
            (
                f"{m} · history {h}",
                [p for p in pairs if p["cell"] == f"noisy-h{h}" and p["mode"] == m],
            )
            for h in (3, 0)
            for m in ("adaptive", "adaptive_max")
        ],
    )
    section(
        lines,
        "Ablations of the live loop (adaptive_max, history 3)",
        [
            (
                f"{label} · {s}",
                [
                    p
                    for p in pairs
                    if p["cell"] == cell and p["mode"] == "adaptive_max" and p["scenario"] == s
                ],
            )
            for label, cell in (
                ("hourly, with recent facts", "modes-h3"),
                ("hourly, no recent facts", "ablate-no-recent-h3"),
                ("every 6 h", "cadence-6h-h3"),
                ("every 24 h", "cadence-24h-h3"),
            )
            for s in ("none", "ctr_drop")
        ],
    )
    section(
        lines,
        "Shock timing (CTR −40 % on the top channel, adaptive_max, history 3)",
        [
            (
                label,
                [
                    p
                    for p in pairs
                    if p["cell"] == cell
                    and p["mode"] == "adaptive_max"
                    and p["scenario"] == "ctr_drop"
                ],
            )
            for label, cell in (
                ("hour 120 (day 6)", "shock-early-h3"),
                ("hour 252 (day 11)", "modes-h3"),
                ("hour 400 (day 17)", "shock-late-h3"),
            )
        ],
    )
    section(
        lines,
        "KPI = clicks (history 3)",
        [
            (
                f"{m} · {s}",
                [
                    p
                    for p in pairs
                    if p["cell"] == "clicks-h3" and p["mode"] == m and p["scenario"] == s
                ],
            )
            for m in ("adaptive", "adaptive_max")
            for s in ("none", "ctr_drop")
        ],
    )
    lines.append(
        "\nUplift is the live mode's fact KPI over frozen execution of the same approved plan on "
        "the same world, seed and shock; wins is the share of pairs with positive uplift. "
        "Recovered is the share of the KPI the shock took from frozen execution that the live "
        "mode won back: (live − frozen_shock) / (frozen_calm − frozen_shock). Reaction is the "
        "number of hours after the shock until the live plan cut the shocked channel's cap by "
        "20 % relative to the same live mode without the shock (6 h smoothing); reacted is the "
        "share of shocked pairs where that happened at all. Reallocated is the share of budget "
        "moved away from the approved caps. |Dev KPI| is the case metric of the live run: its "
        "final deviation from the approved plan."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", default=str(HERE / "runs" / "tm"))
    parser.add_argument("--world-seeds", default="1-8")
    parser.add_argument("--campaign-seeds", default="1,2")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--simulator-port", type=int, default=19080)
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    common = [
        "--world-seeds",
        args.world_seeds,
        "--campaign-seeds",
        args.campaign_seeds,
        "--workers",
        str(args.workers),
        "--simulator-port",
        str(args.simulator_port),
    ]
    if not args.summarize_only:
        for cell in CELLS:
            run_cell(cell, out_dir, common)
    rows = load_runs(out_dir)
    (out_dir / "all_runs.json").write_text(json.dumps(rows))
    pairs = pair_rows(out_dir, rows)
    (out_dir / "pairs.json").write_text(json.dumps(pairs))
    summary = summarize(pairs)
    (out_dir / "summary.md").write_text(summary)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
