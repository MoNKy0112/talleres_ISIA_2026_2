"""Puertos secundarios que la aplicación necesita de la persistencia."""

from typing import Protocol, runtime_checkable

from src.domain.models import Incident


@runtime_checkable
class IncidentRepositoryPort(Protocol):
    """Contrato estructural para almacenar y consultar incidentes."""

    def save_incident(self, incident: Incident) -> None:
        """Persiste un incidente."""

    def get_incident(self, incident_id: str) -> Incident | None:
        """Obtiene un incidente por identificador estable."""

    def find_open_duplicates(
        self, component: str, duplicate_group_key: str
    ) -> list[Incident]:
        """Devuelve todas las coincidencias OPEN sin modificar el repositorio."""

    def list_active_incidents(
        self, component_filter: str | None = None
    ) -> list[Incident]:
        """Lista incidentes OPEN o IN_PROGRESS, opcionalmente por componente."""

    def check_health(self) -> bool:
        """Indica si el repositorio puede atender consultas."""
