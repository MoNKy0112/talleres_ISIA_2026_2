"""Acceptance and runtime contract tests for Hito 004."""

from fastapi.testclient import TestClient
from datetime import datetime, timezone
import inspect
import os
import pytest
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.factory import create_repository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService
from src.domain.models import Incident


class HealthRepository:
    def __init__(self, result: bool = True, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def check_health(self) -> bool:
        if self.error is not None:
            raise self.error
        return self.result


@pytest.mark.parametrize(
    ("repository", "expected_status", "expected_body"),
    [
        (
            HealthRepository(True),
            200,
            {"status": "ok", "database": "connected"},
        ),
        (
            HealthRepository(False),
            503,
            {"status": "error", "database": "unavailable"},
        ),
        (
            HealthRepository(error=RuntimeError("connection details")),
            503,
            {"status": "error", "database": "unavailable"},
        ),
        (
            None,
            503,
            {"status": "error", "database": "unavailable"},
        ),
    ],
)
def test_health_api_maps_repository_status(
    repository: HealthRepository | None,
    expected_status: int,
    expected_body: dict[str, str],
) -> None:
    client = TestClient(create_app(IncidentService(repository)))

    response = client.get("/health")

    assert response.status_code == expected_status
    assert response.json() == expected_body


@pytest.mark.parametrize(
    ("repository", "expected_exit", "expected_output"),
    [
        (
            HealthRepository(True),
            0,
            '{"status": "ok", "database": "connected"}',
        ),
        (
            HealthRepository(False),
            1,
            '{"status": "error", "database": "unavailable"}',
        ),
        (
            HealthRepository(error=RuntimeError("connection details")),
            1,
            '{"status": "error", "database": "unavailable"}',
        ),
        (
            None,
            1,
            '{"status": "error", "database": "unavailable"}',
        ),
    ],
)
def test_health_cli_maps_repository_status(
    monkeypatch: pytest.MonkeyPatch,
    repository: HealthRepository | None,
    expected_exit: int,
    expected_output: str,
) -> None:
    monkeypatch.setattr(
        "src.adapters.inbound.cli.IncidentService",
        lambda _repository=None: IncidentService(repository),
    )

    result = CliRunner().invoke(cli_app, ["health"])

    assert result.exit_code == expected_exit
    assert result.stdout.strip() == expected_output


def test_incident_service_health_is_false_without_repository() -> None:
    assert IncidentService().check_health() is False


def test_factory_selects_sqlite_for_url_and_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert isinstance(create_repository(), SQLiteIncidentRepository)
    assert isinstance(
        create_repository("sqlite:///./runtime-test.db"), SQLiteIncidentRepository
    )


@pytest.mark.parametrize("scheme", ["postgresql://", "postgres://"])
def test_factory_selects_postgres_for_supported_schemes(scheme: str) -> None:
    from src.adapters.outbound.postgres_repository import PostgresIncidentRepository

    repository = create_repository(f"{scheme}user:pass@localhost:5432/incidents")

    assert isinstance(repository, PostgresIncidentRepository)


def test_factory_rejects_unsupported_scheme() -> None:
    with pytest.raises(ValueError, match="Unsupported DATABASE_URL scheme"):
        create_repository("mysql://localhost/incidents")


def test_both_repositories_satisfy_runtime_checkable_port_without_postgres() -> None:
    from src.adapters.outbound.postgres_repository import PostgresIncidentRepository

    sqlite_repository = create_repository()
    postgres_repository = create_repository(
        "postgresql://user:pass@127.0.0.1:1/incidents"
    )

    assert isinstance(sqlite_repository, IncidentRepositoryPort)
    assert isinstance(postgres_repository, IncidentRepositoryPort)
    assert isinstance(postgres_repository, PostgresIncidentRepository)
    for method_name in (
        "save_incident",
        "get_incident",
        "incident_id_exists",
        "find_open_duplicates",
        "list_active_incidents",
        "check_health",
    ):
        assert callable(getattr(postgres_repository, method_name))
        assert inspect.signature(
            getattr(type(postgres_repository), method_name)
        ) == inspect.signature(getattr(IncidentRepositoryPort, method_name))


def _sample_incident(
    incident_id: str = "INC-PG-1",
    status: str = "OPEN",
    created_at: datetime | None = None,
) -> Incident:
    return Incident(
        incident_id=incident_id,
        title="Database connectivity issue",
        raw_text="database connectivity issue",
        component="database",
        severity="P2",
        status=status,  # type: ignore[arg-type]
        created_at=created_at or datetime(2026, 11, 24, 8, tzinfo=timezone.utc),
        duplicate_group_key="database:connectivity",
    )


def test_sqlite_duplicate_query_uses_exact_supplied_statuses() -> None:
    repository = create_repository()
    repository.save_incident(_sample_incident("INC-OPEN", "OPEN"))
    repository.save_incident(_sample_incident("INC-RESOLVED", "RESOLVED"))

    open_matches = repository.find_open_duplicates(
        "database:connectivity", frozenset({"OPEN"}), "INC-NEW"
    )
    resolved_matches = repository.find_open_duplicates(
        "database:connectivity", frozenset({"RESOLVED"}), "INC-NEW"
    )

    assert [incident.incident_id for incident in open_matches] == ["INC-OPEN"]
    assert [incident.incident_id for incident in resolved_matches] == ["INC-RESOLVED"]


def test_postgres_health_executes_select_one_and_handles_driver_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.adapters.outbound import postgres_repository as postgres_module
    from src.adapters.outbound.postgres_repository import PostgresIncidentRepository

    class ConnectionDouble:
        def __init__(self) -> None:
            self.statements: list[str] = []

        def __enter__(self) -> "ConnectionDouble":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, statement: str, _parameters: object = None):
            self.statements.append(statement)
            return type("Cursor", (), {"fetchone": lambda _self: {"?column?": 1}})()

    connection = ConnectionDouble()
    monkeypatch.setattr(postgres_module.psycopg, "connect", lambda *a, **kw: connection)
    repository = PostgresIncidentRepository("postgresql://user:pass@localhost/db")

    assert repository.check_health() is True
    assert connection.statements == ["SELECT 1"]

    def fail_connect(*_args: object, **_kwargs: object):
        raise postgres_module.psycopg.OperationalError("unavailable")

    monkeypatch.setattr(postgres_module.psycopg, "connect", fail_connect)
    assert repository.check_health() is False


