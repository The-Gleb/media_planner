# Feature Specification: Minimal Budget Planner

**Feature Branch**: `[003-minimal-budget-planner]`

**Created**: 2026-09-04

**Status**: Draft

**Input**: User description: "Add fixed-budget planning and target-KPI planning. For a target KPI, estimate the least one-ruble-quantized budget that reaches the public-catalog benchmark forecast, or return a structured capacity diagnosis. After approval, execute both modes through the same fixed-budget feedback loop without automatically increasing spend."

## Clarifications

### Session 2026-09-04

- Q: Правильно ли явно зафиксировать, что v0 поддерживает только одну активную кампанию, а её часы выполняются строго последовательно без параллельных запусков? → A: Только одна активная кампания и строго последовательные шаги.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create an Even Budget Plan (Priority: P1)

A user selects fixed-budget planning, enters a total campaign budget and horizon, chooses one of the
supported KPIs, and selects the uniform-allocation strategy. The user receives a complete plan that
assigns a budget cap to every channel for every hour in the horizon.

The KPIs available for selection are unique reach (`unique_reach`), clicks (`clicks`), and
conversions (`conversions`). In this first version, the selected KPI is recorded with the plan but
does not change the uniform allocation.

**Why this priority**: A deterministic plan turns a campaign-level budget into executable hourly
channel actions and is the smallest useful planning capability.

**Independent Test**: Supply a valid total budget, a three-hour horizon and two channels. The
result contains six allocations, covers every hour/channel pair once, and its budget caps sum exactly
to the supplied total budget.

**Acceptance Scenarios**:

1. **Given** fixed-budget mode, a valid budget, a non-empty horizon and available channels, **When** the user requests a plan, **Then** the system returns one allocation for each channel in each hour.
2. **Given** a budget exactly divisible across all allocations, **When** the uniform strategy creates a plan, **Then** every allocation has the same budget cap and all caps sum to the total budget.
3. **Given** a budget that is not exactly divisible at the supported monetary precision, **When** a plan is created, **Then** the smallest monetary remainder is assigned deterministically and the caps still sum exactly to the total budget.
4. **Given** two requests with identical planning inputs, **When** plans are created, **Then** their horizons, allocation ordering and budget caps are identical.
5. **Given** the user selects any supported KPI, **When** the v0 plan is created, **Then** the selected KPI is visible in the plan while the allocation remains uniform.

---

### User Story 2 - Execute and Replan Hour by Hour (Priority: P2)

The application takes the allocations for the simulation's current hour, advances the simulation by
one hour, records the returned observations, and supplies the updated campaign state to the planner.
Uniform returns the same deterministic plan. Optimized recalibrates its channel model from committed
facts and reallocates all remaining budget over the remaining horizon after every hour.

The planner only calculates from explicitly supplied inputs. It neither reads from nor advances the
simulation itself. The application coordinating the campaign is responsible for passing plan actions
to the simulation and passing committed observations back into the next planning request.

**Why this priority**: This establishes the planner–simulator feedback loop needed for later adaptive
reallocation without prematurely adding forecasting or learning logic.

**Independent Test**: Execute one hour, supply the resulting channel facts and updated current hour,
verify uniform remains unchanged and optimized can change future caps while preserving the exact
remaining-budget constraint.

**Acceptance Scenarios**:

1. **Given** an active plan and a current simulation hour, **When** the user advances one hour, **Then** only allocations matching that hour are submitted as channel budget caps.
2. **Given** a committed simulation step, **When** its observations are incorporated, **Then** the next planning request contains updated campaign and per-channel spend, requests, impressions, unique reach, clicks and conversions.
3. **Given** updated observed state, **When** optimized replans, **Then** it maximizes expected incremental KPI over the remaining budget and horizon without conditioning reallocation on KPI lag.
4. **Given** a failed or uncommitted simulation step, **When** replanning would otherwise occur, **Then** no observed totals are changed and no new planning round is accepted as based on that failed step.
5. **Given** a plan whose current hour has no matching allocation, **When** execution is requested, **Then** the campaign does not advance and the user sees an actionable consistency error.
6. **Given** an active campaign or a step/replanning operation in progress, **When** another campaign or overlapping hourly step is requested, **Then** the request is rejected or disabled and no parallel execution begins.

---

### User Story 3 - Monitor Actual Campaign Outcomes (Priority: P3)

During execution, the user sees cumulative actual unique reach, clicks and conversions across all
completed hours and channels. When the horizon finishes, the same totals remain visible as the final
campaign outcome.

