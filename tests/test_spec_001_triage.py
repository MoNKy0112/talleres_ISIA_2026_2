"""Pruebas de aceptación BDD para H001: triaje HTTP y CLI."""

import json

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner


PAYMENT_REPORT = (
    "URGENTE: HTTP 502 en todas las transacciones con tarjeta; "
    "ningún comercio puede cobrar"
)


def test_critical_payment_outage_is_triaged_over_http(client: TestClient) -> None:
    """Given caída global 502, When POST triage, Then P0 y routing de pagos."""
    response = client.post(
        "/api/v1/incidents/triage",
        json={"incident_id": "INC-1001", "raw_text": PAYMENT_REPORT},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["severity"] == "P0"
    assert result["component"] == "payments-gateway"
    assert result["recommended_team"] == "Backend-Core"
    assert result["duplicate_group_key"] == "payments-gateway:http-502-outage"
    assert set(result) == {
        "incident_id",
        "severity",
        "component",
        "rationale",
        "recommended_team",
        "duplicate_group_key",
        "consistency_ratio",
    }


def test_individual_account_lockout_mentioning_today_is_not_p0(
    client: TestClient,
) -> None:
    """Given bloqueo individual que menciona hoy, Then P2 y Security-IAM."""
    response = client.post(
        "/api/v1/incidents/triage",
        json={
            "incident_id": "INC-1002",
            "raw_text": "Mi cuenta individual está bloqueada y necesito acceder hoy",
        },
    )

    assert response.status_code == 200
    assert response.json()["severity"] == "P2"
    assert response.json()["recommended_team"] == "Security-IAM"


@pytest.mark.parametrize(
    "payload",
    [
        {"incident_id": "INC-1001", "raw_text": " "},
        {"incident_id": "", "raw_text": PAYMENT_REPORT},
    ],
)
def test_empty_or_whitespace_input_returns_422(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    """Given entrada vacía, When POST triage, Then 422 sin resultado."""
    response = client.post("/api/v1/incidents/triage", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json(), dict)
    assert "detail" in response.json()


def test_cli_json_matches_http_result(
    client: TestClient,
    cli_runner: CliRunner,
    cli_app_instance,
) -> None:
    """Given reporte 502, When CLI triage, Then JSON coincide con HTTP."""
    http_response = client.post(
        "/api/v1/incidents/triage",
        json={"incident_id": "INC-1001", "raw_text": PAYMENT_REPORT},
    )
    cli_result = cli_runner.invoke(
        cli_app_instance,
        [
            "triage",
            "--incident-id",
            "INC-1001",
            "--raw-text",
            PAYMENT_REPORT,
        ],
    )

    assert http_response.status_code == 200
    assert cli_result.exit_code == 0, cli_result.output
    cli_json = json.loads(cli_result.stdout)
    assert cli_json["severity"] == "P0"
    assert cli_json["recommended_team"] == "Backend-Core"
    assert cli_json == http_response.json()


@pytest.mark.parametrize(
    "args",
    [
        ["triage", "--incident-id", "INC-1001", "--raw-text", " "],
        ["triage", "--incident-id", "INC-1001"],
    ],
)
def test_cli_rejects_invalid_input_and_exits_with_code_one(
    cli_runner: CliRunner,
    cli_app_instance,
    args: list[str],
) -> None:
    """Given entrada inválida, When CLI triage, Then stderr y código 1."""
    result = cli_runner.invoke(cli_app_instance, args)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Error:" in result.stderr
