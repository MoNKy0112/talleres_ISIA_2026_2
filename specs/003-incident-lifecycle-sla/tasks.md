---

description: "Atomic implementation tasks for Incident Lifecycle and SLA"
---

# Tasks: Incident Lifecycle and SLA

**Input**: Design documents from `/specs/003-incident-lifecycle-sla/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/http-openapi.yaml`, `contracts/cli.md`, `quickstart.md`

**Organization**: Tasks follow the requested hexagonal dependency order
(Domain → Port/Application → SQLite → Inbound → BDD/quality). Story labels map
work to the spec: US1 registration, US2 active duplicate reporting, US3 SLA
auditing. Shared implementation tasks may support multiple stories.

**BDD traceability**: The specification has six atomic scenarios covering the
five requested behaviors: initial registration; duplicate detection while
ignoring resolved incidents; deterministic P2 business-hours SLA audit; SLA
not-found and invalid-reference errors (split into separate 404 and 422
scenarios); and equivalent create/SLA operation through CLI.

## Phase 1: Setup

**Purpose**: Confirm the existing application layout and test entrypoints before
changing implementation.

- [X] T001 Confirm the current source, test, and dependency layout against `specs/003-incident-lifecycle-sla/plan.md` and `pyproject.toml`
- [X] T002 Review required create/SLA fields and response shapes against `specs/003-incident-lifecycle-sla/contracts/http-openapi.yaml` and `specs/003-incident-lifecycle-sla/contracts/cli.md`

## Phase 2: Domain — models and deterministic SLA

**Purpose**: Establish framework-free domain structures and UTC-consistent SLA
behavior before application or adapter work.

- [X] T003 [US1] Extend `Incident` in `src/domain/models.py` with optional `recommended_team` and `duplicate_group_key` fields and define the canonical active-duplicate status policy (for example `OPEN_DUPLICATE_STATUSES`) excluding `RESOLVED`, as defined by `data-model.md` (`Incident.recommended_team`, `Incident.duplicate_group_key`)
- [X] T004 [US1] Add the persisted original report field needed by the model in `src/domain/models.py` as defined by `data-model.md` (`Incident.raw_text`)
- [X] T005 [US3] Add one domain-level datetime normalizer in `src/domain/sla_calculator.py` that treats naive values as UTC and converts aware values to UTC, per `data-model.md` (`Incident.created_at`)
- [X] T006 [US3] Use normalized timestamps for ordering validation, elapsed-minute calculation, and business-hour interval intersections in `src/domain/sla_calculator.py`
- [X] T007 [US3] Ensure SLA results clamp remaining minutes to zero after breach and expose exceeded minutes when breached in `src/domain/models.py` and `src/domain/sla_calculator.py`, per `data-model.md` (`SLA evaluation.remaining_minutes`, `SLA evaluation.exceeded_minutes`)

## Phase 3: Port and Application

**Purpose**: Define persistence needs and implement transport-neutral shared
use cases before connecting concrete storage or inbound adapters.

- [X] T008 [US1] Extend `IncidentRepositoryPort` in `src/application/ports.py` with save, get-by-ID, and unique-ID availability operations required by `create_incident`, using `data-model.md` (`Incident.incident_id`)
- [X] T009 [US2] Define `find_open_duplicates(duplicate_group_key, open_statuses, exclude_incident_id)` in `src/application/ports.py`, accepting the domain-supplied allowed statuses and explicit new-ID exclusion, using `data-model.md` (`Incident.duplicate_group_key`, `Duplicate result.duplicate_of`)
- [X] T010 [US3] Update the `get_incident` port docstring to specify `None` for absent IDs in `src/application/ports.py`, matching `data-model.md` (`SLA evaluation.incident_id`)
- [X] T011 [US1] Add transport-neutral `IncidentNotFoundError` and retain application validation errors in `src/application/services.py`
- [X] T012 [US1] Implement `IncidentService.create_incident` in `src/application/services.py`: validate title/raw text and status, normalize created time, generate collision-checked `INC-<HEX8>` IDs, classify via the domain rule, and construct the incident without changing the existing optional `Incident.resolved_at` model semantics, using `data-model.md` (`Incident.incident_id`, `Incident.title`, `Incident.raw_text`, `Incident.status`, `Incident.created_at`, `Incident.component`, `Incident.severity`, `Incident.recommended_team`, `Incident.duplicate_group_key`, `Incident.resolved_at`)
- [X] T013 [US2] Apply the domain-owned active-duplicate status policy and add pre-persistence lookup in `src/application/services.py`; pass `duplicate_group_key`, the explicit allowed `open_statuses`, and `exclude_incident_id` to the port, then return all matching IDs without blocking save, using `data-model.md` (`Incident.duplicate_group_key`, `Duplicate result.is_duplicate`, `Duplicate result.duplicate_of`)
- [X] T014 [US3] Implement `IncidentService.evaluate_incident_sla` in `src/application/services.py`, raising `IncidentNotFoundError` for absent IDs and rejecting references before creation; populate every `SLAEvaluation` field explicitly using `data-model.md` (`SLA evaluation.incident_id`, `SLA evaluation.component`, `SLA evaluation.severity`, `SLA evaluation.status`, `SLA evaluation.elapsed_minutes`, `SLA evaluation.allowed_minutes`, `SLA evaluation.remaining_minutes`, `SLA evaluation.exceeded_minutes`, `SLA evaluation.is_breached`, `SLA evaluation.requires_escalation`)

