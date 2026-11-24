"""Aplicación HTTP del adaptador primario REST."""

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponse,
    CreateIncidentRequest,
    HealthResponse,
    IncidentCreatedResponse,
    SLAEvaluationResponse,
    TriageRequest,
    TriageResponse,
)
from src.adapters.outbound.factory import create_repository
from src.application.services import (
    IncidentNotFoundError,
    IncidentService,
    ValidationError,
)


def create_app(service: IncidentService | None = None) -> FastAPI:
    """Construye la API; permite inyectar el caso de uso en pruebas."""
    incident_service = service or IncidentService(create_repository())
    api = FastAPI(title="IncidentOps API")

    @api.get(
        "/health",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse}},
    )
    def health() -> HealthResponse | JSONResponse:
        try:
            connected = incident_service.check_health()
        except Exception:
            connected = False
        if not connected:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "database": "unavailable"},
            )
        return HealthResponse(status="ok", database="connected")

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

    @api.post(
        "/api/v1/incidents",
        response_model=IncidentCreatedResponse,
        status_code=201,
    )
    def create_incident(request: CreateIncidentRequest) -> IncidentCreatedResponse:
        try:
            result = incident_service.create_incident(
                title=request.title,
                raw_text=request.raw_text,
                incident_id=request.incident_id,
                created_at=request.created_at,
                status=request.status,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail={"message": str(exc)}
            ) from exc
        return IncidentCreatedResponse.model_validate(asdict(result))

    @api.get(
        "/api/v1/incidents/{incident_id}/sla",
        response_model=SLAEvaluationResponse,
        status_code=200,
    )
    def evaluate_incident_sla(
        incident_id: str,
        reference_time: datetime | None = Query(None),
    ) -> SLAEvaluationResponse:
        try:
            result = incident_service.evaluate_incident_sla(
                incident_id=incident_id,
                reference_time=reference_time,
            )
        except IncidentNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"message": str(exc)}
            ) from exc
        except (ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail={"message": str(exc)}
            ) from exc
        return SLAEvaluationResponse.model_validate(asdict(result))

    return api


app = create_app()
