# Feature Specification: Simulator Dashboard

**Feature Branch**: `002-simulator-dashboard`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Create a separate web frontend where a user can create a simulation campaign, set an hourly budget for every channel, advance one hour or run to the campaign end, and view every observed metric by channel and in aggregate."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure a simulation and campaign (Priority: P1)

A user opens the dashboard, enters a simulation identifier, market and campaign seeds, start hour
and timezone, then configures a campaign duration and a non-negative hourly budget cap for every
available channel. The dashboard confirms the simulation identity and campaign time range, currency, channels
and initial status before any hour is simulated.

**Why this priority**: Every other dashboard action depends on a valid campaign and explicit channel
budgets. This is the smallest independently valuable slice because it replaces manual request
construction for the most error-prone inputs.

**Independent Test**: Starting with a ready Simulator and no active campaign, a user can complete the
form, create a campaign with at least two channel budgets, and see an active campaign at its selected
start hour with the full duration remaining.

**Acceptance Scenarios**:

1. **Given** the Simulator is ready and exposes configured channels, **When** the user supplies valid campaign inputs and submits the form, **Then** the dashboard displays the created campaign, all available channels, its currency, current hour and remaining hours.
2. **Given** valid campaign inputs, **When** the user assigns a budget to each channel, **Then** those budget caps are retained as the active campaign for subsequent simulation steps.
3. **Given** invalid or incomplete inputs, **When** the user attempts creation, **Then** the dashboard identifies the affected fields and does not present the campaign as active.
4. **Given** another simulation already occupies the Simulator, **When** creation is rejected, **Then** the dashboard explains the conflict and preserves the entered form values.
5. **Given** a simulation already created by this dashboard, **When** the user edits campaign duration or budgets and relaunches, **Then** the same simulation ID and seeds are reset, the edited campaign becomes active, and prior displayed history is cleared only after success.
6. **Given** an active campaign and unsaved edits in the campaign form, **When** the user advances an hour, **Then** the step uses the active campaign budgets rather than the unsubmitted edits.

---

### User Story 2 - Simulate and inspect one hour (Priority: P2)

A user advances the active campaign exactly one hour and immediately sees the observed requests,
impressions, unique reach, clicks, conversions, spend and eCPM for every channel, together with the
new campaign position and visual history.

**Why this priority**: Hour-by-hour inspection is the core feedback loop needed to understand and
debug the simulated market before automating a complete run.

**Independent Test**: With a newly created campaign, one action advances the displayed current hour
by exactly 60 minutes, records one observation per configured channel, and renders that hour in all
metric visualizations.

**Acceptance Scenarios**:

1. **Given** an active campaign with remaining hours, **When** the user selects “Run one hour”, **Then** exactly one hour is committed using the currently displayed channel budgets.
2. **Given** a successful hourly step, **When** its response is shown, **Then** the dashboard presents every returned channel observation and updates all seven metric charts.
3. **Given** a channel budget of zero, **When** one hour is simulated, **Then** the channel remains visible with its available requests, zero purchased results and a missing eCPM where no impressions occurred.
4. **Given** a step failure, **When** the error is returned, **Then** the dashboard shows an actionable message, does not append a fictitious hour and allows a retry.

---

### User Story 3 - Run the remaining campaign automatically (Priority: P3)

A user starts an automatic run that repeatedly advances the campaign until its horizon is exhausted.
The dashboard reports progress as hours complete, updates results during the run, prevents duplicate
run commands, and lets the user stop after the currently executing hour.

**Why this priority**: A complete campaign may contain hundreds or thousands of hours, making manual
stepping impractical while still requiring visibility and control.

**Independent Test**: A campaign with 24 remaining hours can be run to completion from one action;
the dashboard records exactly 24 ordered hours, reaches zero remaining hours and disables further
simulation actions.

**Acceptance Scenarios**:

1. **Given** an active campaign, **When** the user selects “Run to end”, **Then** hours execute sequentially until the campaign is finished or an error occurs.
2. **Given** an automatic run is in progress, **When** the user views the dashboard, **Then** completed hours, remaining hours and percentage progress are visible and continue to update.
3. **Given** an automatic run is in progress, **When** the user selects “Stop”, **Then** no new step starts after the current request completes and all committed observations remain visible.
4. **Given** the campaign reaches its horizon, **When** the final hour completes, **Then** the dashboard marks the campaign finished and disables both run actions.

