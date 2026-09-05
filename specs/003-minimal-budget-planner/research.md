# Research: Minimal Budget Planner

## Service Boundary and Coordinator

**Decision**: The frontend is the v0 campaign coordinator. Planner is a pure stateless calculator and
Simulator remains the authority for committed time and observations. Planner never invokes Simulator.

**Rationale**: This preserves the three requested deployable entities, reuses the existing sequential
dashboard controller and avoids a fourth coordinator service. Snapshot-in/plan-out calls are naturally
retryable and ready for future adaptive strategies.

**Alternatives considered**: Planner or Simulator owning the other service was rejected because it
mixes calculation policy with irreversible execution. A durable coordinator is appropriate once runs
must survive browser loss or multiple operators, but is beyond this in-memory prototype.

## Hourly Commit and Replanning Barrier

**Decision**: Use `plan → Simulator step → validate/commit facts → Planner replan → next step`. After
Simulator commits, the next step remains disabled until replanning succeeds.

**Rationale**: There is no distributed transaction. Simulator's successful step is the irreversible
fact boundary. Retrying the same cumulative Planner snapshot avoids rollback or skipped feedback.

**Alternatives considered**: Replanning before fact commit consumes hypothetical state. Continuing
with the old plan during Planner failure breaks the intended protocol and becomes unsafe when planning
adapts. Parallel calls admit stale responses.

## Creation and Reset Ordering

**Decision**: For a new or edited campaign, obtain the initial plan before creating or resetting
Simulator. Promote the new session, plan, zero facts and empty history only after both calls succeed.

**Rationale**: Planner has no side effects, so its output can be discarded if Simulator rejects the
reset. The prior active run remains intact on either failure.

**Alternatives considered**: Resetting Simulator first can leave a new world position without a plan.
Compensating reset adds an unsafe distributed rollback.

## Python Runtime and HTTP Stack

**Decision**: Use Python 3.14.7 on an official slim Debian image, FastAPI 0.141.x with Pydantic 2.13.x,
and one Uvicorn process. Lock exact artifacts in `uv.lock`.

**Rationale**: The current stable Python line supports the requested typed domain; FastAPI/Pydantic
provide strict validation and OpenAPI 3.1 with little transport code. One process is sufficient for
the bounded stateless calculation.

**Alternatives considered**: Standard-library HTTP with manual validation and Flask with separate
schema tooling require more boundary code. Alpine adds musl wheel/build friction without product value.

