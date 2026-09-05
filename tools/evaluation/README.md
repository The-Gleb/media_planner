# Frozen-vs-adaptive evaluation harness

`evaluate.py` measures the case metric headlessly: MAPE of cumulative spend and of the main KPI
against the approved plan trajectory, for the same approved plan executed in two modes.

```text
approved optimized plan (revision 0)
              │
      ┌───────┴───────┐
   frozen           adaptive
 approved caps    every committed hour → Planner → next caps
   every hour
```

Both modes run on the same `world_seed`, `campaign_seed` and controlled shock, so the paired
difference is attributable to hourly replanning alone. Planner is called through its HTTP contract
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

Useful flags: `--scenarios none,ctr_drop`, `--modes adaptive`, `--replan-every 6`,
`--simulator-url http://127.0.0.1:8080` and `--planner-url http://127.0.0.1:8082` to evaluate the
Compose deployment instead of spawning processes.

## Output

- `summary.md` — per scenario and mode: p50/p90 MAPE of spend and KPI, signed final deviation,
  share of runs within the 20 % threshold, share of budget moved away from approved caps; plus the
  paired adaptive-minus-frozen comparison.
- `runs.json` — one record per run with all metrics and per-channel spend.
- `trajectories/<run>.csv` — hourly cumulative plan and fact for spend and KPI, for charts.
- `approved-plan.json` — the Planner response that was approved, including hourly expectations.

Metric definitions follow `docs/mathematical-model.md`, section 13: `APE_t = |fact_t − plan_t| /
plan_t` over hours with a positive plan, MAPE is their mean, final deviation is signed.
