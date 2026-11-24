# Especificación manual — H001: Triaje HTTP y CLI

## Alcance y contrato

- La clasificación es determinista y no persiste incidentes.
- API: `POST /api/v1/incidents/triage`, con JSON `{"incident_id": "...", "raw_text": "..."}`. Responde `200 OK` con todos los campos de `TriageResult`: `incident_id`, `severity`, `component`, `rationale`, `recommended_team`, `duplicate_group_key` y `consistency_ratio`.
- CLI: subcomando `triage --incident-id ... --raw-text ...`; imprime el resultado en JSON por salida estándar.
- API y CLI invocan el mismo caso de uso compartido. Ambos exigen strings no vacíos ni compuestos solo por espacios; se valida con `strip()` y se conserva el contenido original para clasificar. No se define límite de longitud para H001.
- La API devuelve `422 Unprocessable Entity` con un error JSON estructurado ante entradas inválidas. La CLI escribe el error en `stderr` y termina con código `1`, incluso si faltan argumentos. El endpoint es interno; autenticación y limitación de frecuencia corresponden a controles externos.

## Escenarios BDD

### Escenario 1: Caída crítica HTTP 502 en la pasarela de pagos

**Given** un reporte con `incident_id="INC-1001"` y texto que indica HTTP 502 en todas las transacciones con tarjeta, de modo que ningún comercio puede cobrar  
**When** se envía el reporte a `POST /api/v1/incidents/triage`  
**Then** la respuesta es `200 OK`  
**And** `severity="P0"`  
**And** `component="payments-gateway"`  
**And** `recommended_team="Backend-Core"`  
**And** `duplicate_group_key="payments-gateway:http-502-outage"`

### Escenario 2: Cuenta individual bloqueada que menciona «hoy»

**Given** un reporte con `incident_id="INC-1002"` y `raw_text="Mi cuenta individual está bloqueada y necesito acceder hoy"`  
**When** se envía el reporte a `POST /api/v1/incidents/triage`  
**Then** la respuesta es `200 OK`  
**And** `severity="P2"`, sin elevar la prioridad a P0 por la palabra «hoy»  
**And** `recommended_team="Security-IAM"`

### Escenario 3: Campos vacíos o compuestos solo por espacios

**Given** un reporte cuya entrada tiene `raw_text=" "` o `incident_id=""`  
**When** se envía a `POST /api/v1/incidents/triage`  
**Then** la respuesta es `422 Unprocessable Entity` con un error JSON estructurado  
**And** no se ejecuta la clasificación ni se persiste información

### Escenario 4: Paridad de clasificación en CLI

**Given** el mismo reporte de caída crítica de pagos del escenario 1  
**When** soporte ejecuta `triage --incident-id INC-1001 --raw-text "URGENTE: HTTP 502 en todas las transacciones con tarjeta; ningún comercio puede cobrar"`  
**Then** la salida estándar contiene JSON válido con todos los campos de `TriageResult`  
**And** el JSON contiene `severity="P0"` y `recommended_team="Backend-Core"`  
**And** el código de salida es `0`  
**And** el resultado coincide con el de la API para la misma entrada

### Escenario 5: CLI rechaza texto compuesto solo por espacios

**Given** el argumento `--raw-text` contiene únicamente espacios  
**When** se ejecuta el subcomando `triage`  
**Then** se escribe un error en `stderr`  
**And** el código de salida es `1`  
**And** no se imprime un resultado de clasificación en JSON por salida estándar
