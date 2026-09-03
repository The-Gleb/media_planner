# Data Model: Simulator v0

## Domain conventions

- **Hour**: RFC 3339 instant aligned to `minute=second=nanosecond=0`. State stores UTC; hourly and
  weekday profiles use the configured IANA timezone. Advancing a step adds exactly 60 minutes to the
  instant, including across DST transitions.
- **ChannelID**: Non-empty stable string matching `^[a-z][a-z0-9_-]{0,63}$`.
- **Counts**: Non-negative `int64`. Configuration bounds MUST prevent generated or cumulative counts
  from overflowing `int64`.
- **MoneyMicros**: Non-negative `int64` in one-millionth of the configured ISO-4217 currency unit.
  HTTP represents it as a decimal string with no more than six fractional digits.
- **Rate**: Finite `float64` in `[0,1]`; used only for probabilities/factors, never accumulated money.
- **Stable order**: Configured channels, actions and observations are normalized by ChannelID.

## Entities

### SimulationResource

Represents the externally addressable run and owns exactly one `Simulator` state machine.

| Field | Type | Rules |
|---|---|---|
| `simulation_id` | string | Planner-supplied URL-safe identifier; 1–128 characters; immutable |
| `status` | enum | `active`, `finished`, `deleted` |
| `revision` | uint64 | Starts at 1 after Reset; increments once per committed Step/Reset |
| `engine_version` | string | Immutable for run; `sim-v0` initially |
| `world_config_digest` | hex SHA-256 | Digest of normalized startup model config |
| `config` | SimulationConfig | Immutable until explicit conditional Reset |
| `world` | HiddenWorld | Generated only by world seed and model config |
| `campaign` | CampaignState | Mutable cumulative state and predetermined events |
| `step_cache` | bounded map | `step_id` to normalized request hash, response and resulting ETag |

Only one resource may be `active` or `finished` in v0. A new ID receives `409 active_limit` while
another resource exists; replacing the same ID requires its current ETag.

### SimulationConfig

| Field | Type | Rules |
|---|---|---|
| `world_seed` | int64 | Required; HTTP decimal string to preserve full range |
| `campaign_seed` | int64 | Required; HTTP decimal string to preserve full range |
| `start_hour` | Hour | Required and hour-aligned |
| `duration_hours` | int | Required, `1..2160` |
| `time_zone` | string | Required valid IANA timezone |

The supplied Go shape is retained with one necessary extension for temporal profiles:

```go
type SimulationConfig struct {
    WorldSeed    int64
    CampaignSeed int64
    StartHour    Hour
    DurationHours int
    TimeZone     string
}
```

Currency, channels, range definitions and engine version are service model configuration, not
per-run values. The Reset response exposes their resolved identity.

### WorldModelConfig

Read-only startup configuration validated before readiness becomes healthy.

| Field | Type | Rules |
|---|---|---|
| `engine_version` | string | Must equal a version supported by the binary |
| `currency` | string | Exactly one uppercase ISO-4217 code; no conversion in Simulator |
| `money_scale` | integer | Exactly 6 in v0 |
| `channels` | ChannelModelConfig[] | `1..20`, unique ChannelID |

The normalized JSON byte representation is hashed into `world_config_digest`.

### ChannelModelConfig

Defines plausible ranges, not the concrete channel generated for a run.

| Group | Fields |
|---|---|
| Identity | `id`, `type` |
| Base | CPM positive range; CTR/CR probability ranges; requests/day and capacity integer ranges |
| Hourly profiles | Peak count, circular center, width and amplitude ranges for supply/CPM/CTR/CR |
| Weekday profiles | Variation range and weekend modifier range for supply/CPM/CTR/CR |
| Saturation | Start threshold, price growth, reach decay, frequency reach decay, CTR fatigue and frequency fatigue ranges |
| Volatility | Lognormal sigma ranges for requests and CPM |
| Drift | Occurrence probability, log-strength and duration ranges for supply/CPM/CTR/CR |
| Shocks | Occurrence probability, multiplier and duration ranges for supply/CPM/CTR/CR; pause probability/duration |

