# Data Model: Minimal Budget Planner

The feature separates four provenance classes: `user input`, `Planner output`, `Simulator fact`, and
`frontend-derived actual state`. Planner is stateless; the dashboard owns the active-run aggregate.

## Scalar Types

### ChannelID

String matching the Simulator channel contract: `^[a-z][a-z0-9_-]{0,63}$`.

### Hour

Integer relative to campaign start, `0..2,160`. A horizon is half-open. For a normal campaign,
`from_hour = 0`, `to_hour = duration_hours`, and Simulator `start_hour` corresponds to Planner hour 0.

### MoneyText

Canonical non-negative decimal string with six fractional digits. Input may have 0..6 fractional
digits but is never a JSON number. Maximum value is `9223372036854.775807`, corresponding to signed
int64 micro-units. Domain calculations convert it to integer micros.

### CountText

Canonical non-negative base-10 integer string. Transporting counts as strings prevents loss when a
browser value exceeds JavaScript's safe-integer range. Planner parses them as arbitrary precision
integers and rejects non-canonical, signed-negative or fractional values.

## Enumerations

| Entity | Values | v0 behavior |
|---|---|---|
| `PlanType` | `fixed_budget`, `target_kpi` | Target mode derives an approved budget before execution |
| `KPI` | `unique_reach`, `clicks`, `conversions` | Recorded; does not influence uniform v0 allocation |
| `Strategy` | `uniform`, `optimized` | Exact even split or saturation-aware marginal allocation |
| `MarketStatus` | `unavailable` | No runtime market feed; target mode uses a local public-catalog benchmark |
| `PlanningStatus` | `idle`, `initial_planning`, `resetting_simulation`, `ready`, `stepping`, `replanning`, `replan_failed`, `finished`, `error` | Dashboard workflow state |

## SimulationContext (user input + Simulator metadata)

| Field | Type | Rules |
|---|---|---|
| `simulation_id` | string | Same resource ID used for Simulator |
| `world_seed` | int64 decimal string | Traceability only; Planner does not interpret it |
| `campaign_seed` | int64 decimal string | Traceability only; Planner does not interpret it |
| `start_hour` | RFC3339 hour | Exactly hour-aligned |
| `time_zone` | IANA timezone | Same value supplied to Simulator reset |
| `currency` | three-letter uppercase string | From Simulator world metadata |
| `world_config_digest` | 64 lowercase hex characters | Binds plan to the configured world without exposing hidden parameters |

Audience and geography assumptions are inherited from the identified world. They are not fabricated
or exposed by Planner v0.

## Horizon

| Field | Type | Rules |
|---|---|---|
| `from_hour` | Hour | Included; normally 0 |
| `to_hour` | Hour | Excluded; `from_hour < to_hour` |

`duration = to_hour - from_hour`, `1..2,160`.

## PlanningDraft (user input)

| Field | Type | Rules |
|---|---|---|
| `type` | PlanType | Default `fixed_budget` |
| `duration_hours` | integer | Defines horizon `[0, duration_hours)` |
| `budget` | MoneyText or null | Required only for fixed budget; total for full horizon |
| `optimize` | KPI | Required for fixed budget |
| `strategy` | Strategy | User-selectable for fixed budget; `optimized` for target KPI |
| `target` | TargetKPI or null | Required for target mode |

This replaces manually entered per-channel hourly budget fields. Those caps are Planner output.

## TargetKPI

| Field | Type | Rules |
|---|---|---|
| `metric` | KPI | One of three supported KPI identifiers |
| `value` | CountText | Positive target submitted for initial target planning |

## MarketForecast

| Field | Type | Rules |
|---|---|---|
| `status` | MarketStatus | Always `unavailable` in v0 |

No rates, expected results or hidden Simulator state are present.

## ChannelState (frontend-derived actual fact)

| Field | Type | Initial | Rule |
|---|---|---:|---|
| `spent` | MoneyText | `0.000000` | Exact sum of committed channel observations |
| `impressions` | CountText | `0` | Exact cumulative sum |
| `unique_reach` | CountText | `0` | Exact cumulative sum for this channel |
| `clicks` | CountText | `0` | Exact cumulative sum |
| `conversions` | CountText | `0` | Exact cumulative sum |

There is exactly one entry for each ordered request channel.

## CampaignState (frontend-derived actual fact)

| Field | Type | Rules |
|---|---|---|
| `current_hour` | Hour | Next relative hour; may equal `to_hour` only when finished |
| `state_revision` | integer | Starts at 0; increments once per committed hour |
| `last_step_id` | UUID or null | Simulator idempotency key of latest committed fact |
| `last_observed_at` | RFC3339 hour or null | Simulator hour represented by the latest commit |
| `spent` | MoneyText | Sum of every committed observation's spend |
| `unique_reach` | CountText | Sum across hours/channels; not cross-channel deduplicated |
| `clicks` | CountText | Sum across hours/channels |
| `conversions` | CountText | Sum across hours/channels |
| `channels` | map ChannelID → ChannelState | Complete exact channel breakdown |

Campaign totals and channel totals update in the same reducer transition that accepts a validated
Simulator response. Duplicate step/hour responses are no-ops only when identical; conflicts fail.

## PlanRequest

Common fields:

| Field | Type | Rules |
|---|---|---|
| `request_id` | UUID | Generated once per state revision; reused for retry |
| `type` | PlanType | Discriminator |
| `strategy` | Strategy | Required |
| `horizon` | Horizon | Required |
| `channels` | ChannelID[] | 1..20, unique; request order is not allocation order |
| `simulation` | SimulationContext | Required traceability context |
| `market` | MarketForecast | Required explicit unavailable status |
| `current` | CampaignState | Complete cumulative snapshot, not an append event |

