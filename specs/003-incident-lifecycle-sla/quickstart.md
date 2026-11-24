# Quickstart: Validate Hito 003

Run all commands from the repository root. Dependencies are managed with `uv`.

## Prerequisites

```powershell
uv sync
```

## Automated acceptance and architecture checks

```powershell
uv run pytest -v tests/test_spec_003_lifecycle_sla.py
uv run ruff check src/
```

Expected: the five required BDD behaviors pass through `TestClient` and
`CliRunner`, including HTTP/CLI parity; Ruff reports no lint or import-boundary
violations.

## HTTP smoke checks

Start the service:

```powershell
uv run uvicorn src.adapters.inbound.api.app:app --reload
```

Register a report:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/incidents `
  -ContentType 'application/json' `
  -Body '{"title":"Falla de pagos","raw_text":"El gateway de pagos devuelve 502 al completar una transacción"}'
```

Expected: HTTP 201, generated or supplied ID, complete classification, and
`is_duplicate`/`duplicate_of`.

Query an incident's SLA, substituting the returned identifier:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/incidents/INC-ABCDEF12/sla?reference_time=2026-11-09T09:00:00'
```

Expected: HTTP 200 and an SLA evaluation. An unknown ID returns 404; a valid
reference earlier than receipt returns 422.

## CLI smoke checks

Use a file-backed SQLite database so `create` and `sla`, which run as separate
processes, share persisted state:

```powershell
$env:DATABASE_URL = "sqlite:///h003-quickstart.db"
uv run python -m src.adapters.inbound.cli create --title "Falla de pagos" --raw-text "El gateway de pagos devuelve 502 al completar una transacción"
# Use the incident_id returned by create in the following command.
uv run python -m src.adapters.inbound.cli sla INC-<HEX8> --reference-time 2026-11-09T09:00:00
```

Expected: successful commands emit JSON and exit 0; invalid registration,
unknown IDs, and invalid temporal ordering emit an error and exit 1.

## Fixed P2 business-hours example

Create a P2 incident with `created_at` `2026-11-06T17:00:00` and evaluate at
`2026-11-09T09:00:00`. Expected values: `elapsed_minutes=120`,
`allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false`, and
`requires_escalation=false`.

For complete request/response fields see [HTTP contract](contracts/http-openapi.yaml)
and [CLI contract](contracts/cli.md); for persisted fields see [data model](data-model.md).
