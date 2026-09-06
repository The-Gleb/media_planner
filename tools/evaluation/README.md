# Evaluation harness: history, frozen and adaptive

`evaluate.py` measures the case metric headlessly: deviation of cumulative spend and of the main
KPI from the approved plan trajectory. It varies two factors independently on identical seeds and
shocks: how much campaign history the planner had when the plan was approved (cold catalog versus
warm history), and whether execution replans every hour (adaptive) or keeps the approved caps
(frozen).

```text
approved optimized plan (revision 0)
              │
      ┌───────┼──────────────────┐
   frozen   adaptive          adaptive_max
 approved   every hour → Planner  every hour → Planner
   caps     tracks the approved   maximises remaining KPI
            plan (recent window,  (earlier behaviour,
            approved target)      cumulative calibration)
```

Both live modes send the last 72 committed hours (`current.recent_hours`) with every replanning
request. `adaptive_max` is the primary live algorithm: it maximises the remaining KPI every hour.
`adaptive` additionally sends the approved plan (`approved`: KPI target and channel budgets) and
keeps the approved channel mix while the projected finish is on plan, moving budget only to get
back on plan or to spend what a paused channel cannot take; it is the conservative variant that
reshuffles ~2 % of the budget instead of ~30 %.

Two roles, two questions, and `summary.md` is split accordingly: the planner is judged by the
symmetric forecast error under frozen execution; the traffic manager by the KPI delivered on the
approved plan relative to frozen execution, with budget use and reallocation as context.

Both modes run on the same `world_seed`, `campaign_seed` and controlled shock, so the paired
difference is attributable to hourly replanning alone. History warm-up plays `--history-levels`
earlier campaigns on the same world seed (other campaign seeds, budgets cycled through
`--history-budget-factors`, random market events on unless `--history-no-random-events`, planned
by `--history-mode`: `frozen` by default, i.e. optimized plans executed as approved, because such
campaigns buy the strong channels deep enough for the saturation parameters to be learned; `uniform`
warm-ups leave them at the catalog and the plan keeps a +15–20 % bias on generous markets), turns
their observable facts into the planner's `history` request field and caches them per world in
`history/world-<seed>.json`. Planner is called through its HTTP contract
in-process (FastAPI test client); Simulator runs as the real Go binary, one process per worker,
because one Simulator process holds one simulation resource. Random market drift and shocks are
disabled unless `--random-events` is given.

## Scenarios

The shocked channel is the channel with the largest approved budget. Shocks start at the middle of
the horizon.

| Scenario | Event |
|---|---|
| `none` | no controlled event |
| `ctr_drop` | CTR × 0.6 until the end |
| `cpm_spike` | CPM × 1.6 until the end |
| `supply_drop` | supply × 0.5 until the end |
| `pause` | channel paused for `--pause-hours` (default 72) |

## Run

Build the Simulator once (Go 1.27) and run the harness from the Planner project so its virtual
environment provides `planner` and `fastapi`:

```bash
(cd services/simulator && go build -o bin/simulator ./cmd/simulator)
cd services/planner
uv run --group dev python ../../tools/evaluation/evaluate.py \
  --budget 1200000 --days 21 --optimize conversions \
  --world-seeds 1-5 --campaign-seeds 1,2 --workers 4 \
  --out ../../tools/evaluation/results
```

Useful flags: `--history-levels 0,1,3`, `--history-mode uniform|frozen|adaptive` (how warm-up
campaigns were executed), `--scenarios none,ctr_drop`, `--modes adaptive`, `--replan-every 6`,
`--simulator-url http://127.0.0.1:8080` and `--planner-url http://127.0.0.1:8082` to evaluate the
Compose deployment instead of spawning processes.

## Output

- `summary.md` — per history level, scenario and mode: signed final deviation of spend and KPI
  (the case metric, threshold 20 % on its absolute value), share of runs within the threshold,
  trajectory error of spend and KPI, share of budget moved away from approved caps; plus paired
  cold-versus-warm and frozen-versus-adaptive comparisons.
- `runs.json` — one record per run with all metrics, per-channel spend and per-channel facts.
- `trajectories/<run>.csv` — hourly cumulative plan and fact for spend and KPI, for charts.
- `approved/world-<seed>-h<level>.json` — the approved Planner response per world and history
  level, including hourly expectations.
- `history/world-<seed>.json` — the warm-up campaigns as the planner received them.
- `dataset/hourly.csv` — one row per channel-hour of every simulated campaign (warm-up and
  evaluated): cap, requests, impressions, unique reach, clicks, conversions, spend, hour of day,
  weekday and the cumulative impressions, reach and spend before the hour. This is the training
  set for offline response models; split by `world_seed`, never by shuffled rows.

Metric definitions follow `docs/mathematical-model.md`, section 13. Final deviation is
`(fact_T − plan_T) / plan_T` at the last hour. Trajectory error is the mean of `|fact_t − plan_t| /
plan_t` over hours after the first `--trajectory-skip-hours` (default 24), because the cumulative
plan is close to zero at the start and a few stochastic conversions would dominate the mean.

## Experiment A: planner accuracy (`planner_eval.py`)

`planner_eval.py` runs the harness over a fixed grid of cells — knowledge source (history 0/1/3/5),
KPI, budget (0.5/1.2/3 M), horizon (14/21 d), strategy, warm-up style and task B (`--target`:
least budget for a KPI target, then frozen execution) — on world seeds 1–8 and campaign seeds 1–2,
and aggregates the cells into `all_runs.json`, `calibration.json` (plan versus fact per run),
`decomposition.json` (fact / plan per channel for impressions, CTR, CR and CPM) and `summary.md`:

```bash
cd services/planner
uv run --group dev python ../../tools/evaluation/planner_eval.py --out ../../tools/evaluation/runs/planner
uv run --group dev python ../../tools/evaluation/planner_eval.py --out ../../tools/evaluation/runs/planner --summarize-only
```

The committed copy of the aggregates lives in `results/planner/`; `results/experiment-a-planner.ipynb`
reads it and writes the figures to `results/figures/planner_*.png`.

## Experiment B: traffic-manager quality (`tm_eval.py`)

`tm_eval.py` keeps the approved plan fixed and varies only the live mode. Cells: the three
modes over the four scripted shocks on warm (history 3) and cold (history 0) plans, a noisy
world (`--random-events`), ablations of the live loop (`--no-recent`: replan without
`current.recent_hours`; `--replan-every 6|24`), the shock timing (`--shock-start`) and clicks as
a second KPI. Every live run is paired with its frozen twin (same world, seed, history, shock)
into `pairs.json`: KPI uplift, share of the shock loss recovered, reaction latency (hours until
the live plan cut the shocked channel's cap by 20 % relative to the same mode without the
shock, from the `top_cap` column of the trajectories), budget use, reallocated share and the
final deviation from the plan. `summary.md` aggregates the pairs per slice.

```bash
cd services/planner
uv run --group dev python ../../tools/evaluation/tm_eval.py --out ../../tools/evaluation/runs/tm
```

The committed aggregates live in `results/tm/`; `results/experiment-b-traffic-manager.ipynb`
reads them and writes `results/figures/tm_*.png`.