## Phase 4: SQLite secondary adapter

**Purpose**: Persist the domain model and satisfy the application port without
leaking SQLite into the core.

- [X] T015 [US1] Add idempotent SQLite migration logic for `recommended_team`, `duplicate_group_key`, and new incident report storage in `src/adapters/outbound/sqlite_repository.py`, using `data-model.md` (`Incident.recommended_team`, `Incident.duplicate_group_key`, `Incident.raw_text`)
- [X] T016 [US2] Create index `idx_incidents_dup_key` on `(duplicate_group_key, status)` in `src/adapters/outbound/sqlite_repository.py`
- [X] T017 [US1] Implement `save_incident` without silently replacing an existing ID and persist/read all new model fields in `src/adapters/outbound/sqlite_repository.py`, using `data-model.md` (`Incident.incident_id`, `Incident.raw_text`, `Incident.recommended_team`, `Incident.duplicate_group_key`)
- [X] T018 [US1] Implement `get_incident` and row-to-domain conversion for nullable legacy fields in `src/adapters/outbound/sqlite_repository.py`; persist and rehydrate `Incident.resolved_at` correctly without changing its value, using `data-model.md` (`Incident.recommended_team`, `Incident.duplicate_group_key`, `Incident.created_at`, `Incident.resolved_at`)
- [X] T019 [US2] Implement `find_open_duplicates(duplicate_group_key, open_statuses, exclude_incident_id)` in `src/adapters/outbound/sqlite_repository.py` as a parameterized query using only its supplied arguments; do not hardcode active statuses or duplicate business rules in SQLite, using `data-model.md` (`Incident.duplicate_group_key`, `Duplicate result.duplicate_of`)
- [X] T020 [US1] Keep `SQLiteIncidentRepository` structurally compliant with `IncidentRepositoryPort` and preserve existing summary/health behavior in `src/adapters/outbound/sqlite_repository.py`

## Phase 5: Inbound adapters — HTTP and CLI

**Purpose**: Expose the same application use cases through FastAPI and Typer,
keeping transport validation, serialization, and error mapping at the boundary.

- [X] T021 [US1] Define `CreateIncidentRequest` with required title/raw text and optional ID, creation time, and status in `src/adapters/inbound/api/schemas.py`, following `contracts/http-openapi.yaml`
- [X] T022 [US1] Define `IncidentCreatedResponse` with full classification and duplicate fields in `src/adapters/inbound/api/schemas.py`, following `contracts/http-openapi.yaml`
- [X] T023 [US3] Define `SLAEvaluationResponse` with incident context and SLA fields in `src/adapters/inbound/api/schemas.py`, following `contracts/http-openapi.yaml`
- [X] T024 [US1] Add `POST /api/v1/incidents` to `src/adapters/inbound/api/app.py`, delegate to `IncidentService.create_incident`, return 201, and map validation errors to 422
- [X] T025 [US3] Add `GET /api/v1/incidents/{incident_id}/sla` to `src/adapters/inbound/api/app.py`, delegate to `IncidentService.evaluate_incident_sla`, map not-found to 404 and invalid temporal order to 422
- [X] T026 [US1] Add Typer `create` command to `src/adapters/inbound/cli.py`, delegate to the same service use case, output JSON on success, and exit 1 on validation errors
- [X] T027 [US3] Add Typer `sla` command to `src/adapters/inbound/cli.py`, delegate to the same service use case, output JSON on success, and exit 1 on not-found or temporal validation errors
- [X] T028 [US1] Ensure inbound adapters obtain persistence through `src/adapters/outbound/factory.py` and import no concrete repository or database driver in `src/adapters/inbound/api/app.py` and `src/adapters/inbound/cli.py`

## Phase 6: BDD acceptance tests and quality gates

**Purpose**: Verify all five required observable behaviors, adapter parity, and
hexagonal import rules.

### User Story 1 — Registration

**Independent Test**: A valid HTTP create returns 201 with generated ID,
classification, `is_duplicate=false`, and empty `duplicate_of`; invalid blank
title or raw text returns 422 and creates no record.

- [X] T029 [US1] Add `TestClient` BDD coverage for valid initial registration, generated ID, complete classification, and no duplicates in `tests/test_spec_003_lifecycle_sla.py`
- [X] T030 [US1] Add `TestClient` and `CliRunner` coverage proving blank title/raw text are rejected with HTTP 422/CLI exit 1 and no persistence in `tests/test_spec_003_lifecycle_sla.py`

### User Story 2 — Open duplicate detection

