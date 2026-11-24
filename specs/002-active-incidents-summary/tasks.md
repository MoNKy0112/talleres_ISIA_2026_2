---

description: "Implementation task list for Active Incident Summary"
---

# Tasks: Active Incident Summary

**Input**: Design documents from `specs/002-active-incidents-summary/`

**Prerequisites**: `plan.md`, `spec.md`; design references: `research.md`,
`data-model.md`, `contracts/active-incidents-summary.openapi.yaml`,
`quickstart.md`

**Tests**: Included because the specification and constitution require automated
BDD pytest coverage and cross-adapter parity.

**Organization**: Tasks are grouped by user story. Shared persistence, composition,
and use-case prerequisites are foundational.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the repository's static architecture gates before implementing
the feature.

- [X] T001 Configure `[tool.ruff.lint]` with `select = ["E4", "E7", "E9", "F", "TID"]` in `pyproject.toml`
- [X] T002 [P] Add the domain Ruff extension and TID251 banned APIs for outward dependencies in `src/domain/ruff.toml`
- [X] T003 [P] Add the application Ruff extension and TID251 bans for adapters, frameworks, and database drivers in `src/application/ruff.toml`
- [X] T004 [P] Add the inbound Ruff extension and TID251 bans for direct database drivers and concrete SQLite repository imports, while permitting the outbound factory, in `src/adapters/inbound/ruff.toml`
- [X] T005 Ensure each hierarchical Ruff file extends the root `pyproject.toml`, retains TID selection, and sets `ban-relative-imports = "parents"` in `src/domain/ruff.toml`, `src/application/ruff.toml`, and `src/adapters/inbound/ruff.toml`

**Checkpoint**: Ruff configuration exists and the current source passes or reports
only feature-related violations to address in the story/polish phases.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create the persistence abstraction and composition needed by both
inbound interfaces.

**⚠️ CRITICAL**: User-story work depends on these shared capabilities.

- [X] T006 Define runtime-checkable `IncidentRepositoryPort` with `save_incident`, `get_incident`, `find_open_duplicates`, `list_active_incidents`, and `check_health` using domain-only types in `src/application/ports.py`
- [X] T007 Add required `duplicate_group_key` to the `Incident` domain entity in `src/domain/models.py` and update its construction sites in `src/incident_repository.py` and `src/domain/sla_calculator.py`; implement SQLite schema initialization, save/read, exact open-duplicate lookup, active listing, and health check in `src/adapters/outbound/sqlite_repository.py`; map `Incident.incident_id`, `Incident.title`, `Incident.component`, `Incident.duplicate_group_key`, `Incident.severity`, `Incident.status`, `Incident.created_at`, and `Incident.resolved_at` as defined in `data-model.md`. Interpret legacy naive timestamps as UTC. Duplicate lookup returns all exact component/key matches in `OPEN` status and does not mutate storage.
- [X] T008 Implement filtered active selection using one `INNER JOIN sla_policies`, active statuses, optional exact component, and composite `(component, status)` index in `src/adapters/outbound/sqlite_repository.py`; return domain incidents for `data-model.md` `Incident.*` fields without evaluating SLA there
- [X] T009 Implement SQLite `DATABASE_URL` parsing, unsupported-scheme errors, and `sqlite:///:memory:` default in `src/adapters/outbound/factory.py`
- [X] T010 Add shared application summary result/item types and implement `IncidentService.get_active_incidents_summary(component_filter, reference_time)` using `evaluate_sla_status` and one reference instant in `src/application/services.py`; satisfy `data-model.md` fields `SLA Evaluation.elapsed_minutes`, `SLA Evaluation.is_breached`, `SLA Evaluation.requires_escalation`, `Active Incident Item.incident_id`, `Active Incident Item.title`, `Active Incident Item.component`, `Active Incident Item.severity`, `Active Incident Item.status`, `Active Incident Item.elapsed_minutes`, `Active Incident Item.requires_escalation`, `Active Incidents Summary.total_active`, `Active Incidents Summary.breached_count`, and `Active Incidents Summary.incidents`
- [X] T011 Compose one repository/service per application lifetime and inject the shared use case through the outbound factory in `src/adapters/inbound/api/app.py` and `src/adapters/inbound/cli.py`

**Checkpoint**: Shared domain-backed summary use case can read through the port;
factory defaults and rejects unsupported database schemes predictably.

---

## Phase 3: User Story 1 - Review the global active incident summary (Priority: P1) 🎯 MVP

**Goal**: Deliver the HTTP summary with global listing, component filtering, and
successful empty results.

**Independent Test**: Exercise the endpoint with active/inactive incidents and
multiple components; verify the response fields and counts, filtered subset,
empty state, and deterministic SLA details for a supplied reference time.

### Tests for User Story 1

- [X] T012 [US1] Add BDD API acceptance tests for global summary, exclusion of inactive statuses, component filtering, empty `200` response, supplied reference time, and unchanged persisted incidents before and after the request in `tests/test_spec_002_summary.py`
- [X] T013 [US1] Test runtime-checkable `IncidentRepositoryPort` conformance and repository behavior for save, get, exact open-duplicate lookup, active listing, and health check in `tests/test_spec_002_summary.py`

### Implementation for User Story 1

