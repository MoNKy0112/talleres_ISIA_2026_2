# Data Model: Incident Lifecycle and SLA

## Incident

Represents a persisted incoming report and its deterministic classification.

| Field | Type | Required | Rule |
|---|---|---:|---|
| `incident_id` | string | Yes | Caller value or generated `INC-<HEX8>`; unique. Never overwrite an existing incident. |
| `title` | string | Yes | Non-blank after whitespace trimming for validation; preserve submitted value. |
| `raw_text` | string | Yes on create | Non-blank after whitespace trimming; input to deterministic classification. Preserve for traceability. |
| `component` | string | Yes | Derived by the domain classifier. |
| `severity` | `P0 \| P1 \| P2 \| P3` | Yes | Derived by the domain classifier. |
| `recommended_team` | optional `RecommendedTeam` | No | Derived classification; `None` is permitted for legacy or incomplete records. |
| `duplicate_group_key` | optional string | No | Derived classification key; `None` is permitted for legacy records and cannot match an active duplicate query. |
| `status` | valid incident status | Yes | Defaults to `OPEN`; explicitly supplied values must be valid. |
| `created_at` | datetime | Yes | Defaults to current UTC instant; naive values mean UTC; aware values normalize to UTC. |
| `resolved_at` | optional datetime | No | Preserved for existing SLA semantics. |

`TriageResult` remains the authoritative complete classification result, including
`rationale` and `consistency_ratio`; those fields are returned in the create
response. The persistence model stores the classification fields needed for
future incident operations.

## Duplicate result

| Field | Type | Rule |
|---|---|---|
| `is_duplicate` | boolean | True iff at least one other matching active incident exists. |
| `duplicate_of` | list of strings | All matching IDs in `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`; exclude the new incident ID and `RESOLVED`. |

Matching is by `duplicate_group_key` only. It does not compare component
separately. Lookup is performed before saving the new incident.

## SLA evaluation

| Field | Type | Rule |
|---|---|---|
| `incident_id` | string | ID requested. |
| `component` | string | Component persisted on the incident. |
| `severity` | severity | Severity persisted on the incident. |
| `status` | incident status | Current persisted status. |
| `elapsed_minutes` | integer | Deterministic elapsed SLA minutes at normalized reference time. |
| `allowed_minutes` | integer | From the domain severity policy. |
| `remaining_minutes` | integer | `max(allowed_minutes - elapsed_minutes, 0)`. |
| `exceeded_minutes` | optional integer | Present when elapsed exceeds allowed. |
| `is_breached` | boolean | True only when elapsed minutes exceed allowed minutes. |
| `requires_escalation` | boolean | Domain policy; escalation starts at the 75% threshold and remains active after breach. |

If `reference_time` precedes `created_at`, evaluation fails validation. An
unknown ID raises an application not-found error.

## SQLite persistence

- `incidents` remains the persistence table; add `recommended_team` and ensure
  `duplicate_group_key` exists using an idempotent migration.
- Add `idx_incidents_dup_key` on `(duplicate_group_key, status)`.
- Preserve existing rows and normalize persisted naive timestamp values as UTC
  when read.
- `raw_text` persistence is needed for the feature entity; existing records can
  receive `NULL` during migration while newly created records store the text.
