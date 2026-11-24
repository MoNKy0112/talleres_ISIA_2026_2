"""Adaptador CLI de IncidentOps."""

from dataclasses import asdict
import json
from datetime import datetime, timezone

import typer

from src.adapters.outbound.factory import create_repository
from src.application.services import IncidentService, ValidationError

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

    typer.echo(json.dumps(asdict(result), ensure_ascii=False))


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
    typer.echo(json.dumps(asdict(result), ensure_ascii=False))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
