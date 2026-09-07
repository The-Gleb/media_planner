# Simulator v0

Simulator is the first standalone service in Media Planner. It creates a seeded synthetic advertising
market and advances it exactly one hour for every accepted Step. It has no runtime dependency on the
future Planner or Predictor services.

## Run

From the repository root:

```bash
go test ./services/simulator/...
docker compose up --build --wait simulator
```

The local Compose profile exposes `http://127.0.0.1:8080`. Service health is available at
`/health/live` and `/health/ready`; low-cardinality process metrics are internal at `/metrics`.

`GET /v1/world-metadata` returns only the public immutable bootstrap fields used by clients:
`engine_version`, `world_config_digest`, `currency`, and ordered `channel_ids`. Hidden market rates,
audience capacities, profiles, drift and shocks are intentionally excluded.

## Configuration

`configs/world-config.audience.json` is the Simulator Compose default. It defines eight channels:
`social_1..3`, `programmatic`, `marketplace_1..3`, and `sms`, with channel-specific CPM, CTR, CR,
supply, volatility and saturation ranges. It is strict JSON and is mounted read-only in Compose.
The smaller `configs/world-config.json` remains a deterministic test fixture. The service refuses
readiness when a config is unknown, incomplete, out of range, contains duplicate channel IDs or
cannot be normalized.

The current action contract purchases impressions under a CPM budget cap. Until package-priced
inventory is introduced, `sms` therefore uses an explicit effective CPM-equivalent in the default
world; it must not be interpreted as a real SMS tariff.

The reset call supplies WorldSeed, CampaignSeed, StartHour, DurationHours and IANA timezone. Exact
replay identity consists of:

- engine and binomial sampler versions;
- normalized world-config SHA-256 digest;
- Go toolchain and supported platform (`linux/amd64` for v0);
- both seeds, time range and timezone;
- normalized sequence of channel actions.

WorldSeed selects base market properties, time profiles and response curves. CampaignSeed selects
noise, outcomes, drift and random shock schedules. Independent keyed random streams prevent channel
order or an unrelated random draw from changing other processes.

Reset can additionally supply deterministic `scenario_events` for `supply`, `cpm`, `ctr`, `cr`, or
`pause`, with a channel, relative start hour, duration and multiplier. Set
`disable_random_events=true` when comparing strategies so both sequential runs see only the same
controlled scenario. Scenario events are validated against the selected channels and horizon and
become part of the replay identity.

## Money and reach semantics

HTTP money is a non-negative decimal string with up to six fractional digits. Internally it is
`int64` micro-units. Affordability floors impressions and billing ceils spend at micro-unit precision,
guaranteeing `spend <= budget_cap`.

`unique_reach` is the number of people first reached by that channel in the observed hour. It is not
deduplicated across channels and MUST NOT be summed into campaign reach. Cross-channel overlap belongs
to the future Predictor model.

## Lifecycle and recovery

Simulator v0 permits one in-memory run. Strong ETags serialize state changes; `step_id` makes a lost
Step response safely retryable. A successful Step commits every channel atomically before advancing
CurrentHour by 60 minutes. Restart intentionally loses the active run. Recover by Reset with the same
identity inputs and replay the same ordered action sequence.

Strict ETag preconditions are enabled by default. Local Compose sets
`SIMULATOR_RELAX_PRECONDITIONS=true`, so Reset, Step and Delete can be called from Swagger UI without
conditional headers. Remove that variable or set it to `false` to test production-style stale-write
protection.

See `specs/001-adaptive-media-planning/quickstart.md` for full contract examples and acceptance checks.

## Segmented world (default)

