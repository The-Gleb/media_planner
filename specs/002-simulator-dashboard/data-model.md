# Data Model: Simulator Dashboard

The dashboard does not introduce durable server-side storage. Its model distinguishes four origins:
`user input`, `Simulator metadata/state`, `observed facts`, and `derived presentation values`.

## WorldMetadata (Simulator fact)

| Field | Type | Rules |
|---|---|---|
| `engineVersion` | string | Non-empty public engine identifier |
| `worldConfigDigest` | string | 64 lowercase hexadecimal characters |
| `currency` | string | ISO-4217-style three uppercase letters |
| `channelIds` | ordered `ChannelID[]` | 1..20 unique IDs, each `^[a-z][a-z0-9_-]{0,63}$` |

Loaded only after readiness succeeds. It supplies all budget rows and labels; hidden market model
fields never enter the frontend.

## SimulationDraft (user input)

| Field | Type | Rules |
|---|---|---|
| `simulationId` | string | `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` |
| `worldSeed` | decimal string | Signed 64-bit range; canonical integer syntax |
| `campaignSeed` | decimal string | Signed 64-bit range; canonical integer syntax |
| `startHour` | RFC3339 string / form value | Valid instant exactly aligned to an hour |
| `timeZone` | string | Valid IANA timezone, 1..64 characters |

These fields identify the simulated world and its initial position. After the first successful create,
the dashboard keeps them immutable while campaigns are edited and relaunched on that same simulation.

## CampaignDraft (user input)

| Field | Type | Rules |
|---|---|---|
| `durationHours` | integer | 1..2,160 |
| `budgets` | `Map<ChannelID, MoneyText>` | Exactly one editable entry for every current metadata channel |
| `fieldErrors` | map | Local or decoded Simulator field errors; does not erase values |
| `dirty` | boolean | Whether campaign inputs differ from the active campaign |

`MoneyText` is non-negative decimal text with at most six fractional digits. Empty input is invalid,
not zero. A normalized action uses a canonical decimal representation at the API boundary; the
displayed user text need not be rewritten while editing.

## ChannelBudget (user input submitted per hour)

| Field | Type | Rules |
|---|---|---|
| `channelId` | `ChannelID` | Must occur once and belong to current metadata/session |
| `budgetCap` | `MoneyText` | Non-negative, <=6 fractional digits, accepted by Simulator money range |

Every step sends the complete ordered channel list from the active campaign snapshot. Editing the
campaign draft never changes an in-progress run; edited values become active only after a successful
simulation reset and campaign relaunch.

## ActiveRun (Simulator state plus submitted campaign snapshot)

| Field | Type | Rules |
|---|---|---|
| `simulationId` | string | Equals the resource path ID |
| `status` | `active \| finished` | Returned by Simulator |
| `currentHour` | RFC3339 hour | Next hour not yet simulated |
| `endHourExclusive` | RFC3339 hour | `start + duration` when create/reset state is available |
| `durationHours` | integer | 1..2,160 |
| `remainingHours` | integer | 0..duration; zero iff finished |
| `timeZone` | string | Campaign profile timezone |
| `currency` | string | Must match current WorldMetadata |
| `engineVersion` | string | Traceability identifier |
| `worldConfigDigest` | string | Traceability identifier |
| `channelIds` | ordered array | Immutable for this session |
| `etag` | string or null | Latest strong ETag; sent when present even in relaxed mode |

The Simulator resource is the server source of truth for time and generated state. The dashboard
retains the submitted campaign duration and budgets as a separate immutable active snapshot. A
successful reset replaces both and only then atomically clears displayed history. A failed reset
leaves the prior active run/history untouched.

## Observation (observed fact)

| Field | Type | Rules |
|---|---|---|
| `channelId` | `ChannelID` | Exactly one observation per configured channel per result |
| `hour` | RFC3339 hour | Equals the parent result's `observedHour` |
| `requests` | non-negative `BigInt` | Transport number must be safe; convert after decoding |
| `impressions` | non-negative `BigInt` | `<= requests`; transport number must be safe |
| `uniqueReach` | non-negative `BigInt` | Newly reached by this channel/hour; safe transport number |
| `clicks` | non-negative `BigInt` | `<= impressions`; transport number must be safe |
| `conversions` | non-negative `BigInt` | `<= clicks`; transport number must be safe |
| `spend` | `MoneyText` | Raw decimal string retained |
| `ecpm` | `MoneyText \| null` | Null iff no impressions; raw string retained |