@pytest.mark.skipif(
    not os.getenv("INCIDENTOPS_TEST_POSTGRES_URL"),
    reason="Set INCIDENTOPS_TEST_POSTGRES_URL to run PostgreSQL integration parity.",
)
def test_postgres_repository_schema_crud_duplicate_and_sla_parity() -> None:
    from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
    from src.domain.sla_calculator import evaluate_sla_status

    database_url = os.environ["INCIDENTOPS_TEST_POSTGRES_URL"]
    postgres = PostgresIncidentRepository(database_url)
    sqlite = create_repository()
    incident = _sample_incident()
    reference_time = datetime(2026, 11, 24, 15, tzinfo=timezone.utc)

    with postgres._connection() as connection:
        postgres._initialize_schema(connection)
        policy_count = connection.execute(
            "SELECT count(*) AS count FROM sla_policies"
        ).fetchone()["count"]
        index_names = {
            row["indexname"]
            for row in connection.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'incidents'"
            ).fetchall()
        }
    assert policy_count == 4
    assert "idx_incidents_component_status" in index_names
    assert "idx_incidents_dup_key" in index_names

    for repository in (postgres, sqlite):
        repository.save_incident(incident)
        assert repository.incident_id_exists(incident.incident_id)
        assert repository.get_incident(incident.incident_id) == incident
        assert [
            item.incident_id
            for item in repository.find_open_duplicates(
                "database:connectivity", frozenset({"OPEN"}), "INC-OTHER"
            )
        ] == [incident.incident_id]
        resolved_matches = repository.find_open_duplicates(
            "database:connectivity", frozenset({"RESOLVED"}), "INC-OTHER"
        )
        assert resolved_matches == []
        assert [item.incident_id for item in repository.list_active_incidents()] == [
            incident.incident_id
        ]
        loaded = repository.get_incident(incident.incident_id)
        assert loaded is not None
        assert evaluate_sla_status(loaded, reference_time) == evaluate_sla_status(
            incident, reference_time
        )
        assert loaded.created_at.tzinfo == timezone.utc
        assert repository.check_health()


def test_container_runtime_files_define_required_image_and_orchestration() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in dockerfile
    assert "uv sync --locked --no-dev" in dockerfile
    for ignored in (".venv/", "__pycache__/", ".git/", ".env", "tests/"):
        assert ignored in dockerignore
    assert "services:" in compose
    assert "postgres:16-alpine" in compose
    assert "pg_isready" in compose
    assert "condition: service_healthy" in compose
    assert "@db:5432/" in compose
    assert '"8000:8000"' in compose
    assert '"--host", "0.0.0.0"' in dockerfile
    assert "127.0.0.1:8000/health" in compose
    assert "/health" in compose
