# Feature Specification: Active Incident Summary

**Feature Branch**: `002-active-incidents-summary`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "Consultar el resumen de incidentes activos (`OPEN` e `IN_PROGRESS`) desde la web y el terminal, incluyendo el total activo, los incumplimientos de SLA y el detalle de cada incidente (título, componente, severidad, estado, minutos transcurridos y si requiere escalamiento), con filtro opcional por componente y un instante de referencia opcional."

## Clarifications

### Session 2026-11-23

- Q: Para los minutos de cada incidente, ¿debe mostrarse el tiempo corrido desde su creación o solo el tiempo que consume el SLA, que excluye noches y fines de semana para P2/P3? → A: Mostrar los minutos consumidos según el SLA; P2/P3 no acumulan minutos fuera del horario laboral.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review the global active incident summary (Priority: P1)

As a support operator, I want to review all active incidents and their SLA risk
from the web interface so that I can assess the current operational workload.

**Why this priority**: A reliable global summary is the primary way to understand
active work and identify SLA risk.

**Independent Test**: With known active and inactive incidents, an operator can
request the global summary and verify the included incidents, totals, breach count,
and details.

**Acceptance Scenarios**:

1. **Given** incidents in `OPEN`, `IN_PROGRESS`, `RESOLVED`, and
   `ESCALATION_REQUIRED` states, **When** an operator requests the global summary
   from the web interface, **Then** only `OPEN` and `IN_PROGRESS` incidents are
   included, with the active total, SLA breach count, and each incident's title,
   component, severity, status, SLA-consuming minutes, and escalation requirement.
2. **Given** active incidents across multiple components, **When** an operator
   requests a summary for one component, **Then** only matching incidents are
   included and the total and breach count describe that filtered set.

---

### User Story 2 - Review the same summary from the terminal (Priority: P1)

As a support operator, I want to review the active incident summary from the
terminal so that I can perform the same operational check without the web
interface.

**Why this priority**: Terminal access is an explicit operational channel and must
offer the same information as the web interface.

**Independent Test**: Given the same incident set, component, and reference time,
compare the terminal summary with the web summary for equivalent counts and
incident details.

**Acceptance Scenarios**:

3. **Given** there are no active incidents, or no active incidents match the
   selected component, **When** an operator requests the summary from the web
   interface, **Then** the request succeeds with a valid summary containing
   `total_active=0`, `breached_count=0`, and an empty incident list.
4. **Given** the same incidents, component filter, and reference time are used,
   **When** an operator requests the summary from the terminal, **Then** the
   returned summary contains equivalent totals and incident details to the web
   summary.

### Edge Cases

- No active incidents exist: return zero totals and an empty incident list.
- The component filter matches no active incident: return the same empty summary,
  not an error.
- Only inactive incidents exist: do not include them in the active total or list.
- An active incident is exactly at its SLA limit: it is not counted as breached;
  escalation follows the established 75% threshold.
- A summary is generated near an SLA boundary: counts and details use one
  consistent reference instant.
- If `reference_time` is omitted, evaluate the summary at the current instant.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web interface MUST provide
  `GET /api/v1/incidents/summary` with optional `component` and `reference_time`
  query parameters.
- **FR-002**: The terminal MUST provide the `summary [--component ...]
  [--reference-time ...]` subcommand.
- **FR-003**: Both interfaces MUST report the summary fields `total_active`,
  `breached_count`, and `incidents`.
- **FR-004**: The system MUST treat only `OPEN` and `IN_PROGRESS` incidents as
  active for this summary; other statuses MUST NOT be included.
- **FR-005**: Each incident detail MUST include its title, component, severity,
  status, SLA-consuming `elapsed_minutes`, and `requires_escalation` value.
- **FR-006**: `total_active` MUST equal the number of listed incidents, and
  `breached_count` MUST count included incidents whose elapsed SLA time exceeds the
  applicable resolution limit.
- **FR-007**: An omitted `component` MUST include incidents from all components.
  A supplied component MUST limit both the incident list and its aggregate counts
  to matching incidents.
- **FR-008**: If there are no active incidents in scope, the web interface MUST
  return `200 OK` with a valid JSON summary containing
  `total_active=0`, `breached_count=0`, and `incidents=[]`. The terminal MUST
  return the equivalent empty summary.
- **FR-009**: An omitted `reference_time` MUST use the current instant. A supplied
  reference time MUST be used consistently for all SLA evaluations in that summary.
- **FR-010**: For equivalent inputs, web and terminal summaries MUST contain
  equivalent business data.
- **FR-011**: Reading a summary MUST NOT create, update, or resolve incidents.

### Key Entities

- **Incident**: An operational report with a title, component, severity, lifecycle
  status, and creation time.
- **SLA evaluation**: The minutes consumed under the applicable severity policy,
  whether the resolution limit has been exceeded, and whether escalation is
  required at the reference time.
- **Active incident summary**: The active total, the count of SLA breaches, and
  the details of every incident in scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In every acceptance scenario, 100% of `OPEN` and `IN_PROGRESS`
  incidents in scope appear exactly once, and no other status appears.
- **SC-002**: For every summary, the active total equals the number of listed
  incidents and the breach count matches the incidents that exceeded their SLA.
- **SC-003**: For every component-filtered summary, 100% of listed incidents match
  the requested component; no matches yield zero totals and an empty list.
- **SC-004**: For equivalent incidents, filters, and reference times, web and
  terminal summaries contain equivalent counts and incident details.
- **SC-005**: A support operator can determine active workload and SLA risk from
  either interface without manually combining separate incident records.

## Assumptions

- “Active” means exactly `OPEN` or `IN_PROGRESS`; `ESCALATION_REQUIRED` and
  `RESOLVED` are excluded.
- SLA policy is P0: 60 minutes and P1: 240 minutes, counted continuously; P2:
  480 minutes and P3: 1440 minutes, counted Monday through Friday from 08:00 to
  18:00. Weekdays count as working days, including holidays. Escalation begins at
  75% of the SLA; a breach occurs only after exceeding the allowed SLA time.
- The incident detail's elapsed minutes are SLA-consuming minutes, not wall-clock
  age. P2/P3 do not accumulate SLA time outside working hours.
- If `reference_time` is absent, one current instant is used for the complete
  summary in UTC. When supplied, `reference_time` is an RFC 3339 timestamp with
  timezone, normalized to UTC and shared by all evaluations. Persisted legacy
  timestamps without a timezone are interpreted as UTC.
- A blank or omitted component filter means no component restriction; a supplied
  component is matched exactly.
- The terminal presents the same summary data as the web interface in JSON.
- The feature reads incidents already available to IncidentOps; creating or
  changing incident lifecycle data is outside this feature.
