"""Cálculo determinista de SLA continuo y en horario hábil."""

from datetime import datetime, time, timedelta, timezone
from typing import Dict

from src.domain.models import Incident, SLAEvaluation, SLARule, SeverityLevel

SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

WORKDAY_START = time(8, 0)
WORKDAY_END = time(18, 0)
WORKDAY_MINUTES = 600


def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra la tabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]


def normalize_utc(value: datetime) -> datetime:
    """Interpreta una fecha naive como UTC y convierte fechas aware a UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _business_minutes(start: datetime, end: datetime) -> int:
    """Suma la intersección del intervalo con jornadas L-V de 08:00 a 18:00.

    Recorre cada fecha del intervalo una vez; su complejidad temporal es O(D),
    siendo D la cantidad de días comprendidos entre start y end.
    """
    total_seconds = 0.0
    current_date = start.date()
    last_date = end.date()

    while current_date <= last_date:
        if current_date.weekday() < 5:
            work_start = datetime.combine(current_date, WORKDAY_START, tzinfo=start.tzinfo)
            work_end = datetime.combine(current_date, WORKDAY_END, tzinfo=start.tzinfo)
            interval_start = max(start, work_start)
            interval_end = min(end, work_end)
            if interval_end > interval_start:
                total_seconds += (interval_end - interval_start).total_seconds()

        current_date += timedelta(days=1)

    # Truncar el total una sola vez mantiene el conteo en minutos enteros.
    return int(total_seconds // 60)


def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa tiempo transcurrido, incumplimiento y escalamiento de un incidente."""
    rule = get_sla_rule_for_severity(incident.severity)
    created_at = normalize_utc(incident.created_at)
    end_time = normalize_utc(incident.resolved_at or reference_time)

    if end_time < created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    if rule.operates_24x7:
        elapsed_minutes = int((end_time - created_at).total_seconds() // 60)
    else:
        elapsed_minutes = _business_minutes(created_at, end_time)

    remaining_minutes = max(rule.max_resolution_minutes - elapsed_minutes, 0)
    is_breached = elapsed_minutes > rule.max_resolution_minutes
    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    requires_escalation = is_breached or (
        incident.status != "RESOLVED" and elapsed_minutes >= escalation_limit
    )

    return SLAEvaluation(
        incident_id=incident.incident_id,
        severity=incident.severity,
        elapsed_minutes=elapsed_minutes,
        allowed_minutes=rule.max_resolution_minutes,
        remaining_minutes=remaining_minutes,
        is_breached=is_breached,
        requires_escalation=requires_escalation,
        component=incident.component,
        status=incident.status,
        exceeded_minutes=(
            elapsed_minutes - rule.max_resolution_minutes if is_breached else None
        ),
    )


def _run_demo() -> None:
    """Verifica en terminal casos borde con resultados exactos esperados."""
    cases = [
        # Viernes 17:00 a lunes 09:00: solo una hora el viernes y una el lunes.
        ("P2 cruza fin de semana", "P2", datetime(2026, 11, 6, 17), datetime(2026, 11, 9, 9), 120, False),
        # Creación antes de apertura: el conteo comienza el lunes a las 08:00.
        ("P2 creación antes de horario", "P2", datetime(2026, 11, 9, 7), datetime(2026, 11, 9, 9), 60, False),
        # Creación después del cierre del viernes; comienza el lunes a las 08:00.
        ("P2 creación después de horario", "P2", datetime(2026, 11, 6, 19), datetime(2026, 11, 9, 9), 60, False),
        # Mismo intervalo que el primer caso, pero P0 contabiliza las 64 horas.
        ("P0 continuo 24/7", "P0", datetime(2026, 11, 6, 17), datetime(2026, 11, 9, 9), 3840, True),
        # Dos semanas naturales: cinco jornadas completas de lunes a viernes.
        ("P2 intervalo de varias semanas", "P2", datetime(2026, 11, 9, 8), datetime(2026, 11, 16, 8), 3000, True),
        # Seis horas hábiles alcanzan exactamente el umbral de 75% de P2.
        ("P2 alcanza umbral de escalamiento", "P2", datetime(2026, 11, 9, 8), datetime(2026, 11, 9, 14), 360, True),
    ]

    print("=== Verificación determinista del cálculo de SLA ===")
    for name, severity, created_at, reference_time, expected_minutes, expected_escalation in cases:
        incident = Incident(
            incident_id=name,
            title=name,
            component="verification",
            duplicate_group_key=f"verification:{name}",
            severity=severity,  # type: ignore[arg-type]
            status="OPEN",
            created_at=created_at,
        )
        result = evaluate_sla_status(incident, reference_time)
        assert result.elapsed_minutes == expected_minutes, (
            f"{name}: esperado {expected_minutes}, obtenido {result.elapsed_minutes}"
        )
        assert result.requires_escalation == expected_escalation, (
            f"{name}: requires_escalation inesperado: {result.requires_escalation}"
        )
        print(
            f"OK | {name}: {result.elapsed_minutes} min "
            f"(esperado {expected_minutes}), escalation={result.requires_escalation}"
        )

    resolved_breach = Incident(
        incident_id="P2 resuelto con incumplimiento",
        title="P2 resuelto con incumplimiento",
        component="verification",
        duplicate_group_key="verification:p2-resolved-breach",
        severity="P2",
        status="RESOLVED",
        created_at=datetime(2026, 11, 9, 8),
        resolved_at=datetime(2026, 11, 10, 17),
    )
    result = evaluate_sla_status(resolved_breach, datetime(2026, 11, 10, 17))
    assert result.elapsed_minutes == 1140
    assert result.is_breached and result.requires_escalation
    print("OK | P2 resuelto tras incumplir: 1140 min, breach=True, escalation=True")
    print(f"Verificación completada: {len(cases) + 1} casos.")


if __name__ == "__main__":
    _run_demo()
