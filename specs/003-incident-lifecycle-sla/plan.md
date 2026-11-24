# Implementation Plan: Incident Lifecycle and SLA

**Branch**: `003-incident-lifecycle-sla` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-incident-lifecycle-sla/spec.md`

## Summary

Hito 003 agrega creación persistente de incidentes, clasificación determinista,
detección no bloqueante de duplicados activos y auditoría SLA por HTTP y CLI.
`IncidentService` coordinará las reglas del dominio y el puerto de repositorio;
FastAPI y Typer solo traducirán entradas, serializarán DTOs y mapearán errores.
SQLite implementará la búsqueda por clave y estados activos. Las fechas naive se
interpretan como UTC y las fechas aware se normalizan a UTC antes de evaluar SLA.

## Technical Context

**Language/Version**: Python >=3.10  
**Primary Dependencies**: FastAPI, Pydantic v2, Typer; biblioteca estándar para
SQLite y fechas  
**Storage**: SQLite3, mediante `IncidentRepositoryPort`  
**Testing**: pytest, FastAPI `TestClient`, Typer `CliRunner`, Ruff  
**Target Platform**: Servicio HTTP local/desplegable y CLI Python  
**Project Type**: Servicio backend con adaptadores HTTP y CLI  
**Performance Goals**: Sin SLO nuevo en la especificación; conservar consultas
indexadas y cálculo SLA determinista O(D) para horario hábil  
**Constraints**: Dominio sin frameworks ni drivers; aplicación depende solo de
dominio y puertos; adaptadores primarios comparten los mismos casos de uso;
SQLite sin ORM  
**Scale/Scope**: Una entidad de incidente, persistencia SQLite y dos interfaces
primarias; no se añade flujo de transición de estados

## Constitution Check

| Principio | Gate | Aplicación en H003 |
|---|---|---|
| I. Deterministic Domain Authority | PASS | Clasificación, política canónica de estados que califican como duplicados abiertos, normalización temporal y cálculo SLA se mantienen en dominio/aplicación; los adaptadores no redefinen políticas. |
| II. Strict Hexagonal Boundaries | PASS | `IncidentService` usa `IncidentRepositoryPort`; SQLite implementa el puerto; entradas dependen de servicio y factory, nunca del repositorio concreto. |
| III. Shared Use Cases, Multiple Inbound Adapters | PASS | API y CLI llaman exactamente `create_incident` y `evaluate_incident_sla` del mismo servicio. |
| IV. Replaceable Persistence | PASS | SQLite permanece tras el puerto; campos e índices son detalles del adaptador. |
| V. Verifiable Quality | PASS | Cobertura pytest de escenarios BDD por `TestClient`/`CliRunner`, paridad de interfaces y `uv run ruff check src/`. |
| Tecnología y calidad | PASS | Python >=3.10, FastAPI/Pydantic v2, Typer, SQLite3, `uv run pytest -v` y Ruff según Constitución. |

No se identifica una excepción constitucional. La migración de esquema conserva
la base SQLite y no introduce ORM ni nueva dependencia.

## Project Structure

### Documentation (this feature)

```text
specs/003-incident-lifecycle-sla/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── http-openapi.yaml
    └── cli.md
```

### Source Code (repository root)

```text
src/
├── domain/
│   ├── models.py                 # Incident y valores opcionales de clasificación
│   └── sla_calculator.py         # normalización temporal y reglas SLA
├── application/
│   ├── ports.py                  # operaciones de persistencia requeridas
│   └── services.py               # create_incident / evaluate_incident_sla
└── adapters/
    ├── outbound/
    │   └── sqlite_repository.py  # esquema, migración e implementación del puerto
    └── inbound/
        ├── api/
        │   ├── app.py
        │   └── schemas.py        # DTOs de creación y evaluación SLA
        └── cli.py                # comandos create y sla

tests/
└── test_spec_003_lifecycle_sla.py
```

**Structure Decision**: Se conserva el proyecto Python hexagonal existente.
Ningún módulo nuevo fuera de sus capas; DTOs pertenecen al adaptador HTTP y las
respuestas CLI se serializan desde resultados compartidos de aplicación.

## Phase 0: Research

Decisiones y patrones verificados contra los módulos actuales, ADR-002,
ADR-003, la Constitución y `hexagonal-architecture`; detalle en
[research.md](research.md). No quedan decisiones técnicas bloqueantes.

## Phase 1: Design

- Entidades y validaciones: [data-model.md](data-model.md).
- Contratos API y CLI: [contracts/](contracts/).
- Verificación ejecutable: [quickstart.md](quickstart.md).

## Post-Design Constitution Check

| Gate | Resultado |
|---|---|
| Dominio independiente y determinista | PASS |
| Casos de uso dependen solo de puerto | PASS |
| API/CLI delegan los mismos casos de uso | PASS |
| SQLite aislado en adaptador secundario | PASS |
| BDD, paridad, pytest y Ruff contemplados | PASS |

Los contratos describen transporte, pero no trasladan políticas de dominio a los
adaptadores. `src/domain/models.py` será la autoridad para los estados que
califican como duplicados abiertos, mediante una constante o regla de dominio
basada en `IncidentStatus` que excluye `RESOLVED`. `IncidentService.create_incident`
obtendrá esa política del dominio y la pasará explícitamente al puerto
`IncidentRepositoryPort.find_open_duplicates(duplicate_group_key, open_statuses,
exclude_incident_id)`. `SQLiteIncidentRepository` solo ejecutará la consulta
parametrizada con esos valores; no mantendrá una lista de estados activa propia ni
otra regla de negocio hardcodeada.

## Complexity Tracking

No hay violaciones constitucionales que requieran excepción o ADR.