The displayed reach is the arithmetic sum of channel observations and is explicitly labeled as not
deduplicated across channels. It must not be presented as a cross-channel unique-person count.

**Why this priority**: The user needs a compact outcome view to judge campaign progress and compare
the final result with the selected KPI, even before forecasting exists.

**Independent Test**: Commit observations for at least two channels across two hours and verify that
the three displayed totals equal the exact sums of all committed observations; after the final hour,
the totals remain unchanged and are labeled final.

**Acceptance Scenarios**:

1. **Given** no completed hours, **When** a campaign begins, **Then** cumulative reach, clicks and conversions are shown as zero actual results.
2. **Given** a newly committed hour, **When** its observations are accepted, **Then** all three cumulative metrics update once using every returned channel observation.
3. **Given** a completed horizon, **When** the campaign is shown, **Then** the cumulative metrics are labeled as final and remain available with the plan and history.
4. **Given** cumulative reach is displayed, **When** the user reviews its meaning, **Then** the interface states that it is a non-deduplicated sum across channels.
5. **Given** a simulation reset for a new campaign run, **When** the reset succeeds, **Then** prior actual totals are cleared atomically with prior observation history.

---

### User Story 4 - Estimate Budget for a Target KPI (Priority: P1)

The user selects target-KPI planning, a reach/click/conversion target and a horizon. The Planner uses
the optimized public-catalog model to return the least one-ruble-quantized budget whose benchmark
forecast reaches the target. If catalog capacity cannot reach it, the result contains no executable
allocations and recommends the maximum achievable target.

**Why this priority**: This implements case planning type B and prevents users from approving a KPI
without first checking its modeled budget and capacity feasibility.

**Independent Test**: Request 50,000 clicks over 336 hours in the default eight-channel catalog and
receive a deterministic executable plan; request an impossible target and receive `feasible=false`
without resetting or advancing Simulator.

**Acceptance Scenarios**:

1. **Given** an achievable target and initial campaign state, **When** target planning completes, **Then** the response contains the target, forecast, required budget and exact full-horizon allocations.
2. **Given** an unreachable target, **When** target planning completes, **Then** the response is a non-executable capacity diagnosis and Simulator is unchanged.
3. **Given** an executable target plan is approved, **When** campaign execution starts, **Then** its calculated budget is fixed and all later planning rounds use the existing fixed-budget feedback loop.

### Edge Cases

- The total budget is zero; the plan remains feasible and contains zero caps for all allocations.
- The budget is negative, empty, non-numeric, exceeds the supported monetary range, or has more
  precision than the campaign currency permits.
- The horizon is empty, reversed, starts before the simulation's current hour, or exceeds the
  campaign duration.
- The channel list is empty or contains duplicate/unknown identifiers.
- The number of hours multiplied by the number of channels is large enough to make a full plan
  impractical; the request is rejected at the documented campaign limits rather than partially
  planned.
- A simulation spends less than a cap because inventory is unavailable. The unused amount remains
  unallocated in v0; the stable plan is not increased to compensate.
- Actual spend differs from planned caps, including a channel with zero impressions and zero spend.
- Observations are duplicated, missing a planned channel, assigned to the wrong hour, or arrive out
  of order; they are not counted twice and do not silently advance campaign state.
- Replanning is requested after the horizon has ended; the plan remains inspectable but no further
  executable allocation exists.
- The selected KPI or strategy is unsupported or absent.
- The planner is temporarily unavailable after a simulation hour commits; the facts remain retained
  and the same replanning request can be retried without advancing another hour.
- A second campaign launch or hourly step is requested while another campaign/step is active; v0
  rejects or disables it rather than running work concurrently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The planning interface MUST distinguish fixed-budget planning from target-KPI planning.
- **FR-002**: Fixed-budget planning MUST accept a total campaign budget, a half-open hourly horizon,
  the available channel identifiers, one optimization KPI, and one supported allocation strategy.
- **FR-003**: The selectable optimization KPIs MUST be `unique_reach`, `clicks`, and `conversions`,
  with user-facing labels for reach, clicks, and conversions.
- **FR-004**: The strategy control MUST identify uniform allocation as the only supported v0
  strategy and MUST NOT imply that it uses forecasts or observed performance.
- **FR-005**: Target-KPI mode MUST accept a positive reach, click or conversion target and MUST use
  the optimized public-catalog strategy at initial state revision zero.
- **FR-006**: Target-KPI planning MUST return either an executable plan with a one-ruble-quantized
  required budget and benchmark forecast, or a non-executable `target_exceeds_capacity` diagnosis.
