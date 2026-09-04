---

description: "Dependency-ordered implementation tasks for the minimal budget Planner"
---

# Tasks: Minimal Budget Planner

**Input**: Design documents from `/specs/003-minimal-budget-planner/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Tests are required by the feature specification and project constitution. Within every
story, write the listed tests first and confirm that they fail for the missing behavior before
implementation.

**Organization**: Tasks are grouped by user story so each increment has a separately demonstrable
outcome. Paths are repository-relative.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after the phase prerequisites because it owns different files
- **[Story]**: User story mapping from `spec.md`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the new Python service and reproducible toolchain without changing runtime behavior.

- [X] T001 Create Planner package/test directories and package markers under `services/planner/src/planner/{domain,application,transport/http}` and `services/planner/tests/{unit,contract}`
- [X] T002 Configure Python 3.14, FastAPI/Pydantic/Uvicorn runtime dependencies, pytest/Hypothesis/HTTPX dev dependencies, Ruff and strict mypy in `services/planner/pyproject.toml`
- [X] T003 Generate and commit the exact dependency resolution for T002 in `services/planner/uv.lock`
- [X] T004 [P] Add the pinned Python 3.14 slim multi-stage container skeleton, non-root runtime user and exec-form command in `services/planner/Dockerfile`
- [X] T005 [P] Add shared Planner pytest fixtures and import-path configuration in `services/planner/tests/conftest.py`
- [X] T006 [P] Exclude Python bytecode, virtual environments, pytest/mypy/Ruff caches and coverage output in `.gitignore` and `.dockerignore`
- [X] T007 [P] Document local dependency, test and service commands without claiming implemented behavior in `services/planner/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Provide service health, consistent problems, same-origin routing and independent readiness required by every story.

**⚠️ CRITICAL**: No user story implementation begins until this phase passes.

### Foundational Tests

- [X] T008 [P] Add failing liveness/readiness and no-outbound-dependency contract tests in `services/planner/tests/contract/test_health.py`
- [X] T009 [P] Add failing RFC 9457 content type, trace ID, malformed JSON and unexpected-error projection tests in `services/planner/tests/contract/test_problem.py`
- [X] T010 [P] Add failing Planner health-client and problem-decoding tests in `services/frontend/src/api/plannerClient.test.ts`
- [X] T011 [P] Add failing combined Simulator/Planner bootstrap-state component tests in `services/frontend/src/app/useServicesBootstrap.test.tsx`

### Foundational Implementation

- [X] T012 [P] Implement immutable address/log-level/service-version settings with startup validation in `services/planner/src/planner/config.py`
- [X] T013 [P] Implement Planner error codes, field errors and RFC 9457 responses in `services/planner/src/planner/transport/http/problem.py`
- [X] T014 Implement request/trace ID middleware, exception translation, `/health/live` and dependency-free `/health/ready` in `services/planner/src/planner/transport/http/app.py`
- [X] T015 Add a hardened `planner` peer service on internal port 8080 and loopback port 8082 with readiness healthcheck to `compose.yaml`
- [X] T016 [P] Preserve `/api/` for Simulator and add `/planner-api/` Planner routes, timeouts and request IDs in `services/frontend/nginx.conf` and `services/frontend/vite.config.ts`
- [X] T017 Implement the shared Planner HTTP client, health request and problem error class in `services/frontend/src/api/plannerClient.ts` and `services/frontend/src/api/problem.ts`
- [X] T018 Implement independent Simulator/Planner bootstrap states and Russian availability labels in `services/frontend/src/app/useServicesBootstrap.ts` and `services/frontend/src/features/campaign/ServiceStatus.tsx`
- [X] T019 Verify direct Planner readiness, frontend Planner proxying and independent frontend liveness in `tests/integration/planner_compose_test.go`

**Checkpoint**: Planner starts in Compose, both health routes work, and the dashboard distinguishes which backend is unavailable.

---

## Phase 3: User Story 1 - Create an Even Budget Plan (Priority: P1) 🎯 MVP

**Goal**: Accept a total fixed budget, KPI, relative horizon and uniform strategy; return and display a complete exact plan before creating/resetting Simulator.

**Independent Test**: Submit 12 RUB for two hours and two channels; receive four ordered `3.000000` allocations whose exact sum is 12 RUB, display the plan, then create Simulator only after Planner success.

### Tests for User Story 1

