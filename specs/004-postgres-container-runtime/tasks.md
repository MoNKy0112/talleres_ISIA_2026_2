---
description: "Atomic implementation tasks for PostgreSQL Container Runtime"
---

# Tasks: PostgreSQL Container Runtime

**Input**: Design documents from `/specs/004-postgres-container-runtime/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, and `contracts/`.

**Organization**: Tasks are grouped by the three user stories in `spec.md`; within each increment, work follows hexagonal layers from shared configuration and application core to outbound/inbound adapters and runtime.

## Format: `[ID] [P?] [Story] Description`

- **[P]** means the task edits a different file from concurrent tasks and has no unmet dependency.
- Story labels map to the user stories in `spec.md`.
- Every task includes the target file path.

## Phase 1: Setup

**Purpose**: Prepare the dependency and architectural boundary checks used by all increments.

- [X] T001 Add `psycopg[binary]` to runtime dependencies in `pyproject.toml` and synchronize the committed `uv.lock` using `uv lock`.
- [X] T002 [P] Add explicit `psycopg` and `sqlite3` entries under Ruff `TID251` (`lint.flake8-tidy-imports.banned-api`) in `src/domain/ruff.toml`.
- [X] T003 [P] Add explicit `psycopg` and `sqlite3` entries under Ruff `TID251` (`lint.flake8-tidy-imports.banned-api`) in `src/application/ruff.toml`.
- [X] T004 [P] Add explicit `psycopg` and `sqlite3` entries under Ruff `TID251` (`lint.flake8-tidy-imports.banned-api`) in `src/adapters/inbound/ruff.toml`.

**Checkpoint**: Dependency is locked; Ruff prevents PostgreSQL driver imports outside outbound adapters.

## Phase 2: Foundational

**Purpose**: Establish the shared application contract before implementing either database or health transport.

- [X] T005 Add `check_health() -> bool` to the `@runtime_checkable` `IncidentRepositoryPort` in `src/application/ports.py`.
- [X] T006 Implement `IncidentService.check_health()` in `src/application/services.py`: delegate to the configured repository port and return its boolean result; if no repository is configured, safely return `False` without raising so API `/health` and CLI `health` report unavailable.

**Checkpoint**: Application exposes a transport-neutral connectivity use case and runtime-checkable persistence port.

## Phase 3: User Story 1 - Consultar la salud real del servicio (Priority: P1) 🎯 MVP

**Goal**: Operators can determine actual database connectivity using either HTTP or CLI, with a stable degraded response.

**Independent Test**: Use healthy and failing repository doubles to assert HTTP 200/503 response status and body, CLI JSON output and exit code 0/1, and verify the shared service health method is called.

### Tests for User Story 1

- [X] T007 [US1] Add API health success and unavailable (`False`, exception, and `IncidentService` without a configured repository) cases with exact JSON/status assertions to `tests/test_spec_004_runtime_health.py`; assert missing repository yields HTTP 503 rather than an unhandled error.
- [X] T008 [US1] Add CLI health success, unavailable (`False` and exception), and `IncidentService` without a configured repository cases asserting stdout JSON and exit codes 0/1; directly assert `IncidentService.check_health()` returns `False` without a repository in `tests/test_spec_004_runtime_health.py`.

### Implementation for User Story 1

- [X] T009 [US1] Add `HealthResponse` with `status` and `database` fields to `src/adapters/inbound/api/schemas.py`.
- [X] T010 [US1] Add `GET /health` to `src/adapters/inbound/api/app.py`, delegate to `IncidentService.check_health()`, return the contract response on success, and map false/raised connectivity failure to HTTP 503 without exposing exception details.
- [X] T011 [US1] Add the `health` command to `src/adapters/inbound/cli.py`, delegate to `IncidentService.check_health()`, print the contract JSON to stdout, and exit 0/1 according to health.

**Checkpoint**: Health works independently through HTTP and CLI using an injected test repository; database-driver details remain outside inbound.

## Phase 4: User Story 2 - Seleccionar persistencia sin cambiar el uso del servicio (Priority: P1)

**Goal**: Select SQLite or PostgreSQL from configuration and preserve the common repository behavior, including health, incident/SLA operations, and UTC timestamps.

**Independent Test**: Construct both repository adapters through the factory without a PostgreSQL daemon, verify structural port conformance, validate URL routing/rejection, and exercise equivalent repository behavior against each engine when PostgreSQL is available.

### Tests for User Story 2

- [X] T012 [US2] Add factory routing tests for `postgresql://`, `postgres://`, `sqlite:///`, absent URL/default, and unsupported-scheme `ValueError` to `tests/test_spec_004_runtime_health.py`.
- [X] T013 [US2] Add runtime protocol-conformance tests for SQLite and lazily constructed PostgreSQL repositories, plus PostgreSQL construction without a live daemon; assert each adapter exposes and satisfies all six `IncidentRepositoryPort` methods, in `tests/test_spec_004_runtime_health.py`.
- [X] T014 [US2] Add PostgreSQL adapter tests for `save_incident(incident: Incident) -> None` (insert/update per port contract), `get_incident(incident_id: str) -> Incident | None`, `incident_id_exists(incident_id: str) -> bool`, `find_open_duplicates(duplicate_group_key: str, open_statuses: frozenset[IncidentStatus], exclude_incident_id: str) -> list[Incident]`, `list_active_incidents(component_filter: str | None = None) -> list[Incident]`, and `check_health() -> bool`; cover real `SELECT 1` success/failure, idempotent schema/index/SLA seeds, incident CRUD/query parity, and UTC timestamps in `tests/test_spec_004_runtime_health.py`. Include at least two different `open_statuses` sets and assert only the supplied statuses match, proving the rule is caller-owned; compare SQLite/PostgreSQL SLA evaluations for the same incident and `reference_time`.