Positive bases use `log_uniform(min,max)` in v0; rates use `logit_uniform(min,max)`. The labels
`lognormal` and `beta` are not accepted with only min/max because their shape is undefined. Lognormal
is used for hourly noise, for which sigma is explicitly configured. Generated requests/day and
audience capacity are rounded to positive integers once during world generation.

### HiddenWorld

Generated during Reset solely from `world_seed`, engine version and normalized model config.

| Field | Type | Meaning |
|---|---|---|
| `channels` | map[ChannelID]HiddenChannel | Concrete market for every configured channel |
| `fingerprint` | SHA-256 | Non-secret diagnostic identity; no hidden values exposed |

### HiddenChannel

| Group | Concrete generated values |
|---|---|
| Base | `base_cpm_micros`, `base_ctr`, `base_cr`, `base_requests_per_day`, `audience_capacity` |
| Hourly | Four normalized arrays computed from generated peaks; arrays are hidden output, not config |
| Weekly | Four normalized seven-day profiles |
| Saturation | Threshold and strengths for price, reach and fatigue curves |
| Volatility | Request and CPM sigma |
| Event characteristics | Concrete probability/range choices used to create campaign schedules |

Changing `campaign_seed` MUST NOT change HiddenWorld or its fingerprint.

### CampaignState

Generated/reset from `campaign_seed`, HiddenWorld, start and duration; then updated per Step.

| Field | Type | Rules |
|---|---|---|
| `current_hour` | Hour | Next hour not yet simulated; equals StartHour after Reset |
| `steps_completed` | int | `0..duration_hours` |
| `channels` | map[ChannelID]ChannelRuntimeState | Mutable cumulative per-channel state |
| `events` | EventSchedule[] | Predetermined drift/shock/pause schedules |

### ChannelRuntimeState

| Field | Type | Rules |
|---|---|---|
| `cumulative_impressions` | int64 | Non-negative |
| `cumulative_unique_reach` | int64 | `0..audience_capacity` |

Clicks, conversions and spend do not affect saturation/fatigue in v0 and need not be cumulative state.
They remain reproducible in returned/cached observations.

### EventSchedule

| Field | Type | Rules |
|---|---|---|
| `channel_id` | ChannelID | Existing channel |
| `kind` | enum | `drift` or `shock` |
| `metric` | enum | `supply`, `cpm`, `ctr`, `cr`, or `pause` for shock |
| `start_index` | int | Hour index inside run |
| `duration_hours` | int | Positive |
| `direction` | -1 or +1 | Drift only |
| `log_strength` | float64 | Drift only, non-negative |
| `multiplier` | float64 | Shock only, non-negative |

At most one drift and one shock exist per channel/metric in v0. Drift transitions to a new persistent
level; shock returns to factor 1 after its duration. Pause overrides supply and yields zero requests.

### ChannelAction

| Field | Type | Rules |
|---|---|---|
| `channel_id` | ChannelID | Known and unique within request |
| `budget_cap` | MoneyMicros | Non-negative |

Actions may be sparse: an omitted active channel receives a zero cap but still returns an Observation.
The compatibility Go façade may expose `BudgetCap float64`; it immediately validates and converts the
value once, before simulation calculations.

### Observation

Represents one channel during the simulated hour. It contains no hidden rate or user identifier.

| Field | Type | Meaning/rules |
|---|---|---|
| `channel_id` | ChannelID | Channel observed |
| `hour` | Hour | Hour just simulated, not next current hour |
| `requests` | int64 | Available ad opportunities; at most one impression per request |
| `impressions` | int64 | Purchased impressions, `0..requests` |
| `unique_reach` | int64 | Users new to this channel in this hour, `0..impressions` |
| `clicks` | int64 | `0..impressions` |
| `conversions` | int64 | `0..clicks` |
| `spend` | MoneyMicros | `0..budget_cap` |
| `ecpm` | nullable decimal | `null` iff impressions is zero; otherwise observed spend/impressions × 1000 |

