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

## Audience selection

Use `docker compose up --build -d` from the root. The synthetic segmented world is enabled
by default (recreating Simulator discards its in-memory run).
The campaign form offers one shared geo/gender/age segment selection for all channels, or all audiences.
In the business/expert dashboard, this selection is in the Brief step in both modes.
After calculation, approve the media plan to open campaign controls; return to the brief to edit the audience before reset.
Common segment dimensions are mapped to each channel's IDs; channels without segments need no selection.
Selection is fixed for the run; editing a new draft only takes effect after reset.
Catalogue failures block launch and offer retry. Legacy worlds need no selection.
ActiveRun stores immutable segment selection and sends it directly to Simulator reset and every Step,
including retries. Planner requests contain no audience and no echo is required, so pre-segmentation
Planner versions work unchanged. Stale plan replies from an invalidated run cannot be applied. Charts remain channel-level aggregates.
Browser proof: `AUDIENCE_E2E=1 DASHBOARD_BASE_URL=http://127.0.0.1:18081 npm run test:e2e -- audience-selection.spec.ts`.
