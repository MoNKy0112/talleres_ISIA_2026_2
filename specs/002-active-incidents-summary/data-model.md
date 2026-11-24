# Data Model: Active Incident Summary

## Incident (existing domain entity)

Represents a persisted incident selected for the summary.

| Field | Type | Constraints / meaning |
|---|---|---|
| `incident_id` | string | Stable unique identifier; SQLite primary key. |
| `title` | string | Business-facing incident title. |
| `component` | string | Affected component; exact-match filter value. |
| `duplicate_group_key` | string | Required persisted key identifying component and symptom category for duplicate lookup. |
| `severity` | `P0 \| P1 \| P2 \| P3` | Selects the domain SLA rule. |
| `status` | `OPEN \| IN_PROGRESS \| ESCALATION_REQUIRED \| RESOLVED` | Summary includes only `OPEN` and `IN_PROGRESS`. |
| `created_at` | datetime | Start of SLA evaluation; normalized to UTC. Naive legacy values are interpreted as UTC. |
| `resolved_at` | optional datetime | Existing lifecycle timestamp; normalized to UTC. Naive legacy values are interpreted as UTC; active-list selection excludes resolved status. |

Persistence retains the existing `incidents` and `sla_policies` tables. The active
query filters to active statuses and, if supplied, one component. It joins the
severity policy row in one query and is supported by `(component, status)`.
`sla_policies` supplies persistence-level policy metadata only; the domain
calculator remains authoritative for evaluation.

## SLA Evaluation (existing domain value)

Produced by `evaluate_sla_status(incident, reference_time)`.

| Field | Meaning |
|---|---|
| `elapsed_minutes` | Minutes consumed under the severity's 24/7 or weekday business-hours policy. |
| `is_breached` | Elapsed minutes exceed allowed resolution minutes. |
| `requires_escalation` | Preventive escalation threshold reached or breach active. |

All incidents in one summary use the same reference instant. The function also
provides allowed and remaining minutes; the inbound summary contract exposes only
the requested summary fields.

## Active Incident Item (summary projection)

One item per matching active incident:

- `incident_id`: incident identity, retained to distinguish records in clients.
- `title`, `component`, `severity`, `status`: incident business attributes.
- `elapsed_minutes`: SLA-consuming integer minutes, not wall-clock age.
- `requires_escalation`: boolean from domain SLA evaluation.

## Active Incidents Summary (application result / response)

| Field | Type | Invariant |
|---|---|---|
| `total_active` | integer | Equals `len(incidents)`. |
| `breached_count` | integer | Number of returned items whose SLA evaluation is breached. |
| `incidents` | list of Active Incident Item | Contains only active incidents matching the optional component. |

If there are no matches, return `total_active=0`, `breached_count=0`, and an empty
`incidents` list. HTTP returns this as `200 OK` JSON; CLI emits the equivalent JSON
object.

## Port: IncidentRepositoryPort

Application-owned structural abstraction. Required operations:

- `save_incident(incident)`: persist a domain incident.
- `get_incident(incident_id)`: retrieve one incident by stable identifier.
- `find_open_duplicates(component, duplicate_group_key)`: return all existing
  incidents whose status is `OPEN` and whose component and persisted
  `duplicate_group_key` exactly match. This operation is read-only; it does not
  suppress, reject, or create an incident. Records without a duplicate key do not
  match.
- `list_active_incidents(component_filter=None)`: list active domain incidents,
  optionally constrained by exact component.
- `check_health()`: report repository availability.

Duplicate lookup is a query only. Any decision to act on matches belongs to a
separate incident-registration use case, not this summary feature. Transport
models must not enter the port.