Fixed-budget fields:

| Field | Type | Rules |
|---|---|---|
| `budget` | MoneyText | Required |
| `optimize` | KPI | Required |
| `target` | null | Must be null/absent |

Target-KPI requests use `budget = null`, `optimize = null`, strategy `optimized`, initial revision zero
and a required `target`. The response either supplies the calculated executable budget or a capacity
diagnosis. Subsequent hourly rounds use fixed-budget requests with that calculated budget.

Cross-field invariants:

- `current.current_hour` is within `[from_hour, to_hour]`.
- `current.state_revision = current.current_hour - from_hour`.
- `current.channels` has exactly the same keys as `channels`.
- `history` (optional, oldest first) lists finished campaigns on the same market as 24 hour-of-day
  bins per channel of observable facts only: hours, requests, impressions, unique reach, clicks,
  conversions, spend. It sharpens the catalog prior for optimized plans and enters their `plan_id`.
- `simulation.currency` governs every monetary value.
- `duration × channel_count <= 43,200`.

## Allocation

| Field | Type | Rules |
|---|---|---|
| `channel_id` | ChannelID | One configured channel |
| `hour` | Hour | One included horizon hour |
| `budget_cap` | MoneyText | Non-negative exact cap |
| `expected` | HourlyExpected or null | Benchmark expectation of the channel hour (`spend`, fractional `impressions`, `unique_reach`, `clicks`, `conversions`); null for committed hours and for channels absent from the catalog |

Ordering is ascending `hour`, then lexicographic `channel_id`. Every pair occurs exactly once.

### Uniform allocation invariant

Let `B` be total budget micros and `N = duration × channel_count`:

```text
base, remainder = divmod(B, N)
cap[i] = base + 1  when i < remainder
cap[i] = base      otherwise
```

Therefore `sum(cap) = B` and `max(cap) - min(cap) <= 1 micro`.

## MediaPlan

| Field | Type | Rules |
|---|---|---|
| `request_id` | UUID | Echoes request |
| `state_revision` | integer | Echoes accepted snapshot revision |
| `plan_id` | 64-character lowercase SHA-256 hex | Stable for plan-defining inputs |
| `feasible` | boolean | `true` for every valid fixed-budget v0 response |
| `type` | PlanType | `fixed_budget` |
| `strategy` | Strategy | `uniform` |
| `optimize` | KPI | Echoed selection |
| `currency` | string | Echoed SimulationContext currency |
| `budget` | MoneyText | Canonical input total |
| `unallocated_budget` | MoneyText or null | Explicit reserve; zero for uniform, null for infeasible target responses |
| `horizon` | Horizon | Echoed |
| `expected` | ExpectedOutcome or null | Projected campaign total: observed facts plus the forecast of future caps; null only when a channel is absent from the catalog |
| `allocations` | Allocation[] | Complete deterministic schedule |
| `required_budget` | null | Reserved for target mode |
| `reason` | null | Reserved for infeasible future plans |

`plan_id` hashes a versioned canonical representation of PlanType, Strategy, KPI, budget, horizon,
sorted channels and SimulationContext. Uniform excludes CampaignState and remains stable. Optimized
also fingerprints CampaignState because every committed observation can change future allocations.

Budget conservation depends on strategy. Uniform satisfies `sum(allocation caps) = budget`.
Optimized satisfies `actual spent + future allocation caps + unallocated_budget = budget`; completed
slots reconstruct actual spend for auditability, so equivalently the complete response satisfies
`sum(allocation caps) + unallocated_budget = budget`.

## ActivePlan (dashboard state)

The latest validated MediaPlan plus an hour index `Map<Hour, ChannelAction[]>`. The index is derived
once from allocations and is not another source of truth. The dashboard retains only the latest plan,
not every full planning response.

## ActualKPISummary (presentation projection)

| Field | Source | Display |
|---|---|---|
| `unique_reach` | CampaignState.unique_reach | “Охват — сумма по каналам, без дедупликации” |
| `clicks` | CampaignState.clicks | “Клики” |
| `conversions` | CampaignState.conversions | “Конверсии” |
| `final` | Simulator status | Current while active; final when finished |

## Pending Operations

### PendingStep

Existing Simulator `step_id`, expected RFC3339 hour, selected relative plan hour, immutable normalized
actions and ETag. Ambiguous retry reuses all fields.

### PendingPlanningRound

| Field | Type | Rules |
|---|---|---|
| `request_id` | UUID | Reused for retry |
| `state_revision` | integer | Must still equal dashboard revision on response |
| `plan_id_expected` | hash or null | Existing active plan ID during replan |
| `request` | immutable PlanRequest | Complete byte-equivalent semantic snapshot |
| `attempt` | positive integer | Incremented on retry |

Late responses with the wrong request ID, revision, SimulationContext, horizon or channel coverage are
rejected as desynchronized.

## Coordinator State Transitions

```text
idle
  └─ submit valid fixed-budget draft → initial_planning
       ├─ Planner failure → error (old active run preserved)
       └─ plan accepted → resetting_simulation
            ├─ Simulator failure → error (old active run preserved)
            └─ reset accepted → ready (new plan/session; zero facts/history)

ready
  └─ one hour / automatic iteration → stepping
       ├─ unresolved failure → error (same PendingStep retained)
       └─ Simulator response validated → replanning
            ├─ facts/history/session committed atomically
            ├─ Planner failure → replan_failed
            │    └─ retry same PendingPlanningRound → replanning
            └─ matching plan accepted → ready | finished

replan_failed blocks every further Simulator step.
finished exposes the final KPI summary and plan but has no executable allocation.
```

Stopping an automatic run takes effect only between complete iterations. An iteration is complete
after the Planner response is accepted, not immediately after Simulator commits.
