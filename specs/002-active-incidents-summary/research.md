# Research: Active Incident Summary

**Date**: 2026-11-23
**Scope**: Design decisions for the H002 implementation plan.

## Decisions

### Port and dependency direction

- **Decision**: Define `IncidentRepositoryPort` as a `typing.Protocol` in
  `src/application/ports.py`. Give it the requested `save_incident`,
  `get_incident`, `find_open_duplicates`, `list_active_incidents`, and
  `check_health` operations. The port returns domain incidents for reads; it does
  not return HTTP schemas or precomputed SLA results.
- **Duplicate lookup semantics**: `find_open_duplicates` returns every persisted
  `OPEN` incident matching the exact component and duplicate-group key. It does
  not mutate storage, reject a candidate, or silently discard one. Persist the
  key with the incident; records without a key are not matches. Any policy for
  acting on results belongs to a separate registration use case, not H002.
- **Rationale**: This matches the constitution's secondary-port boundary and keeps
  application policy independent of SQLite. `get_active_incidents_summary` owns
  orchestration and calls `evaluate_sla_status` for each active incident at one
  shared reference instant.
- **Alternatives considered**: Let inbound adapters query SQLite directly (breaks
  hexagonal boundaries); put SLA decisions in repository SQL (duplicates domain
  policy).

### SQLite query and indexing

- **Decision**: Move persistence behavior into
  `src/adapters/outbound/sqlite_repository.py`. Implement the active-list query
  with status restriction and optional component predicate in SQL, a single
  `INNER JOIN sla_policies`, and composite index `(component, status)`.
- **Rationale**: This removes the inherited full-table Python scan and N+1 policy
  query while preserving the existing schema's SLA-policy relationship. The
  required join is retained as the requested persistence design, not as the
  authority for SLA evaluation.
- **Alternatives considered**: Fetch all rows then filter in Python (retains the
  benchmark anti-pattern); separate policy lookups (N+1); add an ORM (contrary to
  constitution).

### Factory and database URL

- **Decision**: Parse and validate `DATABASE_URL` only at
  `src/adapters/outbound/factory.py`; support the SQLite URL forms required by the
  project and default to `sqlite:///:memory:`. Return a repository configured for
  the selected SQLite database.
- **Rationale**: Composition is the boundary mandated by the constitution; domain
  and use cases do not know URL syntax.
- **Alternatives considered**: Read environment variables in services (couples
  application to deployment); default to a file database (changes requested
  in-memory behavior).
- **Operational note**: In-memory SQLite is connection-scoped. The application
  composition should create one repository/service for the app lifetime rather
  than construct a fresh repository per request or CLI operation that needs to
  observe previously seeded data.

### Summary use case and time

- **Decision**: `IncidentService.get_active_incidents_summary(component_filter,
  reference_time)` loads active records through the port, evaluates each using
  `evaluate_sla_status`, and creates one shared result consumed by both adapters.
  If time is omitted at the inbound boundary, resolve it once to the current
  UTC instant; an explicit RFC 3339 timestamp with timezone is normalized to UTC
  at the adapter edge. Naive legacy persisted timestamps are interpreted as UTC
  before evaluation so both sides of the SLA comparison use the same timezone.
- **Rationale**: Reuses deterministic business rules and ensures totals and item
  details are consistent. Active statuses are exactly `OPEN` and `IN_PROGRESS`.
- **Alternatives considered**: Compute independently in API and CLI (parity drift);
  calculate only elapsed time in SQL (policy duplication).

### Inbound contracts and output

- **Decision**: Keep the HTTP endpoint at `GET /api/v1/incidents/summary`, with
  optional `component` and `reference_time` query parameters and a JSON response
  containing `total_active`, `breached_count`, and `incidents`. Add the matching
  Typer `summary` command with `--component` and `--reference-time`; emit JSON for
  parity with the HTTP payload.
- **Rationale**: Implements the confirmed feature contract and provides a
  deterministic path to acceptance-test both adapters.
- **Alternatives considered**: A separate CLI-only presentation shape (harder to
  compare); HTTP error for no matches (contradicts the accepted empty-state rule).

### Static boundary checks

- **Decision**: Add the requested Ruff selection to `pyproject.toml` and
  hierarchical configuration at domain, application, and inbound adapter layers.
  Configure TID251 banned APIs per layer and TID252 to reject parent-relative
  imports, while allowing inbound code to use the outbound factory.
- **Rationale**: Enforces dependency direction at lint time and matches the
  constitution and repository architecture skill.
- **Alternatives considered**: Rely only on review (not an automated quality gate);
  blanket-ban all outbound imports in inbound (would also reject the approved
  factory composition seam).

### Acceptance verification

- **Decision**: Add `tests/test_spec_002_summary.py` with API/CLI behavior and
  parity, filtering, empty result, reference-time/SLA behavior, read-only
  assertions, and behavioral checks for repository save/read, duplicate lookup,
  active listing, and health operations. Verify that `SQLiteIncidentRepository`
  satisfies the runtime-checkable protocol.
- **Rationale**: Covers observable behavior and the explicitly requested adapter
  conformance without coupling acceptance assertions to query implementation.
- **Alternatives considered**: Only unit-test repository SQL (misses interface
  parity); only test HTTP (misses CLI and shared-use-case behavior).

## Implementation Notes

- Finalize port annotations to match the semantics in `data-model.md`; preserve
  `duplicate_group_key` on incidents and implement the exact open-duplicate query.
- The existing benchmark class is not yet used by production composition; keep
  its standalone teaching purpose distinct from the new production repository.
- Validate SQLite URL parsing for the in-memory default, relative paths, and
  absolute paths without allowing unsupported schemes to silently fall back.