Per-channel `unique_reach` values MUST NOT be summed and presented as campaign-deduplicated reach.
Cross-channel audience overlap is a future Predictor/shared-audience concern.

### StepRecord

| Field | Type | Rules |
|---|---|---|
| `step_id` | UUID | Unique within simulation |
| `observed_hour` | Hour | Value of CurrentHour before commit |
| `normalized_action_hash` | SHA-256 | Stable hash of sorted, quantized actions |
| `observations` | Observation[] | Stable ChannelID order |
| `resulting_revision` | uint64 | Revision after commit |

The bounded cache retains enough recent StepRecords for retry. Reuse with a different action hash is
an error.

## Relationships

```text
WorldModelConfig 1 ──generates──> 1 HiddenWorld
SimulationConfig 1 ──configures─> 1 SimulationResource
HiddenWorld      1 ──contains───> N HiddenChannel
CampaignState    1 ──tracks─────> N ChannelRuntimeState
CampaignState    1 ──owns───────> N EventSchedule
StepRecord       1 ──contains───> N Observation
ChannelAction    N ──influences─> N Observation for one observed Hour
```

## State transitions

```text
NONEXISTENT --conditional Reset--> ACTIVE (current = start, completed = 0)
ACTIVE      --successful Step----> ACTIVE (current += 60m, completed += 1)
ACTIVE      --last Step----------> FINISHED (completed = duration)
ACTIVE      --conditional Reset--> ACTIVE (new world/state, revision += 1)
ACTIVE/FINISHED --Delete---------> DELETED tombstone
DELETED     --tombstone expiry---> NONEXISTENT
```

Malformed config/action, stale ETag, cancellation before commit, invariant failure, and Step after
finish leave all state, random provenance, revision and CurrentHour unchanged.

## World generation

For every channel/component, derive independent random streams from a canonical tuple. Generate:

1. base CPM/CTR/CR, requests/day and audience capacity;
2. independent hourly peaks for supply, CPM, CTR and CR;
3. structured weekday factors and weekend modifier;
4. saturation/reach/fatigue strengths;
5. request/CPM volatility;
6. campaign-specific drift, shock and pause schedules.

For metric `x`, circular hourly profile:

```text
raw_x(h) = 1 + Σ amplitude_k × exp(-distance24(h, center_k)^2 / (2 × width_k^2))
hour_factor_x(h) = raw_x(h) / mean(raw_x(0..23))
```

Weekday factors are generated smoothly, modified jointly for Saturday/Sunday, kept positive and
normalized to mean 1. Base hourly requests equal `base_requests_per_day / 24`.

## Hour calculation order

All channel calculations read runtime state at the start of the hour.

### 1. Saturation and frequency

```text
saturation = clamp(cumulative_unique_reach / audience_capacity, 0, 1)
frequency = 1                                       if cumulative_unique_reach = 0
frequency = max(1, cumulative_impressions /
                   cumulative_unique_reach)         otherwise
z = clamp((saturation - start_threshold) /
          (1 - start_threshold), 0, 1)
```

### 2. Reach, price and fatigue factors

```text
new_user_probability = clamp(
    (1-z)^reach_decay_strength ×
    exp(-frequency_reach_decay_strength × max(frequency-1, 0)),
    0, 1)

saturation_price_factor = 1 + price_growth_strength × z²

fatigue_factor = exp(
    -ctr_fatigue_strength × z
    -frequency_fatigue_strength × max(frequency-1, 0))
```

### 3. Noise and events

Positive fast noise for requests and CPM has mean 1:

