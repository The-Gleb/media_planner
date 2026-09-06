# UI and Orchestration Contract: Minimal Budget Planner

## Service Boundaries

The browser dashboard is the v0 coordinator and uses two independent same-origin routes:

- `/api/...` proxies unchanged to Simulator.
- `/planner-api/...` removes the prefix and proxies to Planner.

Planner and Simulator do not call each other. A frontend restart does not reset either service.
Planner readiness and Simulator readiness/metadata are checked separately and named separately in
the UI. Frontend static liveness does not imply either dependency is healthy.

## Campaign Form

The existing form keeps the separate Simulation section:

- simulation ID;
- world seed and campaign seed;
- Simulator start hour;
- timezone.

The Campaign section replaces manual per-channel hourly caps with:

- planning mode: “Фиксированный бюджет” and “Целевой KPI”;
- total campaign budget and currency;
- duration in hours, defining Planner horizon `[0, duration)`;
- KPI: “Охват (`unique_reach`)”, “Клики (`clicks`)”, or “Конверсии (`conversions`)”;
- strategy: “Равномерно (`uniform`)” or “Оптимизировано (`optimized`)”.

Target-KPI mode accepts a positive target, fixes strategy `optimized` and explains that its calculated
budget is a public-catalog estimate. Only Planner creates channel/hour caps; the UI never presents
manual and planned caps as competing inputs.

## Initial Plan and Reset Transaction

On submit:

1. Validate Simulation and Campaign drafts locally.
2. Build zero CampaignState and request either a fixed-budget plan or an initial target-KPI estimate.
3. For an infeasible target, show the capacity diagnosis and do not reset Simulator.
4. For an executable result, validate correlation, exact `sum(caps) + unallocated_budget = budget`,
   horizon and channel/hour coverage.
5. Create/reset Simulator with the same start and duration.
6. On success, atomically install the Simulator session and ActivePlan and clear old history, actual
   totals and pending operations.

Planner failure never calls Simulator. Simulator failure never replaces the current active plan/run;
the side-effect-free candidate plan may be discarded and the user's draft remains editable.

## Plan Presentation

After successful creation the dashboard shows:

- total budget and currency;
- source mode, selected KPI and strategy;
- for target mode, the original target, calculated budget and benchmark forecast;
- relative horizon and allocation count;
- explicit “Резерв вне каналов” and a saturation explanation when it is non-zero;
- plan ID prefix for traceability;
- “Прогноз недоступен” for fixed-budget v0; a labeled public-catalog forecast for target mode;
- an exact allocation table with hour rows and channel columns.

The table uses bounded pagination (24 hours per page by default) so a 2,160-hour plan does not mount
all 43,200 cells at once. The current relative hour is identified. Every monetary value is rendered
from exact response text; no chart coordinate is used as a calculation source.

## One-Hour Workflow

For relative hour `h = duration_hours - remaining_hours`:

1. ActivePlan must contain exactly one allocation for every active channel at `h`.
2. Convert those allocations to the existing Simulator ChannelAction list without changing caps.
3. Create/freeze PendingStep and submit one Simulator step.
4. Validate step ID, expected RFC3339 observed hour, next hour, remaining count and channel coverage.
5. In one state transition append the raw result, advance the Simulator session and increment exact
   campaign/per-channel actual state.
6. Freeze a PlanningRound for the new `state_revision` and request a fixed-budget plan using the
   originally entered or target-derived approved budget.
7. Accept only a response with matching request ID, revision, horizon, budget and complete allocation
   schedule. Require the previous plan ID only for uniform; optimized receives a state-derived ID.
8. Enable the next step, or mark the campaign finished.

Uniform returns the same plan while optimized may redistribute every future cap. Automatic execution
awaits this complete workflow for each hour.

## Retry and Failure Behavior

- Ambiguous Simulator failure retains the same PendingStep ID, normalized actions and ETag.
- After a committed Simulator response, Planner failure enters `replan_failed`; history and actual
  totals remain committed, but all further Simulator steps are disabled.
- “Повторить перепланирование” reuses the same request ID and exact cumulative snapshot.
- A late Planner response is ignored/rejected if its request ID or state revision no longer matches.
- Automatic execution pauses on either failure and never skips the replanning barrier.
- Browser loss after a commit cannot be reconstructed because Simulator has no observation-history
  endpoint. The dashboard reports desynchronization and never fabricates missing facts.

## Actual KPI Summary

Three cards appear before execution controls:

| Card | Exact source | Active label | Finished label |
|---|---|---|---|
| Охват | CampaignState `unique_reach` | Фактически на текущий момент | Итоговый; сумма по каналам, без дедупликации |
| Клики | CampaignState `clicks` | Фактически на текущий момент | Итоговые |
| Конверсии | CampaignState `conversions` | Фактически на текущий момент | Итоговые |

All cards show zero before the first committed hour and update once per accepted hour. They do not
reuse hourly chart aggregates or Planner expected fields. Reset success clears them with history;
reset failure leaves them untouched.

## Accessibility and Responsive Behavior

- Mode, KPI and strategy controls have programmatic Russian labels and visible focus.
- Disabled/unavailable meaning is conveyed by text, not color or a disabled control alone.
- Planning/replanning status uses polite live announcements; failures use assertive alerts.
- The allocation table is a named, focusable horizontal-scroll region and pagination is keyboard
  operable.
- At viewport widths >=768 px, the page itself has no horizontal scrolling.

## Acceptance State Machine

```text
draft → initial planning → Simulator reset → ready
ready → Simulator step → facts committed/replanning → ready | finished
facts committed/replanning → Planner failure → replan failed → retry replanning
```

No UI transition may jump directly from a committed Simulator step to another Simulator step.
