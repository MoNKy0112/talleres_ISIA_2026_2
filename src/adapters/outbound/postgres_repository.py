"""Repositorio PostgreSQL explícito y compatible con IncidentRepositoryPort."""

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, cast

import psycopg
from psycopg.rows import dict_row

from src.application.ports import IncidentRepositoryPort
from src.domain.models import Incident, IncidentStatus, RecommendedTeam, SeverityLevel
from src.domain.sla_calculator import SLA_POLICY_TABLE


class PostgresIncidentRepository(IncidentRepositoryPort):
    """Adaptador PostgreSQL con conexiones bajo demanda y SQL parametrizado."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    @contextmanager
    def _connection(self, initialize: bool = True) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self._database_url, row_factory=dict_row) as connection:
            if initialize:
                self._initialize_schema(connection)
            yield connection

    @staticmethod
    def _initialize_schema(connection: psycopg.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sla_policies (
                severity TEXT PRIMARY KEY,
                max_resolution_minutes INTEGER NOT NULL,
                operates_24x7 BOOLEAN NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                raw_text TEXT,
                component TEXT NOT NULL,
                recommended_team TEXT,
                duplicate_group_key TEXT,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_incidents_component_status "
            "ON incidents (component, status)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_incidents_dup_key "
            "ON incidents (duplicate_group_key, status)"
        )
        for policy in SLA_POLICY_TABLE.values():
            connection.execute(
                """
                INSERT INTO sla_policies
                    (severity, max_resolution_minutes, operates_24x7)
                VALUES (%s, %s, %s)
                ON CONFLICT (severity) DO NOTHING
                """,
                (
                    policy.severity,
                    policy.max_resolution_minutes,
                    policy.operates_24x7,
                ),
            )

    def save_incident(self, incident: Incident) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id, title, raw_text, component, recommended_team,
                    duplicate_group_key, severity, status, created_at, resolved_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (incident_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    raw_text = EXCLUDED.raw_text,
                    component = EXCLUDED.component,
                    recommended_team = EXCLUDED.recommended_team,
                    duplicate_group_key = EXCLUDED.duplicate_group_key,
                    severity = EXCLUDED.severity,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    resolved_at = EXCLUDED.resolved_at
                """,
                (
                    incident.incident_id,
                    incident.title,
                    incident.raw_text,
                    incident.component,
                    incident.recommended_team,
                    incident.duplicate_group_key,
                    incident.severity,
                    incident.status,
                    _as_utc(incident.created_at).isoformat(),
                    (
                        _as_utc(incident.resolved_at).isoformat()
                        if incident.resolved_at is not None
                        else None
                    ),
                ),
            )

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM incidents WHERE incident_id = %s", (incident_id,)
            ).fetchone()
        return _incident_from_row(row) if row is not None else None

    def incident_id_exists(self, incident_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM incidents WHERE incident_id = %s", (incident_id,)
            ).fetchone()
        return row is not None

    def find_open_duplicates(
        self,
        duplicate_group_key: str,
        open_statuses: frozenset[IncidentStatus],
        exclude_incident_id: str,
    ) -> list[Incident]:
        if not open_statuses:
            return []
        placeholders = ", ".join("%s" for _ in open_statuses)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM incidents
                WHERE status IN ({placeholders})
                  AND duplicate_group_key = %s
                  AND incident_id != %s
                ORDER BY incident_id
                """,
                (*sorted(open_statuses), duplicate_group_key, exclude_incident_id),
            ).fetchall()
        return [_incident_from_row(row) for row in rows]

    def list_active_incidents(
        self, component_filter: str | None = None
    ) -> list[Incident]:
        query = """
            SELECT i.*
            FROM incidents AS i
            INNER JOIN sla_policies AS p ON p.severity = i.severity
            WHERE i.status IN ('OPEN', 'IN_PROGRESS')
        """
        parameters: tuple[str, ...] = ()
        if component_filter is not None and component_filter.strip():
            query += " AND i.component = %s"
            parameters = (component_filter,)
        query += " ORDER BY i.incident_id"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [_incident_from_row(row) for row in rows]

    def check_health(self) -> bool:
        try:
            with self._connection(initialize=False) as connection:
                row = connection.execute("SELECT 1").fetchone()
                return row is not None and next(iter(row.values())) == 1
        except psycopg.Error:
            return False

    def close(self) -> None:
        """No-op: each operation owns and closes its own lazy connection."""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _incident_from_row(row: dict[str, object]) -> Incident:
    resolved_at = row["resolved_at"]
    return Incident(
        incident_id=str(row["incident_id"]),
        title=str(row["title"]),
        raw_text=cast(str | None, row["raw_text"]),
        component=str(row["component"]),
        recommended_team=cast(RecommendedTeam | None, row["recommended_team"]),
        duplicate_group_key=cast(str | None, row["duplicate_group_key"]),
        severity=cast(SeverityLevel, row["severity"]),
        status=cast(IncidentStatus, row["status"]),
        created_at=_parse_utc(str(row["created_at"])),
        resolved_at=_parse_utc(str(resolved_at)) if resolved_at is not None else None,
    )


def _parse_utc(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value))
