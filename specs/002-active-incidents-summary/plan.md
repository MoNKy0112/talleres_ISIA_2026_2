# Implementation Plan: Active Incident Summary

**Branch**: `002-active-incidents-summary` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-active-incidents-summary/spec.md`

## Summary

Add the active-incidents summary to the shared application service and expose it
through FastAPI and Typer. Keep incident/SLA decisions in the domain, persistence
behind `IncidentRepositoryPort`, and SQLite selected by the outbound factory using
`DATABASE_URL`. Refactor the Semana 1 repository's SQL into a filtered
`INNER JOIN` against `sla_policies`, backed by `(component, status)`, while
delegating SLA evaluation to `evaluate_sla_status`.

## Technical Context

**Language/Version**: Python >=3.10

**Primary Dependencies**: FastAPI, Pydantic v2, Typer, pytest, Ruff; SQLite3 from
the Python standard library

**Storage**: SQLite; factory default `sqlite:///:memory:`, configurable via
`DATABASE_URL`

**Testing**: pytest acceptance/integration tests; Ruff lint and import-boundary gate

**Target Platform**: Python runtime supported by the repository and `uv`

**Project Type**: Hexagonal Python web service and CLI

**Performance Goals**: Avoid a full-table Python scan and per-incident policy
queries; filter active incidents in SQL using the composite index and a single
joined query. No latency SLO is defined for this milestone.

**Constraints**: Keep domain deterministic and infrastructure-free; no ORM;
REST and CLI delegate to the same use case; preserve default in-memory SQLite
behavior; return empty summaries as successful results.

**Scale/Scope**: The inherited teaching benchmark seeds 10,000 rows. This milestone
does not add pagination, connection pooling, or a production throughput target.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / gate | Plan compliance |
|---|---|
| I. Deterministic Domain Authority | Application calls `evaluate_sla_status`; no duplicated SLA thresholds or policy in adapters or SQL. |
| II. Strict Hexagonal Boundaries | `IncidentRepositoryPort` lives in application; SQLite implements it in outbound; inbound gets it through factory; dependencies point inward. |
| III. Shared Use Cases | FastAPI and Typer call `IncidentService.get_active_incidents_summary` and serialize the same result. |
| IV. Replaceable Persistence | Factory selects only persistence from `DATABASE_URL`; SQLite stdlib remains the default; no new engine or ORM. |
| V. Verifiable Quality | Add BDD pytest coverage for HTTP, CLI parity, filtering, empty state, SLA reference-time behavior, and structural port conformance. |
| Quality gates | Configure Ruff TID rules and layer-specific bans; verify with `uv run ruff check src/` and `uv run pytest -v`. |

**Gate result**: PASS. The requested repository abstraction, SQLite adapter, factory,
and inbound adapters are constitutional requirements, not exceptions. No ADR or
complexity exception is needed. Performance is addressed by query shape and index;
a numeric latency target remains unspecified and is not assumed.

## Project Structure

### Documentation (this feature)

```text
specs/002-active-incidents-summary/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── active-incidents-summary.openapi.yaml
```

### Source Code (repository root)

```text
src/
├── application/
│   ├── ports.py
│   └── services.py
├── adapters/
│   ├── inbound/
│   │   ├── cli.py
│   │   └── api/
│   │       ├── app.py
│   │       └── schemas.py
│   └── outbound/
│       ├── factory.py
│       └── sqlite_repository.py
├── domain/
│   ├── models.py
│   └── sla_calculator.py
└── incident_repository.py     # Semana 1 teaching benchmark; migration boundary

tests/
├── test_spec_001_triage.py
└── test_spec_002_summary.py

pyproject.toml
src/domain/ruff.toml
src/application/ruff.toml
src/adapters/inbound/ruff.toml
```

**Structure Decision**: Extend the existing single Python project and its
hexagonal `domain / application / adapters` layout. Retain the teaching benchmark
module as a benchmark/reference unless implementation confirms it can be removed
without losing its documented standalone purpose; production composition must use
the new outbound adapter.

## Complexity Tracking

No constitution violations or additional projects are introduced.
