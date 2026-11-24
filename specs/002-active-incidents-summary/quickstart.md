# Quickstart: Validate Active Incident Summary

Run commands from the repository root. Python dependencies are managed by `uv`.

## Setup

```powershell
uv sync
```

Use SQLite in-memory storage by default, or set `DATABASE_URL` to a supported
SQLite URL. Keep the same application/repository composition alive while seeding
and querying an in-memory database.

## Automated validation

```powershell
uv run pytest -v tests/test_spec_002_summary.py
uv run ruff check src/
```

The acceptance suite should prove:

1. Global summary returns only `OPEN` and `IN_PROGRESS` incidents.
2. Component filtering constrains items and both aggregate counts.
3. No matches return a successful empty summary.
4. An explicit reference time produces deterministic SLA minutes, breach count,
   and escalation result.
5. HTTP and CLI return equivalent business data for the same inputs.
6. SQLite implements all operations declared by `IncidentRepositoryPort`.

## Manual HTTP check

Start the service:

```powershell
$env:DATABASE_URL = "sqlite:///:memory:"
uv run uvicorn src.adapters.inbound.api.app:app --reload
```

Query the summary (with an optional component and explicit RFC 3339 reference
time in UTC):

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/incidents/summary?component=payments-gateway&reference_time=2026-11-20T12%3A00%3A00Z"
```

Expected response shape:

```json
{
  "total_active": 0,
  "breached_count": 0,
  "incidents": []
}
```

The result is valid even when no active incidents are seeded. For non-empty
behavior, use the test fixtures in `tests/test_spec_002_summary.py`; do not rely
on the standalone Semana 1 benchmark as an API seeding mechanism.

## Manual CLI check

```powershell
uv run python -m src.adapters.inbound.cli summary --component payments-gateway --reference-time 2026-11-20T12:00:00Z
```

The CLI should emit JSON with the same summary shape and values as HTTP. Omit
either option to exercise its default behavior.
