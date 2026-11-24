"""Repositorio SQLite que implementa el puerto de incidentes."""

from datetime import datetime, timezone
import sqlite3
from typing import cast

from src.application.ports import IncidentRepositoryPort
from src.domain.models import Incident, IncidentStatus, RecommendedTeam, SeverityLevel
from src.domain.sla_calculator import SLA_POLICY_TABLE


class SQLiteIncidentRepository(IncidentRepositoryPort):
    """Persistencia SQLite sin trasladar reglas de SLA fuera del dominio."""

    def __init__(self, database_path: str = ":memory:") -> None:
        self.connection = sqlite3.connect(database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sla_policies (
                severity TEXT PRIMARY KEY,
                max_resolution_minutes INTEGER NOT NULL,
                operates_24x7 INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
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
        columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(incidents)").fetchall()
        }
        if "duplicate_group_key" not in columns:
            cursor.execute(
                "ALTER TABLE incidents ADD COLUMN duplicate_group_key TEXT"
            )
        if "recommended_team" not in columns:
            cursor.execute("ALTER TABLE incidents ADD COLUMN recommended_team TEXT")
        if "raw_text" not in columns:
            cursor.execute("ALTER TABLE incidents ADD COLUMN raw_text TEXT")
        cursor.execute(
            """
            UPDATE incidents
            SET duplicate_group_key = '__legacy__:' || incident_id
            WHERE duplicate_group_key IS NULL OR duplicate_group_key = ''
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_incidents_component_status "
            "ON incidents (component, status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_incidents_dup_key "
            "ON incidents (duplicate_group_key, status)"
        )
        for rule in SLA_POLICY_TABLE.values():
            cursor.execute(
                """
                INSERT OR REPLACE INTO sla_policies
                    (severity, max_resolution_minutes, operates_24x7)
                VALUES (?, ?, ?)
                """,
                (
                    rule.severity,
                    rule.max_resolution_minutes,
                    int(rule.operates_24x7),
                ),
            )
        self.connection.commit()

    def save_incident(self, incident: Incident) -> None:
        """Inserta el registro; nunca reemplaza silenciosamente un ID existente."""
        self.connection.execute(
            """
            INSERT INTO incidents (
                incident_id, title, raw_text, component, recommended_team,
                duplicate_group_key, severity, status, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        self.connection.commit()

    def get_incident(self, incident_id: str) -> Incident | None:
        row = self.connection.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return _incident_from_row(row) if row is not None else None

    def incident_id_exists(self, incident_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM incidents WHERE incident_id = ?", (incident_id,)
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
        status_placeholders = ", ".join("?" for _ in open_statuses)
        rows = self.connection.execute(
            f"""
            SELECT * FROM incidents
            WHERE status IN ({status_placeholders})
              AND duplicate_group_key = ?
              AND incident_id != ?
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
            query += " AND i.component = ?"
            parameters = (component_filter,)
        query += " ORDER BY i.incident_id"
        rows = self.connection.execute(query, parameters).fetchall()
        return [_incident_from_row(row) for row in rows]

    def check_health(self) -> bool:
        try:
            self.connection.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            return False
        return True

    def close(self) -> None:
        """Cierra la conexión SQLite asociada al repositorio."""
        self.connection.close()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _incident_from_row(row: sqlite3.Row) -> Incident:
    created_at = _parse_utc(row["created_at"])
    resolved_at = (
        _parse_utc(row["resolved_at"]) if row["resolved_at"] is not None else None
    )
    return Incident(
        incident_id=row["incident_id"],
        title=row["title"],
        raw_text=row["raw_text"] if "raw_text" in row.keys() else None,
        component=row["component"],
        recommended_team=(
            cast(RecommendedTeam, row["recommended_team"])
            if "recommended_team" in row.keys() and row["recommended_team"] is not None
            else None
        ),
        duplicate_group_key=(
            row["duplicate_group_key"]
            if "duplicate_group_key" in row.keys()
            else None
        ),
        severity=cast(SeverityLevel, row["severity"]),
        status=cast(IncidentStatus, row["status"]),
        created_at=created_at,
        resolved_at=resolved_at,
    )


def _parse_utc(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value))
