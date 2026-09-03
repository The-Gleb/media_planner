# Tasks: Simulator v0

**Input**: Design documents from `specs/001-adaptive-media-planning/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Scope**: This task list implements only User Story 1 (Simulator), FR-017–FR-025, SC-001 and
SC-002, as narrowed by `plan.md`. User Stories 2–4 (Planner, Predictor and live replanning) are
deferred to later feature plans. No placeholder services are created for them.

**Tests**: Automated tests are mandatory under the project constitution. Story tests are listed
before implementation tasks and MUST be written first and observed failing for the intended reason.

**Organization**: Tasks are grouped into setup, blocking foundations, the independently testable
Simulator story, and cross-cutting release gates.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after dependencies of its phase are satisfied because it owns
  different files and does not depend on another incomplete task in that group.
- **[US1]**: Maps the task to User Story 1, “Симуляция результатов каналов”.
- Every task names the exact file or directory it creates or changes.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the Go service, workspace, container boundary and reference model config.

- [X] T001 Initialize module `media-planner/services/simulator` with `go 1.27.0` and `toolchain go1.27.1` in services/simulator/go.mod
- [X] T002 [P] Create the multi-stage non-root container build skeleton in services/simulator/Dockerfile and services/simulator/.dockerignore
- [X] T003 [P] Define the Simulator-only local service network, read-only config mount and healthcheck in compose.yaml
- [X] T004 [P] Create a schema-conformant `sim-v0` model with `social_1` and `search_1` ranges in services/simulator/configs/world-config.json
- [X] T005 Initialize the isolated contract/integration test module, pin a test-only OpenAPI 3.1 validator and add workspace references in tests/go.mod and go.work

**Checkpoint**: Go workspace, container skeleton and reference configuration exist; no Planner or
Predictor source directories have been introduced.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement validated domain primitives, startup configuration and HTTP foundations used
by every Simulator operation.

**⚠️ CRITICAL**: Phase 3 cannot begin until these domain and startup boundaries pass their tests.

### Foundation tests — write and observe failure first

- [X] T006 [P] Add table/property tests for decimal parsing, half-away quantization, overflow checks and formatting in services/simulator/internal/domain/money_test.go
- [X] T007 [P] Add tests for ChannelID, hour alignment, timezone handling, observations and typed domain errors in services/simulator/internal/domain/types_test.go
- [X] T008 [P] Add strict JSON, cross-field range, unique-channel, normalization and SHA-256 digest tests in services/simulator/internal/config/loader_test.go
- [X] T009 [P] Add RFC 9457 envelope, sensitive-detail suppression and status/code mapping tests in services/simulator/internal/transport/http/problem_test.go

### Foundation implementation

- [X] T010 Implement the Simulator interface, Hour, ChannelID, SimulationConfig, ChannelAction, Observation, status enums and domain errors in services/simulator/internal/domain/types.go
- [X] T011 Implement MoneyMicros checked arithmetic, decimal wire conversion and the float64 compatibility quantizer in services/simulator/internal/domain/money.go
- [X] T012 Implement WorldModelConfig and all nested channel range/profile/event configuration types in services/simulator/internal/config/model.go
- [X] T013 Implement strict config loading, semantic validation, canonical normalization and world_config_digest generation in services/simulator/internal/config/loader.go
- [X] T014 Implement the RFC 9457 problem writer and stable error-to-status/code mapping in services/simulator/internal/transport/http/problem.go
- [X] T015 Implement strict JSON decoding, content-type enforcement, request size limits, trace IDs and ETag parsing in services/simulator/internal/transport/http/middleware.go
- [X] T016 Implement startup readiness state plus `/health/live` and `/health/ready` handlers in services/simulator/internal/transport/http/health.go

**Checkpoint**: Config failures prevent readiness; valid config has an explicit currency, engine
version and stable digest; domain money cannot accumulate binary floating-point error.

---

## Phase 3: User Story 1 — Симуляция результатов каналов (Priority: P1) 🎯 MVP

**Goal**: Reset a reproducible hidden advertising world and advance it atomically one hour per Step,
returning a complete, causally consistent Observation for every configured channel.

**Independent Test**: With the reference two-channel model, Reset a 24-hour run and apply a fixed
sequence of actions. Every Step advances exactly one hour, satisfies funnel/capacity/money invariants,
and returns stable ChannelID ordering. Repeating the same engine/config/seeds/timezone/actions produces
byte-equivalent normalized observations; zero-impression observations have `ecpm: null`.

### Tests for User Story 1 — write and observe failure first

- [X] T017 [P] [US1] Add golden vector tests for SHA-256 seed derivation, per-domain PCG streams, action-order independence and mean-one lognormal noise in services/simulator/internal/simulation/sampling_test.go
- [X] T018 [P] [US1] Add boundary, small-n oracle, large-n statistical and stable-sequence tests for `binomial-btrd-v1` in services/simulator/internal/simulation/binomial_test.go
- [X] T019 [P] [US1] Add tests for circular Gaussian peaks, mean-one normalization, smooth weekdays, weekends and DST lookup in services/simulator/internal/simulation/profiles_test.go
- [X] T020 [P] [US1] Add deterministic schedule and boundary tests for persistent drift, temporary shocks, overlap and pause precedence in services/simulator/internal/simulation/events_test.go
- [X] T021 [P] [US1] Add monotonic and clamp tests for saturation, new-user probability, CPM pressure, frequency and CTR fatigue in services/simulator/internal/simulation/dynamics_test.go
- [X] T022 [P] [US1] Add affordability, ceil-spend, eCPM-nullability, extreme-value and `spend <= budget_cap` tests in services/simulator/internal/simulation/accounting_test.go
- [X] T023 [P] [US1] Add world generation tests for range compliance, profile independence, stable fingerprints and world/campaign seed separation in services/simulator/internal/simulation/world_test.go
- [X] T024 [P] [US1] Add Reset/Step atomicity, sparse actions, funnel invariants, stable order, horizon exhaustion and replay tests in services/simulator/internal/simulation/simulator_test.go
- [X] T025 [P] [US1] Add one-active-run, conditional reset, ETag race, cached retry and conflicting step_id tests in services/simulator/internal/app/registry_test.go
- [X] T026 [P] [US1] Add handler tests for Reset, CurrentHour, Step, Delete, validation errors and exact OpenAPI examples in services/simulator/internal/transport/http/handler_test.go
- [X] T027 [P] [US1] Add OpenAPI loading, local-reference resolution, JSON examples, world-schema and response conformance tests in tests/contract/simulator_contract_test.go
- [X] T028 [P] [US1] Add black-box 24-hour HTTP lifecycle, seed replay, zero-budget, finish and restart expectations in tests/integration/simulator_lifecycle_test.go
- [X] T029 [P] [US1] Add Compose health, config-mount, service-DNS, isolation and two-container replay scenarios in tests/integration/simulator_compose_test.go

### Implementation for User Story 1

- [X] T030 [P] [US1] Implement canonical length-delimited seed derivation, keyed PCG creation and mean-one lognormal sampling in services/simulator/internal/simulation/sampling.go
- [X] T031 [P] [US1] Implement the versioned exact inversion/transformed-rejection binomial sampler in services/simulator/internal/simulation/binomial.go
- [X] T032 [P] [US1] Implement generated normalized circular-hour and structured weekday profiles in services/simulator/internal/simulation/profiles.go
- [X] T033 [P] [US1] Implement campaign-seeded drift, shock and pause schedule generation/evaluation in services/simulator/internal/simulation/events.go
- [X] T034 [P] [US1] Implement saturation, frequency, reach decay, CPM price growth and CTR fatigue curves in services/simulator/internal/simulation/dynamics.go
- [X] T035 [P] [US1] Implement fixed-point affordable impressions, ceil spend and observed nullable eCPM calculations in services/simulator/internal/simulation/accounting.go
- [X] T036 [US1] Implement hidden channel generation, normalized channel ordering and stable world fingerprinting using T030–T034 in services/simulator/internal/simulation/world.go
- [X] T037 [US1] Implement the atomic Reset/Step/CurrentHour state machine, sparse zero actions, per-hour causal order and invariant checks using T031–T036 in services/simulator/internal/simulation/simulator.go
- [X] T038 [US1] Implement the one-active-simulation registry, per-resource lock, revision ETags, tombstones and bounded step retry cache using T037 in services/simulator/internal/app/registry.go
- [X] T039 [P] [US1] Implement OpenAPI DTOs, decimal/seed codecs and domain mappings in services/simulator/internal/transport/http/dto.go
- [X] T040 [US1] Implement conditional PUT Reset, GET CurrentHour and DELETE resource handlers using T038–T039 in services/simulator/internal/transport/http/resources.go
- [X] T041 [US1] Implement Step with cached step_id lookup before ETag validation, atomic commit and stable observations using T038–T039 in services/simulator/internal/transport/http/steps.go
- [X] T042 [US1] Assemble versioned routes, HTTP timeouts, request limits and graceful shutdown hooks in services/simulator/internal/transport/http/server.go
- [X] T043 [US1] Wire config loading, readiness, registry, structured logging, signals, server mode and built-in healthcheck mode in services/simulator/cmd/simulator/main.go
- [X] T044 [US1] Record reviewed exact replay vectors for same seeds/actions and controlled world/campaign seed changes in services/simulator/testdata/golden/sim-v0.json

**Checkpoint**: User Story 1 is independently functional through the Go interface and HTTP contract;
all T017–T029 tests pass without requiring Planner or Predictor.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Complete operability, performance evidence, container hardening and release validation.

- [X] T045 [P] Add low-cardinality request/step counters, latency summaries and structured operation logs without seed/body/ID metric labels in services/simulator/internal/transport/http/observability.go
- [X] T046 [P] Add Reset, 20-channel Step, large-binomial and 2,160-hour replay benchmarks in services/simulator/internal/simulation/benchmark_test.go
- [X] T047 [P] Extend invalid config/action, overflow, cancellation and partial-mutation fuzz coverage in services/simulator/internal/simulation/simulator_fuzz_test.go
- [X] T048 [P] Document configuration, replay identity, per-channel unique reach, restart loss and operational commands in services/simulator/README.md
- [X] T049 Harden runtime as non-root/read-only with dropped capabilities, tmpfs, resource limits and pinned images in services/simulator/Dockerfile and compose.yaml
- [X] T050 Reconcile all handler examples and error codes with the final implementation and make the conformance suite pass in specs/001-adaptive-media-planning/contracts/openapi.yaml and tests/contract/simulator_contract_test.go
- [X] T051 Execute every scenario in specs/001-adaptive-media-planning/quickstart.md, fix discrepancies in that file, and pass gofmt, go vet, go test, race, fuzz, contract, integration and Compose gates

**Checkpoint**: Simulator v0 meets performance, reproducibility, security and documentation gates and
is ready to be consumed by future Planner/Predictor features.

---

## Deferred User Stories

- **US2 / P2 — fixed-budget maximization**: deferred to a Planner/Predictor feature plan.
- **US3 / P3 — fixed-goal cost minimization**: deferred to a Planner/Predictor feature plan.
- **US4 / P4 — hourly adaptive replanning**: deferred until Simulator, Predictor and Planner exist.

These stories deliberately have no task IDs in this file.

## Dependencies & Execution Order

### Phase dependencies

```text
Phase 1: Setup
        ↓
