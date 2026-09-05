# Quickstart: Validate Minimal Budget Planner

This guide is the Phase 1 acceptance path. Commands describe the intended post-implementation
workspace. See [planner.openapi.yaml](contracts/planner.openapi.yaml) for payload details and
[ui-orchestration.md](contracts/ui-orchestration.md) for ordering guarantees.

## Prerequisites

- Docker with Compose v2
- `curl`
- Node.js 24 for direct frontend checks
- Python 3.14 and `uv` for direct Planner checks
- Go 1.27 for existing Simulator/integration checks

## Start the Three Services

From repository root:

```bash
docker compose up -d --build --wait
docker compose ps
```

Expected services and loopback ports:

| Service | URL | Expected readiness |
|---|---|---|
| Simulator | `http://127.0.0.1:8080/health/ready` | `200`, status `ok` |
| Frontend | `http://127.0.0.1:8081/health` | `200`, status `ok` |
| Planner | `http://127.0.0.1:8082/health/ready` | `200`, status `ok` |

Verify both frontend proxies independently:

```bash
curl -fsS http://127.0.0.1:8081/api/health/ready
curl -fsS http://127.0.0.1:8081/planner-api/health/ready
```

Both must succeed, but frontend `/health` must remain available if either backend is later stopped.

## Validate a Deterministic Plan

Send the `fixedBudget` request example from
[Planner OpenAPI](contracts/planner.openapi.yaml) to:

```bash
curl -fsS -X POST http://127.0.0.1:8082/v1/plans \
  -H 'Content-Type: application/json' \
  --data-binary @request.json
```

For the documented 12 RUB, two-hour, two-channel example, verify:

- response status is 200;
- there are four allocations ordered by hour then channel;
- each cap is `3.000000` and their exact sum is `12.000000`;
- `expected`, allocation `expected`, `required_budget` and `reason` are null;
- retrying the same request preserves the result; changing actual state preserves uniform but may
  change optimized `plan_id` and future caps;
- echoed `request_id` and `state_revision` match the latest request.

Repeat with budget `0.000001`: exactly one first allocation receives `0.000001`, all others receive
`0.000000`, and the sum remains exact.

## Validate Target-KPI Mode

Use the `target_kpi` request shape from the contract with strategy `optimized`, initial state revision
zero and a reachable target. Expected result:

- HTTP 200 with `feasible=true`;
- `required_budget` equals the executable plan `budget` and is quantized to a whole ruble;
- the selected expected KPI reaches the target;
- allocation caps sum exactly to the calculated budget.

Repeat with a target above catalog capacity. The response remains HTTP 200 but has `feasible=false`,
zero allocations and reason `target_exceeds_capacity`; Simulator remains unchanged.

Malformed money, duplicate channels, invalid horizon/current revision and unexpected fields must
also produce named validation errors rather than partial plans.

## Validate the Browser Workflow

Open `http://127.0.0.1:8081/` and:

1. Confirm Simulator and Planner readiness are separately visible.
2. Configure Simulation fields.
3. In Campaign select fixed budget, enter total budget and duration, choose a KPI and either uniform
   or catalog-optimized strategy.
4. Select target-KPI mode, enter a target and confirm the optimized strategy is fixed.
5. Launch target mode and inspect calculated budget, benchmark forecast, target, horizon and
   allocation table. For an impossible target, confirm the diagnosis appears and Simulator does not reset.
6. Confirm manual per-channel budget inputs are absent.
7. Before the first hour, confirm actual reach, clicks and conversions are zero.
8. Run one hour. Confirm facts commit, status visibly enters replanning, optimized may change future
   caps, and aggregate spend/impressions/reach/clicks/conversions update once.
9. Run to completion. Confirm every Simulator hour is preceded by a plan and followed by a successful
   replan, and the KPI cards change to final labels.
10. Confirm reach always says “сумма по каналам, без дедупликации”.
11. Finish a run, switch strategy and reset. Confirm the first result remains in “Сравнение
    стратегий”, the second begins from hour zero with the same seeds, and both final rows are shown.
12. Optionally configure a controlled shock in Simulation before the first run; confirm it is reused
    for the second strategy and cannot be edited between the two sequential runs.

The default world contains eight channels. `sms` currently uses an effective CPM-equivalent because
the Simulator action contract has not yet introduced package purchases.

## Validate Failure Barriers

During a multi-hour run, stop Planner after one hour commits but before replanning completes.

Expected behavior:

- the committed observation, session position and cumulative totals remain visible;
- automatic execution pauses and no next Simulator step occurs;
- the UI shows `replan_failed` guidance;
- after Planner restarts, “Повторить перепланирование” reuses the same planning request snapshot;
- the same immutable planning request is accepted and only then may the next Simulator hour start.

Also inject an ambiguous Simulator response and verify its retry reuses the same `step_id` and caps,
with no duplicate history or KPI contribution.

## Run Automated Checks

Planner:

```bash
cd services/planner
uv sync --locked --group dev
uv run ruff format --check .
uv run ruff check .
uv run mypy --strict src tests
uv run pytest
```

Frontend:

```bash
cd services/frontend
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run test:e2e
```

Simulator:

```bash
cd services/simulator
go test ./...
go vet ./...
```

Cross-container contracts and lifecycle:

```bash
cd tests
RUN_COMPOSE_TESTS=1 SIMULATOR_BASE_URL=http://127.0.0.1:8080 \
  PLANNER_BASE_URL=http://127.0.0.1:8082 FRONTEND_BASE_URL=http://127.0.0.1:8081 \
  go test -count=1 ./...
```

The automated acceptance set must cover exact allocation properties, OpenAPI compatibility,
plan-before-reset, step-before-replan, Planner outage/retry, target-mode rejection, cumulative totals,
final labels and independent frontend lifecycle.

## Validation Record — 2026-09-04

- Planner: Ruff format/check and strict mypy passed; 95 pytest tests passed, including an API-level
  proof that new committed facts change optimized future allocations while preserving exact budget.
- Frontend: typecheck, ESLint and production build passed; 54 Vitest tests and 13 Playwright
  Chromium journeys passed.
- Simulator: `go test ./...` and `go vet ./...` passed against the eight-channel config and explicit
  scenario-event coverage.
- Compose: configuration validation, repository contract/integration suites, eight-channel metadata,
  and the independent Planner stop/restart lifecycle passed.
- Full-plan performance: 168 × 20 completed in 0.02 s and 2,160 × 20 in 0.17 s on the validation
  host; allocation-count, exact-sum, payload-size, peak-memory and prior-response-retention bounds
  all passed.

## Measure the Known v0 Limit

Run the Planner performance test for both 168 × 20 and 2,160 × 20 allocations. Record duration,
response byte size and peak memory. Acceptance targets are defined in [plan.md](plan.md). The result
must explicitly report full-plan amplification; it must not retain prior planning responses.
