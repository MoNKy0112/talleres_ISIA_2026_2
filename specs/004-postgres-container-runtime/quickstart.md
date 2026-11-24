# Quickstart: Validate Hito 004

Run commands from the repository root. The unit and acceptance checks use SQLite
or test doubles and do not require a PostgreSQL daemon.

## Setup and automated checks

```powershell
uv sync
uv run pytest -v tests/test_spec_004_runtime_health.py
uv run ruff check src tests
```

Expected: API/CLI health behavior, database selection, port conformance, and
container configuration checks pass; Ruff enforces the restricted-layer import
rules, including `psycopg` bans.

## Local health checks

With default in-memory SQLite:

```powershell
uv run uvicorn src.adapters.inbound.api.app:app --reload
```

Request health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
uv run python -m src.adapters.inbound.cli health
```

Expected for a working repository: `{"status":"ok","database":"connected"}`;
HTTP status 200 and CLI exit 0.

## Container runtime

Provide database credentials in the shell environment (never commit secrets),
then start the services:

```powershell
$env:POSTGRES_USER = "incidentops"
$env:POSTGRES_PASSWORD = "replace-with-local-secret"
$env:POSTGRES_DB = "incidentops"
docker compose config
docker compose up --build
```

Expected: rendered configuration has no missing substitutions; `db` becomes
healthy through `pg_isready`; Compose then starts `api`. Verify
`http://localhost:8000/health` returns the connected response. Recreate only the
API service and verify database data remains on the named volume. Do not remove
the database volume when testing API recreation.

See [HTTP](contracts/health-openapi.yaml), [CLI](contracts/cli.md), and
[container runtime](contracts/container-runtime.md) contracts for exact behavior.