```text
noise = exp(sigma × Normal(0,1) - sigma²/2)
```

Drift at/after start progresses over configured duration and then persists:

```text
progress = clamp((hour_index - start_index + 1) / duration_hours, 0, 1)
drift_factor = exp(direction × log_strength × progress)
```

Shock multiplier applies only while `start_index <= hour_index < start_index + duration_hours`.

### 4. Hidden market values

```text
requests_raw = base_requests_per_day / 24
    × hour_factor_supply × weekday_factor_supply
    × supply_drift × supply_shock × supply_noise
requests = max(0, round_half_away_from_zero(requests_raw))

current_cpm = base_cpm × hour_factor_cpm × weekday_factor_cpm
    × saturation_price_factor × cpm_drift × cpm_shock × cpm_noise

current_ctr = clamp(base_ctr × hour_factor_ctr × weekday_factor_ctr
    × fatigue_factor × ctr_drift × ctr_shock, 0, 1)

current_cr = clamp(base_cr × hour_factor_cr × weekday_factor_cr
    × cr_drift × cr_shock, 0, 1)
```

Pause sets requests to zero. Generated CPM MUST be finite and positive before conversion to micros.

### 5. Observable funnel and accounting

```text
affordable_impressions = floor(budget_micros × 1000 / current_cpm_micros)
impressions = min(requests, affordable_impressions)

unique_raw ~ Binomial(impressions, new_user_probability)
unique_reach = min(unique_raw, audience_capacity - cumulative_unique_reach)
clicks ~ Binomial(impressions, current_ctr)
conversions ~ Binomial(clicks, current_cr)

spend_micros = ceil(impressions × current_cpm_micros / 1000)
ecpm = null                                           if impressions = 0
ecpm = spend_micros / impressions × 1000             otherwise
```

Multiplications use checked integer arithmetic. Configuration maxima MUST prove that intermediates
cannot overflow. Because affordability floors and spend ceils the same rational price,
`spend_micros <= budget_micros` remains true.

### 6. Atomic commit

After all channels calculate and validate successfully, add impressions and unique reach to their
cumulative state, save StepRecord, increment revision, then advance CurrentHour by 60 minutes. Return
observations in ChannelID order.

## Validation rules

### Startup model config

- Engine version supported, currency valid, money scale exactly 6.
- 1–20 unique valid channels.
- Every range finite with `min <= max`; positive fields strictly above zero.
- CTR/CR/probability bounds in `[0,1]`; saturation threshold `<1`.
- Peak width/duration/count positive; center in `[0,24)`; amplitude/noise sigma non-negative.
- Shock multipliers non-negative; generated maxima fit count/money limits.

### Reset

- Seeds parse as signed 64-bit integers.
- StartHour is an RFC 3339 hour boundary.
- Duration is `1..2160`.
- Timezone resolves through the embedded/host IANA database.
- Reset validates and generates into temporary state, then swaps it atomically.

### Step

- `step_id` is a valid UUID. A cached ID is checked first: the same normalized action hash returns
  the original response and ETag, while a different hash is rejected. Only a new `step_id` requires
  the request ETag to match the current revision.
- Each action has a known unique ChannelID and non-negative money with at most six decimals.
- Missing channels normalize to zero action.
- A finished simulation rejects Step.
- Every calculated observation passes funnel, capacity, spend and eCPM invariants before commit.

## Reproducibility contract

Byte-equivalent normalized observations require equality of:

1. `engine_version` and binomial sampler version;
2. `world_config_digest`;
3. Go toolchain and supported GOOS/GOARCH for v0;
4. WorldSeed and CampaignSeed;
5. StartHour, duration and timezone;
6. ordered sequence of normalized ChannelActions.

World streams never use CampaignSeed. Campaign streams never use action amounts when generating
exogenous noise/events; the amount only caps impressions. Each channel/process/hour has an independent
stream, so map/action ordering and unrelated draws do not alter its values.