**Sources**: [Python releases](https://www.python.org/doc/versions/), [FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/), [FastAPI versions](https://fastapi.tiangolo.com/deployment/versions/), [Pydantic configuration](https://docs.pydantic.dev/latest/api/config/).

## Exact Money and Uniform Distribution

**Decision**: Transport money as non-negative decimal strings with at most six fractional digits.
Convert validated values to integer micros, compute
`base, remainder = divmod(total_micros, hours × channels)`, and add one micro to the first `remainder`
allocations in ascending-hour then lexicographic-channel order.

**Rationale**: Integer allocation proves `sum(caps) == budget`, bounds cap differences to one micro
and avoids binary floating-point. Stable ordering makes remainder assignment reproducible.

**Alternatives considered**: `float` violates exact financial requirements. Decimal division with a
correction pass is less direct. Dropping the remainder violates the budget invariant.

**Source**: [Python Decimal](https://docs.python.org/3.14/library/decimal.html).

## Relative Integer Hours

**Decision**: Planner hours are campaign-relative integer offsets. The dashboard horizon is
`[0, duration_hours)`; offset 0 corresponds to Simulator `start_hour`. Current offset is
`duration_hours - remaining_hours`.

**Rationale**: This honors `Hour = int` without duplicating wall-clock/timezone behavior owned by
Simulator.

**Alternatives considered**: Unix epoch hours leak wall-clock conversion into Planner. RFC3339
contradicts the requested Planner model. Independent offset inputs risk a duration mismatch.

## Stable Full Plan and Correlation

**Decision**: Every response contains the full original schedule. `plan_id` fingerprints canonical
plan-defining inputs and excludes actual state; `request_id` and `state_revision` are echoed so the
frontend rejects late responses. Replanning accepts cumulative facts but does not change allocations.

**Rationale**: Equivalent inputs produce equivalent output without Planner persistence. The response
acknowledges the exact fact revision while preserving stable v0 allocation.

**Alternatives considered**: Planner storage is unnecessary. Returning only remaining allocations or
deltas changes the required full-plan semantics. Incremental fact events require duplicate storage.

## Forecast and Target-KPI Fields

> Superseded for target-KPI creation by “Target-KPI Inversion Extension” below. Fixed-budget v0
> responses continue to use null expected fields.

**Decision**: Requests carry `market: {status: "unavailable"}` and MediaPlan/allocation expected fields
are `null`. Target-KPI requests receive an RFC 9457 `unsupported_plan_type` problem.

**Rationale**: Zero values would appear to be evidence. Explicit unavailability retains future
extension points without fabricating a forecast.

**Alternatives considered**: Invented zeros and silent fixed-budget fallback are misleading. Removing
the fields creates avoidable future contract churn.

## Frontend State and Actual Totals

**Decision**: Keep editable planning draft, active plan, Simulator session, immutable raw history,
incremental campaign/per-channel facts and pending round distinct. One `stepCommitted` transition
updates session/history/totals and enters replanning. KPI cards read the same exact totals.

**Rationale**: Different provenance and lifecycles cannot silently overwrite each other. Incremental
updates are O(channels) and match the snapshot sent to Planner.

**Alternatives considered**: Reducing all history after every hour is O(hours × channels) per step.
Trusting Planner-echoed totals makes Simulator facts non-authoritative.

## Same-Origin Routing and Compose

**Decision**: Run Planner on internal port 8080 and loopback host port 8082. Preserve `/api/` →
Simulator and add `/planner-api/` → Planner in nginx and Vite. Frontend startup depends on both health
checks; runtime failures remain retryable in the UI.

**Rationale**: Separate prefixes avoid CORS and existing Simulator-route migration while retaining
independent service inspection and the repository's hardened container pattern.

**Alternatives considered**: Direct browser host-port calls require CORS. Routing through Simulator
violates ownership. An internal-only Compose network is unnecessary for loopback-published dev ports.

## Verification Strategy

**Decision**: Use pytest unit tests and Hypothesis allocator properties, strict HTTP/OpenAPI tests,
Ruff, mypy, existing frontend unit/component tests, Playwright journeys and Compose integration checks.

**Rationale**: Properties cover quotient/remainder boundaries; cross-container tests prove ordering,
failure recovery and displayed actual totals.

**Alternatives considered**: Examples alone under-cover allocation boundaries. End-to-end tests alone
are slow and poor at isolating calculation defects.

**Sources**: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), [pytest](https://pypi.org/project/pytest/), [Hypothesis](https://pypi.org/project/hypothesis/), [Ruff](https://pypi.org/project/ruff/), [mypy](https://mypy.readthedocs.io/en/stable/getting_started.html).

## Accepted v0 Full-Plan Amplification

**Decision**: Keep the required full plan on each round, retain only the latest plan in the browser,
cap input at 43,200 allocations and benchmark typical/maximal payloads.

**Rationale**: A maximum campaign can serialize about 93 million allocation objects across 2,160
rounds. This is acceptable only as a measured prototype limitation.

**Alternatives considered**: Conditional/delta responses are a future optimization that changes v0
semantics. Accumulating all responses multiplies memory without audit value.

## Target-KPI Inversion Extension

**Decision**: Implement planning type B only at initial state revision zero. Use the existing
catalog-optimized fixed-budget solver as the forward function and binary-search the least whole-ruble
budget whose deterministic benchmark forecast reaches the target.

**Rationale**: This reuses one allocation policy for both planning modes. Once approved, the derived
budget becomes immutable execution input and every later round uses the existing fixed-budget
feedback loop, preventing silent spend increases.

**Alternatives considered**: Re-solving the required total budget after every observed hour was
rejected because it lets model changes increase financial commitment without a new approval. Treating
capacity failure as HTTP validation failure was rejected because infeasibility is a valid domain result.
