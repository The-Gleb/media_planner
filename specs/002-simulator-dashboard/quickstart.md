# Quickstart Validation: Simulator Dashboard

This guide validates the planned feature after implementation. It assumes Docker with Compose,
Go 1.27.1, Node.js 24 and npm are installed.

## 1. Static and automated checks

From the repository root:

```bash
go test ./services/simulator/... ./tests/...
go vet ./services/simulator/... ./tests/...
npm --prefix services/frontend ci
npm --prefix services/frontend run lint
npm --prefix services/frontend test -- --run
npm --prefix services/frontend run build
```

Expected: Simulator metadata/contract tests and frontend validation, exact aggregation, execution
controller and component tests all pass. No dependency output is written into the Go workspace.

Run the browser suite against the Compose stack as defined by the frontend package:

```bash
docker compose up --build --wait
npm --prefix services/frontend run test:e2e
```

Expected: Playwright's Chromium journey completes campaign creation, one step, automatic run/stop,
completion, chart inspection and keyboard-only interaction.

## 2. Container and proxy readiness

```bash
docker compose ps
curl -fsS http://127.0.0.1:8080/health/ready
curl -fsS http://127.0.0.1:8081/health
curl -fsS http://127.0.0.1:8081/api/health/ready
curl -fsS http://127.0.0.1:8081/api/v1/world-metadata
```

Expected:

- both `simulator` and `frontend` are healthy;
- direct and proxied Simulator readiness return `{"status":"ok"}`;
- metadata contains only engine version, world digest, currency and 1..20 ordered channel IDs;
- hidden CPM/CTR/CR/capacity/profile configuration is absent.

Open `http://127.0.0.1:8081/`. The status region must show readiness, currency, channels and model
traceability before enabling campaign creation.

## 3. Create and step a campaign

Use a free singleton Simulator (delete a prior known campaign first if needed), then enter:

- simulation ID: `dashboard-demo_1`
- world seed: `42001`
- campaign seed: `77001`
- start: `2026-09-03T06:00:00Z`
- duration: `24`
- timezone: `Europe/Moscow`
- a non-negative hourly budget for every discovered channel; set at least one to zero.

Create the campaign and verify the returned ID, current/end hour, duration, remaining hours, currency,
channels, engine version and config digest. Select “Один час”. Expected:

- current hour advances exactly one hour and remaining decreases from 24 to 23;
- one observation appears for every channel;
- the zero-budget channel can show requests but has zero purchased results/spend and `—` eCPM;
- all seven metric tabs contain the observed hour and an `Итого` series;
- repeated clicks while the request is in flight cannot create a second request.

## 4. Verify exact aggregates

For the displayed hour, compare the exact inspector with channel rows:

- requests, impressions, clicks, conversions and spend equal their channel sums;
- aggregate reach equals the channel sum and is labeled non-deduplicated;
- aggregate eCPM equals exact total spend divided by total impressions times 1,000 and is absent if
  total impressions is zero;
- null channel eCPM is a chart gap, not zero;
- currency appears for spend/eCPM.

The unit tests must also cover six-decimal values whose floating-point sum would be unsafe, eCPM
upward micro-unit rounding, zero impressions, safe aggregate counts beyond the JS Number range, and
rejection of non-safe JSON integer counts.

## 5. Automatic run, stop and recovery

Start “До конца”, then activate “Остановить” while a request is in flight. Expected:

- completed/remaining/percentage update from server state;
- the in-flight hour is retained if it commits;
- no later step starts;
- history remains visible and manual/run controls become available for the still-active campaign.

Resume to completion. Expected: exactly 24 ordered unique hours in total, zero remaining, finished
status, and disabled step/run controls.

For failure validation, stop the Simulator during another automatic run:

```bash
docker compose stop simulator
```

Expected: the dashboard stops its loop, identifies the failed operation in Russian, preserves draft,
campaign and all committed observations, and offers safe retry. After Simulator recovery, an
ambiguous step retry uses the same `step_id` and action body.

## 6. Accessibility and scale

- At widths 768 px and wider, complete all create, step, run, stop, metric selection and exact-value
  inspection tasks using keyboard only; verify visible focus and no page-level horizontal scroll.
- Verify state, errors and channel series remain distinguishable with color perception disabled.
- Verify the latest-results table has its own labeled scroll region when dense.
- Run a 2,160-hour/20-channel fixture in the frontend performance test. All seven metric views must
  become inspectable within three seconds after final ingestion, with only the selected chart mounted
  and all exact observations retained.

## 7. Independent frontend lifecycle

While a campaign is active:

```bash
docker compose stop frontend
curl -fsS http://127.0.0.1:8080/v1/simulations/dashboard-demo_1/current-hour
docker compose up -d --wait frontend
```

Expected: Simulator current hour/status does not change when the frontend stops or restarts. The
reloaded dashboard may have empty chart history, as documented, but MUST NOT automatically PUT,
DELETE, advance or fabricate observations.

## 8. Cleanup

Delete the known singleton campaign through the Simulator API if the implemented UI does not expose
explicit deletion, then stop the stack:

```bash
docker compose down
```