- [X] T020 [P] [US1] Add failing canonical MoneyText parsing, int64-micro bounds and CountText validation tests in `services/planner/tests/unit/test_values.py`
- [X] T021 [P] [US1] Add failing example and Hypothesis properties for allocation count, exact sum, one-micro spread, ordering, zero budget and determinism in `services/planner/tests/unit/test_uniform.py`
- [X] T022 [P] [US1] Add failing plan fingerprint tests proving request ID/current state exclusion and plan-defining input inclusion in `services/planner/tests/unit/test_planning.py`
- [X] T023 [P] [US1] Add failing fixed-budget endpoint tests for the documented response, strict extra-field rejection and invalid horizon/channel/state relationships in `services/planner/tests/contract/test_plans.py`
- [X] T024 [P] [US1] Add a failing generated-schema compatibility test against `specs/003-minimal-budget-planner/contracts/planner.openapi.yaml` in `services/planner/tests/contract/test_openapi.py`
- [X] T025 [P] [US1] Add failing exact plan response codec, coverage, ordering, null-expected and budget-sum tests in `services/frontend/src/api/plannerCodecs.test.ts`
- [X] T026 [P] [US1] Add failing fixed-budget draft validation and accessible total-budget/KPI/strategy form tests in `services/frontend/src/features/campaign/PlanningFields.test.tsx`
- [X] T027 [P] [US1] Add a failing browser journey for plan-first creation, plan presentation, pagination and Planner-failure preservation in `services/frontend/e2e/fixed-budget-plan.spec.ts`

### Implementation for User Story 1

- [X] T028 [P] [US1] Define frozen KPI, PlanType, Strategy, Horizon, SimulationContext, CampaignState, Allocation and MediaPlan domain values in `services/planner/src/planner/domain/models.py`
- [X] T029 [P] [US1] Implement canonical Decimal-string validation and integer-micro conversion without binary floats in `services/planner/src/planner/domain/values.py`
- [X] T030 [US1] Implement quotient/remainder uniform allocation in ascending-hour then lexicographic-channel order in `services/planner/src/planner/domain/uniform.py`
- [X] T031 [US1] Implement fixed-budget validation, SHA-256 canonical `plan_id` generation and null forecast/expected output in `services/planner/src/planner/application/planning.py`
- [X] T032 [US1] Implement strict Pydantic v2 fixed-budget request/MediaPlan DTOs, count strings and cross-field invariants in `services/planner/src/planner/transport/http/dto.py`
- [X] T033 [US1] Add stateless `POST /v1/plans`, response validation, request correlation and named validation problems in `services/planner/src/planner/transport/http/app.py`
- [X] T034 [US1] Align generated operation IDs, schemas, examples and error responses with `specs/003-minimal-budget-planner/contracts/planner.openapi.yaml` in `services/planner/src/planner/transport/http/app.py` and `services/planner/src/planner/transport/http/dto.py`
- [X] T035 [P] [US1] Add PlanningDraft, PlanRequest, MediaPlan, Allocation and ActivePlan frontend domain types in `services/frontend/src/domain/planning.ts`
- [X] T036 [US1] Implement strict exact-string decoding and complete allocation validation in `services/frontend/src/api/plannerCodecs.ts`
- [X] T037 [US1] Implement fixed-budget `POST /planner-api/v1/plans` with request IDs and user-facing problems in `services/frontend/src/api/plannerClient.ts`
- [X] T038 [P] [US1] Build zero-state fixed-budget requests with horizon `[0,duration)` and Simulator context in `services/frontend/src/features/planning/planRequest.ts`
- [X] T039 [P] [US1] Replace per-channel budget validation with total budget, duration, KPI and uniform strategy validation in `services/frontend/src/features/campaign/validation.ts`
- [X] T040 [US1] Replace manual channel caps with the Russian fixed-budget planning controls in `services/frontend/src/features/campaign/CampaignForm.tsx` and `services/frontend/src/features/campaign/PlanningFields.tsx`
- [X] T041 [US1] Validate response correlation, exact total, pair coverage and derive the relative-hour action index in `services/frontend/src/features/planning/activePlan.ts`
- [X] T042 [US1] Extend campaign reducer state with planning draft, candidate plan and ActivePlan promotion while preserving old active runs on failure in `services/frontend/src/features/campaign/campaignState.ts`
- [X] T043 [US1] Orchestrate Planner-before-Simulator create/reset and atomic plan/session/history promotion in `services/frontend/src/features/campaign/useCampaignController.ts`
- [X] T044 [P] [US1] Implement plan identity, budget/KPI/strategy/horizon and explicit unavailable-forecast summary in `services/frontend/src/features/planning/PlanSummary.tsx`
- [X] T045 [P] [US1] Implement the exact 24-hour-paged hour-by-channel allocation table in `services/frontend/src/features/planning/AllocationTable.tsx`
- [X] T046 [P] [US1] Add responsive planning form, plan summary, table scroll-region and current-hour styles in `services/frontend/src/app/styles.css`
- [X] T047 [US1] Wire dual-service readiness, planning form, plan-first creation and plan presentation into `services/frontend/src/app/App.tsx`
- [X] T048 [US1] Run the US1 Planner, frontend and browser test subset and record the MVP checkpoint in `specs/003-minimal-budget-planner/quickstart.md`