---

### User Story 4 - Compare channel and aggregate performance (Priority: P4)

A user reviews the campaign’s hourly history through a separate chart for each observed metric. Every
chart distinguishes individual channels from an aggregate series and exposes exact values for a
selected hour, allowing the user to compare supply, delivery, response and cost over time.

**Why this priority**: Visualization turns raw observations into an understandable campaign story and
is the main value of a dashboard beyond replacing manual requests.

**Independent Test**: Given a multi-channel campaign with at least three completed hours, the user can
inspect seven charts, identify every channel and the aggregate series, and retrieve the exact value
for any plotted hour and series.

**Acceptance Scenarios**:

1. **Given** completed observations, **When** the user views the results, **Then** separate charts are available for requests, impressions, unique reach, clicks, conversions, spend and eCPM.
2. **Given** a metric chart, **When** multiple channels have observations, **Then** each channel has a stable distinguishable series and the chart also contains an aggregate series.
3. **Given** requests, impressions, clicks, conversions or spend, **When** an aggregate point is calculated, **Then** it equals the sum of channel values for that hour.
4. **Given** unique reach, **When** an aggregate point is shown, **Then** it is labeled as a non-deduplicated sum of channel reach and is not presented as campaign-level unique reach.
5. **Given** eCPM, **When** an aggregate point is shown, **Then** it is calculated from total spend and total impressions rather than by summing or averaging channel eCPMs.

### Edge Cases

- The Simulator is unavailable or becomes unavailable during an automatic run.
- The channel list is empty, changes after a campaign reset, or contains a channel without an entered budget.
- A budget is empty, negative, non-numeric, too precise or too large for the Simulator contract.
- The simulation identifier contains characters that are unsafe in a URL path or exceeds its allowed length.
- The selected start time is not aligned to an hour, the timezone is unknown, or duration is outside the supported range.
- The user clicks step controls repeatedly or opens two dashboard tabs against the one-active-simulation service.
- An automatic run is stopped while a request is already in flight.
- A campaign finishes, is reset, or is replaced while old observations are still displayed.
- A channel has requests but zero impressions, requiring zero spend and no eCPM point.
- Long campaigns contain up to 2,160 hours and up to 20 channels, producing dense charts.
- Browser refresh loses transient display state while the Simulator still holds an active campaign.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The dashboard MUST show whether the Simulator is reachable and ready before enabling campaign mutations.
- **FR-002**: The dashboard MUST obtain and display the available channel identifiers and campaign currency from the Simulator configuration.
- **FR-003**: Users MUST be able to enter a simulation identifier, world seed, campaign seed, hour-aligned start time and timezone separately from campaign configuration.
- **FR-004**: Users MUST be able to enter a non-negative hourly budget cap for every available channel, using the displayed campaign currency.
- **FR-005**: The dashboard MUST validate required fields and known input constraints before submitting a campaign request.
- **FR-006**: Users MUST be able to edit campaign duration and budgets and relaunch the campaign after resetting the same simulation.
- **FR-007**: Successful simulation creation or reset MUST clear observations from the previous displayed run and show the simulation identity plus campaign status, current hour, end hour and remaining hours.
- **FR-008**: The dashboard MUST keep an active campaign snapshot separate from edits; hourly steps MUST use the active budgets until an edited campaign is successfully relaunched.
- **FR-009**: Users MUST be able to advance an active campaign by exactly one hour using the current budget cap for each channel.
- **FR-010**: Every committed step MUST append exactly one ordered observation set and update campaign status, current hour and remaining hours.
- **FR-011**: Users MUST be able to run all remaining campaign hours sequentially from a single action.
- **FR-012**: The dashboard MUST prevent overlapping manual and automatic step requests from the same dashboard session.
- **FR-013**: Users MUST be able to stop an automatic run; stopping MUST preserve completed steps and MUST take effect before another step begins.
- **FR-014**: Automatic runs MUST display completed hours, remaining hours and percentage progress throughout execution.
- **FR-015**: The dashboard MUST disable step actions when no campaign is active, a request is in flight, or the campaign is finished.
- **FR-016**: The dashboard MUST display the latest observation for every configured channel in a readable tabular or equivalent exact-value view.
- **FR-017**: The dashboard MUST maintain the ordered observation history collected during the current dashboard session.
- **FR-018**: The dashboard MUST provide separate time-series visualizations for requests, impressions, unique reach, clicks, conversions, spend and eCPM.
- **FR-019**: Every metric visualization MUST provide a stable, distinguishable series for each channel and an aggregate series.
- **FR-020**: Aggregate requests, impressions, clicks, conversions and spend MUST equal the per-hour sum of channel values.
- **FR-021**: Aggregate unique reach MUST equal the per-hour sum of channel unique reach and MUST be labeled as non-deduplicated across channels.
- **FR-022**: Aggregate eCPM MUST equal total hourly spend divided by total hourly impressions multiplied by 1,000; it MUST be absent when total impressions are zero.
- **FR-023**: Users MUST be able to identify the exact hour, series and value represented by a chart point.
- **FR-024**: Monetary values MUST preserve the precision returned by the Simulator and MUST display their currency.
- **FR-025**: Errors MUST be presented in user-facing language with the operation that failed, while preserving valid form inputs and already committed observations.
- **FR-026**: The dashboard MUST distinguish empty, loading, active, stopped, finished and error states without relying on color alone.
- **FR-027**: All interactive controls MUST be keyboard operable, visibly labeled and expose a visible focus state.
- **FR-028**: The dashboard MUST remain usable at viewport widths of 768 pixels and above without horizontal page scrolling; dense result tables may scroll within their own region.
- **FR-029**: The dashboard MUST use Russian as the initial interface language while keeping metric identifiers recognizable from the Simulator contract.
- **FR-030**: The frontend MUST be independently startable and stoppable without changing the Simulator’s active campaign state.

