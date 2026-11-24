# Repository guidance

- Run commands from the repository root. Use `uv sync` to install the locked runtime and development dependencies.
- Architecture: `src/domain/` owns models and deterministic triage/SLA rules; `src/application/services.py` exposes shared use cases (`IncidentService`); `src/adapters/inbound/` contains REST and CLI entrypoints. Keep framework and serialization details out of the domain.
- The H001 HTTP contract is `POST /api/v1/incidents/triage`; API and CLI must delegate to `IncidentService`, validate non-blank input, and never persist H001 triage reports.
- Sample triage input is `data/sample_incidents.json`; its path is resolved from `src/domain/triage_rules.py`, not the process working directory.
- Verification: run the acceptance suite with `uv run pytest`. Focused demos: `uv run python -m src.domain.triage_rules` and `uv run python -m src.domain.sla_calculator`.
- Start the API with `uv run uvicorn src.adapters.inbound.api.app:app --reload`; run the CLI with `uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "..."`.
- The context audit is `uv run python -m src.context_audit --symbol <function>` (or `--compare-formats`). It scans Python modules recursively under `src/`.
- `uv run python -m src.incident_repository` is a teaching benchmark: it seeds 10,000 in-memory SQLite rows and intentionally exercises a full-table scan/N+1 query; it is not a test suite.
- SLA business-hour policy and design trade-offs are in `docs/adr/002-calculo-sla-horario-habil.md`. The hexagonal architecture decision is described in `docs/adr/003-arquitectura-hexagonal.md`.
