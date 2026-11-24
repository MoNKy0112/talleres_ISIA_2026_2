# Research: Incident Lifecycle and SLA

## Decision: Reuse the existing deterministic classifier

- **Decision**: `create_incident` calls the domain classifier with the supplied
  or generated incident ID and `raw_text`, then builds the incident from that
  classification and the request title.
- **Rationale**: `src/domain/triage_rules.py` is the authoritative source of
  component, severity, recommended team, rationale, and duplicate key. Reuse
  preserves deterministic behavior and avoids adapter-specific classification.
- **Alternatives considered**: Reimplement classification in the service or
  inbound adapters; rejected because it duplicates domain policy.

## Decision: Generate an eight-hex-character identifier with collision checking

- **Decision**: Generate `INC-` plus eight uppercase hexadecimal characters when
  `incident_id` is omitted. Check for collision through the repository port and
  retry a bounded number of times; a caller-supplied duplicate ID is a validation
  conflict rather than an overwrite.
- **Rationale**: This honors the public format and avoids relying on SQLite
  `INSERT OR REPLACE`, which could silently replace an existing incident.
- **Alternatives considered**: UUID of a different public format or blind
  insertion; rejected because they violate the required ID format or risk data
  loss.

## Decision: Detect duplicates before saving and retain every valid report

- **Decision**: Query the repository using the classified `duplicate_group_key`,
  filter active states `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, exclude the
  new ID, then persist regardless of matches. Return all matching IDs.
- **Rationale**: Duplicate detection is informational, and the required result
  must never prevent traceability. Repository lookup occurs before insertion so
  the new record cannot match itself.
- **Alternatives considered**: Reject duplicates or query after save; rejected
  because rejection violates requirements and post-save lookup risks self-match.

## Decision: Normalize timestamps to UTC at the domain boundary

- **Decision**: A shared domain normalization interprets naive ISO-derived
  datetimes as UTC and converts aware datetimes with `astimezone(UTC)`. SLA
  comparisons and business-hour calculations use normalized values.
- **Rationale**: This implements the accepted clarification and avoids errors
  when equivalent instants have different offsets.
- **Alternatives considered**: Reject naive timestamps or require identical
  timezone objects; rejected because the accepted clarification explicitly
  permits naive-as-UTC and aware-to-UTC normalization.

## Decision: Keep persistence replaceable and migrate SQLite in place

- **Decision**: Extend `IncidentRepositoryPort` for create/get/duplicate lookup;
  implement SQL and schema/index updates only in
  `SQLiteIncidentRepository`. Detect existing columns before adding columns.
- **Rationale**: Matches Constitution principles II and IV and supports existing
  SQLite databases without requiring a new engine or ORM.
- **Alternatives considered**: Access SQLite from service/API/CLI or replace the
  database engine; rejected by architecture and technology constraints.

## Decision: Map application errors at each inbound boundary

- **Decision**: Application exposes transport-neutral validation and not-found
  errors. FastAPI maps them to 422/404; Typer prints a concise error and exits 1.
- **Rationale**: The service remains framework-independent while both adapters
  preserve consistent business behavior.
- **Alternatives considered**: Raise `HTTPException` from application or make
  services depend on Typer; rejected as outward dependencies.

## Integration note: Stored request text

- **Decision**: Preserve `raw_text` for registered incidents because the feature
  specification defines it as incident data; add a nullable-compatible SQLite
  migration for existing rows if persisted as a new column. Keep the requested
  `recommended_team` and duplicate-key columns and index. If implementation must
  restrict schema changes to only the two named columns, resolve this discrepancy
  before coding because it conflicts with the specification's stored entity.
- **Rationale**: The current `Incident` lacks `raw_text`, while creation requires
  it and the spec describes the original report as part of the incident.
- **Alternatives considered**: Discard the submitted report after classification;
  rejected because it loses incident traceability and conflicts with the spec.
