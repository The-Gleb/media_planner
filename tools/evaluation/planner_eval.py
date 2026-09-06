"""Experiment A: how honest is the planner's forecast.

Every cell executes the approved plan frozen, so the deviation of the fact from the plan is the
forecast error alone. Cells vary the knowledge source (catalog, 1/3/5 past campaigns), the KPI,
the budget, the horizon, the planning strategy (optimized versus a uniform "spreadsheet" split),
the warm-up style, and task B (target -> budget). Results of all cells are aggregated into one
`all_runs.json`, a calibration table and `summary.md`.

Run from services/planner:
    uv run --group dev python ../../tools/evaluation/planner_eval.py --out ../../tools/evaluation/runs/planner
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVALUATE = HERE / "evaluate.py"


@dataclass(frozen=True)
class Cell:
    name: str
    optimize: str = "conversions"
    budget: int = 1_200_000
    days: int = 21
    strategy: str = "optimized"
    history_levels: str = "0,3"
    history_mode: str = "frozen"
    target: int | None = None

    def args(self) -> list[str]:
        args = [
            "--optimize",
            self.optimize,
            "--days",
            str(self.days),
            "--strategy",
            self.strategy,
            "--history-levels",
            self.history_levels,
            "--history-mode",
            self.history_mode,
            "--scenarios",
            "none",
            "--modes",
            "frozen",
        ]
        args += (
            ["--target", str(self.target)]
            if self.target is not None
            else ["--budget", str(self.budget)]
        )
        return args


CELLS = [
    Cell("core-conversions-1.2M", history_levels="0,1,3,5"),
    Cell("core-clicks-1.2M", optimize="clicks"),
    Cell("core-reach-1.2M", optimize="unique_reach"),
    Cell("budget-conversions-0.5M", budget=500_000),
    Cell("budget-conversions-3M", budget=3_000_000),
    Cell("budget-clicks-0.5M", optimize="clicks", budget=500_000),
    Cell("budget-clicks-3M", optimize="clicks", budget=3_000_000),
    Cell("horizon-conversions-14d", days=14),
    Cell("uniform-conversions-1.2M", strategy="uniform"),
    Cell("warmup-uniform-conversions-1.2M", history_levels="3", history_mode="uniform"),
    Cell("taskB-clicks-50k-14d", optimize="clicks", days=14, target=50_000),
    Cell("taskB-conversions-2k-21d", optimize="conversions", days=21, target=2_000),
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
                budget_level=cell.budget,
                days=cell.days,
                strategy=cell.strategy,
                history_mode=cell.history_mode,
            )
            rows.append(run)
    return rows


def channel_ratios(out_dir: Path, cell: Cell, run: dict[str, Any]) -> list[dict[str, Any]]:
    """Fact / plan per channel for impressions, CTR, CR, CPM of one frozen run."""
    approved = (
        out_dir / cell.name / "approved" / f"world-{run['world_seed']}-h{run['history']}.json"
    )
    if not approved.exists():
        return []
    plan = json.loads(approved.read_text())
    expected: dict[str, dict[str, float]] = {}
    for item in plan["allocations"]:
        e = item["expected"]
        if e is None:
            continue
        d = expected.setdefault(
            item["channel_id"], {"spend": 0.0, "imp": 0.0, "clicks": 0.0, "conv": 0.0}
        )
        d["spend"] += float(e["spend"])
        d["imp"] += float(e["impressions"])
        d["clicks"] += float(e["clicks"])
        d["conv"] += float(e["conversions"])
    rows = []
    for channel, d in expected.items():
        f = run["channel_facts"].get(channel)
        if not f or d["imp"] < 1000 or f["impressions"] < 1000 or d["clicks"] <= 0:
            continue
        rows.append(
            {
                "cell": cell.name,
                "world_seed": run["world_seed"],
                "history": run["history"],
                "channel": channel,
                "plan_spend": d["spend"],
                "impressions": f["impressions"] / d["imp"],
                "ctr": (f["clicks"] / f["impressions"]) / (d["clicks"] / d["imp"]),
                "cr": (f["conversions"] / max(f["clicks"], 1)) / (d["conv"] / d["clicks"])
                if d["conv"] > 0
                else None,
                "cpm": (run["channel_spend"][channel] / f["impressions"]) / (d["spend"] / d["imp"]),
            }
        )
    return rows


def q(values: list[float], share: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    position = share * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def dev_row(label: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    kpi = [r["final_dev_kpi"] for r in rows]
    abs_kpi = [abs(v) for v in kpi]
    spend = [r["final_dev_spend"] for r in rows]
    within = sum(
        abs(r["final_dev_kpi"]) <= 0.2 and abs(r["final_dev_spend"]) <= 0.2 for r in rows
    ) / len(rows)
    return (
        f"| {label} | {len(rows)} | {statistics.median(spend):+.1%} | {statistics.median(kpi):+.1%} "
        f"| {q(abs_kpi, 0.5):.1%} | {q(abs_kpi, 0.9):.1%} | {within:.0%} |"
    )


def summarize(out_dir: Path, rows: list[dict[str, Any]]) -> str:
    lines = ["# Experiment A: planner forecast accuracy (frozen execution)\n"]
    header = "| Slice | Runs | Dev spend p50 | Dev KPI p50 | |Dev KPI| p50 | |Dev KPI| p90 | Within 20% |\n|---|---:|---:|---:|---:|---:|---:|"

    def section(title: str, groups: list[tuple[str, list[dict[str, Any]]]]) -> None:
        lines.append(f"\n## {title}\n")
        lines.append(header)
        for label, group in groups:
            line = dev_row(label, group)
            if line:
                lines.append(line)

    core = [r for r in rows if r["cell"] == "core-conversions-1.2M"]
    section(
        "Knowledge source (conversions, 1.2M, 21 d)",
        [(f"history {h}", [r for r in core if r["history"] == h]) for h in (0, 1, 3, 5)],
    )
    section(
        "KPI (1.2M, 21 d)",
        [
            (
                f"{o} · history {h}",
                [
                    r
                    for r in rows
                    if r["cell"].startswith(("core-",)) and r["optimize"] == o and r["history"] == h
                ],
            )
            for o in ("conversions", "clicks", "unique_reach")
            for h in (0, 3)
        ],
    )
    section(
        "Budget (21 d)",
        [
            (
                f"{o} · {b / 1e6:.1f}M · history {h}",
                [
                    r
                    for r in rows
                    if r["strategy"] == "optimized"
                    and r["target"] is None
                    and r["days"] == 21
                    and r["history_mode"] == "frozen"
                    and r["optimize"] == o
                    and r["budget_level"] == b
                    and r["history"] == h
                ],
            )
            for o in ("conversions", "clicks")
            for b in (500_000, 1_200_000, 3_000_000)
            for h in (0, 3)
        ],
    )
    section(
        "Horizon (conversions, 1.2M)",
        [
            (
                f"{d} d · history {h}",
                [
                    r
                    for r in rows
                    if r["optimize"] == "conversions"
                    and r["budget_level"] == 1_200_000
                    and r["strategy"] == "optimized"
                    and r["target"] is None
                    and r["history_mode"] == "frozen"
                    and r["days"] == d
                    and r["history"] == h
                ],
            )
            for d in (14, 21)
            for h in (0, 3)
        ],
    )
    section(
        "Strategy (conversions, 1.2M, 21 d)",
        [
            (
                f"{s} · history {h}",
                [
                    r
                    for r in rows
                    if r["cell"] in ("core-conversions-1.2M", "uniform-conversions-1.2M")
                    and r["strategy"] == s
                    and r["history"] == h
                ],
            )
            for s in ("optimized", "uniform")
            for h in (0, 3)
        ],
    )
    section(
        "Warm-up style (conversions, 1.2M, 21 d, history 3)",
        [
            (
                m,
                [
                    r
                    for r in rows
                    if r["optimize"] == "conversions"
                    and r["budget_level"] == 1_200_000
                    and r["days"] == 21
                    and r["strategy"] == "optimized"
                    and r["target"] is None
                    and r["history"] == 3
                    and r["history_mode"] == m
                ],
            )
            for m in ("frozen", "uniform")
        ],
    )

    lines.append("\n## Task B: target -> budget -> frozen execution\n")
    lines.append(
        "| Cell | History | Runs | Target hit (fact ≥ target) | Fact / target p50 | Fact / target p90 | Required budget p50 |\n|---|---:|---:|---:|---:|---:|---:|"
    )
    for cell in CELLS:
        if cell.target is None:
            continue
        for h in (0, 3):
            group = [r for r in rows if r["cell"] == cell.name and r["history"] == h]
            if not group:
                continue
            ratio = [r["fact_kpi"] / r["target"] for r in group]
            lines.append(
                f"| {cell.name} | {h} | {len(group)} | {sum(v >= 1.0 for v in ratio) / len(group):.0%} "
                f"| {q(ratio, 0.5):.2f} | {q(ratio, 0.9):.2f} | {statistics.median(r['required_budget'] for r in group):,.0f} |"
            )

    lines.append(
        "\n## Error decomposition per channel (conversions, 1.2M, 21 d), fact / plan medians\n"
    )
    lines.append(
        "| History | Rows | Impressions | CTR | CR | CPM |\n|---:|---:|---:|---:|---:|---:|"
    )
    cell = CELLS[0]
    for h in (0, 1, 3, 5):
        ratios = [x for r in core if r["history"] == h for x in channel_ratios(out_dir, cell, r)]
        if not ratios:
            continue

        def med(key: str, items: list[dict[str, Any]] = ratios) -> float:
            return float(statistics.median(x[key] for x in items if x[key] is not None))

        lines.append(
            f"| {h} | {len(ratios)} | {med('impressions'):.2f} | {med('ctr'):.2f} | {med('cr'):.2f} | {med('cpm'):.2f} |"
        )
    lines.append(
        "\nDev is (fact − plan) / plan at the end of the campaign; the case threshold of 20% applies to "
        "spend and KPI at once. History N = the plan was built from N earlier campaigns on the same "
        "world seed (0 = public catalog). Task B plans the least budget for the target and then "
        "executes it frozen; fact / target > 1 means the planner reserved more budget than needed."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", default=str(HERE / "runs" / "planner"))
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
    calibration = [
        {
            k: r[k]
            for k in (
                "cell",
                "optimize",
                "budget_level",
                "days",
                "strategy",
                "history",
                "world_seed",
                "campaign_seed",
                "plan_kpi",
                "fact_kpi",
                "plan_spend",
                "fact_spend",
                "final_dev_kpi",
                "final_dev_spend",
                "target",
                "required_budget",
            )
        }
        for r in rows
    ]
    (out_dir / "calibration.json").write_text(json.dumps(calibration))
    summary = summarize(out_dir, rows)
    (out_dir / "summary.md").write_text(summary)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
