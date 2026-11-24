"""Casos de uso compartidos por los adaptadores de entrada."""

from dataclasses import dataclass
from datetime import datetime, timezone

from src.application.ports import IncidentRepositoryPort
from src.domain.models import IncidentStatus, SeverityLevel, TriageResult
from src.domain.sla_calculator import evaluate_sla_status
from src.domain.triage_rules import classify_incident_report


class ValidationError(ValueError):
    """Error de validación de una entrada de aplicación."""


@dataclass(frozen=True)
class ActiveIncidentItem:
    """Proyección de negocio de un incidente activo y su SLA."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    elapsed_minutes: int
    requires_escalation: bool


@dataclass(frozen=True)
class ActiveIncidentsSummary:
    """Resumen de incidentes activos para las interfaces de entrada."""

    total_active: int
    breached_count: int
    incidents: list[ActiveIncidentItem]


class IncidentService:
    """Coordina casos de uso sin depender de una interfaz concreta."""

    def __init__(self, repository: IncidentRepositoryPort | None = None) -> None:
        self._repository = repository

    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        if not isinstance(incident_id, str) or not incident_id.strip():
            raise ValidationError("incident_id debe ser un string no vacío.")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValidationError("raw_text debe ser un string no vacío.")

        # Validar contenido vacío sin alterar el texto que recibe el dominio.
        return classify_incident_report(incident_id, raw_text)

    def get_active_incidents_summary(
        self,
        component_filter: str | None = None,
        reference_time: datetime | None = None,
    ) -> ActiveIncidentsSummary:
        """Calcula el resumen activo evaluando todo con un mismo instante UTC."""
        if self._repository is None:
            raise ValidationError("El repositorio de incidentes no está configurado.")

        if component_filter is not None and not component_filter.strip():
            component_filter = None
        instant = _normalize_utc(reference_time or datetime.now(timezone.utc))
        active_incidents = self._repository.list_active_incidents(component_filter)

        items: list[ActiveIncidentItem] = []
        breached_count = 0
        for incident in active_incidents:
            evaluation = evaluate_sla_status(incident, reference_time=instant)
            if evaluation.is_breached:
                breached_count += 1
            items.append(
                ActiveIncidentItem(
                    incident_id=incident.incident_id,
                    title=incident.title,
                    component=incident.component,
                    severity=incident.severity,
                    status=incident.status,
                    elapsed_minutes=evaluation.elapsed_minutes,
                    requires_escalation=evaluation.requires_escalation,
                )
            )
        return ActiveIncidentsSummary(
            total_active=len(items),
            breached_count=breached_count,
            incidents=items,
        )


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