- [X] T014 [US1] Add `ActiveIncidentItem` and `ActiveIncidentsSummaryResponse` Pydantic schemas matching the OpenAPI response and data-model field constraints in `src/adapters/inbound/api/schemas.py`; cite `Active Incident Item.incident_id`, `Active Incident Item.title`, `Active Incident Item.component`, `Active Incident Item.severity`, `Active Incident Item.status`, `Active Incident Item.elapsed_minutes`, `Active Incident Item.requires_escalation`, `Active Incidents Summary.total_active`, `Active Incidents Summary.breached_count`, and `Active Incidents Summary.incidents`
- [X] T015 [US1] Add `GET /api/v1/incidents/summary` with optional `component` and RFC 3339 `reference_time`; normalize supplied timestamps to UTC, preserve validation/error mapping and shared-service delegation, and serialize empty results as `200` in `src/adapters/inbound/api/app.py`
- [X] T016 [US1] Run and refine the US1 acceptance tests against `contracts/active-incidents-summary.openapi.yaml` and `tests/test_spec_002_summary.py`

**Checkpoint**: HTTP contract and all three web behaviors are independently
verified; this is the MVP milestone.

---

## Phase 4: User Story 2 - Review the same summary from the terminal (Priority: P1)

**Goal**: Expose the same application summary from Typer with equivalent JSON
output.

**Independent Test**: For the same repository fixture, component and reference
time, compare CLI output to the HTTP response; verify options may be omitted and
that an empty result is valid JSON.

### Tests for User Story 2

- [X] T017 [US2] Add BDD CLI acceptance and HTTP/CLI parity tests using the same service fixture, including `--component`, RFC 3339 `--reference-time`, and unchanged persisted incidents before and after the command, in `tests/test_spec_002_summary.py`

### Implementation for User Story 2

- [X] T018 [US2] Add Typer `summary` command with optional `--component` and RFC 3339 `--reference-time`; normalize timestamps to UTC as in HTTP, delegate to the shared service, validate input, and emit JSON matching the response schema in `src/adapters/inbound/cli.py`
- [X] T019 [US2] Verify the equivalent-summary scenario and empty JSON output through the Typer test runner in `tests/test_spec_002_summary.py`

**Checkpoint**: CLI and HTTP expose equivalent business data for equivalent inputs.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Verify architectural boundaries, existing behavior, and documented
run instructions.

- [X] T020 [P] Update the manual H002 invocation and storage configuration examples to match the final adapter composition in `specs/002-active-incidents-summary/quickstart.md`
- [X] T021 Run `uv run ruff check src/` and resolve remaining configured lint or import-boundary violations in the affected `src/` files
- [X] T022 Run `uv run pytest -v` and resolve regressions in H001 or H002 acceptance coverage
- [X] T023 Run the HTTP and CLI checks from `specs/002-active-incidents-summary/quickstart.md` and confirm response parity

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependency on feature code; Ruff sub-configurations
  depend on T001 for the shared rule selection.
- **Foundational (Phase 2)**: Depends on Setup. T007/T008 implement the port
  defined by T006; T009 is independent after the package path exists; T010
  depends on T006 and T008; T011 depends on T009 and T010.
- **User Story 1 (Phase 3)**: Depends on the foundational phase; tests in T012/T013
  can be authored in parallel, then implementation proceeds through T014–T016.
- **User Story 2 (Phase 4)**: Depends on shared foundation and the service in
  T010; CLI parity test T017 can be authored in parallel with US1's API work once
  the service signature is stable. Final verification depends on T018.
- **Polish (Phase 5)**: Depends on both user stories.

### User Story Dependencies

- **US1 (P1)**: Can begin after Phase 2; no dependency on US2. Delivers the MVP.
- **US2 (P1)**: Uses the same foundation and service as US1; does not depend on
  HTTP-specific implementation, only the shared use-case signature.

### Within Each User Story

- Write acceptance tests before implementation and verify they fail for the
  missing behavior.
- Implement schemas before the HTTP route; the route delegates to the shared
  service.
- Implement the CLI adapter against the same service and response field mapping.
- Preserve exact field constraints by citing `data-model.md` in implementing tasks.

## Parallel Opportunities

- Setup T002, T003, and T004 edit separate Ruff configuration files; run in
  parallel after T001. T005 is the cross-file verification/finalization task.
- After T006, SQLite adapter work (T007/T008) and URL factory work (T009) can be
  split where edits do not overlap; T010 follows the port and active-list contract.
- US1 API tests (T012) and port conformance test (T013) can be authored in
  parallel. T014 and US2's test authoring (T017) can also proceed in parallel
  after the service result shape is fixed.
- US1 and US2 interface implementation can be done independently once T010/T011
  are stable, but both touch the composition files in T011; finish composition
  first to avoid file conflicts.

## Parallel Example: User Story 1

```text
Task: T012 — Add API behavior tests in tests/test_spec_002_summary.py
Task: T013 — Add port-conformance test in tests/test_spec_002_summary.py
```

These two test tasks describe distinct test concerns, but share one file; if one
worker is editing the file, sequence the edits or coordinate the merge.

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Setup and Foundational phases.
2. Implement and validate US1's HTTP endpoint, filtering, empty state, and SLA
   reference-time behavior.
3. Stop at the US1 checkpoint to validate the HTTP MVP independently.

### Incremental Delivery

1. Complete Setup + Foundation: ports, SQLite persistence/factory, and shared use
   case.
2. Deliver US1: HTTP summary; validate against its OpenAPI contract.
3. Deliver US2: CLI command and parity check.
4. Run full pytest and Ruff gates, then execute the quickstart checks.

## Notes

- Every task uses the required checkbox, sequential ID, optional `[P]`, required
  story label for story tasks, and an explicit file path.
- `src/incident_repository.py` is a Semana 1 teaching benchmark; the new production
  composition must use `SQLiteIncidentRepository` instead.
- The in-memory default requires a long-lived repository connection. Do not create
  a fresh in-memory repository per API request when data must persist across calls.
