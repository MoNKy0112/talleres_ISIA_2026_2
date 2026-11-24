# CLI Contract

Commands are exposed by `src.adapters.inbound.cli` and emit JSON to stdout on
success. Errors are written to stderr and exit with status 1. The CLI delegates
business behavior to the same `IncidentService` use cases as HTTP.

## `create`

```text
incidentops create --title TEXT --raw-text TEXT
  [--incident-id ID] [--created-at ISO8601] [--status STATUS]
```

- Required: `--title`, `--raw-text`; reject empty or whitespace-only values.
- Optional: `--incident-id` (generated `INC-<HEX8>` when omitted),
  `--created-at` (current UTC when omitted), `--status` (`OPEN` by default).
- Success: exit 0 and JSON with full classification, incident fields,
  `is_duplicate`, and `duplicate_of`.
- Validation failure: exit 1, no incident created.

## `sla`

```text
incidentops sla INCIDENT_ID [--reference-time ISO8601]
```

- `--reference-time` is optional; naive ISO 8601 values mean UTC, aware values
  are normalized to UTC.
- Success: exit 0 and JSON with incident status/component/severity, elapsed and
  allowed minutes, remaining or exceeded minutes, breach and escalation flags.
- Unknown incident or reference before `created_at`: exit 1 with a clear error
  and no fabricated evaluation.