**Checkpoint**: The fixed-budget MVP is usable end-to-end; no forecast, feedback adaptation or target execution is implied.

---

## Phase 4: User Story 2 - Execute and Replan Hour by Hour (Priority: P2)

**Goal**: Execute only the current plan hour, commit exact Simulator facts, send the cumulative snapshot to Planner and block the next hour until a correlated uniform or state-adaptive plan returns.

**Independent Test**: Execute one hour, verify cumulative facts reach Planner, verify uniform remains stable and optimized can change future caps, and execute no second Simulator step while replanning is failed or pending.

### Tests for User Story 2

- [X] T049 [P] [US2] Add endpoint tests that keep uniform stable and make optimized allocations state-dependent for later CampaignState revisions in `services/planner/tests/contract/test_replanning.py`
- [X] T050 [P] [US2] Add failing exact campaign/per-channel accumulator and duplicate-commit tests in `services/frontend/src/domain/campaignFacts.test.ts`
- [X] T051 [P] [US2] Add failing current-relative-hour allocation selection and missing/duplicate channel rejection tests in `services/frontend/src/features/execution/plannedActions.test.ts`
- [X] T052 [P] [US2] Add failing immutable planning-round retry, revision correlation and stale-response rejection tests in `services/frontend/src/features/planning/planningRound.test.ts`
- [X] T053 [P] [US2] Add failing atomic step-commit/replanning/replan-failed/retry reducer tests in `services/frontend/src/features/campaign/campaignState.test.ts`
- [X] T054 [P] [US2] Add failing automatic-run ordering tests proving `step → fact commit → awaited replan → next step` in `services/frontend/src/features/execution/autoRunController.test.ts`
- [X] T055 [P] [US2] Add failing browser journeys for successful feedback, Planner outage after commit and same-round retry in `services/frontend/e2e/planner-feedback.spec.ts`

### Implementation for User Story 2

- [X] T056 [US2] Enforce CampaignState revision/current-hour/channel-key/count/spend invariants while keeping allocation independent of facts in `services/planner/src/planner/transport/http/dto.py` and `services/planner/src/planner/application/planning.py`
- [X] T057 [P] [US2] Implement exact incremental campaign and per-channel fact accumulation from one validated HourlyResult in `services/frontend/src/domain/campaignFacts.ts`
- [X] T058 [P] [US2] Select and normalize exactly one ActivePlan allocation per channel for the current relative hour in `services/frontend/src/features/execution/plannedActions.ts`
- [X] T059 [P] [US2] Extend Planner request construction with the exact committed CampaignState snapshot and state revision in `services/frontend/src/features/planning/planRequest.ts`
- [X] T060 [P] [US2] Implement immutable PendingPlanningRound creation/retry and plan correlation validation in `services/frontend/src/features/planning/planningRound.ts`
- [X] T061 [US2] Refactor hourly commit to return session, history and exact facts as one validated transition in `services/frontend/src/features/execution/history.ts`
- [X] T062 [US2] Add atomic facts-committed/replanning/plan-accepted/replan-failed transitions in `services/frontend/src/features/campaign/campaignState.ts`
- [X] T063 [US2] Implement the Planner replanning controller with retained snapshot retry and no Simulator access in `services/frontend/src/features/planning/usePlanningController.ts`
- [X] T064 [US2] Refactor manual execution to source caps from ActivePlan, commit facts once and await replanning in `services/frontend/src/features/execution/stepController.ts`
- [X] T065 [US2] Add an awaited replanning barrier and stop-between-complete-iterations semantics in `services/frontend/src/features/execution/autoRunController.ts`
- [X] T066 [P] [US2] Implement planning/replanning/retry status and accessible “Повторить перепланирование” control in `services/frontend/src/features/planning/ReplanningStatus.tsx`
- [X] T067 [P] [US2] Add Russian messages for unavailable Planner, stale plan, missing allocation and replan retry states in `services/frontend/src/app/messages.ts`
- [X] T068 [US2] Wire PendingStep and PendingPlanningRound refs, fact-commit barrier and automatic pause into `services/frontend/src/app/App.tsx`
- [X] T069 [US2] Run the US2 service/controller/browser subsets and record the feedback-loop checkpoint in `specs/003-minimal-budget-planner/quickstart.md`

