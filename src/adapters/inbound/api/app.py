"""Aplicación HTTP del adaptador primario REST."""

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponse,
    TriageRequest,
    TriageResponse,
)
from src.adapters.outbound.factory import create_repository
from src.application.services import IncidentService, ValidationError


def create_app(service: IncidentService | None = None) -> FastAPI:
    """Construye la API; permite inyectar el caso de uso en pruebas."""
    incident_service = service or IncidentService(create_repository())
    api = FastAPI(title="IncidentOps API")

    @api.post(
        "/api/v1/incidents/triage",
        response_model=TriageResponse,
        status_code=200,
    )
    def triage_incident(request: TriageRequest) -> TriageResponse:
        try:
            result = incident_service.triage_incident(
                incident_id=request.incident_id,
                raw_text=request.raw_text,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"message": str(exc)},
            ) from exc
        return TriageResponse.model_validate(asdict(result))

    @api.get(
        "/api/v1/incidents/summary",
        response_model=ActiveIncidentsSummaryResponse,
        status_code=200,
    )
    def active_incidents_summary(
        component: str | None = Query(None),
        reference_time: datetime | None = Query(None),
    ) -> ActiveIncidentsSummaryResponse:
        if reference_time is not None:
            if reference_time.tzinfo is None:
                raise HTTPException(
                    status_code=422,
                    detail={"message": "reference_time debe incluir zona horaria RFC 3339."},
                )
            reference_time = reference_time.astimezone(timezone.utc)
        try:
            result = incident_service.get_active_incidents_summary(
                component_filter=component,
                reference_time=reference_time,
            )
        except (ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"message": str(exc)},
            ) from exc
        return ActiveIncidentsSummaryResponse.model_validate(asdict(result))

    return api


app = create_app()
