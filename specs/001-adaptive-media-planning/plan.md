# Implementation Plan: Simulator v0

**Branch**: `001-adaptive-media-planning` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-adaptive-media-planning/spec.md`, narrowed by the
planning instruction to User Story 1, FR-017–FR-025, SC-001 and SC-002.

## Summary

Build Simulator as the first of three independent media-planner services. It is a stateful Go HTTP
microservice that resets a seeded synthetic advertising world, accepts sparse per-channel hourly
budget caps, and atomically advances the world by one hour to return requests, impressions,
incremental per-channel unique reach, clicks, conversions, spend and nullable eCPM.

The world model combines seeded base values, normalized hourly and weekday profiles, audience
saturation, frequency fatigue, gradual drift, temporary shocks and positive fast noise. Independent
keyed random streams and a versioned exact binomial sampler make runs reproducible. Planner and
Predictor are future services: this phase defines their boundary through OpenAPI but does not create
their implementations or non-functional placeholders.

## Technical Context

**Language/Version**: Go 1.27.1 (`go 1.27.0`, `toolchain go1.27.1`)

**Primary Dependencies**: Go standard library only at runtime; HTTP/JSON via `net/http` and
`encoding/json`; deterministic random generation via `math/rand/v2` plus `crypto/sha256`

**Storage**: In-memory active simulation and bounded idempotency cache; read-only versioned JSON world
configuration mounted at startup; no database or persistent volume in v0

**Testing**: Go `testing`, `httptest`, fuzzing, race detector, golden replay, property/statistical
tests, OpenAPI conformance tests and Docker Compose integration tests

**Target Platform**: Linux/amd64 OCI container; local orchestration with Docker Compose

**Project Type**: Stateful HTTP microservice in a future three-service system

**Performance Goals**: Reset of 20 channels within 1 second; Step for 20 channels within 100 ms p95;
complete 2,160-hour replay within 30 seconds on the reference development machine

**Constraints**: One active simulation in v0; 1–20 configured channels; 1–2,160 hours; one successful
Step advances exactly 60 minutes; `spend <= budget_cap`; no personal identifiers; exact replay is
guaranteed only for the same engine version, config digest, toolchain, platform, seeds and actions

**Scale/Scope**: Simulator only; one campaign run at a time; per-channel state and output; no
Planner/Predictor logic, cross-channel reach deduplication, ad creative, real ad-platform integration,
checkpoint persistence or multi-tenant authorization

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### Pre-design gate

| Constitutional rule | Design evidence | Status |
|---|---|---|
| Evidence-Based Planning | Formulas, generated parameters, model version and config digest are explicit and replayable. | PASS |
| Explicit Goals and Constraints | Simulator scope, horizons, channel limits, timezone, currency and v0 exclusions are explicit. | PASS |
| Traceable Data and Calculations | The data model defines computation order, units, rounding, source seeds and state updates. | PASS |
| Testable Delivery | Golden, property, statistical, contract, race, fuzz and Compose tests are planned. | PASS |
| Privacy and Least Privilege | Only aggregate synthetic metrics are generated; container and config access are least-privilege. | PASS |
| Versioned interfaces/formats | OpenAPI, engine version, sampler version and world config digest are contract fields. | PASS |
| Simplicity | Standard library, in-memory state and one deployable service avoid premature persistence/brokers. | PASS |

No constitutional violation requires a Complexity Tracking exception.

### Post-design gate

| Design artifact | Re-check result |
|---|---|
| `research.md` | All technology/model decisions include rationale and alternatives; no clarification remains. |
| `data-model.md` | Units, validation, formulas, state transitions, random provenance and rounding are explicit. |
| `contracts/openapi.yaml` | Versioned inputs/outputs, decimal money, timezone, errors, optimistic concurrency and retry are explicit. |
| `contracts/world-config.schema.json` | Channel ranges and all hidden-world controls have machine-testable bounds. |
| `quickstart.md` | End-to-end replay, invariant, idempotency and exhaustion checks are independently runnable. |

Post-design status: **PASS**. No exception or deferred constitutional remediation is required.

## Project Structure

### Documentation (this feature)

```text
specs/001-adaptive-media-planning/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   ├── simulator-interface.md
│   └── world-config.schema.json
└── tasks.md                 # created later by /speckit-tasks
```

### Source Code (repository root)

```text
compose.yaml                         # shared orchestration; Simulator only in this phase
services/
└── simulator/
    ├── cmd/simulator/
    │   └── main.go                  # HTTP server and healthcheck subcommand
    ├── internal/
    │   ├── app/                     # lifecycle and simulation registry
    │   ├── config/                  # JSON loading, normalization, digest and validation
    │   ├── domain/                  # Hour, ChannelID, Money, actions and observations
    │   ├── simulation/
    │   │   ├── simulator.go         # Reset/Step state machine
    │   │   ├── world.go             # hidden world generation
    │   │   ├── profiles.go          # normalized hourly/weekday profiles
    │   │   ├── dynamics.go          # saturation, fatigue, drift and shocks
    │   │   ├── sampling.go          # keyed PRNG streams and binomial sampler
    │   │   └── accounting.go        # fixed-point affordability/spend/eCPM
    │   └── transport/http/           # OpenAPI-aligned handlers and problem responses
    ├── configs/
    │   └── world-config.json         # versioned default model ranges, mounted read-only
    ├── testdata/
    │   └── golden/
    ├── Dockerfile
    ├── go.mod
    └── go.sum
tests/
├── contract/                         # schema/examples and handler conformance
└── integration/                      # HTTP lifecycle and Compose replay
```

**Structure Decision**: Use a service-oriented monorepo rooted at `services/`. Go unit tests remain
beside the packages they test; cross-boundary contract and integration suites live under root
`tests/`. The root Compose file is the eventual assembly point for `planner`, `predictor`, and
`simulator`, but only the working Simulator service is added in this implementation phase.