Phase 2: Foundation
        ↓
Phase 3: US1 tests (red) → simulation components → world → state machine
                    → registry/HTTP → binary → golden/integration green
        ↓
Phase 4: Operability, performance, hardening and full quickstart validation
```

- **Phase 1** has no prerequisite.
- **Phase 2** depends on T001 and T005; T006–T009 are authored before T010–T016.
- **Phase 3** depends on the complete foundation. T017–T029 are written before T030–T044.
- **T036** depends on T030, T032, T033 and T034.
- **T037** depends on T031 and T034–T036.
- **T038** depends on T037; T040–T041 depend on T038–T039; T042 depends on T040–T041.
- **T043** depends on T013, T016, T038 and T042; T044 follows a passing deterministic engine.
- **Phase 4** begins after US1 passes independently. T050 follows final handlers; T051 is last.

### User story dependencies

- **US1 (P1)**: Starts after Phase 2 and has no dependency on any other user story.
- **US2–US4**: Out of scope; they will depend on the published Simulator contract in later plans.

### Within User Story 1

1. Write each targeted test and confirm it fails for the expected missing behavior.
2. Implement independent sampling/profile/event/dynamics/accounting components.
3. Compose those components into HiddenWorld and the atomic Simulator state machine.
4. Add registry concurrency/idempotency, then HTTP mappings and server lifecycle.
5. Freeze reviewed golden vectors only after formulas and model version are approved.
6. Pass contract and black-box tests before cross-cutting polish.

## Parallel Opportunities

- Setup T002–T004 can proceed in parallel after T001 is assigned.
- Foundation test tasks T006–T009 can proceed in parallel.
- US1 test files T017–T029 can be authored in parallel after Phase 2.
- Component implementations T030–T035 can proceed in parallel against their failing tests.
- DTO work T039 can proceed while T036–T038 compose the engine and registry.
- Polish T045–T048 can proceed in parallel after the US1 checkpoint.

## Parallel Example: User Story 1

```text
Parallel test batch:
Task T017: sampling_test.go
Task T018: binomial_test.go
Task T019: profiles_test.go
Task T020: events_test.go
Task T021: dynamics_test.go
Task T022: accounting_test.go
Task T023: world_test.go

