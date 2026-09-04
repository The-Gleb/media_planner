---

description: "Dependency-ordered implementation tasks for the Simulator Dashboard"
---

# Tasks: Simulator Dashboard

**Input**: Design documents from `/specs/002-simulator-dashboard/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required by the project constitution. Test tasks precede the implementation they verify
and must demonstrate a failing assertion before the corresponding production task begins.

**Organization**: Tasks are grouped by user story so every increment has an explicit independent
test and can be reviewed before proceeding to the next priority.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with adjacent tasks because it owns different files and has no unmet
  dependency on another task in the same group.
- **[Story]**: Maps the task to a user story from `spec.md`.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the React workspace and separate frontend container skeleton without implementing
campaign behavior.

- [X] T001 Initialize the React 19.2, TypeScript 6.0, Vite 8.2 and Recharts 3.10 package with pinned Node 24 engines and npm scripts in `services/frontend/package.json` and generate `services/frontend/package-lock.json`
- [X] T002 [P] Configure strict TypeScript and Vite `/api` development proxy settings in `services/frontend/tsconfig.json`, `services/frontend/tsconfig.app.json`, `services/frontend/tsconfig.node.json`, and `services/frontend/vite.config.ts`
- [X] T003 [P] Configure ESLint and shared npm formatting/typecheck commands in `services/frontend/eslint.config.js` and `services/frontend/package.json`
- [X] T004 [P] Configure Vitest, jsdom, Testing Library and Playwright Chromium in `services/frontend/vitest.config.ts`, `services/frontend/src/test/setup.ts`, and `services/frontend/playwright.config.ts`
- [X] T005 Create the minimal SPA entry point and global responsive design tokens in `services/frontend/index.html`, `services/frontend/src/main.tsx`, `services/frontend/src/app/App.tsx`, and `services/frontend/src/app/styles.css`
- [X] T006 Create the Node-build-to-unprivileged-nginx image, SPA fallback, `/health`, and `/api/` proxy in `services/frontend/Dockerfile`, `services/frontend/nginx.conf`, and `services/frontend/.dockerignore`
- [X] T007 Add the independently health-checked frontend service on `127.0.0.1:8081` to `compose.yaml` and ignore Node, Vite, coverage and Playwright artifacts in `.gitignore`

**Checkpoint**: The frontend builds and serves a placeholder through its own container; campaign
behavior remains unimplemented.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the public Simulator metadata contract, exact transport codecs, shared domain
types and API client required by every user story.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

### Tests for foundational behavior

- [X] T008 [P] Add failing Registry and HTTP tests for sanitized ordered world metadata and `GET /v1/world-metadata` in `services/simulator/internal/app/registry_test.go` and `services/simulator/internal/transport/http/handler_test.go`
- [X] T009 [P] Add failing canonical OpenAPI contract assertions for `WorldMetadata` and the metadata route in `tests/contract/simulator_contract_test.go`
- [X] T010 [P] Add failing tests for money parsing/formatting, integer-micro upward division, safe count decoding and count aggregation in `services/frontend/src/domain/numeric.test.ts`
- [X] T011 [P] Add failing API codec tests for success payloads, ETag capture, invalid/unsafe values and RFC problem bodies in `services/frontend/src/api/codecs.test.ts`
- [X] T012 [P] Add failing client tests for readiness, metadata, create/reset/current-hour/step routing, proxy paths and conditional headers in `services/frontend/src/api/simulatorClient.test.ts`

### Implementation for foundational behavior

- [X] T013 Expose a sanitized `WorldMetadata` projection with engine version, config digest, currency and sorted channel IDs in `services/simulator/internal/app/registry.go`
- [X] T014 Implement `GET /v1/world-metadata` without hidden market parameters and register the route in `services/simulator/internal/transport/http/world.go` and `services/simulator/internal/transport/http/server.go`
- [X] T015 Merge the additive metadata endpoint and version guidance into the canonical Simulator contract in `specs/001-adaptive-media-planning/contracts/openapi.yaml` and `services/simulator/README.md`
- [X] T016 [P] Define transport and domain types for metadata, campaign draft/session, budgets, observations, hourly results, pending steps and problem details in `services/frontend/src/domain/types.ts` and `services/frontend/src/api/types.ts`
- [X] T017 Implement exact `BigInt` money/count primitives, canonical decimal formatting and ceiling eCPM division in `services/frontend/src/domain/numeric.ts`
- [X] T018 Implement strict runtime response codecs that preserve decimal strings, convert safe transport counts to `BigInt`, validate channel coverage, and reject malformed responses in `services/frontend/src/api/codecs.ts`
- [X] T019 Implement the typed fetch client with relative `/api` URLs, encoded simulation IDs, ETag propagation and `application/problem+json` decoding in `services/frontend/src/api/simulatorClient.ts`
- [X] T020 [P] Centralize Russian labels, metric units and known problem-code guidance in `services/frontend/src/app/messages.ts`
- [X] T021 Implement readiness/metadata bootstrap state and retry behavior without campaign mutations in `services/frontend/src/app/useSimulatorBootstrap.ts` and `services/frontend/src/features/campaign/SimulatorStatus.tsx`

**Checkpoint**: The dashboard can safely determine Simulator readiness, public channels and currency;
all shared numeric/API invariants are tested.

---

## Phase 3: User Story 1 - Configure and create a campaign (Priority: P1) 🎯 MVP

**Goal**: Let a user enter all campaign inputs and per-channel hourly budgets, validate them, create
or reset the singleton campaign, and see its initial state while preserving inputs on errors.

**Independent Test**: With a ready Simulator and no active resource, create a two-channel campaign
from the browser and verify the returned identity, channels, currency, current/end hour and complete
remaining horizon before any step is executed; verify invalid fields and `active_limit` preserve the
draft and do not show a false active state.

### Tests for User Story 1

- [X] T022 [P] [US1] Add failing boundary tests for simulation ID, int64 seeds, exact-hour start, duration, timezone and complete money budgets in `services/frontend/src/features/campaign/validation.test.ts`
- [X] T023 [P] [US1] Add failing accessible component tests for metadata-driven budget fields, inline errors, readiness gating, retained inputs and create/reset states in `services/frontend/src/features/campaign/CampaignForm.test.tsx`
- [X] T024 [P] [US1] Add a failing campaign-session reducer test for atomic successful reset, ETag retention and failure history preservation in `services/frontend/src/features/campaign/campaignState.test.ts`
- [X] T025 [US1] Add a failing Playwright MVP journey for ready metadata, invalid form correction, two-channel creation and singleton conflict messaging in `services/frontend/e2e/campaign-create.spec.ts`

### Implementation for User Story 1

- [X] T026 [P] [US1] Implement client-side campaign and per-channel budget validation with field-addressable errors in `services/frontend/src/features/campaign/validation.ts`
- [X] T027 [P] [US1] Implement campaign session/draft reducer transitions that clear history only after successful create/reset in `services/frontend/src/features/campaign/campaignState.ts`
- [X] T028 [US1] Implement the Russian campaign form with metadata-driven channel budgets, currency units, error summary and visible focus behavior in `services/frontend/src/features/campaign/CampaignForm.tsx`
- [X] T029 [P] [US1] Implement the campaign identity, traceability, time range and remaining-hours summary in `services/frontend/src/features/campaign/CampaignSummary.tsx`
- [X] T030 [US1] Implement create-versus-reset orchestration, `If-None-Match`/`If-Match` selection and problem-to-field mapping in `services/frontend/src/features/campaign/useCampaignController.ts`
- [X] T031 [US1] Compose Simulator status, campaign form, campaign summary and durable operation messages into the MVP screen in `services/frontend/src/app/App.tsx`

**Checkpoint**: User Story 1 is deployable and testable as the MVP without step or chart behavior.

---

## Phase 4: User Story 2 - Simulate and inspect one hour (Priority: P2)

**Goal**: Advance exactly one hour with current budgets, atomically retain its validated observations,
show exact latest values, and place the hour in each of the seven raw channel metric views.

**Independent Test**: From a newly created campaign, activate “Один час” once and verify a 60-minute
advance, one ordered observation per channel, all seven metric tabs updated, zero-budget/null-eCPM
behavior, duplicate-click protection and safe retry without a fictitious hour.

### Tests for User Story 2

- [X] T032 [P] [US2] Add failing history-ingestion tests for expected/next hour, complete channel coverage, uniqueness, invariant failures and atomic append in `services/frontend/src/features/execution/history.test.ts`
- [X] T033 [P] [US2] Add failing pending-step and one-hour controller tests for UUID/body stability, current budget snapshots, ETags, duplicate guards and ambiguous retry in `services/frontend/src/features/execution/stepController.test.ts`
- [X] T034 [P] [US2] Add failing component tests for disabled/busy/finished step controls and the exact latest-observation table including null eCPM in `services/frontend/src/features/execution/StepControls.test.tsx` and `services/frontend/src/features/results/LatestObservations.test.tsx`
- [X] T035 [P] [US2] Add failing component tests that one committed hour appears in all seven raw channel metric tabs in `services/frontend/src/features/results/MetricHistory.test.tsx`
- [X] T036 [US2] Add a failing Playwright journey for one step, zero budget, seven metric tabs and retained data after a mocked failure/retry in `services/frontend/e2e/single-step.spec.ts`

### Implementation for User Story 2

- [X] T037 [P] [US2] Implement validated hour-major history ingestion and desynchronization detection in `services/frontend/src/features/execution/history.ts`
- [X] T038 [US2] Implement pending-step creation, immutable complete action snapshots and same-ID retry behavior in `services/frontend/src/features/execution/stepController.ts`
- [X] T039 [US2] Implement the guarded one-hour action and visible execution/error states in `services/frontend/src/features/execution/StepControls.tsx`
- [X] T040 [P] [US2] Implement the exact latest-observation table with currency, contract metric identifiers and an internal labeled scroll region in `services/frontend/src/features/results/LatestObservations.tsx`
- [X] T041 [US2] Implement seven discoverable metric tabs and the selected raw per-channel Recharts view with null gaps in `services/frontend/src/features/results/MetricHistory.tsx` and `services/frontend/src/features/results/MetricChart.tsx`
- [X] T042 [US2] Integrate manual stepping, ordered session history and retained-error behavior into `services/frontend/src/app/App.tsx`

**Checkpoint**: User Stories 1 and 2 work together; automatic execution and aggregate comparison are
not required for this checkpoint.

---

## Phase 5: User Story 3 - Run the remaining campaign automatically (Priority: P3)

**Goal**: Sequentially run every remaining hour with live progress, prevent overlapping mutations,
stop after the in-flight request, and safely recover from ambiguous failures.

**Independent Test**: Run a 24-hour campaign to completion and observe exactly 24 ordered results,
zero remaining hours and disabled run controls; in a second run request stop during an in-flight hour
and prove no subsequent request starts while the committed current hour remains visible.

### Tests for User Story 3

- [X] T043 [P] [US3] Add failing fake-client tests for sequential execution, fresh per-hour budget snapshots, single in-flight request, stop boundary, final state and network failure in `services/frontend/src/features/execution/autoRunController.test.ts`
- [X] T044 [P] [US3] Add failing component tests for completed/remaining/percentage progress, running/stopping/stopped labels, focus return and mutation exclusion in `services/frontend/src/features/execution/RunProgress.test.tsx`
- [X] T045 [US3] Add a failing Playwright journey for run-to-end, stop-after-current-hour, resume, Simulator outage and same-step retry in `services/frontend/e2e/automatic-run.spec.ts`

### Implementation for User Story 3

- [X] T046 [US3] Implement the sequential automatic-run loop with one request in flight, fresh action snapshots and atomic result commits in `services/frontend/src/features/execution/autoRunController.ts`
- [X] T047 [US3] Implement stop-request handling that awaits and records the in-flight response before exiting the loop in `services/frontend/src/features/execution/autoRunController.ts`
- [X] T048 [P] [US3] Implement accessible completed/remaining/percentage progress and throttled live announcements in `services/frontend/src/features/execution/RunProgress.tsx`
- [X] T049 [US3] Extend execution controls with run, stop, resume, finished disabling, focus restoration and cross-action exclusion in `services/frontend/src/features/execution/StepControls.tsx`
- [X] T050 [US3] Integrate automatic execution and recoverable stopped/error states while preserving all committed history in `services/frontend/src/app/App.tsx`

**Checkpoint**: A long campaign no longer requires manual stepping and its stopping semantics are
independently verified.

---

## Phase 6: User Story 4 - Compare channel and aggregate performance (Priority: P4)

**Goal**: Provide exact, accessible comparison of every channel and the correctly defined aggregate
for all seven metrics across the collected campaign history.

**Independent Test**: With at least three multi-channel hours, inspect every metric tab, distinguish
all stable channel/aggregate series without color alone, and retrieve the exact hour/series/value;
verify all sum formulas, the non-deduplicated reach label and weighted eCPM/null rules.

### Tests for User Story 4

- [X] T051 [P] [US4] Add failing exact aggregate tests for count `BigInt` sums, six-decimal spend, non-deduplicated reach, ceiling weighted eCPM and zero-impression null in `services/frontend/src/domain/aggregates.test.ts`
- [X] T052 [P] [US4] Add failing series-projection tests for stable channel styles, aggregate labels, ordered points, exact display values and null chart gaps in `services/frontend/src/features/results/metricSeries.test.ts`
- [X] T053 [P] [US4] Add failing accessible component tests for seven tab names, legend visibility controls, chart labels and keyboard exact-value selection in `services/frontend/src/features/results/MetricChart.test.tsx` and `services/frontend/src/features/results/ExactValueInspector.test.tsx`
- [X] T054 [P] [US4] Add a failing 20-channel x 2,160-hour render/projection benchmark with a three-second acceptance threshold in `services/frontend/src/features/results/resultsPerformance.test.tsx`
- [X] T055 [US4] Add a failing Playwright comparison journey for three hours, channel/aggregate inspection, reach warning and exact weighted eCPM in `services/frontend/e2e/results-comparison.spec.ts`

### Implementation for User Story 4

- [X] T056 [P] [US4] Implement exact per-hour aggregates from normalized observations using `BigInt` counts and micro-units in `services/frontend/src/domain/aggregates.ts`
- [X] T057 [US4] Implement memoized metric projections, stable channel color-plus-dash styles and aggregate series definitions in `services/frontend/src/features/results/metricSeries.ts`
- [X] T058 [US4] Extend the selected Recharts view with aggregate series, accessible title/description, axes/units, legend controls and non-color distinctions in `services/frontend/src/features/results/MetricChart.tsx`
- [X] T059 [P] [US4] Implement the keyboard-accessible metric/hour/series exact-value inspector and aggregate explanation in `services/frontend/src/features/results/ExactValueInspector.tsx`
- [X] T060 [US4] Add lazy selected-chart mounting, memoization, bulk-run animation suppression and throttled chart redraws in `services/frontend/src/features/results/MetricHistory.tsx`
- [X] T061 [US4] Integrate aggregate ingestion, exact inspection and the explicit non-deduplicated reach label into `services/frontend/src/app/App.tsx`

**Checkpoint**: All four stories and every metric/aggregate formula are independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify container isolation, accessibility, security, documentation and the complete
quickstart across stories.

- [X] T062 [P] Update Compose integration assertions for both service memberships, frontend health and proxied metadata while cleaning singleton fixtures in `tests/integration/simulator_compose_test.go` and `tests/integration/simulator_lifecycle_test.go`
- [X] T063 [P] Add a frontend lifecycle integration test proving stop/restart does not mutate Simulator campaign state in `tests/integration/frontend_lifecycle_test.go`
- [X] T064 [P] Add a keyboard-only 768px accessibility journey with focus, live status, non-color series and internal table scrolling assertions in `services/frontend/e2e/accessibility.spec.ts`
- [X] T065 Harden frontend runtime headers, proxy timeouts, request-size limits, read-only filesystem, tmpfs and dropped capabilities in `services/frontend/nginx.conf`, `services/frontend/Dockerfile`, and `compose.yaml`
- [X] T066 [P] Document local npm/Compose workflows, ports, session-history limitation, singleton conflict and troubleshooting in `services/frontend/README.md` and root `README.md`
- [X] T067 Audit user-visible failures and logs to ensure operation context/trace IDs are useful and no request bodies, seeds, budgets or hidden world configuration leak in `services/frontend/src/api/simulatorClient.ts`, `services/frontend/src/app/App.tsx`, and `services/simulator/internal/transport/http/world.go`
- [X] T068 Run every command and manual acceptance scenario in `specs/002-simulator-dashboard/quickstart.md`, record any platform-specific correction in that file, and confirm all Go, frontend, Playwright and Compose checks pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependency; T002-T004 can proceed in parallel after T001 establishes the
  package, while T006 can proceed independently before T007 integrates Compose.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks every story. Write T008-T012 first and
  observe their intended failures; then implement T013-T021.
- **Phase 3 (US1 / MVP)**: Depends on Phase 2. It delivers the first deployable user value.
- **Phase 4 (US2)**: Depends on the US1 campaign session because a step requires a created campaign.
- **Phase 5 (US3)**: Depends on US2's validated single-step primitive and history ingestion.
- **Phase 6 (US4)**: Depends on US2 history; it may be implemented in parallel with US3 after US2.
- **Phase 7 (Polish)**: Depends on all stories selected for release.

### User Story Dependency Graph

```text
Setup → Foundation → US1 (create) → US2 (one hour) ─┬→ US3 (run/stop)
                                                     └→ US4 (compare/aggregate)
