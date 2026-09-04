# Implementation Plan: Simulator Dashboard

**Branch**: `002-simulator-dashboard` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-simulator-dashboard/spec.md`

## Summary

Build a separately deployable Russian-language React dashboard for the existing singleton Simulator.
The dashboard discovers the Simulator's public channel IDs and currency, creates a seeded simulation,
creates or edits a campaign on it, submits exact per-channel hourly budget caps, advances one hour or sequentially runs the
remaining horizon, and presents exact tabular observations plus seven channel/aggregate time-series
views. A small read-only Simulator endpoint fills the current bootstrap-contract gap. In Docker
Compose, an unprivileged nginx container serves the built SPA and proxies same-origin `/api/` calls
to the Simulator, so no browser CORS policy is required.

## Technical Context

**Language/Version**: TypeScript 6.0.x with React 19.2.x on Node.js 24 LTS; Go 1.27.1 for the additive Simulator metadata endpoint
**Primary Dependencies**: Vite 8.2.x, Recharts 3.10.x, React DOM 19.2.x, nginx-unprivileged 1.30.x; no frontend state-management or decimal-arithmetic dependency in v0
**Storage**: Browser memory only for separate simulation/campaign drafts, active campaign snapshot and observation history; the Simulator remains in-memory and authoritative. Refresh may lose charts and MUST NOT reset the Simulator.
**Testing**: Vitest 4.1.x, React Testing Library 16.3.x, user-event 14.x, Playwright 1.62.x (Chromium), existing Go unit/contract/integration tests
**Target Platform**: Current evergreen desktop browsers at widths >=768 px; Linux containers under Docker Compose
**Project Type**: Web application with a separately deployable SPA frontend and existing Go backend service
**Performance Goals**: A successful step visible within 2 seconds; 20 channels x 2,160 hours and all seven metrics inspectable within 3 seconds after final ingestion; automatic execution remains sequential with one request in flight
**Constraints**: Russian initial UI; one Simulator resource; no auth; no hidden market parameters exposed; money and aggregate counts calculated with integer `BigInt` values; unsafe JSON integers rejected rather than rounded; keyboard operation and non-color-only states; no page-level horizontal scrolling at >=768 px
**Scale/Scope**: One local operator, one campaign, <=20 channels, <=2,160 hourly results, <=43,200 observations, seven metric views, one dashboard screen

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1 design.*

| Principle / gate | Design evidence | Result |
|---|---|---|
| I. Evidence-Based Planning | The UI labels user inputs, Simulator observations and derived aggregates separately. It does not expose forecasts or portray channel-summed reach as deduplicated campaign reach. | PASS |
| II. Explicit Audience, Goals, and Constraints | This feature controls a simulation, not a completed media plan. Seeds, campaign horizon, timezone, currency, per-channel budget constraints and Simulator status remain visible; audience, geography and optimization objective are explicitly outside this dashboard scope. | PASS |
| III. Traceable Data and Calculations | Raw contract values are retained. Spend and counts are aggregated with integers; aggregate eCPM and non-deduplicated reach have documented formulas, units, null and rounding behavior. Count codecs reject unsafe JS integers. | PASS |
| IV. Testable Delivery | Unit tests cover codecs, validation, aggregation and the run state machine; component tests cover controls/errors/accessibility; Go contract tests cover metadata; Playwright and Compose tests cover the cross-container workflow. | PASS |
| V. Privacy and Least Privilege | No personal data, credentials or new secrets are introduced. Metadata exposes only public IDs/version/digest/currency. Both host ports bind to loopback and the frontend runtime is unprivileged/read-only. | PASS |
| Product constraints | Canonical hour, currency and budget period are explicit. Existing versioned API semantics are preserved through an additive endpoint. The separate container is required for independent operation and owns only static serving/proxying. | PASS |
| UI requirements | Russian localization, accessible status/error semantics, exact-value alternative to charts, keyboard paths and >=768 px behavior are defined in the UI contract. | PASS |

**Post-design re-check**: PASS. The data model records provenance (`user`, `observed`, `derived`),
the API contract does not leak hidden world parameters, the UI contract defines exact formulas and
accessible equivalents, and quickstart checks calculation, isolation, failure and keyboard paths.
No constitutional exception is required.

## Project Structure

### Documentation (this feature)

```text
specs/002-simulator-dashboard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── simulator-metadata.openapi.yaml
│   └── ui-contract.md
└── tasks.md                         # generated later by /speckit-tasks
```

### Source Code (repository root)

```text
services/
├── simulator/
│   └── internal/
│       ├── app/                     # sanitized world metadata projection
│       └── transport/http/          # GET /v1/world-metadata handler
└── frontend/
    ├── src/
    │   ├── app/                     # composition, top-level state and styling
    │   ├── api/                     # Simulator client, codecs and Problem mapping
    │   ├── domain/                  # types, exact money and aggregate formulas
    │   ├── features/
    │   │   ├── campaign/            # configuration and campaign summary
    │   │   ├── execution/           # one-step and sequential run controller
    │   │   └── results/             # latest table, charts and exact inspector
    │   └── test/                    # shared unit/component test setup
    ├── e2e/                         # Playwright dashboard journeys
    ├── Dockerfile                   # Node build -> unprivileged nginx runtime
    ├── nginx.conf                   # SPA fallback, health and /api proxy
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    └── vite.config.ts

tests/
├── contract/                        # canonical Simulator OpenAPI assertions
└── integration/                     # Compose membership, health and proxy workflow

compose.yaml                         # frontend + simulator on one non-internal network
.gitignore                           # Node/Vite/test artifacts
```

**Structure Decision**: Keep the existing Go Simulator intact as the source of truth and add the
smallest safe bootstrap endpoint to it. Place the independently lifecycle-managed React application
under `services/frontend`; its nginx runtime is an HTTP boundary only and contains no campaign
business state. Cross-service verification remains under the root `tests/` modules.

## Complexity Tracking

No constitution violations require justification. The second container is a stated feature
requirement and isolates frontend lifecycle from Simulator state; nginx replaces both a custom
frontend server and backend-wide CORS handling.
