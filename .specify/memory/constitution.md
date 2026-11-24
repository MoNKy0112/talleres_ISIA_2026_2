<!--
Sync Impact Report
- Version: unversioned -> 1.0.0 (first versioned formalization)
- Modified principles:
  - Dominio determinista único -> I. Deterministic Domain Authority
  - Arquitectura Hexagonal -> II. Strict Hexagonal Boundaries
  - Gobernanza técnica y calidad -> V. Verifiable Quality
- Added sections: Technology Constraints; Quality Gates
- Removed sections: None
- Follow-up TODOs: Original ratification date is unknown. ADR-001 is referenced by
  the source request but was not found under docs/adr/.
-->

# IncidentOps Constitution

## Core Principles

### I. Deterministic Domain Authority
`src/domain/models.py`, `src/domain/triage_rules.py`, and
`src/domain/sla_calculator.py` are the sole authority for domain models, triage,
severity, routing, duplicate grouping, and SLA decisions. The domain MUST remain
deterministic and MUST NOT import frameworks, application/adapters, or database
drivers; only the standard library and other domain modules may be imported.

Severity policy is P0 for global critical-service outage or active cross-organization
data exposure; P1 for severe shared-infrastructure degradation with imminent outage
risk; P2 for moderate degradation or an individual user blockage; and P3 for cosmetic
requests or preventive non-production maintenance. P0/P1 SLAs run 24/7; P2/P3 count
Monday through Friday, 08:00–18:00. Escalation begins at 75% of the SLA and remains
active after breach, including for resolved incidents. Valid teams are
`Backend-Core`, `Platform-SRE`, `Data-DBA`, and `Security-IAM`; valid states are
`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, and `RESOLVED`. Duplicate keys identify
component and symptom category. Adapters MUST NOT copy or redefine these policies.

### II. Strict Hexagonal Boundaries
`src/application/ports.py` defines secondary ports with `typing.Protocol`;
`src/application/services.py` coordinates shared use cases. Dependencies point
inward: inbound/outbound adapters depend on application ports, application depends
on domain, and domain has no outward dependency. Adapters MUST NOT make the domain
or application depend on FastAPI, Typer, storage implementations, or transport
schemas.

### III. Shared Use Cases, Multiple Inbound Adapters
REST and CLI adapters MUST delegate to the same application use cases. A future
MCP adapter MUST reuse those use cases rather than duplicate business logic.
Inbound adapters are responsible for translating and validating transport input
and serializing output; business decisions remain in the domain/application core.

### IV. Replaceable Persistence
Outbound adapters under `src/adapters/outbound/` implement application ports and
MUST be replaceable without changing domain rules or inbound contracts.
`DATABASE_URL` selects/configures persistence only at the composition or adapter
boundary; it MUST NOT enter domain policy or use-case decisions. SQLite3 from the
Python standard library is the default persistence engine, without heavy ORMs.
Adopting another database engine requires a dedicated, accepted ADR before
implementation or migration.

### V. Verifiable Quality
Behavioral requirements MUST have BDD acceptance scenarios in `Given / When / Then`
form and automated pytest coverage. Tests MUST verify externally observable
contracts and cross-adapter parity where multiple adapters expose the same use
case. Hexagonal import boundaries MUST be checked statically as part of quality
verification.

## Technology Constraints

- Python MUST be version 3.10 or newer; `uv` manages project and development
  dependencies.
- REST uses FastAPI and Pydantic v2; the terminal interface uses Typer.
- SQLite3 is the standard-library persistence baseline. Heavy ORMs are not
  permitted under this baseline.

## Quality Gates

- `uv run ruff check src/` MUST pass, including configured rules that enforce
  hexagonal import boundaries.
- `uv run pytest -v` MUST pass before a change is accepted.
- Acceptance coverage MUST express behavior as BDD scenarios; adapter tests MUST
  exercise the shared use case rather than substitute business logic.

## Governance

This constitution governs architecture and quality requirements; implementation
plans and runtime instructions MUST remain consistent with it. Amendments MUST be
reviewed, update this document, and explain their effect on existing principles.
Compliance MUST be reviewed for changes to domain rules, dependency direction,
adapters, persistence, and quality gates. Exceptions MUST be justified, scoped,
and recorded in an ADR.

Constitution versions use semantic versioning: MAJOR for incompatible principle
removals or redefinitions, MINOR for new or materially expanded principles or
sections, and PATCH for clarifications and non-semantic edits.

**Version**: 1.0.0 | **Ratified**: TODO(RATIFICATION_DATE): original adoption date unknown | **Last Amended**: 2026-11-23