- **FR-007**: A fixed-budget plan MUST contain exactly one allocation for every Cartesian pair of
  hour in the horizon and available channel.
- **FR-008**: Uniform allocation MUST divide the total budget across all allocations at the
  supported monetary precision, and the sum of allocation caps MUST equal the total budget exactly.
- **FR-009**: Any indivisible smallest-unit remainder MUST be distributed in stable hour-then-channel
  order so equivalent requests produce equivalent plans.
- **FR-010**: Each allocation MUST identify its channel, hour and non-negative budget cap.
- **FR-011**: Fixed-budget v0 responses MUST keep expected outcomes explicitly unavailable. Target-KPI
  responses MUST label expected outcomes as deterministic public-catalog benchmark estimates.
- **FR-012**: Valid fixed-budget plans MUST be marked feasible; invalid requests MUST return no
  executable allocations and MUST identify the validation reason.
- **FR-013**: The planning process MUST accept current campaign totals and per-channel totals for
  actual spend, impressions, unique reach, clicks and conversions.
- **FR-014**: The planner MUST calculate solely from supplied planning inputs and campaign state; it
  MUST NOT retrieve observations from or advance the simulation directly.
- **FR-015**: The campaign coordinator MUST submit only the current hour's planned channel caps to
  the simulation, then incorporate only successfully committed observations before replanning.
- **FR-016**: For unchanged plan-defining inputs, the v0 replanning result MUST retain the original
  horizon, allocation ordering and allocation caps regardless of updated actual campaign state.
- **FR-017**: Unspent budget caused by delivery below a budget cap MUST NOT be redistributed in v0.
- **FR-018**: A planning or simulation failure MUST preserve the last committed campaign state and
  permit safe retry without counting observations twice.
- **FR-019**: The interface MUST show cumulative actual unique reach, clicks and conversions while a
  campaign is active and after it finishes.
- **FR-020**: Each cumulative actual metric MUST equal the exact sum of that field over all committed
  channel observations and completed hours in the current run.
- **FR-021**: Cumulative unique reach MUST be labeled as a non-deduplicated channel sum.
- **FR-022**: After the horizon ends, actual totals MUST be labeled final and no additional plan
  allocation may be executed.
- **FR-023**: A successful simulation reset for a new run MUST clear actual KPI totals, observations
  and active-plan progress together; a failed reset MUST preserve all three.
- **FR-024**: The interface MUST keep the selected planning mode, budget, horizon, KPI and strategy
  visible alongside the active plan and actual results.
- **FR-025**: Monetary amounts MUST retain the configured currency and supported precision across
  user input, allocation, execution and actual-spend state.
- **FR-026**: User-provided inputs, planned caps, simulation observations and calculated totals MUST
  be visually and semantically distinguishable.
- **FR-027**: New controls and summaries MUST be keyboard operable, visibly labeled, readable in the
  existing Russian interface, and must not rely on color alone for state or availability.
- **FR-028**: Every plan MUST remain associated with the active simulation context that supplies its
  channel set, currency, timezone, audience assumptions and geography assumptions, so the plan's
  scope is reviewable even though those assumptions are not edited by this v0 planner.
- **FR-029**: The v0 workflow MUST support at most one active campaign and one in-flight operation;
  campaign hours MUST execute strictly sequentially, and the next Simulator step MUST NOT begin until
  the preceding observations are committed and their replanning response is accepted.
- **FR-030**: The default Compose world MUST expose `social_1`, `social_2`, `social_3`,
  `programmatic`, `marketplace_1`, `marketplace_2`, `marketplace_3`, and `sms`, using the approved
  CPM/CTR/CR ranges and retaining deterministic world generation.
- **FR-031**: Simulation reset MUST optionally accept explicit supply/CPM/CTR/CR/pause events and a
  switch that disables seed-generated drift/shocks, so two strategies can be evaluated against the
  same controlled market scenario.
- **FR-032**: Fixed-budget planning MUST offer both exact uniform allocation and a catalog-based
  optimized strategy. The optimized strategy MUST use only public world-config ranges, MUST NOT read
  hidden seeded world values, and MUST still return allocations whose micro-unit sum equals budget.
- **FR-033**: The interface MUST support two sequential runs with different strategies on the same
  simulation ID, seeds, start hour and scenario, preserving the completed first result while the
  Simulator is reset for the second run and displaying spend/reach/click/conversion comparison.
- **FR-034**: After every committed hour, `optimized` MUST subtract actual spend, recalibrate its
  channel assumptions from observed facts, and redistribute the remaining budget across all future
  slots by marginal KPI gain, whether actual KPI is below or above the initial trajectory.