**Checkpoint**: Every committed hour is followed by one accepted planning round; a Planner failure can never advance another Simulator hour.

---

## Phase 5: User Story 3 - Monitor Actual Campaign Outcomes (Priority: P3)

**Goal**: Show exact cumulative actual reach, clicks and conversions during execution and retain final labeled totals at completion.

**Independent Test**: Commit two hours for two channels and verify all three cards equal exact observation sums, reach is labeled non-deduplicated, reset clears totals only on success, and completion changes labels to final.

### Tests for User Story 3

- [X] T070 [P] [US3] Add failing zero/live/final/non-deduplicated accessibility tests in `services/frontend/src/features/results/ActualKPISummary.test.tsx`
- [X] T071 [P] [US3] Add failing successful-reset clear, failed-reset preserve and finished-state actual-total reducer tests in `services/frontend/src/features/campaign/campaignState.test.ts`
- [X] T072 [P] [US3] Add a failing two-channel multi-hour browser journey for live and final exact KPI cards in `services/frontend/e2e/actual-kpi-summary.spec.ts`

### Implementation for User Story 3

- [X] T073 [US3] Implement zero/live/final actual KPI cards sourced only from CampaignState in `services/frontend/src/features/results/ActualKPISummary.tsx`
- [X] T074 [US3] Ensure reset promotion atomically clears facts/history and failed reset preserves both in `services/frontend/src/features/campaign/campaignState.ts`
- [X] T075 [P] [US3] Add responsive, non-color-only actual KPI card and final-state styles in `services/frontend/src/app/styles.css`
- [X] T076 [US3] Place actual KPI cards before campaign controls and bind final state to Simulator completion in `services/frontend/src/app/App.tsx`
- [X] T077 [US3] Verify the Planner request snapshot and displayed KPI cards use the same exact totals in `services/frontend/src/features/planning/planRequest.test.ts`
- [X] T078 [US3] Run the US3 unit/component/browser subsets and record the outcome-summary checkpoint in `specs/003-minimal-budget-planner/quickstart.md`

**Checkpoint**: Actual KPI summaries are exact, single-sourced, reset-safe and visibly final when the horizon ends.

---

## Phase 6: User Story 4 - See Future Target-KPI Mode (Priority: P4)

**Goal**: Show the future target mode without allowing it to create a plan or move Simulator, and reject direct target requests explicitly.

**Independent Test**: Focus/select target mode and see an unavailable explanation with blocked launch; a direct valid-shaped target request receives `unsupported_plan_type` and leaves Simulator unchanged.

### Tests for User Story 4

- [X] T079 [P] [US4] Add failing valid-shape TargetKPI request and `unsupported_plan_type` RFC 9457 tests in `services/planner/tests/contract/test_target_kpi.py`
- [X] T080 [P] [US4] Add failing keyboard-focusable target-mode, KPI/value and blocked-submit component tests in `services/frontend/src/features/campaign/PlanningFields.test.tsx`
- [X] T081 [P] [US4] Add a failing browser journey proving target mode is explicit and produces zero Planner/Simulator mutations in `services/frontend/e2e/target-kpi-unavailable.spec.ts`

### Implementation for User Story 4

- [X] T082 [US4] Add strict TargetKPI request DTO shape and explicit `unsupported_plan_type` rejection in `services/planner/src/planner/transport/http/dto.py` and `services/planner/src/planner/transport/http/app.py`
- [X] T083 [P] [US4] Add target draft types and target-value validation without constructing an executable request in `services/frontend/src/domain/planning.ts` and `services/frontend/src/features/campaign/validation.ts`
- [X] T084 [US4] Add accessible fixed-budget/target-KPI mode controls, target fields and unavailable explanation in `services/frontend/src/features/campaign/PlanningFields.tsx`
- [X] T085 [US4] Guard campaign submission and map unsupported target problems without falling back to fixed budget in `services/frontend/src/features/campaign/useCampaignController.ts` and `services/frontend/src/app/messages.ts`
- [X] T086 [US4] Run the US4 contract/component/browser subsets and record the unavailable-mode checkpoint in `specs/003-minimal-budget-planner/quickstart.md`

