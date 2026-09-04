# Media Planner

Prototype of an adaptive media-planning system with three independent services: a seeded Go market
Simulator, a stateless Python Planner, and a React dashboard that orchestrates planning and hourly execution.

```bash
docker compose up --build --wait
```

- Dashboard: `http://127.0.0.1:8081`
- Simulator API: `http://127.0.0.1:8080`
- Planner API: `http://127.0.0.1:8082`
- Simulator OpenAPI: `specs/001-adaptive-media-planning/contracts/openapi.yaml`
- Planner OpenAPI: `specs/003-minimal-budget-planner/contracts/planner.openapi.yaml`

The browser coordinates `Planner → Simulator step → committed facts → Planner` through same-origin
`/planner-api/` and `/api/` proxies. Planner and Simulator never call each other. A Planner failure
after a committed hour blocks the next Simulator step until the exact planning round is retried.
Money remains decimal text at service boundaries and integer micros in calculations.

The default deterministic world contains eight channels (`social_1..3`, `programmatic`,
`marketplace_1..3`, `sms`). Planner offers exact `uniform` allocation and a catalog-based
`optimized` water-filling strategy. Controlled market shocks can be attached to reset. To compare
strategies, finish one run, select the other strategy and reset: execution remains sequential while
the dashboard retains both result summaries.

See `services/simulator/README.md`, `services/planner/README.md`, `services/frontend/README.md`, and
`specs/003-minimal-budget-planner/quickstart.md` for development, failure handling, and validation details.
