"""Esquemas Pydantic del adaptador HTTP."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from src.domain.models import IncidentStatus, RecommendedTeam, SeverityLevel


class TriageRequest(BaseModel):
    """Entrada estricta para clasificar un reporte."""

    model_config = ConfigDict(extra="forbid", strict=True)

    incident_id: str
    raw_text: str


class TriageResponse(BaseModel):
    """Representación HTTP de todos los campos de TriageResult."""

    incident_id: str
    severity: SeverityLevel
    component: str
    rationale: str
    recommended_team: RecommendedTeam
    duplicate_group_key: str
    consistency_ratio: float


class HealthResponse(BaseModel):
    """Respuesta estable del chequeo de salud del runtime."""

    status: str
    database: str


class ActiveIncidentItem(BaseModel):
    """Detalle HTTP de un incidente activo y su evaluación de SLA."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: Literal["OPEN", "IN_PROGRESS"]
    elapsed_minutes: int
    requires_escalation: bool


class ActiveIncidentsSummaryResponse(BaseModel):
    """Respuesta HTTP del resumen de incidentes activos."""

    total_active: int
    breached_count: int
    incidents: list[ActiveIncidentItem]


class CreateIncidentRequest(BaseModel):
    """Entrada para registrar y clasificar un incidente."""

    model_config = ConfigDict(extra="forbid")

    title: str
    raw_text: str
    incident_id: str | None = None
    created_at: datetime | None = None
    status: IncidentStatus = "OPEN"

    @field_validator("title", "raw_text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El valor no puede estar vacío.")
        return value


class IncidentCreatedResponse(BaseModel):
    """Respuesta completa de clasificación y registro."""

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


class SLAEvaluationResponse(BaseModel):
    """Respuesta de auditoría SLA con contexto del incidente."""

    incident_id: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    exceeded_minutes: int | None
    is_breached: bool
    requires_escalation: bool
