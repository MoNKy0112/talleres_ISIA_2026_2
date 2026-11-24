# Implementation Plan: PostgreSQL Container Runtime

**Branch**: `004-postgres-container-runtime` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-postgres-container-runtime/spec.md`

## Summary

Hito 004 incorpora chequeo real de salud, selección de persistencia SQLite o
PostgreSQL detrás de `IncidentRepositoryPort`, y runtime de dos contenedores. API
y CLI delegan el estado de conectividad a `IncidentService.check_health()`.
`create_repository` selecciona el motor por `DATABASE_URL`. El adaptador PostgreSQL
usa `psycopg` sin ORM, conexiones lazy, SQL parametrizado y esquema/seeds
idempotentes. Docker Compose inicia PostgreSQL y luego la API según healthchecks.

## Technical Context

**Language/Version**: Python >=3.10; imagen de runtime `python:3.12-slim`  
**Primary Dependencies**: FastAPI, Pydantic v2, Typer, `psycopg[binary]`; `uv`
para sincronización reproducible  
**Storage**: SQLite3 por defecto en desarrollo/pruebas; PostgreSQL 16 en
contenedores/producción  
**Testing**: pytest, FastAPI `TestClient`, Typer `CliRunner`, Ruff; pruebas de
paridad de contrato aisladas por motor  
**Target Platform**: Runtime Python en contenedores Docker Compose; CLI local  
**Project Type**: Servicio backend con API HTTP, CLI y dos adaptadores SQL  
**Performance Goals**: No se define SLO cuantitativo nuevo; el healthcheck debe
ejecutar una consulta breve de conectividad real  
**Constraints**: Selección solo en `src/adapters/outbound/factory.py`; dominio,
aplicación e inbound no importan drivers; no ORM; timestamps UTC ISO 8601 en
`TEXT`; PostgreSQL se instancia sin abrir conexiones hasta una operación  
**Scale/Scope**: Dos motores con contrato idéntico, dos servicios Compose (`api`,
`db`), sin migración a otro proveedor ni cambios a los casos de uso existentes

**Repository contract**: `PostgresIncidentRepository` implements the exact
`IncidentRepositoryPort` signatures: `save_incident(incident: Incident) -> None`,
`get_incident(incident_id: str) -> Incident | None`,
`incident_id_exists(incident_id: str) -> bool`,
`find_open_duplicates(duplicate_group_key: str,
open_statuses: frozenset[IncidentStatus], exclude_incident_id: str) ->
list[Incident]`, `list_active_incidents(component_filter: str | None = None) ->
list[Incident]`, and `check_health() -> bool`. The adapter treats status policy
as caller-owned: `find_open_duplicates` filters by exactly the supplied
`open_statuses`; it MUST NOT define its own active/open status list in SQL.
`list_active_incidents` follows the existing port's documented OPEN and
IN_PROGRESS behavior.

## Constitution Check

| Principio | Gate | Aplicación en H004 |
|---|---|---|
| I. Deterministic Domain Authority | PASS | No se trasladan políticas de SLA, clasificación o dominio a persistencia, health route ni CLI. |
| II. Strict Hexagonal Boundaries | PASS | `IncidentRepositoryPort` permanece en aplicación; drivers y SQL solo viven en outbound. Factory es composición, no lógica de negocio. |
| III. Shared Use Cases, Multiple Inbound Adapters | PASS | API y CLI llaman `IncidentService.check_health()` y traducen el mismo resultado. |
| IV. Replaceable Persistence | PASS | SQLite/PostgreSQL implementan el mismo puerto; `DATABASE_URL` se resuelve solo en factory; `check_health` verifica conectividad real. |
| V. Verifiable Quality | PASS | Pruebas BDD con TestClient/CliRunner, contrato de ambos repositorios, verificación estática de límites y pytest/Ruff. |
| Tecnología y despliegue | PASS | Python/uv, FastAPI, Typer, psycopg sin ORM, Docker Compose y PostgreSQL `16-alpine` conforme a ADR-004. |

La inicialización lazy no cambia el contrato del puerto: evita requerir un
servidor PostgreSQL para instanciar o verificar la factory en pruebas. El primer
uso de persistencia establece el esquema de manera idempotente. El healthcheck
ejecuta una consulta real y reporta degradación si no puede conectar.

## Project Structure

### Documentation (this feature)

```text
specs/004-postgres-container-runtime/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── health-openapi.yaml
    ├── cli.md
    └── container-runtime.md
```

### Source Code (repository root)

```text
src/
├── application/
│   ├── ports.py                 # runtime-checkable IncidentRepositoryPort
│   └── services.py              # check_health use case delegation
└── adapters/
    ├── outbound/
    │   ├── factory.py           # DATABASE_URL selection
    │   ├── sqlite_repository.py # SQLite contract and health query
    │   └── postgres_repository.py
    └── inbound/
        ├── api/
        │   ├── app.py           # GET /health
        │   └── schemas.py       # HealthResponse
        └── cli.py               # health command

Dockerfile
.dockerignore
docker-compose.yml
tests/
└── test_spec_004_runtime_health.py
```

The root `pyproject.toml` contains `psycopg[binary]`; the existing hierarchical
Ruff configurations at `src/domain/`, `src/application/`, and
`src/adapters/inbound/` explicitly ban both `psycopg` and `sqlite3` via
`TID251` (`banned-api`). Verify these boundaries with `uv run ruff check src/`;
database drivers are confined to `src/adapters/outbound/`.

**Structure Decision**: Preserve the established hexagonal project structure.
Only outbound adapters may import database driver code (`psycopg` and `sqlite3`);
the factory selects adapters without importing drivers. Ruff explicitly bans both
drivers in domain, application, and inbound. The
inbound health adapters consume the shared application use case; container
artifacts remain at repository root.

`IncidentService` and the persistence adapters do not redefine duplicate-state
policy. The service passes `OPEN_DUPLICATE_STATUSES` to
`find_open_duplicates`; the adapter applies the exact supplied set as query
parameters rather than a SQL-owned status list.

## Phase 0: Research

Findings and decisions are recorded in [research.md](research.md). Stack and
contracts are specified by the accepted ADR and feature spec; no unresolved
technical clarification blocks Phase 1.

## Phase 1: Design

- Entity/port data and persistence invariants: [data-model.md](data-model.md).
- HTTP, CLI, and container contracts: [contracts/](contracts/).
- Runnable local, integration, and container validation: [quickstart.md](quickstart.md).

## Post-Design Constitution Check

| Gate | Resultado |
|---|---|
| Driver imports isolated to outbound | PASS only when all three restricted-layer Ruff configs ban both `psycopg` and `sqlite3` via TID251 and `uv run ruff check src/` passes |
| Factory alone selects database from `DATABASE_URL` | PASS |
| Both repositories implement identical port and real health check | PASS |
| API and CLI share `IncidentService.check_health()` | PASS |
| No ORM; timestamps normalized UTC as `TEXT` | PASS |
| Compose health ordering and persistent PostgreSQL volume specified | PASS |
| BDD tests, pytest, Ruff, and runtime configuration checks specified | PASS |
| Duplicate status policy remains caller-owned | PASS; `find_open_duplicates` uses the exact `open_statuses` argument and has tests with different supplied sets |

No constitutional exception or new ADR is required.

## Complexity Tracking

No violations of constitutional principles are proposed.