From the repository root: `docker compose up --build -d`.
Recreating Simulator loses its in-memory run. Planner keeps `world-config.mediaplan.json`
for channel benchmarks and does not need segment support.
The synthetic `world-config.audience.json` uses sim-v2-delivery: twenty geo/gender/age groups per channel,
each with independent warm/cold capacity and history. `GET /v1/audience-segments` exposes only
IDs and dimensions. Ages are [13,19), [19,31), [31,46), [46,60), [60,131):
13–18, 19–30, 31–45, 46–59 and 60+ (130 is the schema's maximum supported age).
Age capacity uses the following relative weights within each geo/gender combination:

| Channel | 13–18 | 19–30 | 31–45 | 46–59 | 60+ |
| --- | ---: | ---: | ---: | ---: | ---: |
| social_1 | 15 | 15 | 10 | 7 | 5 |
| social_2 | 8 | 10 | 12 | 12 | 8 |
| social_3 | 5 | 7 | 10 | 15 | 15 |
| marketplace_1/2/3 | 7 | 10 | 12 | 12 | 8 |
| programmatic, sms | 1 | 1 | 1 | 1 | 1 |

Weights are normalized separately for warm/cold pools, retaining each geo/gender pool's
total capacity. Integer rounding uses largest remainders, with younger ages breaking ties.
These are synthetic channel archetypes, not demographic estimates or measured conversion rates.
Existing CTR/CR/CPM/supply multipliers are unchanged: age affects capacity, not intrinsic
conversion probability. Supply already depends on pool capacity; no extra age supply multiplier is added.
The previous 25–34/35–44 IDs are replaced; the config digest changes. Finish existing runs before
deploying and create a new simulation with the new catalogue. Old IDs are rejected, not reinterpreted.
PUT/reset accepts optional `audience`; Step may confirm the same selection
but cannot change it. Omission on Step uses the reset selection; null/empty selections are invalid.
Public selection contains only segment_ids. Temperature is not accepted in PUT/Step.
Internally warm/cold compete by history-based delivery score (priority4/1, saturation/fatigue floors0.05);
a separate allocator buys target impression shares under CPM/supply/cap. These are synthetic constants,
not a KPI optimizer. Saturated warm can receive repeat impressions. All pool counts/costs sum to the channel.
Old sim-v1-segments configs require an explicit version change and fresh reset; seeds identify the new model.
Responses retain channel aggregates and `ecpm`, with no segment details.

Budgets are hourly caps, not deposited balances. Underdelivery is not charged or stored;
only actual spend reduces the campaign's remaining budget in the caller.

### SMS delivery

The default segmented world enables a separate SMS policy through the channel's `sms` block:
`segment_price: 7.34`, `segments_per_message: 2`, `min_interval_hours: 168`.
One message costs 14.68 RUB and is delivered with probability 1 (an explicit v0 simplification).
No auction, geo, saturation, drift or shock CPM multiplier changes that price. Supply/pause
events, temporal throughput, CTR/CR and response fatigue still apply.

The synthetic SMS base contains 20 million recipients (4 million warm, 16 million cold),
split equally across the twenty geo/gender/age groups. This is not a measured operator audience.
Base throughput is 1–2 million messages/day before hourly/weekday/noise/event factors.
Targeting reduces the available base and throughput. Warm/cold remain internal.

Each pool keeps aggregate cooldown cohorts, not individual recipients. Every send reserves one
recipient until step `sent_at + 168`, including when the campaign crosses a calendar week.
New recipients are contacted first within a pool; repeats are allowed only after cooldown.
Unreached + eligible repeats + cooldown recipients always equals pool capacity. No refresh of
the base occurs during a run. Reset clears reach and cooldown together. Campaigns of less than
168 hours cannot send a second message to the same recipient.

Public fields remain unchanged: `requests` is hourly send opportunities capped by eligible
recipients, `impressions` counts delivered messages (not technical SMS segments), `unique_reach`
counts newly contacted recipients, and clicks/conversions are sampled from messages/clicks.
`spend = impressions * 14.68`; nonempty `ecpm = 14680` is only a reporting equivalent.
Empty delivery has zero spend and null eCPM. Exhausted recipients or throughput cause unspent budget.

The `sms` block is optional and valid only for SMS channels in a segmented world. Configs without
it retain their original CPM-based behavior. The legacy `world-config.mediaplan.json` remains a
Planner benchmark (updated price/capacity/throughput), not the source of cooldown behavior.
Planner receives no recipient state and must learn underdelivery from observations. Deploy with
a fresh/reset simulation: the new config has a different digest. Restore the previous config to
roll back the SMS policy; no public API migration is needed.

For rollback, finish the run and restore the old binary with its sim-v0 config; no in-memory
state migration is supported. See `specs/004-audience-segments/quickstart.md` for tests and
1-CPU latency/RSS checks (100/500 ms p95 for 8/128 segments, 256 MiB).
