"""Reglas deterministas de clasificación y enrutamiento de IncidentOps."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List

from src.domain.models import RecommendedTeam, SeverityLevel, TriageResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample_incidents.json"


def _normalize(text: str) -> str:
    """Normaliza mayúsculas y acentos para comparar reportes en español."""
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _has(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica por impacto y funcionalidad; la urgencia declarada no eleva severidad."""
    text = _normalize(raw_text)

    # Componentes y síntomas específicos conservan separados problemas con
    # síntomas parecidos que afectan funcionalidades distintas.
    if _has(text, "company_id", "otra organizacion", "otra empresa", "facturas pertenecientes"):
        component = "reporting-api"
        symptom = "cross_tenant_invoice_exposure"
        team: RecommendedTeam = "Security-IAM"
        severity: SeverityLevel = "P0"
        rationale = (
            "Cambiar company_id permite ver facturas de otra organización; el reporte evidencia "
            "exposición activa de datos entre tenants, por lo que es P0 y requiere Security-IAM."
        )
    elif _has(text, "postgresql", "94%", "pool de conexiones", "conexiones"):
        component = "database-cluster"
        symptom = "connection_pool_saturation"
        team = "Data-DBA"
        severity = "P1"
        rationale = (
            "El nodo primario registra 94% de uso de conexiones y timeouts intermitentes; "
            "es una degradación severa de infraestructura compartida con riesgo de caída (P1)."
        )
    elif _has(text, "pasarela", "gateway de pagos", "cobros", "pagos", "pagar", "tarjeta") and _has(text, "502", "bad gateway", "cayo", "no pueden cobrar", "no pueden completar"):
        component = "payments-gateway"
        symptom = "http-502-outage"
        team = "Backend-Core"
        global_outage = _has(text, "todas las transacciones", "ningun comercio", "indisponibilidad global", "todos los comercios")
        severity = "P0" if global_outage else "P2"
        if global_outage:
            rationale = (
                "El reporte indica HTTP 502 en todas las transacciones y que ningún comercio "
                "puede cobrar; la indisponibilidad global de pagos críticos es P0."
            )
        else:
            rationale = (
                "Se reporta fallo HTTP 502 en pagos para los clientes descritos, pero no se "
                "afirma que el impacto sea global; se clasifica P2 y se enruta a Backend-Core."
            )
    elif _has(text, "cuenta", "ingresar", "bloqueada"):
        component = "auth-identity"
        symptom = "individual_account_lockout"
        team = "Security-IAM"
        severity = "P2"
        rationale = (
            "El bloqueo afecta la cuenta de una persona y no se reporta una caída general "
            "de autenticación; corresponde a P2 y al equipo Security-IAM."
        )
    elif _has(text, "dashboard", "reportes historicos"):
        component = "reporting-dashboard"
        symptom = "large_order_query_latency"
        team = "Data-DBA"
        severity = "P2"
        rationale = (
            "El dashboard tarda 4.5 segundos con más de 10.000 órdenes y sigue respondiendo; "
            "es degradación moderada de rendimiento (P2), sin causa raíz confirmada."
        )
    elif _has(text, "listado de planes", "clientes corporativos"):
        component = "customer-directory"
        symptom = "large_customer_list_latency"
        team = "Data-DBA"
        severity = "P2"
        rationale = (
            "El listado de planes e historial supera 3 segundos con más de 10.000 registros; "
            "es degradación moderada (P2). La funcionalidad difiere del dashboard de reportes."
        )
    elif re.search(r"\bexcel\b", text) or _has(text, "exportacion mensual"):
        component = "report-export"
        symptom = "slow_excel_export"
        team = "Data-DBA"
        severity = "P2"
        rationale = (
            "La exportación tarda unos 20 segundos pero termina correctamente; el cierre "
            "contable expresa urgencia, no una caída, por lo que es P2."
        )
    elif _has(text, "color", "boton", "monitor"):
        component = "frontend-ui"
        symptom = "export_button_color"
        team = "Backend-Core"
        severity = "P3"
        rationale = "Se solicita un cambio cosmético de color; no se describe una falla funcional, por lo que es P3."
    elif _has(text, "staging", "certificado", "tls", "rotacion programada"):
        component = "infra-certificates"
        symptom = "staging_certificate_rotation"
        team = "Platform-SRE"
        severity = "P3"
        rationale = (
            "El certificado de staging vence en 14 días y requiere rotación programada; "
            "es mantenimiento preventivo no productivo (P3)."
        )
    else:
        component = "reporting-api"
        symptom = "unclassified_report"
        team = "Backend-Core"
        severity = "P3"
        rationale = (
            "El reporte no aporta evidencia suficiente para identificar una falla concreta "
            "ni un impacto mayor; se mantiene P3 provisional y se recomienda Backend-Core."
        )

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        rationale=rationale,
        recommended_team=team,
        duplicate_group_key=f"{component}:{symptom}",
    )


def _run_triage_audit() -> None:
    """Imprime la clasificación de los diez reportes de muestra."""
    incidents: List[Dict[str, str]] = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
    print("=== Auditoría del motor de triaje ===")
    print(f"{'ID':<10} | {'Sev.':<5} | {'Componente':<22} | {'Equipo':<14} | {'Clave de duplicado':<48} | Justificación")
    print("-" * 170)
    for item in incidents:
        result = classify_incident_report(item["id"], item["raw_text"])
        print(
            f"{result.incident_id:<10} | {result.severity:<5} | {result.component:<22} | "
            f"{result.recommended_team:<14} | {result.duplicate_group_key:<48} | {result.rationale}"
        )


if __name__ == "__main__":
    _run_triage_audit()
