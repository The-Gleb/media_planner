<!--
Sync Impact Report
- Version change: unversioned template -> 1.0.0
- Modified principles: none (initial ratification)
- Added principles:
  - I. Evidence-Based Planning
  - II. Explicit Audience, Goals, and Constraints
  - III. Traceable Data and Calculations
  - IV. Testable Delivery
  - V. Privacy and Least Privilege
- Added sections:
  - Product and Technical Constraints
  - Development Workflow and Quality Gates
- Removed sections: none
- Follow-up TODOs: none
-->
# Media Planner Constitution

## Core Principles

### I. Evidence-Based Planning
Every recommendation, forecast, channel choice, and budget allocation MUST be supported by an
identified data source or an explicitly labeled assumption. The system MUST distinguish observed
facts, user-provided inputs, derived values, and estimates. When evidence is incomplete, output
MUST expose the uncertainty and MUST NOT present an estimate as a verified fact. This keeps media
plans reviewable and prevents false precision from driving spending decisions.

### II. Explicit Audience, Goals, and Constraints
Each plan MUST define its target audience, campaign objective, measurable success criteria,
timeframe, geography, currency, and budget constraints before it is treated as complete. Conflicting
or missing inputs MUST be surfaced for resolution or recorded as explicit assumptions. Generated
recommendations MUST remain within the accepted constraints, and any exception MUST be clearly
identified with its expected impact. This ensures that planning results are relevant and actionable.

### III. Traceable Data and Calculations
Inputs, transformations, formulas, units, rounding rules, and outputs MUST be traceable through the
planning workflow. Monetary and rate calculations MUST use types and precision rules appropriate to
their domains; binary floating-point MUST NOT be used where it can create material financial error.
The same validated inputs and configuration MUST produce equivalent results. Changes to formulas or
data schemas MUST include migration or compatibility guidance when existing plans are affected.

### IV. Testable Delivery
Every behavior change MUST have automated tests at the lowest effective level. Calculation rules,
validation boundaries, and allocation constraints MUST have unit tests; persistence, external data
sources, and cross-component workflows MUST have integration tests. A defect fix MUST include a
regression test that fails without the fix. Work MUST NOT be considered complete while required tests,
static checks, or acceptance criteria fail.

### V. Privacy and Least Privilege
The system MUST collect and retain only data required for an approved planning use case. Personal,
credential, and commercially sensitive data MUST be protected in storage, transit, logs, exports,
and test fixtures. Access MUST follow least privilege, secrets MUST remain outside source control,
and destructive or externally visible operations MUST require explicit authorization. Security and
privacy risks MUST be assessed whenever a new data source, integration, or export path is introduced.

## Product and Technical Constraints

- The canonical unit, currency, timezone, attribution window, and reporting period MUST be explicit
  wherever ambiguity can change a result.
- External data MUST retain provenance, retrieval time, and applicable freshness metadata. Stale or
  unavailable inputs MUST produce an explicit status rather than silent substitution.
- User-facing plans MUST expose the assumptions and calculations needed for an informed review.
- Interfaces and stored formats MUST be versioned when compatibility cannot otherwise be preserved.
- Architecture and dependencies MUST remain no more complex than the validated requirements demand;
  added operational complexity requires a documented benefit and owner.
- Accessibility, localization, and observability requirements MUST be defined in each feature spec
  when the feature introduces a user interface, regional behavior, or production operation.

## Development Workflow and Quality Gates

1. Each change MUST begin with a specification containing independently testable acceptance criteria.
2. Planning MUST identify affected data contracts, calculations, security boundaries, and external
   dependencies before implementation begins.
3. Implementation MUST preserve traceability from requirements to tests and from calculated outputs
   to their inputs and formulas.
4. Reviewers MUST verify constitutional compliance, successful automated checks, and evidence for
   user-visible behavior. Any justified exception MUST be recorded with scope, owner, and expiry or
   remediation plan.
5. Releases MUST document user-visible changes, migrations, known limitations, and rollback needs.

## Governance

This constitution is the highest-priority project governance document. Where another project
practice conflicts with it, this constitution prevails.

Amendments MUST be proposed as a documented change that states the rationale, affected principles,
compatibility impact, and any migration work. Adoption requires explicit approval by the project's
maintainers. The amended constitution MUST include an updated Sync Impact Report and amendment date.

Versions follow semantic versioning: MAJOR for removal or incompatible redefinition of a principle,
MINOR for a new principle or materially expanded obligation, and PATCH for non-semantic clarification.
The version and dates in this document MUST agree with its Sync Impact Report.

Every feature specification, implementation plan, and code review MUST include a constitution check.
Material complexity or exceptions MUST be justified in writing and revisited before release. At least
once per release, maintainers MUST review active exceptions and confirm that delivered behavior still
complies with this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-09-03 | **Last Amended**: 2026-09-03
