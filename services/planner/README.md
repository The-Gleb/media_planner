# Planner

Stateless FastAPI service for deterministic media planning. It accepts a complete planning snapshot,
makes no outbound calls, and supports fixed-budget schedules plus initial target-KPI budget estimates.
Target planning uses only public catalog ranges, searches in one-ruble quanta and returns either an
executable plan or a structured `target_exceeds_capacity` result.

## Allocation and budget conservation

Money is transported as canonical non-negative decimal strings and converted to signed-64-safe
integer micro-units. For `N = hours × channels`, the allocator uses `divmod(total_micros, N)` and
assigns one remainder micro in ascending-hour, then lexicographic-channel order. Every response uses
exactly six fractional digits. For `uniform`, caps sum exactly to the requested budget; observed
campaign state is validated but does not change the schedule or `plan_id`.

`optimized` reads public ranges from the mounted world config and recalibrates channel CPM, CTR, CR
and supply from cumulative Simulator facts. Its response curves model increasing effective CPM and
decreasing CTR, CR and new reach as reach and frequency rise. A 128-point quadratic grid gives finer
resolution at low spend; a concavity projection makes marginal gains non-increasing, and deterministic
water-filling buys only segments with positive marginal KPI return. Every hour Planner subtracts
actual spend and reallocates the remaining useful amount over the remaining horizon—regardless of
whether the run is ahead of or behind its initial KPI trajectory.

Every plan whose channels exist in the public catalog also carries a benchmark trajectory: each future
allocation has `expected` hourly spend, impressions, new unique reach, clicks and conversions computed
by the same saturation model and the same calibration the optimizer uses, and the top-level `expected`
is the projected campaign total (observed facts plus the forecast of future caps). At revision zero the
cumulative sum of hourly expectations is the approved plan trajectory used for plan-versus-fact MAPE;
committed hours carry `expected: null`. The frozen-versus-adaptive evaluation harness lives in
`tools/evaluation/`.

Optimized plans accept an optional `history`: finished campaigns on the same market as 24
hour-of-day bins per channel of observable facts (hours, requests, impressions, unique reach, clicks,
conversions, spend), oldest first. Planner turns them into a recency-weighted prior for CTR, CR, CPM,
daily supply and the hourly supply profile, correcting each campaign's rates for the saturation it
ran under, and then applies the ordinary current-campaign calibration on top. The first campaign on a
market plans from public benchmarks; every next one plans from what that market actually showed.
History enters the optimized `plan_id` and never changes uniform plans.

The optimized conservation invariant is `actual spend + future caps + unallocated_budget = approved
budget`. The explicit reserve prevents a very large budget from being dumped into a saturated channel.
State changes produce a new plan ID; largest-remainder conversion keeps all allocated micro-units
exact. Planner never calls Simulator or reads the seeded hidden world.

## Target-KPI planning

At state revision zero, `target_kpi` with strategy `optimized` repeatedly solves the existing
fixed-budget allocation problem and binary-searches the smallest whole-ruble budget whose benchmark
forecast reaches the requested reach, click or conversion target. The response includes aggregate
expected impressions, non-deduplicated reach, clicks and conversions. These are catalog estimates,
not guarantees for a hidden Simulator seed.

Once the target plan is approved, the dashboard freezes its calculated budget and uses ordinary
fixed-budget replanning for every committed hour. Planner never raises the approved campaign budget.

## Local development

Python 3.14 and [uv](https://docs.astral.sh/uv/) are required.

```bash
cd services/planner
uv sync --locked --group dev
uv run ruff format --check .
uv run ruff check .
uv run mypy --strict src tests
uv run pytest
uv run planner
```

The process listens on `0.0.0.0:8080` by default. Configuration is read at startup from
`PLANNER_ADDR`, `PLANNER_PORT`, `PLANNER_LOG_LEVEL`, and `PLANNER_VERSION`.

Endpoints:

- `GET /health/live` — process liveness;
- `GET /health/ready` — local initialization readiness, with no dependency probes;
- `POST /v1/plans` — deterministic planning;
- `GET /openapi.json` — OpenAPI 3.1 contract.

When integrated by Compose, the host endpoint is `http://127.0.0.1:8082`; containers address the
service as `http://planner:8080`. Planner remains independent of Simulator and has no persistence.

## Container

Build from the repository root so the Dockerfile can copy the locked service files:

```bash
docker build -f services/planner/Dockerfile -t media-planner-planner .
docker run --rm -p 8082:8080 media-planner-planner
```

The multi-stage image installs only locked runtime dependencies and runs as the unprivileged
`planner` user.

## Known v0 limitation

Every replanning round returns the full schedule (up to 2,160 × 20 = 43,200 allocations). This is
intentional for auditability but amplifies response traffic over long runs. The service retains no
prior responses.