### Key Entities

- **Simulation Draft**: User-entered simulation identity, seeds, start hour and timezone; immutable in the dashboard after first creation.
- **Campaign Draft**: User-entered duration and editable per-channel budget caps for the next launch.
- **Active Run**: The simulation state and immutable submitted campaign snapshot currently controlled by the dashboard, including status, current hour, remaining hours, channel list, currency and latest concurrency token when present.
- **Channel Budget**: A channel identifier paired with the hourly maximum spend that will be submitted for subsequent steps.
- **Hourly Result**: One committed hour and the complete ordered set of channel observations returned for that hour.
- **Metric Series**: Ordered hourly values for one metric and one channel, or the explicitly defined aggregate of all channels.
- **Automatic Run**: The transient process that submits sequential hourly steps, tracks progress and can be stopped between steps.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can configure a two-channel campaign and produce the first simulated hour in under 2 minutes without constructing a manual API request.
- **SC-002**: After a successful one-hour operation, campaign position, exact observations and all seven metric visualizations reflect the new hour within 2 seconds.
- **SC-003**: A 168-hour campaign can run to completion from one user action with exactly 168 ordered hourly results and no duplicate or skipped displayed hours.
- **SC-004**: A user can stop an automatic run, and no additional request begins after the currently in-flight hour completes.
- **SC-005**: For campaigns containing up to 20 channels and 2,160 collected hours, all seven charts become inspectable within 3 seconds after the final data is received.
- **SC-006**: In acceptance testing, 100% of aggregate points match the documented sum or weighted-eCPM formulas, and aggregate unique reach is always marked non-deduplicated.
- **SC-007**: All creation, stepping, automatic-run and chart inspection tasks can be completed using only a keyboard at viewport widths of 768 pixels and above.
- **SC-008**: When the Simulator rejects or cannot complete an operation, the dashboard shows an actionable error and retains all previously committed observations in 100% of tested failure scenarios.

## Assumptions

- The feature is a local prototype for one operator and does not require authentication, authorization or multi-user collaboration.
- The existing Simulator remains the source of truth and continues to allow at most one active or finished simulation resource at a time.
- A budget cap applies independently to each hour; changing a displayed budget affects future steps only.
- Channels and currency come from the Simulator’s startup model and do not change during an active run.
- Cross-channel audience identity is unavailable, so aggregate unique reach is informative channel-summed reach rather than deduplicated campaign reach.
- Dashboard observation history is session-scoped; refreshing the browser may clear charts without deleting or resetting the Simulator campaign.
- An automatic run is sequential and uses the current budget values captured when each step begins.
- The frontend and Simulator are separately operable components connected through the project’s local service environment.
- Mobile layouts below 768 pixels, persistent report storage, export, authentication and editing already committed observations are outside this feature’s scope.