**Checkpoint**: The future mode is discoverable but impossible to mistake for implemented optimization.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Prove maximum boundaries, contract drift protection, container lifecycle and complete documentation.

- [X] T087 [P] Add typical 168×20 and maximum 2,160×20 timing, payload-size, memory and prior-response-retention checks in `services/planner/tests/unit/test_performance.py`
- [X] T088 [P] Add maximum-plan decode/index/pagination render performance regression coverage in `services/frontend/src/features/planning/planningPerformance.test.tsx`
- [X] T089 [P] Validate the checked-in Planner OpenAPI paths, schemas, money/count strings and problems from the repository contract suite in `tests/contract/planner_contract_test.go`
- [X] T090 [P] Verify Planner stop/restart, frontend independence and no Simulator mutation across service lifecycle in `tests/integration/planner_lifecycle_test.go`
- [X] T091 Harden Planner image/runtime and verify non-root, read-only, tmpfs, dropped capabilities, resource limits and graceful shutdown in `services/planner/Dockerfile` and `compose.yaml`
- [X] T092 [P] Document three-service architecture, ports, proxy paths, exact allocation, feedback failures and known full-plan amplification in `README.md`, `services/planner/README.md`, and `services/frontend/README.md`
- [X] T093 Run Ruff, mypy, pytest/Hypothesis, frontend typecheck/lint/Vitest/build/Playwright, Simulator Go tests/vet and Compose contract/integration suites; record results in `specs/003-minimal-budget-planner/quickstart.md`
- [X] T094 Execute every manual validation and maximum-boundary measurement in `specs/003-minimal-budget-planner/quickstart.md` and reconcile any contract/documentation drift in `specs/003-minimal-budget-planner/contracts/`

## Phase 8: Eight-Channel Strategy Comparison Extension

- [X] T095 Import and tune the eight-channel world profile with approved CPM/CTR/CR ranges in `services/simulator/configs/world-config.mediaplan.json` and use it in `compose.yaml`
- [X] T096 Add deterministic explicit scenario events and random-event suppression to Simulator reset, OpenAPI and tests
- [X] T097 Port saturation-aware marginal water-filling as exact `optimized` Planner strategy with catalog and contract tests
- [X] T098 Expose uniform/optimized strategy and controlled scenario fields in the React campaign form
- [X] T099 Preserve one completed run across reset and render exact sequential strategy comparison without concurrent execution
- [X] T100 Reconcile feature specification, service documentation and checked-in API contracts for the extension
- [X] T101 Run complete Planner, Simulator, frontend, browser and Compose contract/integration validation for the extension

## Phase 9: Target-KPI Planning Extension

- [X] T102 Extract aggregate benchmark forecasting from optimized allocation
- [X] T103 Implement whole-ruble inverse budget search and capacity diagnosis
- [X] T104 Extend Planner DTOs, endpoint and OpenAPI with executable/infeasible target results
- [X] T105 Enable target-KPI form submission and result decoding in the dashboard
- [X] T106 Freeze the calculated budget and reuse fixed-budget hourly replanning after launch
- [X] T107 Add target solver, contract, codec, form and request-builder tests

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 — Setup**: Starts immediately.
- **Phase 2 — Foundational**: Depends on Phase 1 and blocks every story.
- **Phase 3 — US1**: Depends on Foundation and delivers the MVP.
- **Phase 4 — US2**: Depends on US1 ActivePlan/request/client behavior; unit fixtures permit isolated development, but integrated delivery follows US1.
- **Phase 5 — US3**: Depends on the exact CampaignState accumulator introduced by US2.
- **Phase 6 — US4**: Depends only on Foundation and shared DTO/form structures, but is scheduled after core executable behavior by priority.
- **Phase 7 — Polish**: Depends on all selected stories.

### User Story Dependency Graph

```text
Setup → Foundation → US1 (fixed-budget MVP) → US2 (feedback loop) → US3 (actual KPI UI)
                     └──────────────────────────────→ US4 (unavailable target mode)

US1 + US2 + US3 + US4 → Polish / full acceptance
```

