"""Composition boundary for choosing the SQLite repository from DATABASE_URL."""

import os

from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort


def create_repository(database_url: str | None = None) -> IncidentRepositoryPort:
    """Builds the configured SQLite repository; defaults to an in-memory database."""
    url = database_url if database_url is not None else os.getenv(
        "DATABASE_URL", "sqlite:///:memory:"
    )
    if not url.startswith("sqlite:///"):
        raise ValueError(f"Unsupported DATABASE_URL scheme: {url!r}")

    database_path = url[len("sqlite:///") :]
    if not database_path:
        raise ValueError("SQLite DATABASE_URL must include a database path.")
    if database_path.startswith("//"):
        database_path = database_path[1:]
    return SQLiteIncidentRepository(database_path)
