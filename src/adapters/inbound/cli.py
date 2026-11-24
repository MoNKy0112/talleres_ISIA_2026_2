"""Adaptador CLI de IncidentOps."""

from dataclasses import asdict
import json
from datetime import datetime, timezone

import typer

from src.adapters.outbound.factory import create_repository
from src.application.services import (
    IncidentNotFoundError,
    IncidentService,
    ValidationError,
)

app = typer.Typer(help="Herramientas de soporte para IncidentOps.")


@app.callback()
def main_callback() -> None:
    """Comandos de soporte de IncidentOps."""


@app.command()
def triage(
    incident_id: str | None = typer.Option(None, "--incident-id"),
    raw_text: str | None = typer.Option(None, "--raw-text"),
) -> None:
    """Clasifica y enruta un reporte sin persistirlo."""
    service = IncidentService()
    try:
        result = service.triage_incident(
            incident_id=incident_id if incident_id is not None else "",
            raw_text=raw_text if raw_text is not None else "",
        )
    except ValidationError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(asdict(result), ensure_ascii=False, default=_json_default))


@app.command()
def health() -> None:
    """Comprueba conectividad del repositorio configurado."""
    service = IncidentService(create_repository())
    try:
        connected = service.check_health()
    except Exception:
        connected = False
    payload = (
        {"status": "ok", "database": "connected"}
        if connected
        else {"status": "error", "database": "unavailable"}
    )
    typer.echo(json.dumps(payload))
    if not connected:
        raise typer.Exit(code=1)


@app.command()
def summary(
    component: str | None = typer.Option(None, "--component"),
    reference_time: str | None = typer.Option(None, "--reference-time"),
) -> None:
    """Muestra el resumen de incidentes activos en JSON."""
    parsed_reference_time: datetime | None = None
    if reference_time is not None:
        try:
            parsed_reference_time = datetime.fromisoformat(
                reference_time.replace("Z", "+00:00")
            )
            if parsed_reference_time.tzinfo is None:
                raise ValueError("reference_time debe incluir zona horaria RFC 3339.")
            parsed_reference_time = parsed_reference_time.astimezone(timezone.utc)
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    service = IncidentService(create_repository())
    try:
        result = service.get_active_incidents_summary(
            component_filter=component,
            reference_time=parsed_reference_time,
        )
    except (ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(asdict(result), ensure_ascii=False, default=_json_default))


@app.command()
def create(
    title: str | None = typer.Option(None, "--title"),
    raw_text: str | None = typer.Option(None, "--raw-text"),
    incident_id: str | None = typer.Option(None, "--incident-id"),
    created_at: str | None = typer.Option(None, "--created-at"),
    status: str = typer.Option("OPEN", "--status"),
) -> None:
    """Registra un incidente clasificado y devuelve el resultado en JSON."""
    try:
        parsed_created_at = _parse_datetime(created_at) if created_at else None
        result = IncidentService(create_repository()).create_incident(
            title=title if title is not None else "",
            raw_text=raw_text if raw_text is not None else "",
            incident_id=incident_id,
            created_at=parsed_created_at,
            status=status,  # type: ignore[arg-type]
        )
    except (ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(asdict(result), ensure_ascii=False, default=_json_default))


@app.command()
def sla(
    incident_id: str,
    reference_time: str | None = typer.Option(None, "--reference-time"),
) -> None:
    """Evalúa el SLA de un incidente y devuelve el resultado en JSON."""
    try:
        parsed_reference_time = (
            _parse_datetime(reference_time) if reference_time else None
        )
        result = IncidentService(create_repository()).evaluate_incident_sla(
            incident_id=incident_id,
            reference_time=parsed_reference_time,
        )
    except (IncidentNotFoundError, ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(asdict(result), ensure_ascii=False, default=_json_default))


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Fecha ISO 8601 inválida: {value}") from exc


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Tipo no serializable en JSON: {type(value).__name__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