- **FR-035**: Live and final summaries MUST show aggregate spend, impressions, non-deduplicated
  reach, clicks and conversions across all channels.

### Key Entities

- **Planning Mode**: Whether the campaign fixes total budget or fixes a target KPI. Only fixed budget
  is executable in this version.
- **KPI**: The selected campaign outcome—unique reach, clicks, or conversions. It is descriptive in
  v0 because uniform allocation does not optimize against performance data.
- **Strategy**: The allocation rule selected for a plan. `uniform` divides exact micro-units evenly;
  `optimized` uses saturation-aware marginal KPI water-filling over public channel benchmarks.
- **Horizon**: A half-open interval from the first included integer hour to the first excluded hour;
  its length is the number of executable campaign steps.
- **Plan Request**: The plan type, total budget, KPI, strategy, horizon, channels and latest committed
  campaign state supplied for one planning round.
- **Campaign State**: The current hour and cumulative actual totals, including a breakdown for every
  channel. It is derived only from committed simulation observations.
- **Media Plan**: Feasibility, horizon, selected KPI and strategy, and the complete deterministic set
  of hourly channel allocations. Forecast outcomes are unavailable in v0.
- **Allocation**: One channel/hour pair and its maximum permitted spend for that simulation step.
- **Planning Round**: One request and response in the feedback loop. Uniform retains its schedule;
  optimized produces a new state-correlated plan for future hours.
- **Actual KPI Summary**: Cumulative spend, impressions, non-deduplicated unique reach, clicks and
  conversions across all channels, shown live and at completion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can configure fixed-budget mode and obtain an executable plan in under two
  minutes without manually calculating per-channel or per-hour caps.
- **SC-002**: For 100% of valid test campaigns, the plan contains exactly `hours × channels`
  allocations and their caps sum exactly to the entered total budget.
- **SC-003**: For 100% of equivalent planning requests, allocation hours, channel ordering and caps
  are identical.
- **SC-004**: After each committed simulation hour, the updated plan and actual KPI summary become
  visible before the user initiates the next manual hour.
- **SC-005**: Across representative multi-hour, multi-channel runs, displayed cumulative reach,
  clicks and conversions match the exact sums of committed observations in 100% of cases.
- **SC-006**: A complete campaign executes exactly one planned action per channel per hour and never
  executes outside its configured horizon.
- **SC-007**: Achievable target requests produce an exact executable plan, while infeasible target
  requests produce zero Simulator mutations and an actionable capacity diagnosis.
- **SC-008**: A planner outage or rejected observation causes zero duplicate hours and zero duplicate
  contributions to cumulative KPIs after retry.
- **SC-009**: Across manual and automatic acceptance runs, at most one campaign is active and the
  combined number of in-flight Simulator steps and planning rounds never exceeds one.
- **SC-010**: Both strategies allocate exactly 100% of the requested micro-unit budget, while an
  optimized plan differs from a uniform plan for at least one representative eight-channel case.
- **SC-011**: A user can finish one strategy, reset, finish the other strategy and see both exact
  result rows without ever running two Simulator campaigns concurrently.

## Assumptions

- The total fixed budget applies to the entire campaign horizon, not to each hour.
- A horizon uses integer hours and half-open semantics: `from_hour` is included and `to_hour` is
  excluded.
- The existing simulation supplies the authoritative channel list, currency, current hour and
  committed hourly observations.
- The selected simulation world supplies the campaign's audience and geography assumptions; editing
  those assumptions is outside the minimal planner but their simulation context remains traceable
  from the plan.
- The application coordinating the user workflow passes actions to the simulation and facts back to
  the planner. Direct planner-to-simulation access is outside this feature.
- The full original plan is returned on every v0 planning round. The coordinator selects allocations
  for the current hour; completed allocations remain in the plan for auditability.
- Uniform allocation ignores the selected KPI and observed results. Optimized allocation uses the
  selected KPI and public range midpoints but its forecast values remain internal and are not exposed
  as product forecasts in this iteration.
- Learned forecasts, unused-budget recovery, deduplicated cross-channel reach, probabilistic service
  levels and automatic post-launch budget increases are outside this feature.
- The current campaign limits of up to 2,160 hours and 20 channels remain applicable.
- Parallel campaign execution and overlapping hourly steps are outside v0 scope.
- Until Simulator gains a package-purchase action, `sms` is represented internally by an effective
  CPM-equivalent per thousand delivered messages; its CTR/CR and supply behavior use the SMS ranges.
