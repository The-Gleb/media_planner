# Planner

Stateless FastAPI service for the deterministic v0 media budget plan. It accepts a complete planning
snapshot, makes no outbound calls, and returns the full fixed-budget schedule on every round.
Target-KPI requests are shape-validated and rejected with the RFC 9457 code
`unsupported_plan_type`.

## Exact allocation

Money is transported as canonical non-negative decimal strings and converted to signed-64-safe
integer micro-units. For `N = hours × channels`, the allocator uses `divmod(total_micros, N)` and
assigns one remainder micro in ascending-hour, then lexicographic-channel order. Every response uses
exactly six fractional digits, and caps sum exactly to the requested budget. For `uniform`, observed
campaign state is validated but does not change the schedule or `plan_id`.

`optimized` reads public ranges from the mounted world config and recalibrates channel CPM, CTR, CR
and supply from cumulative Simulator facts. Every hour it subtracts actual spend, accounts for
observed saturation, and water-fills the remaining budget over the remaining horizon by marginal
reach/click/conversion gain—regardless of whether the run is ahead of or behind its initial KPI
trajectory. State changes produce a new plan ID; largest-remainder conversion keeps the full
schedule's micro-unit sum exact. Planner never calls Simulator or reads the seeded hidden world.

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
