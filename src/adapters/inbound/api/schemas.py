"""Esquemas Pydantic del adaptador HTTP."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.domain.models import RecommendedTeam, SeverityLevel


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
