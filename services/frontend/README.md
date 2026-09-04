# Simulator Dashboard

Russian-language React dashboard for the hourly Simulator. The frontend is a separate container at
`http://127.0.0.1:8081`; nginx serves the SPA and proxies same-origin `/api/` calls to `simulator:8080`
and `/planner-api/` calls to `planner:8080`. No CORS configuration is required.

## Development

```bash
npm ci --legacy-peer-deps
npm run dev
npm test -- --run
npm run lint
npm run build
```

Run Vite from `services/frontend`. It proxies `/api` to `SIMULATOR_URL` or
`http://127.0.0.1:8080`. Production startup uses `docker compose up --build --wait` from the repository
root.

## Operational constraints

- Simulator v0 holds one in-memory campaign. A different active or finished ID causes
  `active_limit`; the dashboard never deletes an unknown campaign automatically.
- Browser history is tab-memory only. Refresh may clear charts while the Simulator campaign remains.
- Automatic execution is presented as a time-lapse. It advances only after the Simulator result and
  the corresponding Planner round are committed; the delay between hours is UI pacing and can be
  changed or paused without altering simulation determinism.
- Live analytics includes a timezone-aware stacked chart of hourly spend by channel for each local
  campaign day; the current-day view follows the time-lapse automatically.
- Stopping or rebuilding the frontend does not reset, delete or advance Simulator state.
- Money is retained as decimal text and aggregated in integer micro-units; aggregate unique reach is
  explicitly a non-deduplicated channel sum.
- Uniform and catalog-optimized runs can be compared sequentially. A completed first run remains in
  tab memory while reset starts the other strategy with the same immutable simulation and scenario.
