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

## Configuration

`configs/world-config.json` defines currency, engine version and plausible ranges for each channel.
It is strict JSON and is mounted read-only in Compose. The service refuses readiness when the config
is unknown, incomplete, out of range, contains duplicate channel IDs or cannot be normalized.

The reset call supplies WorldSeed, CampaignSeed, StartHour, DurationHours and IANA timezone. Exact
replay identity consists of:

- engine and binomial sampler versions;
- normalized world-config SHA-256 digest;
- Go toolchain and supported platform (`linux/amd64` for v0);
- both seeds, time range and timezone;
- normalized sequence of channel actions.

WorldSeed selects base market properties, time profiles and response curves. CampaignSeed selects
noise, outcomes, drift and shock schedules. Independent keyed random streams prevent channel order or
an unrelated random draw from changing other processes.

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

See `specs/001-adaptive-media-planning/quickstart.md` for full contract examples and acceptance checks.