### Within Each User Story

- Write tests first and observe the expected failures.
- Implement immutable/domain values before calculation/application services.
- Implement services before transport handlers and clients.
- Validate decoded contracts before promoting state or rendering it.
- Complete the story checkpoint before starting the next dependent story.

### Parallel Opportunities

- In Setup, T004–T007 own separate files after T001; T003 follows T002.
- In Foundation, Planner contract tests T008–T009 and frontend tests T010–T011 can run concurrently; T012–T013 are independent.
- In US1, T020–T027 can be authored concurrently; domain models/value parsing T028–T029 and UI components T044–T046 have separate ownership.
- In US2, tests T049–T055 are independent; facts, action selection, request building and round correlation T057–T060 use separate modules.
- In US3, T070–T072 are independent and T075 can run beside component/state implementation.
- In US4, T079–T081 are independent and T083 can run alongside backend target handling.
- Polish performance, contract, lifecycle and documentation tasks T087–T090/T092 can run concurrently before final full validation.

---

## Parallel Example: User Story 1

```text
Task T020: Money/count boundary tests in services/planner/tests/unit/test_values.py
Task T021: Uniform allocator properties in services/planner/tests/unit/test_uniform.py
Task T025: Frontend plan codec tests in services/frontend/src/api/plannerCodecs.test.ts
Task T026: Fixed-budget form tests in services/frontend/src/features/campaign/PlanningFields.test.tsx
Task T027: Browser plan journey in services/frontend/e2e/fixed-budget-plan.spec.ts
```

## Parallel Example: User Story 2

```text
Task T057: Exact fact accumulator in services/frontend/src/domain/campaignFacts.ts
Task T058: Current-hour plan selection in services/frontend/src/features/execution/plannedActions.ts
Task T059: Cumulative Planner request builder in services/frontend/src/features/planning/planRequest.ts
Task T060: Pending planning-round correlation in services/frontend/src/features/planning/planningRound.ts
```

## Parallel Example: User Story 3

```text
Task T070: Actual KPI component tests in services/frontend/src/features/results/ActualKPISummary.test.tsx
Task T071: Reset/final reducer tests in services/frontend/src/features/campaign/campaignState.test.ts
Task T072: Live/final KPI browser journey in services/frontend/e2e/actual-kpi-summary.spec.ts
```

## Parallel Example: User Story 4

```text
Task T079: Target request contract tests in services/planner/tests/contract/test_target_kpi.py
Task T080: Target-mode component tests in services/frontend/src/features/campaign/PlanningFields.test.tsx
Task T081: No-mutation target browser journey in services/frontend/e2e/target-kpi-unavailable.spec.ts
```

---

## Implementation Strategy

### MVP First — User Story 1

1. Complete Setup and Foundation.
2. Implement US1 test-first through T048.
3. Stop and validate the independent fixed-budget workflow.
4. Demonstrate exact plan sum, deterministic remainder, plan table and plan-before-reset behavior.

### Incremental Delivery

1. **MVP**: Planner health + fixed-budget exact allocation + plan-first dashboard creation.
2. **Feedback**: Planned actions drive Simulator and every committed hour must replan.
3. **Outcomes**: Live/final exact cumulative KPI cards share the Planner snapshot source.
4. **Future mode**: Target-KPI is visible and explicitly unavailable at UI and service boundaries.
5. **Hardening**: Maximum-size measurements, drift checks, lifecycle isolation and complete quickstart.

### Suggested Commit Boundaries

1. `Scaffold Python planner service`
2. `Add exact uniform fixed-budget planning`
3. `Integrate planner-first campaign creation`
4. `Add hourly feedback and replanning barrier`
5. `Show live and final actual KPIs`
6. `Expose unavailable target KPI mode`
7. `Harden and document three-service workflow`

## Notes

- `[P]` means different files and no dependency on another incomplete task in the same parallel set.
- Existing feature 002 work is currently uncommitted; preserve it and avoid reverting overlapping frontend/Compose changes.
- Planner receives cumulative snapshots, not raw event append commands, and never imports or calls Simulator code.
- Simulator's existing `step_id`/ETag semantics remain mandatory even though local Compose relaxes preconditions.
- Never use binary floating-point for budget, spend, allocation or exact displayed totals.
- Keep only the latest full plan; do not accumulate all 2,160 large planning responses.
