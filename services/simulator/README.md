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
The synthetic `world-config.audience.json` uses sim-v2-delivery: eight geo/gender/age groups,
each with independent warm/cold capacity and history. `GET /v1/audience-segments` exposes only
IDs and dimensions. PUT/reset accepts optional `audience`; Step may confirm the same selection
but cannot change it. Omission on Step uses the reset selection; null/empty selections are invalid.
Public selection contains only segment_ids. Temperature is not accepted in PUT/Step.
Internally warm/cold compete by history-based delivery score (priority4/1, saturation/fatigue floors0.05);
a separate allocator buys target impression shares under CPM/supply/cap. These are synthetic constants,
not a KPI optimizer. Saturated warm can receive repeat impressions. All pool counts/costs sum to the channel.
Old sim-v1-segments configs require an explicit version change and fresh reset; seeds identify the new model.
Responses retain channel aggregates and `ecpm`, with no segment details.

Budgets are hourly caps, not deposited balances. Underdelivery is not charged or stored;
only actual spend reduces the campaign's remaining budget in the caller.
For rollback, finish the run and restore the old binary with its sim-v0 config; no in-memory
state migration is supported. See `specs/004-audience-segments/quickstart.md` for tests and
1-CPU latency/RSS checks (100/500 ms p95 for 8/128 segments, 256 MiB).