Parallel component batch after the tests are red:
Task T030: sampling.go
Task T031: binomial.go
Task T032: profiles.go
Task T033: events.go
Task T034: dynamics.go
Task T035: accounting.go
Task T039: dto.go
```

## Implementation Strategy

### MVP first — Simulator / User Story 1 only

1. Complete Setup and Foundation.
2. Write all US1 tests before their implementations.
3. Implement pure deterministic simulation components before HTTP/container concerns.
4. Integrate Reset → 24 Steps → finished as the first end-to-end slice.
5. Validate exact replay and invariants independently.
6. Complete hardening and publish the stable v0 contract.

### Incremental delivery inside US1

1. Domain/config foundation → validated, digestible model config.
2. Pure model functions → profiles, dynamics, events, sampling and accounting.
3. Simulation engine → deterministic atomic hourly observations.
4. Registry and HTTP → concurrency-safe external contract.
5. Container and operations → standalone Compose service.
6. Golden/performance/security gates → release-ready Simulator v0.

### Future service strategy

After Simulator v0 is accepted, create separate feature specifications and task lists for Predictor,
Planner and finally hourly replanning. The root `compose.yaml` remains their integration point, while
Simulator must remain independently runnable and healthy.

## Notes

- `[P]` tasks own different files; phase prerequisites still apply.
- `[US1]` provides traceability to the only story authorized by the implementation plan.
- Tests are written first and must fail for the intended missing behavior before code is added.
- Commit after each task or coherent task group without weakening deterministic golden fixtures.
- Any formula, rounding, schema or sampler change requires an engine-version compatibility decision.
