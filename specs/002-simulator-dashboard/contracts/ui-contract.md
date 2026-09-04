# UI Contract: Simulator Dashboard

## Route and service boundary

- The dashboard is a single screen at `/` and is served independently from the Simulator.
- Browser API requests use relative `/api/...` URLs. In production nginx removes `/api/` and proxies
  the remainder to `http://simulator:8080/`; the Vite development proxy mirrors this behavior.
- `ETag`, `If-Match`, `If-None-Match`, `Content-Type`, `Accept` and
  `application/problem+json` bodies pass through unchanged.
- `GET /health` on the frontend container reports frontend serving health only. Simulator readiness
  is displayed from proxied `GET /api/health/ready` and metadata loading.
- Starting/stopping/rebuilding the frontend container MUST NOT call PUT or DELETE and MUST NOT change
  the Simulator's campaign.

## Screen regions

The document has one `main` landmark and the following labeled regions in reading order:

1. **Simulator status**: reachable/ready/unavailable text, engine version and world digest.
2. **Simulation configuration**: simulation ID, seeds, hour-aligned start and IANA timezone.
3. **Campaign configuration**: duration, currency, and one labeled hourly budget input per discovered
   channel. These fields remain editable for a subsequent run.
4. **Campaign control**: current/ending hour, status, completed/remaining hours, percentage, “one
   hour”, “to end” and “stop” actions.
5. **Latest observed hour**: exact table with all channels and seven returned metrics.
6. **History**: seven named metric tabs, stable legend controls, active chart and exact-value
   hour/series inspector.
7. **Operation message**: polite live status and assertive error summary without removing existing
   content.

At viewport widths >=768 px, the page itself does not scroll horizontally. The observation table is
a named, focusable horizontal-scroll region when required.

## Campaign form behavior

- Mutations remain disabled until readiness and `WorldMetadata` both succeed.
- All fields are labeled in Russian; contract names such as `unique_reach` and `eCPM` remain visible.
- Submit validates the rules in `data-model.md`, focuses/summarizes the first invalid field, preserves
  all entered values, and sends `PUT /api/v1/simulations/{encoded simulation_id}`.
- First creation sends `If-None-Match: *`; reset of the displayed same ID sends its latest `If-Match`
  when known. The relaxed development server may ignore absent/stale preconditions, but the client
  does not depend on that relaxation.
- After first creation, simulation fields are read-only. Duration and budgets remain editable as a
  campaign draft.
- A successful PUT resets the same simulation, promotes the edited campaign draft to the active
  campaign, and clears old displayed observations atomically. A failure changes neither history nor
  the active campaign.
- `active_limit` explains that Simulator v0 contains another singleton campaign and preserves draft
  values. The UI does not delete an unknown campaign automatically.

## Step and automatic-run behavior

- “Один час” sends exactly one complete channel action list with the active campaign budgets.
- “До конца” calls the same step endpoint sequentially; there is no batch endpoint.
- Create/reset/manual-step/run actions cannot overlap. Repeated activation while busy is ignored by
  disabled native buttons and the execution guard.
- Draft budgets may be edited between mutations, but an automatic or manual run continues to use the
  active campaign snapshot until the user explicitly resets and relaunches it.
- “Остановить” remains keyboard reachable during automatic execution. It changes status to
  “Остановка после текущего часа”; the current request is recorded if successful, and no next request
  is constructed.
- Progress is derived from Simulator duration/remaining values, not the length of browser history:
  `completed = duration - remaining`, `percent = completed / duration * 100`.
- A successful response is appended only if its simulation ID, step ID, expected hour, next hour,
  channel coverage and remaining-hour transition validate. Otherwise show desynchronization and do
  not fabricate a point.
- For ambiguous transport failure, retry reuses the same pending `step_id`, actions and ETag. A newly
  generated ID is never presented as a retry of the same hour.

## Results and calculation behavior

Metric labels and units:

| Contract metric | Russian label | Unit | Aggregate |
|---|---|---|---|
| `requests` | Запросы | count/hour | sum |
| `impressions` | Показы | count/hour | sum |
| `unique_reach` | Новый охват | people/hour | channel sum, explicitly non-deduplicated |
| `clicks` | Клики | count/hour | sum |
| `conversions` | Конверсии | count/hour | sum |
| `spend` | Расход | campaign currency/hour | exact decimal sum |
| `ecpm` | eCPM | campaign currency per 1,000 impressions | total spend / total impressions x 1,000 |

- The table displays returned exact decimal text and `—` for null eCPM.
- Each metric has a separately named tab/view. Only the active chart must be mounted, but all seven
  tabs and their availability are visible.
- Every chart includes each channel and `Итого`; the same series keeps the same color and line style
  in all views. Visibility controls have text labels and pressed/checked state.
- Aggregate unique reach is labeled “Итого (сумма по каналам, без дедупликации)” in legend, tooltip
  and inspector.
- Chart coordinates may be floating-point projections. Tooltip and inspector exact values MUST come
  from validated raw observations or exact integer-micro aggregate calculations.
- Null eCPM is a gap. It MUST NOT render or announce zero.
- The inspector permits keyboard selection of metric, observed hour and series and presents the exact
  value, unit and aggregate explanation without requiring pointer hover.

## Visible status and errors

- Required textual states: empty, checking/loading, ready, active, running, stopping, stopped,
  finished, unavailable, error and desynchronized.
- State is conveyed through text/icon plus optional color; color alone is never meaningful.
- Known Simulator problem codes map to concise Russian action guidance. `trace_id`, when present, is
  shown as diagnostic context but never replaces the user message.
- Failure preserves valid form input, active session and committed history. Automatic execution
  stops; retry is explicitly offered when safe.
- Live progress announcements are throttled during long runs so screen readers are not notified for
  every one of 2,160 hours. Stop/completion returns focus to the relevant run control/status.

## Accessibility acceptance surface

- Native keyboard tab/shift-tab/enter/space operation reaches all form, execution, legend and exact
  inspection actions with visible focus.
- Every input has a programmatic label; field errors are connected through `aria-describedby`.
- Charts have an accessible title and description, axes expose units, and the exact inspector/table
  is the non-visual equivalent.
- Series are distinguishable by label and dash/weight in addition to color.
- Motion/animation is disabled for `prefers-reduced-motion` and during bulk execution.
