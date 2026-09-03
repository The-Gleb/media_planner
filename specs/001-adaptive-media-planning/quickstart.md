# Quickstart: Validate Simulator v0

This guide is the Phase 1 acceptance path. Commands become runnable after tasks from this plan are
implemented. The normative payload and field definitions are in
[contracts/openapi.yaml](contracts/openapi.yaml); formulas and invariants are in
[data-model.md](data-model.md).

## Prerequisites

- Go 1.27.1
- Docker Engine with Docker Compose
- `curl`
- A shell with `sed` and `diff`

The reference startup config is `services/simulator/configs/world-config.json`. It MUST validate
against [world-config.schema.json](contracts/world-config.schema.json) and contain at least
`social_1` and `search_1`.

## 1. Run local quality gates

```bash
cd services/simulator
go test ./...
go test -race ./...
go test -run TestGoldenReplay ./...
go test -run TestBinomialStatistics ./internal/simulation
go test -fuzz FuzzSimulatorStep -fuzztime 30s ./internal/simulation
```

Expected:

- every command exits successfully;
- golden replay compares complete ordered observations, not only aggregate totals;
- race test reports no data race;
- fuzz failures do not leave a committed partial step.

Then validate cross-boundary tests from the repository root:

```bash
go test ./tests/contract/...
go test ./tests/integration/...
docker compose config --quiet
```

## 2. Start only Simulator

```bash
docker compose up --build --wait simulator
docker compose ps simulator
```

Expected: Simulator is healthy. Planner and Predictor are not required in this phase.

For local validation, Compose publishes Simulator on `127.0.0.1:8080`. Future Planner instances on
the same Compose network reach it as `http://simulator:8080`.

```bash
export SIM_BASE_URL=http://127.0.0.1:8080
curl --fail --silent "$SIM_BASE_URL/health/live"
curl --fail --silent "$SIM_BASE_URL/health/ready"
```

Both responses MUST be `{"status":"ok"}`.

## 3. Reset a deterministic campaign

Use a stable simulation ID for the examples:

```bash
export SIM_ID=11111111-1111-4111-8111-111111111111
curl --silent --show-error \
  -D /tmp/simulator-reset.headers \
  -o /tmp/simulator-reset.json \
  -X PUT "$SIM_BASE_URL/v1/simulations/$SIM_ID" \
  -H 'Content-Type: application/json' \
  -H 'If-None-Match: *' \
  --data '{
    "world_seed":"42001",
    "campaign_seed":"77001",
    "start_hour":"2026-09-03T06:00:00Z",
    "duration_hours":24,
    "time_zone":"Europe/Moscow"
  }'
sed -n '1,30p' /tmp/simulator-reset.headers
sed -n '1,120p' /tmp/simulator-reset.json
```

Expected:

- HTTP `201` and a strong `ETag` header;
- `current_hour` is `2026-09-03T06:00:00Z`;
- `remaining_hours` is 24;
- response exposes `engine_version`, `world_config_digest`, currency and ordered channel IDs.

Store the ETag including its quotes:

```bash
export SIM_ETAG=$(sed -n 's/^[Ee][Tt]ag: \(.*\)\r$/\1/p' /tmp/simulator-reset.headers)
```

## 4. Execute one hour

```bash
export STEP_ID=a04ea33b-b91a-4faa-a0b5-f2869efbdf17
curl --silent --show-error \
  -D /tmp/simulator-step.headers \
  -o /tmp/simulator-step.json \
  -X POST "$SIM_BASE_URL/v1/simulations/$SIM_ID/steps" \
  -H 'Content-Type: application/json' \
  -H "If-Match: $SIM_ETAG" \
  --data "{
    \"step_id\":\"$STEP_ID\",
    \"actions\":[
      {\"channel_id\":\"social_1\",\"budget_cap\":\"1500.000000\"},
      {\"channel_id\":\"search_1\",\"budget_cap\":\"900.000000\"}
    ]
  }"
sed -n '1,160p' /tmp/simulator-step.json
```

Expected for every configured channel:

```text
observed_hour = 2026-09-03T06:00:00Z
next_hour     = 2026-09-03T07:00:00Z
0 <= conversions <= clicks <= impressions <= requests
0 <= unique_reach <= impressions
0 <= spend <= that channel's budget_cap
impressions = 0  => ecpm = null
impressions > 0  => ecpm = spend / impressions * 1000 at declared precision
```

The response includes channels omitted from actions with a zero budget, zero purchased funnel values,
and potentially nonzero requests representing available market supply.

## 5. Verify idempotent retry and stale-write protection

Repeat the exact Step with the original ETag and step ID, saving a second body:

```bash
curl --silent --show-error \
  -o /tmp/simulator-step-retry.json \
  -X POST "$SIM_BASE_URL/v1/simulations/$SIM_ID/steps" \
  -H 'Content-Type: application/json' \
  -H "If-Match: $SIM_ETAG" \
  --data "{
    \"step_id\":\"$STEP_ID\",
    \"actions\":[
      {\"channel_id\":\"social_1\",\"budget_cap\":\"1500.000000\"},
      {\"channel_id\":\"search_1\",\"budget_cap\":\"900.000000\"}
    ]
  }"
diff -u /tmp/simulator-step.json /tmp/simulator-step-retry.json
```

Expected: no diff and CurrentHour remains `07:00Z`, proving the retry did not consume another hour.

Reuse the old ETag with a new step ID. Expected: HTTP `412` and no state change. Reuse the same step ID
with a different action body. Expected: HTTP `409 step_id_reused` and no state change.

## 6. Verify seed semantics

1. Save all 24 Step responses for the initial run with a fixed action sequence.
2. Delete conditionally, Reset with the same engine/config/seeds/timezone, and replay those actions.
3. Compare normalized response bodies; they MUST be byte-equivalent.
4. Repeat with a different CampaignSeed: `world_config_digest` and hidden-world test fingerprint MUST
   remain equal, while at least one noise/event/funnel outcome normally changes.
5. Repeat with a different WorldSeed: the hidden-world test fingerprint MUST change.

The production API never exposes hidden rates or event schedules; their fingerprint is available only
to internal/golden tests.

## 7. Verify saturation and market events

Run deterministic fixture scenarios designed to isolate each effect:

- sustained high budget: cumulative reach approaches capacity, new reach probability decreases,
  observed frequency grows, CPM pressure increases and CTR fatigue decreases response;
- forced drift: affected hidden metric changes gradually and retains its new level;
- forced shock: multiplier changes immediately, remains for the configured interval and returns;
- forced pause: requests and purchased funnel are zero while the pause is active;
- zero supply or zero budget: spend is zero and eCPM is null.

Tests compare documented monotonic properties and exact golden observations. They MUST NOT assert that
the HTTP API exposes hidden CPM/CTR/CR.

## 8. Verify horizon and restart behavior

After 24 committed steps:

- status is `finished`;
- CurrentHour equals `start_hour + 24h`;
- another unique Step returns `409 simulation_finished`;
- revision and observations remain unchanged.

Restart the container. The old simulation MUST return `404`, while liveness/readiness stay healthy.
Reset with the original config and replay actions; the observations MUST match the pre-restart run.
This proves the documented stateless-at-rest behavior.

## 9. Verify service isolation

When Planner and Predictor are later added to Compose:

- Planner resolves Simulator by the `simulator` service name;
- stopping Predictor does not change Simulator readiness or an active run;
- Simulator has no shared writable volume and makes no outbound call to either service.

These checks preserve the three-service boundary shown in the architecture diagram.