## HourlyResult (observed fact container)

| Field | Type | Rules |
|---|---|---|
| `stepId` | UUID | Stable idempotency key for this body |
| `observedHour` | RFC3339 hour | Unique and strictly increasing in local history |
| `nextHour` | RFC3339 hour | Exactly one hour after observed hour |
| `status` | `active \| finished` | Post-step state |
| `remainingHours` | integer | Decreases by exactly one from pre-step state |
| `observations` | ordered `Observation[]` | Covers every session channel exactly once |
| `aggregate` | `HourlyAggregate` | Calculated once after validation and before atomic append |

History is an ordered `HourlyResult[]`, not seven duplicated chart datasets. An append is accepted only
after response validation; duplicate `observedHour` is idempotently ignored only when the `stepId`
and data are identical, otherwise it is a desynchronization error.

## HourlyAggregate (derived value)

For one observed hour:

- `requests`, `impressions`, `clicks`, `conversions`: exact sums of channel integers.
- `uniqueReach`: exact channel sum, always labeled “сумма по каналам, без дедупликации”.
- `spendMicros`: sum of parsed channel spend micro-units using `BigInt`.
- `spend`: canonical decimal representation of `spendMicros` plus session currency.
- `ecpm`: `ceil6(total spend / total impressions * 1000)`, or `null` when total impressions is zero.

For exact integer computation, if `S` is spend in micro-units and `I > 0`, aggregate eCPM micro-units
is `ceil(S * 1000 / I)`: integer quotient plus one whenever the remainder is non-zero. This mirrors
the Simulator's conservative micro-unit rounding. Chart `number` projections are not used as
calculation sources.

## MetricSeries (derived presentation)

| Field | Type | Rules |
|---|---|---|
| `metric` | seven-metric enum | requests, impressions, unique_reach, clicks, conversions, spend, ecpm |
| `seriesId` | ChannelID or `aggregate` | Stable across metric tabs |
| `label` | localized string | Includes API identifier; aggregate reach includes warning |
| `style` | color + dash/weight | Stable by series ID; never color-only |
| `points` | ordered projection | `{hour, plottedNumberOrNull, exactDisplayValue}` sourced from history |

`ecpm: null` remains a chart gap, never a zero point. The exact inspector always reads raw/derived
exact values rather than chart coordinates.

## PendingStep

| Field | Type | Rules |
|---|---|---|
| `stepId` | UUID | Generated once before request |
| `expectedHour` | RFC3339 hour | Campaign current hour at start |
| `actions` | immutable `ChannelBudget[]` | Normalized, complete, deterministic ordering |
| `etag` | string or null | ETag captured at start |
| `attempt` | positive integer | Retry counter for same ID/body only |

## Execution state transitions

```text
idle ──step──> stepping ──success──> idle | finished
  │                 └──failure──> error ──retry same pending step──> stepping
  └──run───> auto_running ──each success──> auto_running
                    │                         ├──horizon──> finished
                    ├──stop──> stopping ──────└──after current response──> stopped
                    └──failure──────────────────────────────────────────> error

stopped ──step/run──> stepping | auto_running
finished ──reset success──> idle
```

Only one pending step exists. `stopping` does not abort the HTTP request. Create/reset/step/run controls
are mutually excluded while a mutation is in flight. Campaign editing remains available between
mutations, but cannot affect the active run until an explicit reset and relaunch succeeds.

## Dashboard visible states

- `empty`: no usable metadata/campaign; creation is disabled until readiness/metadata succeeds.
- `loading`: health, metadata or mutation request in progress.
- `active`: server campaign has remaining hours; history may be empty.
- `stopped`: an automatic run stopped between hours; campaign remains active.
- `finished`: remaining hours zero; step controls disabled.
- `error`: most recent operation failed; valid draft, campaign and history remain visible.
- `detached/desynchronized`: known server position cannot be reconciled with session history; no
  observations are fabricated and the user may inspect retained data or explicitly reset.