**Independent Test**: Seed equivalent incidents in each lifecycle state, create
a new report, and verify 201 persists it while `duplicate_of` contains only
matching active IDs and excludes resolved/self IDs.

- [X] T031 [US2] Add repository and HTTP BDD coverage for matching domain-supplied active statuses, ignoring `RESOLVED`, excluding the new ID, and retaining the new report in `tests/test_spec_003_lifecycle_sla.py`
- [X] T032 [US2] Add CLI BDD coverage for duplicate JSON parity and non-blocking registration in `tests/test_spec_003_lifecycle_sla.py`

### User Story 3 — SLA audit

**Independent Test**: Query known/unknown incidents at fixed reference times
through HTTP and CLI; verify the P2 weekend example, 404, 422, and equivalent
business results.

- [X] T033 [US3] Add `TestClient` BDD coverage for P2 Friday 2026-11-06 17:00 through Monday 2026-11-09 09:00 with exact expected SLA values in `tests/test_spec_003_lifecycle_sla.py`
- [X] T034 [US3] Add HTTP and `CliRunner` BDD coverage for missing incident (404/exit 1), reference before creation (422/exit 1), equivalent SLA data, and the exact P2 CLI `sla` result for Friday `2026-11-06T17:00:00` to Monday `2026-11-09T09:00:00` (`elapsed_minutes=120`, `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false`, `requires_escalation=false`) compared for exact parity with `TestClient` in `tests/test_spec_003_lifecycle_sla.py`
- [X] T035 [US3] Add domain boundary tests for naive-as-UTC, aware-to-UTC, exact SLA boundary, breach, and escalation behavior in `tests/test_spec_003_lifecycle_sla.py`

### Cross-story verification

- [X] T036 Run `uv run pytest -v` from the repository root and resolve regressions in `tests/` and affected `src/` files
- [X] T037 Run `uv run ruff check src/` from the repository root and resolve lint/import-boundary violations, explicitly verifying TID251 and TID252 against the layer-specific `ruff.toml` files under `src/domain/`, `src/application/`, and `src/adapters/inbound/`
- [X] T038 Run the H003 scenarios from `specs/003-incident-lifecycle-sla/quickstart.md` and reconcile observed HTTP/CLI contracts with `specs/003-incident-lifecycle-sla/contracts/`

## Dependencies & Execution Order

### Hexagonal layer order

1. **Domain (T003–T007)**: entity, canonical duplicate-status policy, and deterministic SLA rules.
2. **Port/Application (T008–T014)**: abstract persistence and shared use cases; the service passes the domain's allowed statuses explicitly to duplicate lookup.
3. **SQLite (T015–T020)**: schema, migration, persistence and duplicate query.
4. **Inbound (T021–T028)**: DTOs, HTTP and CLI contracts and error mapping.
5. **BDD/Quality (T029–T038)**: end-to-end behavior, pytest, Ruff and quickstart.

Each layer blocks the next where it consumes the prior layer's contract. Setup
tasks T001–T002 can run first; within a layer, only explicitly marked `[P]`
tasks are safe to parallelize.

### User story dependencies

- **US1 (P1)**: Registration requires domain classification, port/application
  creation, SQLite persistence, then API/CLI entrypoints. This is the suggested
  MVP.
- **US2 (P1)**: Duplicate reporting extends US1 creation; depends on the domain
  duplicate key, duplicate port, SQLite query, and create response. It is not
  independently shippable before the create path.
- **US3 (P1)**: SLA audit depends on the domain timestamp/SLA behavior, repository
  lookup, and inbound SLA endpoints/command. It can be implemented after
  foundational domain and application tasks, but integration still depends on
  SQLite and inbound layers.

### Parallel opportunities

- T003 and T004 are in the same file and should be done together, not parallel.
- T005–T007 are sequential within `sla_calculator.py`.
- T008 and T009 edit the same port file; serialize them. T012–T014 edit the
  same service file; serialize them in listed order.
- T015–T019 edit the same SQLite adapter; serialize them in listed order.
- T021–T023 edit one schema file; serialize them. T024–T025 edit one API file;
  serialize them. T026–T027 edit one CLI file; serialize them.
- T029–T035 all edit `tests/test_spec_003_lifecycle_sla.py` and are intentionally
  unmarked `[P]`; serialize edits to that shared file.
- T036 and T037 can run in parallel after implementation and tests stabilize.

## Implementation Strategy

### MVP

Implement the Domain → Port/Application → SQLite → Inbound path for US1, then
prove one valid create and invalid-input behavior through HTTP and CLI. Extend
that create path with US2 duplicate reporting, then deliver US3 SLA audit.
Complete the BDD suite and both quality gates before accepting the milestone.

## Notes

- Every implementation task names its target file. Constrained model fields cite
  their canonical `data-model.md` entity/field definitions.
- Keep business decisions in the domain/application core; inbound adapters only
  translate/serialize/map errors; SQLite only implements persistence.
- The design document identifies `raw_text` persistence as required by the spec;
  retain it unless the feature specification is revised before implementation.
