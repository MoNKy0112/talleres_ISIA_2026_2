<!--
Sync Impact Report
- Version: 1.0.0 -> 1.1.0
- Modified principles:
  - IV. Replaceable Persistence -> materially expanded to govern dual
    SQLite/PostgreSQL persistence, driver boundaries, factory selection, temporal
    parity, and real connectivity health checks.
- Added sections: None
- Removed sections: None
- Follow-up TODOs:
  - Original ratification date remains unknown.
  - ADR-001 is referenced by ADR-004 as partially replaced but its historical file
    was not found under docs/adr/.
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
Outbound adapters under `src/adapters/outbound/` implement `IncidentRepositoryPort`
and MUST be replaceable without changing domain rules, use cases, or inbound
contracts. SQLite and PostgreSQL adapters MUST implement the same port, including
`check_health`; that operation MUST perform a real connectivity query against the
selected persistence engine rather than report only process or configuration state.

`src/adapters/outbound/factory.py` is the sole boundary that interprets
`DATABASE_URL` and selects the repository implementation. `sqlite:///:memory:`
MUST remain the default for development and fast tests. `postgresql://...` selects
the PostgreSQL adapter for containerized and production deployments. Neither the
domain, application, nor inbound adapters may inspect `DATABASE_URL` or select a
database engine.

SQLite's standard-library `sqlite3` driver and PostgreSQL's `psycopg[binary]`
driver are permitted only in `src/adapters/outbound/`. Database drivers MUST NOT
be imported by `src/domain/`, `src/application/`, or `src/adapters/inbound/`.
Object-relational mappers, including SQLAlchemy and SQLModel, MUST NOT be used;
outbound adapters retain explicit SQL. The `psycopg[binary]` dependency is
authorized solely for the PostgreSQL outbound adapter.

Both persistence adapters MUST store timestamps as ISO 8601 `TEXT`, normalized
to UTC before persistence and after reading, so ordering and SLA behavior remain
deterministic across engines. Production container topology MUST run the API and
PostgreSQL as separate services using Docker Compose, with PostgreSQL based on
`postgres:16-alpine`.

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
- SQLite uses the Python standard-library driver. PostgreSQL uses `psycopg[binary]`
  without an ORM, exclusively in the outbound adapter layer.
- Docker Compose is the production topology for separate API and PostgreSQL
  services; the database service uses `postgres:16-alpine`.

## Quality Gates

- `uv run ruff check src/` MUST pass, including configured rules that enforce
  hexagonal import boundaries and prevent forbidden database-driver imports.
- `uv run pytest -v` MUST pass before a change is accepted, including contract
  parity for SQLite and PostgreSQL adapters and real connectivity checks.
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

**Version**: 1.1.0 | **Ratified**: TODO(RATIFICATION_DATE): original adoption date unknown | **Last Amended**: 2026-11-24
