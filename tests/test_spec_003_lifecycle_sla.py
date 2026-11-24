"""BDD acceptance tests for incident registration, duplicates, and SLA audit."""

from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
import pytest
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.services import IncidentService
from src.domain.models import Incident


P2_TEXT = "El gateway de pagos devuelve 502 al completar una transacción"
P2_KEY = "payments-gateway:http-502-outage"


def _incident(
    incident_id: str,
    *,
    status: str = "OPEN",
    duplicate_group_key: str | None = P2_KEY,
    created_at: datetime = datetime(2026, 11, 6, 17, tzinfo=timezone.utc),
) -> Incident:
    return Incident(
        incident_id=incident_id,
        title=f"Incident {incident_id}",
        component="payments-gateway",
        duplicate_group_key=duplicate_group_key,
        severity="P2",
        status=status,  # type: ignore[arg-type]
        created_at=created_at,
        recommended_team="Backend-Core",
        raw_text=P2_TEXT,
    )


def _client(repository: SQLiteIncidentRepository) -> TestClient:
    return TestClient(create_app(IncidentService(repository)))


def test_bdd_http_creates_initial_incident_without_duplicates():
    """Given no equivalent, When created, Then it is persisted as a new classified incident."""
    repository = SQLiteIncidentRepository()
    response = _client(repository).post(
        "/api/v1/incidents",
        json={"title": "Pagos con error", "raw_text": P2_TEXT},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["incident_id"].startswith("INC-")
    assert len(body["incident_id"]) == 12
    assert body["status"] == "OPEN"
    assert body["component"] == "payments-gateway"
    assert body["severity"] == "P2"
    assert body["recommended_team"] == "Backend-Core"
    assert body["duplicate_group_key"] == P2_KEY
    assert body["is_duplicate"] is False
    assert body["duplicate_of"] == []
    assert repository.get_incident(body["incident_id"]) is not None


@pytest.mark.parametrize(
    "payload",
    [
        {"title": " ", "raw_text": P2_TEXT},
        {"title": "Pagos", "raw_text": "  "},
        {"raw_text": P2_TEXT},
    ],
)
def test_bdd_http_rejects_blank_required_fields_without_persisting(payload):
    """Given invalid required text, When creating, Then HTTP returns 422."""
    repository = SQLiteIncidentRepository()

    response = _client(repository).post("/api/v1/incidents", json=payload)

    assert response.status_code == 422
    assert repository.get_incident("INC-TEST") is None
    count = repository.connection.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    assert count == 0


def test_bdd_open_duplicates_include_all_active_states_and_ignore_resolved():
    """Given equivalent active and resolved reports, When creating, Then only active IDs are returned."""
    repository = SQLiteIncidentRepository()
    for incident in (
        _incident("INC-OPEN", status="OPEN"),
        _incident("INC-PROGRESS", status="IN_PROGRESS"),
        _incident("INC-ESCALATED", status="ESCALATION_REQUIRED"),
        _incident("INC-RESOLVED", status="RESOLVED"),
    ):
        repository.save_incident(incident)

    response = _client(repository).post(
        "/api/v1/incidents",
        json={
            "title": "Pagos devuelve 502",
            "raw_text": P2_TEXT,
            "incident_id": "INC-NEW",
        },
    )

    assert response.status_code == 201
    assert response.json()["is_duplicate"] is True
    assert response.json()["duplicate_of"] == [
        "INC-ESCALATED",
        "INC-OPEN",
        "INC-PROGRESS",
    ]
    assert repository.get_incident("INC-NEW") is not None


def test_bdd_p2_sla_weekend_is_deterministic_and_matches_cli(monkeypatch):
    """Given a P2 Friday report, When audited Monday, Then both adapters return exact equal business data."""
    repository = SQLiteIncidentRepository()
    repository.save_incident(
        _incident(
            "INC-P2",
            created_at=datetime(2026, 11, 6, 17, tzinfo=timezone.utc),
        )
    )
    client = _client(repository)
    monkeypatch.setattr(
        "src.adapters.inbound.cli.create_repository", lambda: repository
    )
    reference_time = "2026-11-09T09:00:00"

    http_response = client.get(
        "/api/v1/incidents/INC-P2/sla",
        params={"reference_time": reference_time},
    )
    cli_result = CliRunner().invoke(
        cli_app,
        ["sla", "INC-P2", "--reference-time", reference_time],
    )

    expected = {
        "incident_id": "INC-P2",
        "component": "payments-gateway",
        "severity": "P2",
        "status": "OPEN",
        "elapsed_minutes": 120,
        "allowed_minutes": 480,
        "remaining_minutes": 360,
        "exceeded_minutes": None,
        "is_breached": False,
        "requires_escalation": False,
    }
    assert http_response.status_code == 200
    assert http_response.json() == expected
    assert cli_result.exit_code == 0, cli_result.output
    assert json.loads(cli_result.stdout) == expected


def test_bdd_sla_not_found_returns_404_and_cli_exit_one(monkeypatch):
    """Given an unknown ID, When auditing, Then HTTP and CLI report not found."""
    repository = SQLiteIncidentRepository()
    monkeypatch.setattr(
        "src.adapters.inbound.cli.create_repository", lambda: repository
    )

    response = _client(repository).get("/api/v1/incidents/NO-SUCH-ID/sla")
    cli_result = CliRunner().invoke(cli_app, ["sla", "NO-SUCH-ID"])

    assert response.status_code == 404
    assert cli_result.exit_code == 1
    assert "no se encontró" in cli_result.output.lower()


def test_bdd_sla_reference_before_created_returns_422_and_cli_exit_one(monkeypatch):
    """Given a reference earlier than receipt, When auditing, Then no SLA is returned."""
    repository = SQLiteIncidentRepository()
    repository.save_incident(_incident("INC-FUTURE"))
    monkeypatch.setattr(
        "src.adapters.inbound.cli.create_repository", lambda: repository
    )
    reference_time = "2026-11-06T16:59:00"

    response = _client(repository).get(
        "/api/v1/incidents/INC-FUTURE/sla",
        params={"reference_time": reference_time},
    )
    cli_result = CliRunner().invoke(
        cli_app,
        ["sla", "INC-FUTURE", "--reference-time", reference_time],
    )

    assert response.status_code == 422
    assert cli_result.exit_code == 1


def test_bdd_cli_create_matches_http_classification_and_duplicate_fields(monkeypatch):
    """Given equivalent reports, When created through both adapters, Then results agree."""
    repository = SQLiteIncidentRepository()
    cli_repository = SQLiteIncidentRepository()
    client = _client(repository)
    monkeypatch.setattr(
        "src.adapters.inbound.cli.create_repository", lambda: cli_repository
    )
    request = {
        "title": "Pagos devuelve 502",
        "raw_text": P2_TEXT,
        "incident_id": "INC-PARITY",
        "created_at": "2026-11-06T17:00:00",
    }

    http_response = client.post("/api/v1/incidents", json=request)
    cli_result = CliRunner().invoke(
        cli_app,
        [
            "create",
            "--title",
            request["title"],
            "--raw-text",
            request["raw_text"],
            "--incident-id",
            request["incident_id"],
            "--created-at",
            request["created_at"],
        ],
    )

    assert http_response.status_code == 201
    assert cli_result.exit_code == 0, cli_result.output
    http_body = http_response.json()
    cli_body = json.loads(cli_result.stdout)
    for key in (
        "incident_id",
        "title",
        "component",
        "severity",
        "rationale",
        "recommended_team",
        "duplicate_group_key",
        "consistency_ratio",
        "status",
        "is_duplicate",
        "duplicate_of",
    ):
        assert cli_body[key] == http_body[key]


def test_cli_create_rejects_blank_values_with_exit_one(monkeypatch):
    """Given blank text, When CLI create runs, Then it exits 1 without storage."""
    repository = SQLiteIncidentRepository()
    monkeypatch.setattr(
        "src.adapters.inbound.cli.create_repository", lambda: repository
    )

    result = CliRunner().invoke(
        cli_app, ["create", "--title", " ", "--raw-text", P2_TEXT]
    )

    assert result.exit_code == 1
    assert repository.connection.execute(
        "SELECT COUNT(*) FROM incidents"
    ).fetchone()[0] == 0


def test_domain_sla_normalizes_naive_and_aware_timestamps():
    """Given mixed timestamp representations, When evaluated, Then UTC semantics are consistent."""
    from src.domain.sla_calculator import evaluate_sla_status

    incident = _incident(
        "INC-UTC",
        created_at=datetime(2026, 11, 6, 17),
    )
    naive = evaluate_sla_status(incident, datetime(2026, 11, 9, 9))
    aware = evaluate_sla_status(
        incident,
        datetime(2026, 11, 9, 11, tzinfo=timezone(timedelta(hours=2))),
    )

    assert naive.elapsed_minutes == 120
    assert aware.elapsed_minutes == 120


def test_sqlite_preserves_resolved_at_and_rejects_duplicate_ids():
    """Given a resolved timestamp, When stored and reloaded, Then it remains unchanged."""
    repository = SQLiteIncidentRepository()
    resolved_at = datetime(2026, 11, 9, 10, tzinfo=timezone.utc)
    incident = _incident("INC-RESOLUTION")
    incident.resolved_at = resolved_at
    repository.save_incident(incident)

    assert repository.get_incident("INC-RESOLUTION").resolved_at == resolved_at
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        repository.save_incident(incident)
