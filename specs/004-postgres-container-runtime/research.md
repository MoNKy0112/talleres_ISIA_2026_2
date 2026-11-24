# Research: PostgreSQL Container Runtime

## Decision: Preserve one application port across both SQL engines

- **Decision**: Keep `IncidentRepositoryPort` as the only persistence contract.
  Both SQLite and PostgreSQL implement every operation, including
  `check_health() -> bool`; `IncidentService.check_health()` delegates through
  that port.
- **Rationale**: Constitution IV and ADR-004 require swappable persistence; the
  inbound adapters must not know which database is active.
- **Alternatives considered**: Add a PostgreSQL-specific port or let API/CLI
  probe the database directly; rejected because that splits behavior and crosses
  hexagonal boundaries.

## Decision: Select the repository only in the composition factory

- **Decision**: The factory accepts an explicit URL or reads `DATABASE_URL`,
  defaults to `sqlite:///:memory:`, routes `sqlite:///` to SQLite and
  `postgresql://`/`postgres://` to PostgreSQL, and rejects any other scheme with
  an explicit `ValueError`.
- **Rationale**: This keeps configuration outside business policy and supports
  local tests without a database daemon.
- **Alternatives considered**: Select the engine in the service or in each
  inbound adapter; rejected because it duplicates configuration and introduces
  outward infrastructure knowledge.

## Decision: Construct PostgreSQL repository lazily

- **Decision**: `PostgresIncidentRepository.__init__` stores connection URL and
  configuration only. Connections are opened on demand for repository
  operations, health checks, and schema initialization. A failure to connect
  during `check_health` returns `False`. Closing a repository that has not
  opened a connection is a safe no-op; connection ownership/lifetime is explicit
  and does not retain an unbounded connection per operation.
- **Rationale**: Factory tests can instantiate and structurally validate the
  adapter without a live PostgreSQL daemon. Runtime operations still fail or
  report unhealthy when the database is unavailable.
- **Alternatives considered**: Connect and initialize schema in the constructor;
  rejected because object construction would require a live server and cannot be
  tested independently.

## Decision: Initialize schema and SLA seeds idempotently

- **Decision**: PostgreSQL initialization creates `sla_policies`, `incidents`,
  indexes for component/status and duplicate-key/status, and SLA seed rows.
  Repeated initialization uses `CREATE TABLE IF NOT EXISTS`,
  `CREATE INDEX IF NOT EXISTS`, and `ON CONFLICT DO NOTHING` for seeds. SQLite
  retains equivalent idempotent initialization behavior. PostgreSQL schema and
  seed initialization runs transactionally so a failed setup does not leave a
  partial initialization.
- **Rationale**: Restarting containers and reconnecting must not duplicate
  schema objects or seed records.
- **Alternatives considered**: Require a separate migration service before API
  startup; not needed for this bounded baseline and would add another runtime
  component. A dedicated migration framework remains out of scope.

## Decision: Use explicit SQL and UTC ISO 8601 text timestamps

- **Decision**: Use psycopg with `dict_row` and `%s` parameters, without an ORM.
  Persist timestamps as canonical ISO 8601 strings normalized to UTC in `TEXT`
  columns, matching SQLite semantics.
- **Rationale**: This preserves explicit SQL and deterministic serialization,
  ordering, and SLA evaluation across both engines.
- **Alternatives considered**: ORM-managed portable models or engine-native
  timestamp columns; rejected because ADR-004 chooses explicit SQL and a common
  UTC text representation.

## Implementation risks and verification guidance

- Use `dict_row` so PostgreSQL row conversion can use the same named-column
  mapping as SQLite; keep nullable legacy fields and UTC parsing consistent.
- Bind all SQL values through `%s` parameters. Any variable-length `IN` clause
  may generate placeholder syntax from the count, but must pass each value as a
  parameter rather than interpolating data.
- Preserve the SQLite adapter's incident-ID conflict semantics; PostgreSQL must
  not silently replace an incident unless the port contract explicitly defines
  an update operation.
- Parity tests should cover repository CRUD, duplicate-ID behavior, active and
  duplicate queries, repeated schema/seeds, health success/failure, and
  timestamp round trips/order. PostgreSQL construction and `check_health`
  failure tests must not require a running database service.

## Decision: Make health a real repository connectivity check

- **Decision**: The repository contract's health operation executes `SELECT 1`.
  The service returns the boolean result; HTTP maps it to 200/503 and CLI emits
  the shared JSON result with exit 0/1.
- **Rationale**: A process-only liveness check cannot establish database
  readiness; a real query validates the configured persistence path.
- **Alternatives considered**: Report healthy based on a configured URL or
  successful object construction; rejected because neither proves connectivity.

## Decision: Use a two-service Compose runtime

- **Decision**: Compose runs the API image and PostgreSQL 16 Alpine separately.
  PostgreSQL owns a persistent volume and uses `pg_isready`; API depends on
  database health and uses `/health` as its own healthcheck.
- **Rationale**: This matches ADR-004's production topology while keeping
  PostgreSQL data independent of API container recreation.
- **Alternatives considered**: SQLite file inside the API container or an
  embedded database container; rejected because production requires a dedicated
  relational service with persistent lifecycle.

## Decision: Build a locked, minimal Python container image

- **Decision**: Build from `python:3.12-slim`, install a pinned `uv` binary, copy
  `pyproject.toml` and `uv.lock` before source for dependency-layer caching, and
  install locked runtime dependencies with `uv sync --locked --no-dev`. Keep
  `.venv`, tests, caches, local databases, Git metadata, and environment-secret
  files out of the build context while retaining runtime source and lock files.
- **Rationale**: A lock-enforced image avoids re-resolving dependency versions at
  build time and a minimal context reduces image size and accidental secret or
  developer-artifact inclusion.
- **Alternatives considered**: Unpinned installer/dependency resolution on each
  build; rejected because it can produce different runtime dependencies from the
  committed lock.

## Container operational caveats

- Compose should use the service DNS name `db` as the PostgreSQL host, bind the
  API to `0.0.0.0`, and align the published API port with its internal
  `/health` check.
- The PostgreSQL healthcheck uses `pg_isready` with an interval, timeout,
  retries, and startup grace period. `depends_on: condition: service_healthy`
  gates initial API startup, but it does not replace application error handling
  after a later database outage.
- Credentials are provided through environment variables; configuration must
  explain required values without committing secrets. A named volume persists
  data when API containers are recreated; removing that volume is a destructive
  operator action.
- Validate rendered Compose configuration, image build, startup health ordering,
  `/health`, and persistence across API recreation.
