# Data Model: PostgreSQL Container Runtime

## Incident persistence

The existing `Incident` entity and application use cases do not change. Each
repository must persist and reconstruct the same fields:

| Field | Persistence representation | Invariant |
|---|---|---|
| `incident_id` | Text primary key | Stable unique identifier; conflict behavior follows `save_incident` contract. |
| `title`, `raw_text` | Text | Preserve original supplied content; legacy `raw_text` may be null. |
| `component`, `severity`, `status` | Text | Preserve domain values without database-specific enum types. |
| `recommended_team`, `duplicate_group_key` | Nullable text | Preserve optional values and nullability. |
| `created_at`, `resolved_at` | Nullable/non-null text as defined by entity | ISO 8601 normalized to UTC; `created_at` is required; `resolved_at` is optional. |

SQLite and PostgreSQL must map these values to the same domain object. Timestamp
write paths normalize naive values as UTC and convert timezone-aware values to
UTC. Read paths parse ISO 8601 and return UTC-aware datetimes.

## SLA policies

`sla_policies` stores one row per severity with the domain's resolution limit
and continuous/working-hours behavior. The domain `SLA_POLICY_TABLE` remains
authoritative; persisted seed rows support the existing repository queries.
Initialization must not create duplicate severity rows.

## Repository health

`IncidentRepositoryPort.check_health() -> bool` denotes whether an actual
connectivity query succeeds. `IncidentService.check_health()` exposes that
transport-neutral result. Inbound representations are:

| Repository result | API response | CLI result |
|---|---|---|
| Connected | HTTP 200, `status=ok`, `database=connected` | JSON with same values, exit 0 |
| Unavailable or query exception | HTTP 503, `status=error`, `database=unavailable` | JSON with same values, exit 1 |

The response contains no database URL, credentials, or driver exception text.

## Database selection

The factory maps URL schemes to structural adapters:

| URL/configuration | Selected adapter |
|---|---|
| `postgresql://...` or `postgres://...` | PostgreSQL |
| `sqlite:///...` | SQLite |
| Missing configuration | SQLite `:memory:` |
| Any unsupported scheme | Explicit configuration error |

## Idempotent schema

Both engines initialize equivalent `sla_policies` and `incidents` tables, the
component/status and duplicate-key/status indexes, and severity policy seeds.
Repeated initialization preserves existing data and does not duplicate tables,
indexes, or seed rows. PostgreSQL connection creation is lazy; schema setup occurs
only when a persistent operation needs it, not when constructing the adapter.
