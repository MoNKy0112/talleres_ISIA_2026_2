"""Puertos secundarios que la aplicación necesita de la persistencia."""

from typing import Protocol, runtime_checkable

from src.domain.models import Incident, IncidentStatus


@runtime_checkable
class IncidentRepositoryPort(Protocol):
    """Contrato estructural para almacenar y consultar incidentes."""

    def save_incident(self, incident: Incident) -> None:
        """Persiste un incidente."""

    def get_incident(self, incident_id: str) -> Incident | None:
        """Obtiene un incidente o devuelve None cuando el ID no existe."""

    def incident_id_exists(self, incident_id: str) -> bool:
        """Indica si el identificador ya está persistido."""

    def find_open_duplicates(
        self,
        duplicate_group_key: str,
        open_statuses: frozenset[IncidentStatus],
        exclude_incident_id: str,
    ) -> list[Incident]:
        """Consulta coincidencias usando la política de estados suministrada."""

    def list_active_incidents(
        self, component_filter: str | None = None
    ) -> list[Incident]:
        """Lista incidentes OPEN o IN_PROGRESS, opcionalmente por componente."""

    def check_health(self) -> bool:
        """Indica si el repositorio puede atender consultas."""
