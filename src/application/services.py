"""Casos de uso compartidos por los adaptadores de entrada."""

from dataclasses import dataclass
from datetime import datetime, timezone
import secrets

from src.application.ports import IncidentRepositoryPort
from src.domain.models import (
    OPEN_DUPLICATE_STATUSES,
    Incident,
    IncidentStatus,
    RecommendedTeam,
    SLAEvaluation,
    SeverityLevel,
    TriageResult,
)
from src.domain.sla_calculator import evaluate_sla_status, normalize_utc
from src.domain.triage_rules import classify_incident_report


class ValidationError(ValueError):
    """Error de validación de una entrada de aplicación."""


class IncidentNotFoundError(LookupError):
    """El incidente solicitado no existe."""


@dataclass(frozen=True)
class IncidentCreatedResult:
    """Resultado de negocio de registrar un incidente."""

    incident_id: str
    title: str
    raw_text: str
    component: str
    severity: SeverityLevel
    rationale: str
    recommended_team: RecommendedTeam
    duplicate_group_key: str
    consistency_ratio: float
    status: IncidentStatus
    created_at: datetime
    is_duplicate: bool
    duplicate_of: list[str]


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

    def check_health(self) -> bool:
        """Comprueba conectividad sin fallar si el puerto no fue configurado."""
        if self._repository is None:
            return False
        return self._repository.check_health()

    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        if not isinstance(incident_id, str) or not incident_id.strip():
            raise ValidationError("incident_id debe ser un string no vacío.")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValidationError("raw_text debe ser un string no vacío.")

        # Validar contenido vacío sin alterar el texto que recibe el dominio.
        return classify_incident_report(incident_id, raw_text)

    def create_incident(
        self,
        title: str,
        raw_text: str,
        incident_id: str | None = None,
        created_at: datetime | None = None,
        status: IncidentStatus = "OPEN",
    ) -> IncidentCreatedResult:
        if self._repository is None:
            raise ValidationError("El repositorio de incidentes no está configurado.")
        if not isinstance(title, str) or not title.strip():
            raise ValidationError("title debe ser un string no vacío.")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValidationError("raw_text debe ser un string no vacío.")
        if status not in {"OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED", "RESOLVED"}:
            raise ValidationError("status no es un estado de incidente válido.")

        received_at = normalize_utc(created_at or datetime.now(timezone.utc))
        assigned_id = incident_id
        if assigned_id is not None:
            if not assigned_id.strip():
                raise ValidationError("incident_id no puede estar vacío.")
            if self._repository.incident_id_exists(assigned_id):
                raise ValidationError(f"incident_id ya existe: {assigned_id}")
        else:
            for _ in range(10):
                candidate = f"INC-{secrets.token_hex(4).upper()}"
                if not self._repository.incident_id_exists(candidate):
                    assigned_id = candidate
                    break
            if assigned_id is None:
                raise ValidationError("No fue posible generar un incident_id único.")

        classification = classify_incident_report(assigned_id, raw_text)
        duplicates = self._repository.find_open_duplicates(
            duplicate_group_key=classification.duplicate_group_key,
            open_statuses=OPEN_DUPLICATE_STATUSES,
            exclude_incident_id=assigned_id,
        )
        incident = Incident(
            incident_id=assigned_id,
            title=title,
            component=classification.component,
            severity=classification.severity,
            status=status,
            created_at=received_at,
            recommended_team=classification.recommended_team,
            duplicate_group_key=classification.duplicate_group_key,
            raw_text=raw_text,
        )
        self._repository.save_incident(incident)
        duplicate_ids = [item.incident_id for item in duplicates]
        return IncidentCreatedResult(
            incident_id=incident.incident_id,
            title=incident.title,
            raw_text=raw_text,
            component=classification.component,
            severity=classification.severity,
            rationale=classification.rationale,
            recommended_team=classification.recommended_team,
            duplicate_group_key=classification.duplicate_group_key,
            consistency_ratio=classification.consistency_ratio,
            status=incident.status,
            created_at=incident.created_at,
            is_duplicate=bool(duplicate_ids),
            duplicate_of=duplicate_ids,
        )

    def evaluate_incident_sla(
        self, incident_id: str, reference_time: datetime | None = None
    ) -> SLAEvaluation:
        if self._repository is None:
            raise ValidationError("El repositorio de incidentes no está configurado.")
        incident = self._repository.get_incident(incident_id)
        if incident is None:
            raise IncidentNotFoundError(f"No se encontró el incidente: {incident_id}")

        instant = normalize_utc(reference_time or datetime.now(timezone.utc))
        created_at = normalize_utc(incident.created_at)
        if instant < created_at:
            raise ValidationError(
                "reference_time no puede ser anterior a created_at."
            )
        return evaluate_sla_status(incident, instant)

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
