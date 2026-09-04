# Implementation Plan: Minimal Budget Planner

## Extension: strategy comparison and controlled market

The default Compose profile uses the eight-channel market configuration. Planner mounts that file
read-only and derives benchmark midpoints without access to the seeded hidden world. Alongside the
exact quotient/remainder `uniform` strategy, `optimized` ports the colleague branch's saturation-aware
marginal water-filling idea and converts its floating benchmark weights back into an exact largest-
remainder micro-unit allocation.

Simulator reset accepts optional explicit scenario events and can suppress random events. The React
coordinator still owns all calls and enforces one active operation. Strategy comparison is sequential:
after a completed run, reset starts the second strategy with immutable simulation parameters while
the first run's exact aggregate facts remain in browser memory for a comparison table.

**Branch**: `[003-minimal-budget-planner]` | **Date**: 2026-09-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-minimal-budget-planner/spec.md`

## Summary

Add a third, independently deployable, stateless Planner service. It accepts a fixed total campaign
budget, relative integer-hour horizon, channel list, KPI, uniform strategy and the latest committed
campaign-state snapshot. It returns a complete deterministic allocation schedule whose exact decimal
budget caps sum to the input budget. The React dashboard remains the coordinator: it requests a plan,
submits the matching hour to Simulator, atomically commits observed facts, and requests a new
state-correlated optimized plan (or the unchanged uniform baseline) before permitting the next hour.
Target-KPI mode is visible but rejected
as unsupported, forecasts and expected results remain explicitly unavailable, and cumulative actual
unique reach, clicks and conversions are shown throughout and after the run.

## Technical Context

**Language/Version**: Python 3.14.7 for the new Planner; existing TypeScript 6.0/React 19 frontend and Go 1.27 Simulator remain in place
**Primary Dependencies**: FastAPI 0.141.x, Pydantic 2.13.x and Uvicorn 0.52.x; Python standard-library `Decimal`; existing frontend dependencies only
**Storage**: None in Planner; browser memory retains the active plan, raw observations, exact cumulative state and pending planning round; Simulator remains in-memory and authoritative for committed hours
**Testing**: pytest 9.1.x, Hypothesis 6.x, HTTPX/FastAPI TestClient, Ruff 0.16.x and mypy 2.3.x; existing Vitest, Playwright and Go contract/integration suites
**Target Platform**: Linux containers under Docker Compose; current evergreen desktop browsers at widths >=768 px
**Project Type**: Three-service web application: static SPA coordinator, stateless planning HTTP service, seeded simulation HTTP service
**Performance Goals**: <=250 ms p95 for typical plans up to 168 hours × 20 channels and <=1 second for the 2,160 × 20 contract maximum on the local reference environment; cumulative updates O(channels) per committed hour; only one Simulator step or Planner request in flight per dashboard session
**Constraints**: Planner makes no outbound calls; money is transported as decimal strings with six fractional digits and allocated as signed-64-safe integer micros; count snapshots use decimal strings to avoid JavaScript precision loss; one uniform strategy; full original plan returned after every committed hour; expected outcomes are null; Russian accessible UI; no CORS through same-origin proxies
**Scale/Scope**: One local operator, one active Simulator resource, one active campaign in the dashboard, 1..2,160 relative hours, 1..20 channels, at most 43,200 allocations per plan response and 43,200 committed observations per run

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1 design.*

| Principle / gate | Design evidence | Result |
|---|---|---|
| I. Evidence-Based Planning | Plan input, deterministic caps, Simulator observations and UI-derived totals are distinct. Forecast and expected fields are null rather than fabricated; the uniform strategy is labeled non-adaptive. | PASS |
| II. Explicit Audience, Goals, and Constraints | Every request includes KPI, horizon, total budget, currency, simulation/world identity and channels. Audience/geography assumptions remain inherited through the identified Simulator world and are labeled unavailable rather than invented. | PASS |
| III. Traceable Data and Calculations | Decimal strings convert to integer micros; quotient/remainder distribution, canonical ordering and `plan_id` fingerprint are specified. Raw observations remain the source of exact accumulated facts. | PASS |
| IV. Testable Delivery | Unit/property tests cover allocation and validation; contract tests cover HTTP/OpenAPI; frontend tests cover state barriers and totals; Compose/Playwright cover the full feedback loop and failures. | PASS |
| V. Privacy and Least Privilege | Planner is stateless, has no outbound integration or secrets, does not log request bodies, and follows read-only/non-root/capability-drop container controls. | PASS |
| Product constraints | Currency, micro precision, relative-hour semantics, timezone, world digest, provenance, null forecast status and retry rules are explicit. v1 interfaces are versioned. | PASS |
| Accessibility/localization/observability | New controls use Russian labels, unavailable states are textual, KPI totals have semantic headings, and service health plus request/trace IDs are defined. | PASS |

**Post-design re-check**: PASS. The contracts expose exact units and provenance, keep Planner free of
Simulator access, reject unsupported target mode, and represent the lack of forecast explicitly. The
full-plan amplification risk is accepted only for this bounded v0 prototype and must be measured by
the maximum-size benchmark before delivery. No constitutional exception is required.

## Project Structure

### Documentation (this feature)

```text
specs/003-minimal-budget-planner/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── planner.openapi.yaml
│   └── ui-orchestration.md
└── tasks.md                         # created later by /speckit-tasks
```

### Source Code (repository root)

```text
services/
├── planner/
│   ├── src/planner/
│   │   ├── domain/
│   │   │   ├── models.py           # immutable domain inputs/outputs and exact values
│   │   │   └── uniform.py          # pure quotient/remainder allocator
│   │   ├── application/
│   │   │   └── planning.py         # validation-to-plan use case and fingerprint
│   │   └── transport/http/
│   │       ├── dto.py              # strict Pydantic request/response models
│   │       ├── problem.py           # RFC 9457 error projection
│   │       └── app.py               # plan and health routes, request tracing
│   ├── tests/
│   │   ├── unit/                   # allocator, money, validation, fingerprint properties
│   │   └── contract/               # HTTP/OpenAPI/problem/health behavior
│   ├── Dockerfile
│   ├── README.md
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── api/                    # new planner client/codecs and shared problem handling
│   │   ├── domain/                 # plan, campaign facts and exact accumulation types
│   │   ├── features/
│   │   │   ├── campaign/           # fixed/target mode, total budget, KPI, strategy
│   │   │   ├── planning/           # plan summary/table and replanning state
│   │   │   ├── execution/          # plan→step→facts→replan barrier
│   │   │   └── results/            # live/final cumulative KPI cards
│   │   └── app/                    # service bootstrap and workflow composition
│   ├── e2e/                        # planning, feedback, failure and final totals journeys
│   ├── nginx.conf                  # /api/ Simulator + /planner-api/ Planner proxies
│   └── vite.config.ts              # matching development proxies
└── simulator/                      # existing service; public contract unchanged

tests/
├── contract/                       # checked-in Planner OpenAPI compatibility
└── integration/                    # three-container health, proxy and lifecycle workflows

compose.yaml                        # planner peer service and frontend health dependency
```

**Structure Decision**: Add `services/planner` as the requested third service and keep its pure domain
allocator independent of FastAPI/Pydantic. Extend the existing dashboard rather than creating a
second campaign workflow. Keep Simulator endpoints unchanged; nginx adds a distinct
`/planner-api/` prefix while existing `/api/` continues to target Simulator.

## Complexity Tracking

No constitution violation requires an exception. The third service is an explicit product entity,
and keeping it stateless/no-outbound is the minimum boundary that permits later planner evolution
without coupling strategy code to Simulator execution.
