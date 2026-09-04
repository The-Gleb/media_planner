# Phase 0 Research: Simulator Dashboard

## 1. Frontend runtime and framework

**Decision**: Use React 19.2 with TypeScript 6.0 and Vite 8.2 on Node.js 24 LTS. Commit the npm
lockfile and pin the Docker build image to a Node 24 patch tag.

**Rationale**: React provides the component and accessibility ecosystem requested by the user;
Vite supplies a small SPA build and a development proxy. Node 24 is the common supported LTS line
for Vite 8 and Playwright. TypeScript 6 is chosen over the newer TypeScript 7 line because its wider
tooling compatibility reduces prototype risk. See [React versions](https://react.dev/versions),
[Vite 8 announcement](https://vite.dev/blog/announcing-vite8), and
[TypeScript 7 migration notes](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/).

**Alternatives considered**: Plain JavaScript was rejected because API/state invariants benefit from
static types. Server-rendered React was rejected because there is no SEO, authentication or
server-owned UI state requirement. TypeScript 7 can be reconsidered after its compiler API/tooling
ecosystem stabilizes.

## 2. Production serving and browser-to-Simulator routing

**Decision**: Build the SPA in Node and serve it from an unprivileged nginx container. Proxy
same-origin `/api/` to `http://simulator:8080/`; expose the frontend on loopback port 8081 and keep
the existing Simulator port available on loopback for API development.

**Rationale**: nginx provides static serving, SPA fallback, a cheap health endpoint and reverse
proxying without adding an application server. Same-origin proxying means no CORS configuration is
needed and preserves `ETag`/`If-Match` headers. Both services can communicate on the ordinary
Compose network while either host port remains independently available. Use the verified
`nginxinc/nginx-unprivileged` image family and run with read-only filesystem/capability restrictions.

**Alternatives considered**: Direct calls from `:8081` to `:8080` would require Simulator CORS and
OPTIONS support. A Node production server adds a runtime and business-free process with no current
benefit. Embedding frontend files in the Go binary would violate independent frontend lifecycle.

## 3. Bootstrap metadata contract

**Decision**: Add `GET /v1/world-metadata`, returning only `engine_version`,
`world_config_digest`, `currency`, and ordered `channel_ids`.

**Rationale**: FR-002 requires the dashboard to show available channels and currency before campaign
creation. The current API returns those values only after a successful PUT, so hard-coding the world
config would create drift and violate source-of-truth traceability. The Registry already owns the
loaded model and can project a stable sanitized DTO without exposing hidden base CPM/CTR/CR,
capacity, shocks or profile parameters.

**Alternatives considered**: Bundling channel IDs in frontend configuration duplicates truth.
Returning the entire world config leaks deliberately hidden state. Guessing channels from a failed
step is neither safe nor usable.

## 4. Client concurrency, idempotency and stop semantics

**Decision**: Use one client-side execution controller and allow at most one step request in flight.
Generate a UUID and immutable normalized action snapshot before each POST. On an ambiguous network
failure, retry the same `step_id` and body. “Stop” sets a flag and lets the current request commit;
the loop exits before creating the next step.

**Rationale**: This directly matches Simulator atomic/idempotent step semantics and FR-012/FR-013.
Reusing the same ID prevents an uncertain response from producing a skipped or duplicate displayed
hour. The client stores and sends returned ETags even though local Compose relaxes preconditions, so
it also works with strict deployments.

**Alternatives considered**: Parallel steps cannot respect state order. Aborting the in-flight step
could hide a server commit. Creating a new `step_id` after timeout risks advancing twice.

## 5. State organization and browser lifetime

**Decision**: Keep orthogonal in-memory slices for service readiness, draft/form validation,
campaign session, execution, history, errors and chart presentation. Refresh is allowed to clear
history and MUST never automatically reset/delete the Simulator. If a known campaign ID is queried
after refresh, show server position without inventing missing observations.

**Rationale**: Orthogonal state avoids a large combinatorial enum while retaining explicit visible
empty/loading/active/stopped/finished/error states. Browser memory is sufficient for at most 43,200
observations and matches the specification's session-scoped-history assumption. An operation error
is separate so committed data remains inspectable.

**Alternatives considered**: IndexedDB recovery adds migrations, cleanup and reconciliation yet
cannot recover hours omitted while the frontend was absent because the backend has no history API.
A global state library is unnecessary for a single screen. Persistent campaign reports are outside
scope.

## 6. Exact numeric representation and aggregation

**Decision**: Preserve money as contract decimal strings, validate at most six fractional digits,
and convert it to integer micro-units with `BigInt`. Validate each count response with
`Number.isSafeInteger`, then convert counts to `BigInt` before aggregation. Compute aggregate eCPM
from exact total spend and total impressions, rounding upward to the next micro-unit as the Simulator
does, and emit `null` for zero impressions. Reject unsafe JSON numbers rather than silently rounding.

**Rationale**: This follows the constitution's no-material-binary-float rule and keeps inputs,
transformations, units and outputs traceable. Chart coordinates may use `number` only as a rendering
projection; exact tooltips/inspector values come from raw strings/integers.

**Alternatives considered**: Native floating-point sums can drift or overflow safe count precision.
A decimal package would work but is unnecessary for fixed six-decimal and integer domains. Accepting
unsafe int64 JSON values would show false precision; changing all existing API counts to strings
would be a breaking change.

## 7. Charts and dense-history performance

**Decision**: Use Recharts 3.10 with a stable channel-to-color-and-dash mapping. Present seven named
metric tabs so every chart is available but only the selected chart is mounted. Store raw data once
in hour-major form, calculate aggregates once on ingestion, memoize the active projection, disable
bulk-run animation, and throttle expensive chart redraws while retaining every committed result.
Add an exact keyboard-accessible hour/series inspector and latest-hour table.

**Rationale**: Recharts is React-native, typed and accessible for the prototype. Mounting all seven
SVG charts at 20 x 2,160 points would create unnecessary DOM work; one selected chart plus memoized
data keeps SC-005 achievable without discarding source observations. Recharts' accessibility layer
helps but does not replace an exact textual alternative. See the
[Recharts guide](https://recharts.github.io/en-US/guide/) and
[Recharts API](https://recharts.github.io/en-US/api/).

**Alternatives considered**: ECharts/canvas scales further but adds an imperative integration for a
small prototype. Rendering all seven at once is simpler conceptually but high-risk at maximum scale.
Permanent downsampling would compromise exact point inspection; it may later be used only as a
visual projection while the inspector reads raw data.

## 8. Accessibility and localization

**Decision**: Use native labeled form controls and buttons, visible focus, `aria-describedby` field
errors, a throttled live status region, textual progress, line style plus color distinctions, and a
table/inspector alternative for charts. Russian is the initial UI language; API metric identifiers
remain visible alongside Russian labels. Respect `prefers-reduced-motion`.

**Rationale**: This satisfies the explicit keyboard, non-color-only, exact inspection and localized
state requirements. Testing Library role/label queries and a Playwright keyboard journey make the
contract enforceable.

**Alternatives considered**: Canvas-only charts or color-only legends are not sufficient for screen
reader/keyboard use. A localization framework is deferred because only one language is required;
labels will still be centralized for future extraction.

## 9. Test strategy

**Decision**: Test pure validation/money/aggregation/run-controller logic with Vitest; user-visible
interactions and accessible names with React Testing Library; Simulator metadata and canonical
OpenAPI with Go contract tests; and the complete frontend-proxy-Simulator journey with Playwright and
Compose integration tests.

**Rationale**: This places each behavior at the lowest effective test level while covering the new
HTTP/container boundary. The existing Compose test must assert required service membership rather
than the old exact one-service list, and lifecycle tests must clean up the singleton resource.

**Alternatives considered**: Browser-only tests are slower and poor at numeric edge coverage.
Frontend-only mocks cannot prove proxy headers, health ordering or container isolation.

## 10. Error and recovery policy

**Decision**: Decode `application/problem+json`, map field errors to form/action fields, translate
known codes to actionable Russian messages, and retain draft/history after failures. A failed
automatic run stops in a retryable error state. Responses whose observed hour is not the expected
hour are rejected as desynchronized and never appended.

**Rationale**: The policy prevents fabricated/duplicated history and fulfills FR-025/SC-008. It also
makes the Simulator singleton, deleted-resource and stale-ETag behaviors understandable.

**Alternatives considered**: Generic toasts lose field context. Silently reconciling server-ahead
state is impossible because the Simulator has no history endpoint.
