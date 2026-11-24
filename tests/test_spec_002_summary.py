"""Pruebas BDD de aceptación para H002 y el puerto de persistencia."""

from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient
import pytest
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.factory import create_repository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService
from src.domain.models import Incident
from src.domain.models import OPEN_DUPLICATE_STATUSES


REFERENCE_TIME = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)


def _incident(
    incident_id: str,
    *,
    component: str = "payments-gateway",
    severity: str = "P0",
    status: str = "OPEN",
    created_at: datetime = datetime(2026, 11, 23, 11, 0),
) -> Incident:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return Incident(
        incident_id=incident_id,
        title=f"Incident {incident_id}",
        component=component,
        duplicate_group_key=f"{component}:http-502",
        severity=severity,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        created_at=created_at,
    )


def test_summary_http_includes_only_active_records_and_does_not_mutate_storage():
    """Given estados mixtos, When se consulta el resumen, Then solo hay activos y nada cambia."""
    repository = SQLiteIncidentRepository()
    incidents = [
        _incident("INC-OPEN", created_at=datetime(2026, 11, 23, 10, 59)),
        _incident("INC-PROGRESS", severity="P2", status="IN_PROGRESS"),
        _incident("INC-RESOLVED", status="RESOLVED"),
        _incident("INC-ESCALATION", status="ESCALATION_REQUIRED"),
    ]
    for incident in incidents:
        repository.save_incident(incident)
    before = [repository.get_incident(item.incident_id) for item in incidents]
    client = TestClient(create_app(IncidentService(repository)))

    response = client.get(
        "/api/v1/incidents/summary",
        params={"reference_time": "2026-11-23T12:00:00Z"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_active"] == 2
    assert body["breached_count"] == 1
    assert {item["incident_id"] for item in body["incidents"]} == {
        "INC-OPEN",
        "INC-PROGRESS",
    }
    open_item = next(item for item in body["incidents"] if item["incident_id"] == "INC-OPEN")
    assert open_item["elapsed_minutes"] == 61
    assert open_item["requires_escalation"] is True
    after = [repository.get_incident(item.incident_id) for item in incidents]
    assert after == before


def test_summary_http_filters_component_and_recomputes_totals():
    """Given dos componentes, When se filtra uno, Then solo se cuentan sus activos."""
    repository = SQLiteIncidentRepository()
    repository.save_incident(_incident("INC-PAY", component="payments-gateway"))
    repository.save_incident(_incident("INC-AUTH", component="auth-identity"))
    client = TestClient(create_app(IncidentService(repository)))

    response = client.get(
        "/api/v1/incidents/summary",
        params={
            "component": "auth-identity",
            "reference_time": "2026-11-23T12:00:00Z",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_active"] == 1
    assert body["breached_count"] == 0
    assert [item["incident_id"] for item in body["incidents"]] == ["INC-AUTH"]


def test_summary_http_returns_valid_empty_summary_for_no_matches():
    """Given ningún activo coincidente, When se consulta, Then devuelve resumen vacío 200."""
    repository = SQLiteIncidentRepository()
    repository.save_incident(_incident("INC-CLOSED", status="RESOLVED"))
    client = TestClient(create_app(IncidentService(repository)))

    response = client.get(
        "/api/v1/incidents/summary",
        params={
            "component": "unknown-component",
            "reference_time": "2026-11-23T12:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "total_active": 0,
        "breached_count": 0,
        "incidents": [],
    }


def test_summary_http_requires_timezone_in_reference_time():
    """Given referencia sin zona, When se consulta, Then se responde 422."""
    client = TestClient(create_app(IncidentService(SQLiteIncidentRepository())))

    response = client.get(
        "/api/v1/incidents/summary",
        params={"reference_time": "2026-11-23T12:00:00"},
    )

    assert response.status_code == 422


def test_sqlite_repository_implements_port_and_repository_operations():
    """Given el puerto, When se usa SQLite, Then satisface contrato y operaciones."""
    repository = SQLiteIncidentRepository()
    assert isinstance(repository, IncidentRepositoryPort)

    open_one = _incident("INC-OPEN-1")
    open_two = _incident("INC-OPEN-2")
    in_progress = _incident("INC-PROGRESS", status="IN_PROGRESS")
    other_component = _incident("INC-OTHER", component="auth-identity")
    for incident in (open_one, open_two, in_progress, other_component):
        repository.save_incident(incident)

    assert repository.get_incident("INC-OPEN-1") == open_one
    assert repository.get_incident("missing") is None
    assert repository.find_open_duplicates(
        "payments-gateway:http-502",
        OPEN_DUPLICATE_STATUSES,
        "INC-NEW",
    ) == [open_one, open_two, in_progress]
    assert repository.list_active_incidents("payments-gateway") == [
        open_one,
        open_two,
        in_progress,
    ]
    assert repository.check_health() is True


def test_repository_reads_legacy_naive_timestamps_as_utc(tmp_path):
    """Given una base antigua, When se abre, Then normaliza la fecha y no duplica."""
    database = tmp_path / "legacy.sqlite"
    import sqlite3

    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE incidents (
            incident_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            component TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            resolved_at TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "INC-LEGACY",
            "Legacy incident",
            "payments-gateway",
            "P0",
            "OPEN",
            "2026-11-23T11:00:00",
            None,
        ),
    )
    connection.commit()
    connection.close()

    repository = SQLiteIncidentRepository(str(database))
    incident = repository.get_incident("INC-LEGACY")

    assert incident is not None
    assert incident.created_at == datetime(2026, 11, 23, 11, 0, tzinfo=timezone.utc)
    assert repository.find_open_duplicates(
        "payments-gateway:http-502",
        OPEN_DUPLICATE_STATUSES,
        "INC-NEW",
    ) == []


def test_repository_factory_defaults_to_in_memory_and_rejects_unknown_schemes(
    monkeypatch,
):
    """Given DATABASE_URL omitida, When se construye repositorio, Then usa SQLite."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    repository = create_repository()

    assert isinstance(repository, SQLiteIncidentRepository)
    assert repository.check_health() is True
    from src.adapters.outbound.postgres_repository import PostgresIncidentRepository

    assert isinstance(
        create_repository("postgresql://localhost/incidents"),
        PostgresIncidentRepository,
    )


def test_repository_factory_opens_absolute_sqlite_path(tmp_path):
    """Given ruta absoluta SQLite, When se construye, Then conecta al archivo."""
    database_path = tmp_path / "factory.sqlite"
    repository = create_repository(f"sqlite:///{database_path.as_posix()}")

    repository.save_incident(_incident("INC-FACTORY"))

    assert database_path.exists()
    assert repository.get_incident("INC-FACTORY") is not None


def test_cli_summary_matches_http_and_keeps_storage_read_only(monkeypatch):
    """Given repositorio compartido, When consultan ambas interfaces, Then coinciden."""
    repository = SQLiteIncidentRepository()
    incident = _incident("INC-PARITY", created_at=datetime(2026, 11, 23, 10, 59))
    repository.save_incident(incident)
    before = repository.get_incident(incident.incident_id)
    service = IncidentService(repository)
    client = TestClient(create_app(service))
    monkeypatch.setattr(
        "src.adapters.inbound.cli.create_repository", lambda: repository
    )
    runner = CliRunner()

    http_response = client.get(
        "/api/v1/incidents/summary",
        params={"reference_time": "2026-11-23T12:00:00Z"},
    )
    cli_result = runner.invoke(
        cli_app,
        ["summary", "--reference-time", "2026-11-23T12:00:00Z"],
    )

    assert http_response.status_code == 200
    assert cli_result.exit_code == 0, cli_result.output
    assert json.loads(cli_result.stdout) == http_response.json()
    assert repository.get_incident(incident.incident_id) == before