### Implementation for User Story 2

- [X] T015 [US2] Ensure SQLite implements `IncidentRepositoryPort.check_health()` with an effective `SELECT 1` and returns `False` on database errors in `src/adapters/outbound/sqlite_repository.py`.
- [X] T016 [US2] Implement lazy connection management, `dict_row` mapping, and the exact `check_health() -> bool` port method using real `SELECT 1`; return `False` on connection/query failure in `src/adapters/outbound/postgres_repository.py`.
- [X] T017 [US2] Implement idempotent PostgreSQL `sla_policies`/`incidents` tables, component/status and duplicate-key/status indexes, SLA seed insertion, and transactional initialization in `src/adapters/outbound/postgres_repository.py`.
- [X] T018 [US2] Implement the remaining exact `IncidentRepositoryPort` methods in `src/adapters/outbound/postgres_repository.py`: `save_incident(incident: Incident) -> None`, `get_incident(incident_id: str) -> Incident | None`, `incident_id_exists(incident_id: str) -> bool`, `find_open_duplicates(duplicate_group_key: str, open_statuses: frozenset[IncidentStatus], exclude_incident_id: str) -> list[Incident]`, and `list_active_incidents(component_filter: str | None = None) -> list[Incident]`; use parameterized `%s` SQL and the required `INSERT ... ON CONFLICT DO UPDATE` for `save_incident`. For `find_open_duplicates`, apply exactly the supplied `open_statuses` as bound values and do not hard-code active/open status lists in SQL. Use the canonical UTC ISO 8601 `TEXT` mapping from `data-model.md` (`Incident.created_at`, `Incident.resolved_at`).
- [X] T019 [US2] Implement URL selection for `postgresql://`, `postgres://`, and `sqlite:///`, the in-memory SQLite default, and explicit unsupported-scheme errors in `src/adapters/outbound/factory.py`.

**Checkpoint**: Factory selects both adapters, each satisfies the port, and PostgreSQL construction stays lazy; parity checks cover incident and SLA behavior.

## Phase 5: User Story 3 - Operar el runtime en contenedores reproducibles (Priority: P1)

**Goal**: Run API and PostgreSQL as separate services, start API only after database readiness, and retain database data across API recreation.

**Independent Test**: Validate Compose configuration, build and start both services, confirm `pg_isready` gates API startup, `/health` reports connectivity, and database volume persists when only API is recreated.

### Tests for User Story 3

- [X] T020 [US3] Add configuration assertions for Docker base image/uv lock install, `.dockerignore` exclusions, and two-service Compose settings (PostgreSQL image, persistent volume, `pg_isready`, `service_healthy`, API URL and `/health` check) to `tests/test_spec_004_runtime_health.py`.

### Implementation for User Story 3

- [X] T021 [P] [US3] Add a `python:3.12-slim` Docker build using pinned `uv`, copying `pyproject.toml` and `uv.lock`, and installing locked production dependencies with the exact command `uv sync --locked --no-dev` in `Dockerfile`.
- [X] T022 [P] [US3] Exclude local virtual environments, caches, tests, local databases, Git metadata, and environment-secret files while retaining runtime source and lock files in `.dockerignore`.
- [X] T023 [US3] Add exactly `db` and `api` to `docker-compose.yml`: `db` uses `postgres:16-alpine`, environment-based credentials, named persistent volume, and `pg_isready` healthcheck; `api` builds the Dockerfile, listens on `0.0.0.0`, publishes a declared host/container port, uses a `DATABASE_URL` whose host is `db` and port is the database service port, waits with `depends_on: condition: service_healthy`, and probes `/health` at the same container API port that is published.