US3 + US4 → Polish / full acceptance
```

### Within Each User Story

- Complete and observe failing story tests before production implementation.
- Build pure validation/domain logic before controllers and UI composition.
- Build controllers before wiring them into `App.tsx`.
- Preserve one-writer ownership of shared `App.tsx` and `StepControls.tsx` tasks in task order.
- Stop at each checkpoint and run that story's unit/component/browser tests independently.

## Parallel Opportunities

- **Setup**: T002, T003 and T004 own separate configuration files; T006 owns container files.
- **Foundation**: T008-T012 are independent test surfaces. After backend metadata lands, T016 and
  T020 can proceed independently while T017-T019 form the numeric-codec-client chain.
- **US1**: T022-T024 can be written concurrently; after validation/state exist, CampaignForm and
  CampaignSummary can be implemented concurrently.
- **US2**: T032-T035 are independent test files; after history ingestion, latest table and raw chart
  work can proceed alongside step-controller work.
- **US3**: Controller and progress component tests can be authored concurrently; RunProgress can be
  implemented while the auto-run controller is completed.
- **US4**: Aggregate, projection, component and performance tests are independent; aggregate logic
  and inspector UI can be implemented concurrently before chart integration.
- **Cross-story**: After US2, US3 and US4 can proceed concurrently because both consume the stable
  one-step/history boundary and own separate primary files.

## Parallel Example: User Story 1

```text
Task T022: campaign validation tests in validation.test.ts
Task T023: campaign form interaction tests in CampaignForm.test.tsx
Task T024: campaign state transition tests in campaignState.test.ts
```

## Parallel Example: User Story 2

```text
Task T032: history invariant tests in history.test.ts
Task T033: pending-step/client orchestration tests in stepController.test.ts
Task T034: controls and latest-table component tests
Task T035: seven-metric raw history component tests
```

## Parallel Example: User Story 3

```text
Task T043: sequential run-controller tests in autoRunController.test.ts
Task T044: progress/state accessibility tests in RunProgress.test.tsx
```

## Parallel Example: User Story 4

```text
Task T051: exact aggregate formula tests in aggregates.test.ts
Task T052: metric series projection/style tests in metricSeries.test.ts
Task T053: chart and inspector accessibility tests
Task T054: maximum-scale performance acceptance test
```

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Setup and Foundation, including the metadata endpoint and exact API codecs.
2. Complete US1 tests and implementation.
3. Validate campaign creation/reset independently through the frontend container.
4. Demonstrate the MVP before adding simulation execution.

### Incremental Delivery

1. **MVP**: Metadata-driven campaign create/reset with validation and visible Simulator state.
2. **Hourly feedback**: Add one safe, idempotent step, exact latest observations and raw metric tabs.
3. **Automation**: Add sequential run-to-end, progress, stop boundary and recovery.
4. **Analysis**: Add exact aggregate series, accessible comparison and maximum-scale optimization.
5. **Release gate**: Complete Compose isolation, accessibility, security and full quickstart checks.

### Suggested Review Boundaries

- Review 1: T001-T021 — build/runtime and safe integration boundary.
- Review 2: T022-T031 — US1 MVP.
- Review 3: T032-T042 — manual hourly simulation.
- Review 4: T043-T050 — automatic execution.
- Review 5: T051-T061 — calculations and visualization.
- Review 6: T062-T068 — release hardening and validation.

## Notes

- `[P]` never permits concurrent edits to the same file; shared composition tasks intentionally have
  no parallel marker.
- API decimal strings remain raw evidence; only exact integer representations drive aggregates.
- A retry of an ambiguous step reuses its `step_id` and immutable body.
- The frontend never automatically deletes/resets a Simulator resource on refresh or shutdown.
- Commit after each task or coherent review boundary and stop at any checkpoint for validation.