**Checkpoint**: Compose starts exactly the API and PostgreSQL services in health order, and API health reflects database connectivity.

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Verify all user stories, architectural boundaries, and documented runtime behavior together.

- [X] T024 Run the complete test suite with `uv run pytest` and fix any regressions in the affected implementation/test files; ensure tests cover `IncidentService.check_health()` returning `False` when no repository is configured and SQLite/PostgreSQL SLA parity for the same incident and `reference_time`.
- [X] T025 Run `uv run ruff check src/` and verify that `psycopg` and `sqlite3` are both rejected in `src/domain/`, `src/application/`, and `src/adapters/inbound/` while remaining usable only in `src/adapters/outbound/`.
- [ ] T026 Validate `specs/004-postgres-container-runtime/quickstart.md` end to end: `docker compose config`, `uv sync --locked --no-dev` image build, API listening on `0.0.0.0`, database/API health ordering, aligned published/API/database ports and `DATABASE_URL` host `db`, `/health`, incident CRUD and SLA parity using the same incident and `reference_time`, and API recreation without removing the database volume. **Blocked: Docker daemon unavailable in the current environment.**

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately; T001–T004 edit distinct files and can run in parallel.
- **Foundational (Phase 2)**: Follows setup; T005 precedes T006 because the service delegates through the port. Blocks all story work.
- **User Stories (Phases 3–5)**: Follow the foundation. The stories share implementation dependencies and are ordered US1 → US2 → US3 for executable incremental delivery.
- **Polish (Phase 6)**: Follows all three stories.

### User Story Dependencies

- **US1 (P1)**: Depends on the application port/service foundation; delivers health independently using a test double.
- **US2 (P1)**: Depends on the application port/service foundation; supplies real configured persistence and extends US1 health to both database adapters.
- **US3 (P1)**: Depends on US2 so Compose can target the implemented PostgreSQL adapter; `/health` from US1 is its readiness check.

### Within Each User Story

- Write the requested test cases before the corresponding implementation and verify their expected failure before implementation.
- Keep application contracts before outbound implementations, and outbound selection/health before inbound wiring that relies on it.
- Do not mark tasks editing the same file `[P]`. Because T007, T008, T012, T013, T014, and T020 all edit `tests/test_spec_004_runtime_health.py`, they MUST be executed sequentially in this exact order: T007 → T008 → T012 → T013 → T014 → T020. Each task starts only after the preceding test-file edit is complete; implementation may begin after the corresponding tests have been recorded.

### Parallel Opportunities

- Setup tasks T002–T004 are parallelizable because they edit separate Ruff files; T001 is also independent of those config edits.
- In US3, T021 and T022 can run in parallel because they edit separate files; T023 follows them.
- No test task for `tests/test_spec_004_runtime_health.py` is marked `[P]`, avoiding concurrent edits to that file.
- Test-file dependency chain: T007 → T008 → T012 → T013 → T014 → T020; no pair in this chain may run concurrently.

## Parallel Example: Setup and User Story 3

```text
Setup after T001 is available:
Task T002: Add the psycopg ban in src/domain/ruff.toml
Task T003: Add the psycopg ban in src/application/ruff.toml
Task T004: Add the psycopg ban in src/adapters/inbound/ruff.toml

US3 after US1 and US2:
Task T021: Create Dockerfile
Task T022: Create .dockerignore
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete setup and foundational port/service work.
2. Complete US1 tests and HTTP/CLI implementation.
3. Validate health success and failure independently using repository doubles; this proves the shared health contract before adding a live database.

### Incremental Delivery

1. Add US2 to make the same health use case operate with selectable SQLite/PostgreSQL persistence and validate repository parity.
2. Add US3 to package and orchestrate the API and PostgreSQL runtime.
3. Run all tests, Ruff checks, and the end-to-end quickstart validation.

## Notes

- `[P]` means different files and no unmet dependency; shared test-file edits are sequential.
- Story labels map to the three P1 user stories in `spec.md`.
- PostgreSQL adapter construction must not connect; only an operation opens a connection.
- The PostgreSQL driver and all SQL remain in `src/adapters/outbound/`; no ORM is introduced.
- `find_open_duplicates` uses the exact `open_statuses` supplied by the service/port; do not move duplicate-state policy into adapter SQL.
- `IncidentService.check_health()` safely returns `False` if no repository is configured.
- The final acceptance commands are `uv run pytest` and `uv run ruff check src/`.
